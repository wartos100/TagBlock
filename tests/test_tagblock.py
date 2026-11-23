"""Unit tests for TagBlock store, room-aware multi-action engine, and HA integration lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tagblock import async_setup_entry, async_unload_entry
from custom_components.tagblock.const import (
    ACTION_ADD_GROCERY,
    ACTION_ALARMO_ARM_AWAY,
    ACTION_ALARMO_DISARM,
    ACTION_PLAY_MUSIC,
    ACTION_RUN_SCRIPT_SCENE,
    ACTION_START_TIMER,
    DOMAIN,
    REMOVE_CANCEL_TIMER,
    REMOVE_PAUSE_MUSIC,
    TARGET_READER_DEFAULT,
)
from custom_components.tagblock.engine import TagBlockEngine
from custom_components.tagblock.store import TagBlockStore


async def test_store_seeds_and_crud(hass):
    """Verify initial migration seed, unlimited tag CRUD, and reader room configs."""
    store = TagBlockStore(hass)
    await store.async_load()

    tags = store.get_tags()
    assert len(tags) == 2

    saved = await store.async_save_tag(
        {
            "tag_id": "AA-BB-CC-DD",
            "name": "Cooking Mode",
            "on_remove": REMOVE_PAUSE_MUSIC,
            "actions": [
                {
                    "action_type": ACTION_RUN_SCRIPT_SCENE,
                    "target": "scene.cooking_lights",
                    "value": "",
                    "volume": 0,
                },
                {
                    "action_type": ACTION_PLAY_MUSIC,
                    "target": TARGET_READER_DEFAULT,
                    "value": "spotify://playlist/cooking",
                    "volume": 35,
                },
            ],
        }
    )
    assert saved["id"]
    assert len(saved["actions"]) == 2
    assert len(store.get_tags()) == 3

    await store.async_save_reader_config(
        "reader_kitchen",
        {
            "default_speaker": "media_player.kitchen_speakers",
            "default_todo": "todo.mealie_boodschappen",
        },
    )
    assert (
        store.get_reader_config("reader_kitchen")["default_speaker"]
        == "media_player.kitchen_speakers"
    )

    assert await store.async_delete_tag(saved["id"]) is True
    assert len(store.get_tags()) == 2


async def test_room_aware_music_and_hold_to_play_remove(hass):
    """Verify the same NFC tag targets Living vs Kitchen speakers depending on which reader scans it."""
    store = TagBlockStore(hass)
    await store.async_load()
    await store.async_save_reader_config(
        "reader_living", {"default_speaker": "media_player.living_speakers"}
    )
    await store.async_save_reader_config(
        "reader_kitchen", {"default_speaker": "media_player.kitchen_speakers"}
    )

    tag = await store.async_save_tag(
        {
            "tag_id": "11-22-33-44",
            "name": "Jazz Coin",
            "on_remove": REMOVE_PAUSE_MUSIC,
            "actions": [
                {
                    "action_type": ACTION_PLAY_MUSIC,
                    "target": TARGET_READER_DEFAULT,
                    "value": "spotify://playlist/jazz",
                    "volume": 40,
                }
            ],
        }
    )

    engine = TagBlockEngine(hass, store)
    calls: list[tuple[str, str, dict]] = []

    async def _fake_call(domain, service, data=None, blocking=False):
        calls.append((domain, service, dict(data or {})))

    with patch.object(hass.services, "async_call", side_effect=_fake_call):
        await engine.async_execute_tag(tag, device_id="reader_kitchen")
        assert (
            "media_player",
            "volume_set",
            {"entity_id": "media_player.kitchen_speakers", "volume_level": 0.4},
        ) in calls
        assert (
            "music_assistant",
            "play_media",
            {
                "entity_id": "media_player.kitchen_speakers",
                "media_id": "spotify://playlist/jazz",
                "enqueue": "replace",
            },
        ) in calls

        calls.clear()
        engine.start()
        hass.bus.async_fire("esphome.tagblock_tag_removed", {"tag_id": "11-22-33-44"})
        await hass.async_block_till_done()
        assert (
            "media_player",
            "media_pause",
            {"entity_id": "media_player.kitchen_speakers"},
        ) in calls
        engine.stop()


async def test_combo_alarmo_grocery_and_timer(hass):
    """Verify combo tags, Alarmo PIN handling, grocery list, and timer start/cancel."""
    store = TagBlockStore(hass)
    await store.async_load()
    engine = TagBlockEngine(hass, store)

    calls: list[tuple[str, str, dict]] = []

    async def _fake_call(domain, service, data=None, blocking=False):
        calls.append((domain, service, dict(data or {})))

    tag = await store.async_save_tag(
        {
            "tag_id": "55-66-77-88",
            "name": "Leave House",
            "on_remove": REMOVE_CANCEL_TIMER,
            "actions": [
                {
                    "action_type": ACTION_ADD_GROCERY,
                    "target": "todo.boodschappen",
                    "value": "Brood",
                    "volume": 0,
                },
                {
                    "action_type": ACTION_ALARMO_ARM_AWAY,
                    "target": "alarm_control_panel.home",
                    "value": "1234",
                    "volume": 0,
                },
                {
                    "action_type": ACTION_ALARMO_DISARM,
                    "target": "alarm_control_panel.home",
                    "value": "",
                    "volume": 0,
                },
                {
                    "action_type": ACTION_START_TIMER,
                    "target": "both_phones",
                    "value": "10",
                    "volume": 0,
                },
            ],
        }
    )

    with patch.object(hass.services, "async_call", side_effect=_fake_call):
        await engine.async_execute_tag(tag)

    assert (
        "todo",
        "add_item",
        {"entity_id": "todo.boodschappen", "item": "Brood"},
    ) in calls
    assert (
        "alarmo",
        "arm",
        {"entity_id": "alarm_control_panel.home", "mode": "away", "code": "1234"},
    ) in calls
    assert (
        "alarmo",
        "disarm",
        {"entity_id": "alarm_control_panel.home"},
    ) in calls
    assert len(store.active_timers) == 1

    timer_id = next(iter(store.active_timers))
    assert engine.cancel_timer(timer_id) is True
    assert len(store.active_timers) == 0


async def test_setup_and_unload_entry(hass):
    """Verify TagBlock registers static paths, sidebar panel, and unloads cleanly."""
    entry = MockConfigEntry(domain=DOMAIN, title="TagBlock", data={})
    entry.add_to_hass(hass)

    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()

    with (
        patch("custom_components.tagblock.frontend.async_register_built_in_panel") as mock_reg_panel,
        patch("custom_components.tagblock.frontend.async_remove_panel") as mock_rm_panel,
    ):
        assert await async_setup_entry(hass, entry) is True
        assert DOMAIN in hass.data
        hass.http.async_register_static_paths.assert_awaited_once()
        mock_reg_panel.assert_called_once()

        assert await async_unload_entry(hass, entry) is True
        mock_rm_panel.assert_called_once()
