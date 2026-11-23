"""Unit tests for TagBlock store, room-aware multi-action engine, and HA integration lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

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
    RETAP_TOGGLE_PAUSE,
    TARGET_READER_DEFAULT,
)
from custom_components.tagblock.engine import (
    TagBlockEngine,
    async_search_music_assistant,
)
from custom_components.tagblock.store import TagBlockStore


async def test_store_crud_and_reader_defaults(hass):
    """Verify clean initial store, unlimited multi-action tag CRUD, and reader room configs."""
    store = TagBlockStore(hass)
    await store.async_load()
    assert store.get_tags() == []

    saved = await store.async_save_tag(
        {
            "tag_id": "AA-BB-CC-DD",
            "name": "Cooking Mode",
            "on_remove": REMOVE_PAUSE_MUSIC,
            "retap_mode": RETAP_TOGGLE_PAUSE,
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
                    "shuffle": True,
                    "radio_mode": True,
                    "enqueue": "add",
                },
            ],
        }
    )
    assert saved["id"]
    assert len(saved["actions"]) == 2
    assert saved["actions"][1]["shuffle"] is True
    assert saved["actions"][1]["radio_mode"] is True
    assert saved["actions"][1]["enqueue"] == "add"
    assert saved["retap_mode"] == RETAP_TOGGLE_PAUSE

    await store.async_save_reader_config(
        "reader_kitchen",
        {
            "default_speaker": "media_player.kitchen_speakers",
            "default_todo": "todo.shopping_list",
        },
    )
    assert (
        store.get_reader_config("reader_kitchen")["default_speaker"]
        == "media_player.kitchen_speakers"
    )

    assert await store.async_delete_tag(saved["id"]) is True
    assert store.get_tags() == []


async def test_room_aware_music_shuffle_retap_and_hold_to_play(hass):
    """Verify room-aware speaker resolution, shuffle/radio/enqueue, re-tap toggle, and hold-to-play."""
    store = TagBlockStore(hass)
    await store.async_load()
    await store.async_save_reader_config(
        "reader_kitchen", {"default_speaker": "media_player.kitchen_speakers"}
    )

    tag = await store.async_save_tag(
        {
            "tag_id": "11-22-33-44",
            "name": "Jazz Coin",
            "on_remove": REMOVE_PAUSE_MUSIC,
            "retap_mode": RETAP_TOGGLE_PAUSE,
            "actions": [
                {
                    "action_type": ACTION_PLAY_MUSIC,
                    "target": TARGET_READER_DEFAULT,
                    "value": "spotify://playlist/jazz",
                    "volume": 40,
                    "shuffle": True,
                    "radio_mode": True,
                    "enqueue": "replace",
                }
            ],
        }
    )

    vol_calls = async_mock_service(hass, "media_player", "volume_set")
    play_calls = async_mock_service(hass, "music_assistant", "play_media")
    shuffle_calls = async_mock_service(hass, "media_player", "shuffle_set")
    toggle_calls = async_mock_service(hass, "media_player", "media_play_pause")
    pause_calls = async_mock_service(hass, "media_player", "media_pause")

    engine = TagBlockEngine(hass, store)

    await engine.async_execute_tag(tag, device_id="reader_kitchen")
    await hass.async_block_till_done()

    assert len(vol_calls) == 1
    assert vol_calls[0].data == {
        "entity_id": "media_player.kitchen_speakers",
        "volume_level": 0.4,
    }
    assert len(play_calls) == 1
    assert play_calls[0].data == {
        "entity_id": "media_player.kitchen_speakers",
        "media_id": "spotify://playlist/jazz",
        "enqueue": "replace",
        "radio_mode": True,
    }
    assert len(shuffle_calls) == 1
    assert shuffle_calls[0].data == {
        "entity_id": "media_player.kitchen_speakers",
        "shuffle": True,
    }

    # Re-tap while playing -> toggles play/pause instead of restarting
    hass.states.async_set("media_player.kitchen_speakers", "playing")
    await engine.async_execute_tag(tag, device_id="reader_kitchen")
    await hass.async_block_till_done()
    assert len(toggle_calls) == 1
    assert len(play_calls) == 1

    # Lift tag off reader -> pauses kitchen speakers
    engine.start()
    hass.bus.async_fire("esphome.tagblock_tag_removed", {"tag_id": "11-22-33-44"})
    await hass.async_block_till_done()
    assert len(pause_calls) == 1
    assert pause_calls[0].data == {"entity_id": "media_player.kitchen_speakers"}
    engine.stop()


async def test_rotary_control_events(hass):
    """Verify optional physical rotary encoder / button events control the room's default speaker."""
    store = TagBlockStore(hass)
    await store.async_load()
    await store.async_save_reader_config(
        "reader_1", {"default_speaker": "media_player.living_speakers"}
    )

    vol_up = async_mock_service(hass, "media_player", "volume_up")
    next_trk = async_mock_service(hass, "media_player", "media_next_track")

    engine = TagBlockEngine(hass, store)
    engine.start()
    hass.bus.async_fire("esphome.tagblock_control", {"command": "volume_up"})
    hass.bus.async_fire("esphome.tagblock_control", {"command": "next_track"})
    await hass.async_block_till_done()

    assert len(vol_up) == 1
    assert vol_up[0].data == {"entity_id": "media_player.living_speakers"}
    assert len(next_trk) == 1
    assert next_trk[0].data == {"entity_id": "media_player.living_speakers"}
    engine.stop()


async def test_combo_alarmo_grocery_and_timer(hass):
    """Verify combo tags, Alarmo PIN handling, grocery list, and timer start/cancel."""
    store = TagBlockStore(hass)
    await store.async_load()
    engine = TagBlockEngine(hass, store)

    todo_calls = async_mock_service(hass, "todo", "add_item")
    arm_calls = async_mock_service(hass, "alarmo", "arm")
    disarm_calls = async_mock_service(hass, "alarmo", "disarm")

    tag = await store.async_save_tag(
        {
            "tag_id": "55-66-77-88",
            "name": "Leave House",
            "on_remove": REMOVE_CANCEL_TIMER,
            "actions": [
                {
                    "action_type": ACTION_ADD_GROCERY,
                    "target": "todo.shopping_list",
                    "value": "Milk",
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

    await engine.async_execute_tag(tag)
    await hass.async_block_till_done()

    assert len(todo_calls) == 1
    assert todo_calls[0].data == {"entity_id": "todo.shopping_list", "item": "Milk"}
    assert len(arm_calls) == 1
    assert arm_calls[0].data == {
        "entity_id": "alarm_control_panel.home",
        "mode": "away",
        "code": "1234",
    }
    assert len(disarm_calls) == 1
    assert disarm_calls[0].data == {"entity_id": "alarm_control_panel.home"}
    assert len(store.active_timers) == 1

    timer_id = next(iter(store.active_timers))
    assert engine.cancel_timer(timer_id) is True
    assert len(store.active_timers) == 0


async def test_music_assistant_search_empty_without_integration(hass):
    """Verify Music Assistant search returns [] gracefully when MA is not installed."""
    assert await async_search_music_assistant(hass, "Daft Punk") == []


async def test_setup_and_unload_entry(hass):
    """Verify TagBlock registers static paths, sidebar panel, and unloads cleanly."""
    entry = MockConfigEntry(domain=DOMAIN, title="TagBlock", data={})
    entry.add_to_hass(hass)

    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()

    with (
        patch(
            "homeassistant.components.frontend.async_register_built_in_panel"
        ) as mock_reg_panel,
        patch(
            "homeassistant.components.frontend.async_remove_panel"
        ) as mock_rm_panel,
    ):
        assert await async_setup_entry(hass, entry) is True
        assert DOMAIN in hass.data
        hass.http.async_register_static_paths.assert_awaited_once()
        mock_reg_panel.assert_called_once()

        assert await async_unload_entry(hass, entry) is True
        mock_rm_panel.assert_called_once()
