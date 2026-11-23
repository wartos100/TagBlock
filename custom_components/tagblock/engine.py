"""Event listener, multi-action room-aware engine, and entity/reader discovery for TagBlock."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import time
from typing import Any
import uuid

from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_call_later

from .const import (
    ACTION_ADD_GROCERY,
    ACTION_ALARMO_ARM_AWAY,
    ACTION_ALARMO_ARM_HOME,
    ACTION_ALARMO_ARM_NIGHT,
    ACTION_ALARMO_DISARM,
    ACTION_PAUSE_SPEAKERS,
    ACTION_PLAY_MUSIC,
    ACTION_RUN_SCRIPT_SCENE,
    ACTION_SEND_NOTIFICATION,
    ACTION_START_TIMER,
    REMOVE_CANCEL_TIMER,
    REMOVE_PAUSE_MUSIC,
    RETAP_TOGGLE_PAUSE,
    SCAN_DEBOUNCE_SECONDS,
    TARGET_READER_DEFAULT,
)
from .store import TagBlockStore

_LOGGER = logging.getLogger(__name__)


class TagBlockEngine:
    """Listens to NFC tag & hardware control events and executes room-aware routines."""

    def __init__(self, hass: HomeAssistant, store: TagBlockStore) -> None:
        """Initialize the engine."""
        self.hass = hass
        self.store = store
        self._unsubs: list[CALLBACK_TYPE] = []
        self._timer_cancels: dict[str, CALLBACK_TYPE] = {}
        # Tracks which resolved speaker(s) a placed tag started, for hold-to-play & re-tap toggle
        self._active_tag_speakers: dict[str, list[str]] = {}
        # Tracks last played tag per speaker for re-tap Play/Pause toggling
        self._speaker_last_tag: dict[str, str] = {}
        # Debounce map: (tag_id, device_id) -> monotonic timestamp
        self._last_scan_mono: dict[tuple[str, str], float] = {}

    def start(self) -> None:
        """Register Home Assistant event listeners."""
        self._unsubs.append(
            self.hass.bus.async_listen("tag_scanned", self._handle_tag_scanned)
        )
        self._unsubs.append(
            self.hass.bus.async_listen(
                "esphome.tagblock_tag_removed", self._handle_tag_removed
            )
        )
        self._unsubs.append(
            self.hass.bus.async_listen(
                "esphome.tagblock_control", self._handle_reader_control
            )
        )

    def stop(self) -> None:
        """Unsubscribe from events and cancel active timers."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        for cancel in list(self._timer_cancels.values()):
            cancel()
        self._timer_cancels.clear()
        self._active_tag_speakers.clear()
        self._speaker_last_tag.clear()
        self._last_scan_mono.clear()
        self.store.active_timers.clear()

    def _resolve_device_id_by_name(self, device_name: str | None) -> str | None:
        """Resolve an ESPHome device_name string to its HA device_id."""
        if not device_name:
            return None
        needle = device_name.strip().lower().replace("_", "-")
        dev_reg = dr.async_get(self.hass)
        for device in dev_reg.devices.values():
            cand = (device.name or "").strip().lower().replace("_", "-").replace(" ", "-")
            if cand == needle:
                return device.id
        return None

    def _resolve_speaker(self, target: str, device_id: str | None) -> str:
        """Resolve 'reader_default' to the scanning reader's default speaker."""
        if target and target != TARGET_READER_DEFAULT:
            return target
        reader_cfg = self.store.get_reader_config(device_id)
        if reader_cfg.get("default_speaker"):
            return reader_cfg["default_speaker"]
        for cfg in self.store.get_reader_configs().values():
            if cfg.get("default_speaker"):
                return cfg["default_speaker"]
        all_players = self.hass.states.async_all("media_player")
        return all_players[0].entity_id if all_players else ""

    def _resolve_todo(self, target: str, device_id: str | None) -> str:
        """Resolve 'reader_default' to the scanning reader's default grocery list."""
        if target and target != TARGET_READER_DEFAULT:
            return target
        reader_cfg = self.store.get_reader_config(device_id)
        if reader_cfg.get("default_todo"):
            return reader_cfg["default_todo"]
        for cfg in self.store.get_reader_configs().values():
            if cfg.get("default_todo"):
                return cfg["default_todo"]
        all_todos = self.hass.states.async_all("todo")
        return all_todos[0].entity_id if all_todos else ""

    async def _async_call_reader_feedback(
        self, device_id: str | None, action_suffix: str
    ) -> None:
        """Optionally trigger buzzer/LED feedback on the scanning ESPHome reader."""
        esphome_services = self.hass.services.async_services().get("esphome", {})
        if not esphome_services:
            return

        candidate_prefixes: list[str] = []
        if device_id:
            dev_reg = dr.async_get(self.hass)
            device = dev_reg.async_get(device_id)
            if device and device.name:
                slug = device.name.lower().replace("-", "_").replace(" ", "_")
                candidate_prefixes.append(slug)

        for svc_name in esphome_services:
            if not svc_name.endswith(f"_{action_suffix}"):
                continue
            if candidate_prefixes and not any(
                svc_name.startswith(p) for p in candidate_prefixes
            ):
                continue
            try:
                await self.hass.services.async_call(
                    "esphome", svc_name, {}, blocking=False
                )
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Optional ESPHome feedback %s failed", svc_name)
            return

    async def _handle_tag_scanned(self, event: Event) -> None:
        """Handle Home Assistant's native tag_scanned event with debounce."""
        tag_id = str(event.data.get("tag_id") or "").strip()
        device_id = event.data.get("device_id")
        if not tag_id:
            return

        # Debounce rapid duplicate scans from the same reader
        key = (tag_id, str(device_id or ""))
        now = time.monotonic()
        if now - self._last_scan_mono.get(key, 0.0) < SCAN_DEBOUNCE_SECONDS:
            return
        self._last_scan_mono[key] = now

        matched = self.store.find_by_tag_id(tag_id, device_id)
        self.store.set_last_scanned(
            tag_id=tag_id,
            device_id=device_id,
            matched_id=matched["id"] if matched else None,
        )

        if matched:
            await self.async_execute_tag(matched, device_id=device_id)
            await self._async_call_reader_feedback(device_id, "tag_ok")
        else:
            await self._async_call_reader_feedback(device_id, "tag_unknown")

    async def _handle_tag_removed(self, event: Event) -> None:
        """Handle tag removal events from ESPHome TagBlock readers."""
        tag_id = str(event.data.get("tag_id") or "").strip()
        if not tag_id:
            return

        device_name = event.data.get("device_name")
        device_id = self._resolve_device_id_by_name(device_name)
        matched = self.store.find_by_tag_id(tag_id, device_id)
        if not matched:
            return

        on_remove = matched.get("on_remove", "")
        if on_remove == REMOVE_PAUSE_MUSIC:
            speakers = self._active_tag_speakers.pop(tag_id, None)
            if not speakers:
                speakers = [
                    self._resolve_speaker(a.get("target", ""), device_id)
                    for a in matched.get("actions", [])
                    if a.get("action_type") == ACTION_PLAY_MUSIC
                ]
            for spk in speakers:
                if spk and spk.startswith("media_player."):
                    await self.hass.services.async_call(
                        "media_player",
                        "media_pause",
                        {"entity_id": spk},
                        blocking=False,
                    )
        elif on_remove == REMOVE_CANCEL_TIMER:
            for timer_id, info in list(self.store.active_timers.items()):
                if info.get("tag_id") == tag_id:
                    self.cancel_timer(timer_id)

    async def _handle_reader_control(self, event: Event) -> None:
        """Handle optional physical rotary encoder / button events from a TagBlock reader."""
        command = str(event.data.get("command") or "").strip().lower()
        device_name = event.data.get("device_name")
        device_id = self._resolve_device_id_by_name(device_name)
        speaker = self._resolve_speaker(TARGET_READER_DEFAULT, device_id)
        if not speaker:
            return

        if command == "volume_up":
            await self.hass.services.async_call(
                "media_player", "volume_up", {"entity_id": speaker}, blocking=False
            )
        elif command == "volume_down":
            await self.hass.services.async_call(
                "media_player", "volume_down", {"entity_id": speaker}, blocking=False
            )
        elif command == "play_pause":
            await self.hass.services.async_call(
                "media_player",
                "media_play_pause",
                {"entity_id": speaker},
                blocking=False,
            )
        elif command == "next_track":
            await self.hass.services.async_call(
                "media_player",
                "media_next_track",
                {"entity_id": speaker},
                blocking=False,
            )

    async def _async_send_mobile_notification(
        self, target: str, title: str, message: str
    ) -> None:
        """Send a notification to one or all mobile_app targets."""
        notify_services = self.hass.services.async_services().get("notify", {})
        targets: list[str] = []
        if target == "both_phones" or not target:
            targets = [s for s in notify_services if s.startswith("mobile_app_")]
        else:
            svc = target.removeprefix("notify.")
            if svc in notify_services:
                targets = [svc]

        for svc in targets:
            await self.hass.services.async_call(
                "notify",
                svc,
                {"title": title, "message": message},
                blocking=False,
            )

    def cancel_timer(self, timer_id: str) -> bool:
        """Cancel a running TagBlock timer."""
        cancel = self._timer_cancels.pop(timer_id, None)
        removed = self.store.active_timers.pop(timer_id, None)
        if cancel:
            cancel()
        if removed:
            self.store.notify_listeners()
            return True
        return False

    async def async_execute_tag(
        self, tag: dict[str, Any], device_id: str | None = None
    ) -> str:
        """Execute all actions in a tag's action list (room-aware)."""
        name = tag.get("name") or tag.get("tag_id") or "TagBlock"
        tag_id = str(tag.get("tag_id") or "").strip()
        retap_mode = str(tag.get("retap_mode") or "restart")
        actions = tag.get("actions") or []
        if not actions and tag.get("action_type"):
            actions = [tag]

        statuses: list[str] = []
        started_speakers: list[str] = []

        for step in actions:
            status, speaker_used = await self._async_execute_single_action(
                step=step,
                tag_name=name,
                tag_id=tag_id,
                retap_mode=retap_mode,
                device_id=device_id,
            )
            if status:
                statuses.append(status)
            if speaker_used:
                started_speakers.append(speaker_used)

        if tag_id and started_speakers:
            self._active_tag_speakers[tag_id] = started_speakers

        return " · ".join(statuses) if statuses else "No actions configured."

    async def _async_execute_single_action(
        self,
        step: dict[str, Any],
        tag_name: str,
        tag_id: str,
        retap_mode: str,
        device_id: str | None,
    ) -> tuple[str, str | None]:
        """Execute one action step and return (status_text, resolved_speaker_or_none)."""
        action = step.get("action_type", "")
        target = str(step.get("target") or "").strip()
        value = str(step.get("value") or "").strip()
        volume = int(step.get("volume") or 0)
        shuffle = bool(step.get("shuffle", False))
        radio_mode = bool(step.get("radio_mode", False))
        enqueue = str(step.get("enqueue") or "replace")

        if action == ACTION_PLAY_MUSIC:
            speaker = self._resolve_speaker(target, device_id)
            if not speaker or not value:
                return ("Missing speaker or music value", None)

            # Re-tap Play/Pause toggle when the same tag is already active on this speaker
            if (
                retap_mode == RETAP_TOGGLE_PAUSE
                and tag_id
                and self._speaker_last_tag.get(speaker) == tag_id
            ):
                sp_state = self.hass.states.get(speaker)
                if sp_state and sp_state.state in ("playing", "paused"):
                    await self.hass.services.async_call(
                        "media_player",
                        "media_play_pause",
                        {"entity_id": speaker},
                        blocking=False,
                    )
                    return (
                        f"Toggled play/pause on {speaker.split('.')[-1]}",
                        speaker,
                    )

            if volume > 0:
                await self.hass.services.async_call(
                    "media_player",
                    "volume_set",
                    {"entity_id": speaker, "volume_level": round(volume / 100, 2)},
                    blocking=True,
                )

            play_data: dict[str, Any] = {
                "entity_id": speaker,
                "media_id": value,
                "enqueue": enqueue,
            }
            if radio_mode:
                play_data["radio_mode"] = True

            await self.hass.services.async_call(
                "music_assistant",
                "play_media",
                play_data,
                blocking=False,
            )

            if shuffle:
                await self.hass.services.async_call(
                    "media_player",
                    "shuffle_set",
                    {"entity_id": speaker, "shuffle": True},
                    blocking=False,
                )

            if tag_id:
                self._speaker_last_tag[speaker] = tag_id

            vol_note = f" ({volume}%)" if volume > 0 else ""
            return (f"Playing on {speaker.split('.')[-1]}{vol_note}", speaker)

        if action == ACTION_PAUSE_SPEAKERS:
            speaker = self._resolve_speaker(target, device_id)
            if not speaker:
                return ("Missing speaker", None)
            await self.hass.services.async_call(
                "media_player",
                "media_pause",
                {"entity_id": speaker},
                blocking=False,
            )
            return (f"Paused {speaker.split('.')[-1]}", None)

        if action == ACTION_START_TIMER:
            try:
                minutes = float(value or "5")
            except ValueError:
                minutes = 5.0
            seconds = max(1, int(minutes * 60))
            timer_id = str(uuid.uuid4())
            ends_at = (
                datetime.now(timezone.utc) + timedelta(seconds=seconds)
            ).isoformat()

            self.store.active_timers[timer_id] = {
                "id": timer_id,
                "tag_id": tag_id,
                "name": tag_name,
                "target": target,
                "ends_at": ends_at,
                "duration_seconds": seconds,
            }
            self.store.notify_listeners()

            @callback
            def _on_timer_done(_now: datetime) -> None:
                self._timer_cancels.pop(timer_id, None)
                self.store.active_timers.pop(timer_id, None)
                self.store.notify_listeners()
                self.hass.async_create_task(
                    self._async_send_mobile_notification(
                        target, "TagBlock Timer Finished", f"{tag_name} is done!"
                    )
                )
                self.hass.async_create_task(
                    self._async_call_reader_feedback(device_id, "tag_timer_done")
                )

            self._timer_cancels[timer_id] = async_call_later(
                self.hass, seconds, _on_timer_done
            )
            return (f"Started {minutes:g}m timer", None)

        if action == ACTION_SEND_NOTIFICATION:
            msg = value or f"{tag_name} scanned!"
            await self._async_send_mobile_notification(target, tag_name, msg)
            return ("Sent notification", None)

        if action == ACTION_ADD_GROCERY:
            list_entity = self._resolve_todo(target, device_id)
            if not list_entity:
                return ("Missing grocery list", None)
            item = value or tag_name
            await self.hass.services.async_call(
                "todo",
                "add_item",
                {"entity_id": list_entity, "item": item},
                blocking=False,
            )
            return (f"Added '{item}'", None)

        if action in (
            ACTION_ALARMO_ARM_AWAY,
            ACTION_ALARMO_ARM_HOME,
            ACTION_ALARMO_ARM_NIGHT,
        ):
            mode_map = {
                ACTION_ALARMO_ARM_AWAY: "away",
                ACTION_ALARMO_ARM_HOME: "home",
                ACTION_ALARMO_ARM_NIGHT: "night",
            }
            panel = target or "alarm_control_panel.home"
            svc_data: dict[str, Any] = {
                "entity_id": panel,
                "mode": mode_map[action],
            }
            if value:
                svc_data["code"] = value
            await self.hass.services.async_call(
                "alarmo", "arm", svc_data, blocking=False
            )
            return (f"Armed Alarmo ({mode_map[action]})", None)

        if action == ACTION_ALARMO_DISARM:
            panel = target or "alarm_control_panel.home"
            svc_data = {"entity_id": panel}
            if value:
                svc_data["code"] = value
            await self.hass.services.async_call(
                "alarmo", "disarm", svc_data, blocking=False
            )
            return ("Disarmed Alarmo", None)

        if action == ACTION_RUN_SCRIPT_SCENE:
            ent = target or value
            if not ent:
                return ("Missing script or scene", None)
            await self.hass.services.async_call(
                "homeassistant",
                "turn_on",
                {"entity_id": ent},
                blocking=False,
            )
            return (f"Ran {ent.split('.')[-1]}", None)

        return ("Unknown action", None)


async def async_search_music_assistant(
    hass: HomeAssistant, query: str, limit: int = 8
) -> list[dict[str, str]]:
    """Search Music Assistant library/providers and return normalized items for the UI picker."""
    entries = hass.config_entries.async_entries("music_assistant")
    if not entries or not query.strip():
        return []

    try:
        resp = await hass.services.async_call(
            "music_assistant",
            "search",
            {
                "config_entry_id": entries[0].entry_id,
                "name": query.strip(),
                "limit": limit,
            },
            blocking=True,
            return_response=True,
        )
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Music Assistant search failed for query %s", query)
        return []

    if not isinstance(resp, dict):
        return []

    results: list[dict[str, str]] = []
    for bucket, media_type in (
        ("playlists", "playlist"),
        ("albums", "album"),
        ("tracks", "track"),
        ("artists", "artist"),
        ("radio", "radio"),
    ):
        for item in resp.get(bucket, []) or []:
            if not isinstance(item, dict):
                continue
            uri = str(item.get("uri") or "").strip()
            name = str(item.get("name") or "").strip()
            if not uri or not name:
                continue
            artists = item.get("artists") or []
            artist_str = ""
            if isinstance(artists, list) and artists:
                first_artist = artists[0]
                artist_str = (
                    first_artist.get("name", "")
                    if isinstance(first_artist, dict)
                    else str(first_artist)
                )
            results.append(
                {
                    "name": name,
                    "artist": artist_str,
                    "media_type": media_type,
                    "uri": uri,
                    "image": str(item.get("image") or ""),
                }
            )
    return results[:20]


def get_targets_and_readers(hass: HomeAssistant) -> dict[str, Any]:
    """Dynamically discover all HA targets and ESPHome NFC tag readers."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    ma_names: set[str] = set()
    media_players: list[dict[str, str]] = []
    other_players: list[dict[str, str]] = []

    for state in hass.states.async_all("media_player"):
        eid = state.entity_id
        if eid.endswith("_screen"):
            continue
        friendly = state.attributes.get("friendly_name", eid)
        reg_entry = ent_reg.async_get(eid)
        is_ma = reg_entry is not None and reg_entry.platform == "music_assistant"
        if is_ma:
            ma_names.add(friendly.lower())
            media_players.append({"value": eid, "label": friendly})
        else:
            other_players.append({"value": eid, "label": friendly})

    for item in other_players:
        if item["value"].startswith("media_player.cast_"):
            continue
        if item["label"].lower() not in ma_names:
            media_players.append(item)

    media_players.sort(key=lambda x: x["label"].lower())

    notify_services = hass.services.async_services().get("notify", {})
    notify_targets: list[dict[str, str]] = []
    mobile_svcs = sorted(
        s for s in notify_services if s.startswith("mobile_app_")
    )
    if len(mobile_svcs) > 1:
        notify_targets.append({"value": "both_phones", "label": "All Phones"})
    for svc in mobile_svcs:
        pretty = svc.removeprefix("mobile_app_").replace("_", " ").title()
        notify_targets.append({"value": f"notify.{svc}", "label": pretty})

    todo_lists = sorted(
        [
            {
                "value": s.entity_id,
                "label": s.attributes.get("friendly_name", s.entity_id),
            }
            for s in hass.states.async_all("todo")
        ],
        key=lambda x: x["label"].lower(),
    )

    alarm_panels = sorted(
        [
            {
                "value": s.entity_id,
                "label": s.attributes.get("friendly_name", s.entity_id),
            }
            for s in hass.states.async_all("alarm_control_panel")
        ],
        key=lambda x: x["label"].lower(),
    )

    scripts_and_scenes: list[dict[str, str]] = []
    for domain_name in ("scene", "script"):
        for s in hass.states.async_all(domain_name):
            friendly = s.attributes.get("friendly_name", s.entity_id)
            prefix = "Scene" if domain_name == "scene" else "Script"
            scripts_and_scenes.append(
                {"value": s.entity_id, "label": f"{prefix}: {friendly}"}
            )
    scripts_and_scenes.sort(key=lambda x: x["label"].lower())

    readers: list[dict[str, Any]] = []
    for device in dev_reg.devices.values():
        entities = er.async_entries_for_device(ent_reg, device.id)
        if not entities:
            continue
        platforms = {e.platform for e in entities}
        if "esphome" not in platforms:
            continue

        model_str = (device.model or "").lower()
        name_str = (device.name_by_user or device.name or "").lower()
        entity_ids = [e.entity_id for e in entities]
        looks_like_reader = (
            "tag" in model_str
            or "tag" in name_str
            or "nfc" in name_str
            or any("write_tag" in eid or "active_tag" in eid for eid in entity_ids)
        )
        if not looks_like_reader:
            continue

        reader_entities: dict[str, str | None] = {
            "status": None,
            "led": None,
            "buzzer_enabled": None,
            "led_enabled": None,
            "remove_sound_enabled": None,
            "tag_present": None,
            "active_tag": None,
            "write_tag_random": None,
            "clean_tag": None,
            "cancel_writing": None,
            "restart": None,
            "esphome_version": None,
            "ssid": None,
            "ip_address": None,
        }
        for e in entities:
            eid = e.entity_id
            low = eid.lower()
            if e.domain == "binary_sensor" and "status" in low:
                reader_entities["status"] = eid
            elif e.domain == "binary_sensor" and "tag_present" in low:
                reader_entities["tag_present"] = eid
            elif e.domain == "light" and "led" in low:
                reader_entities["led"] = eid
            elif e.domain == "switch" and "buzzer" in low:
                reader_entities["buzzer_enabled"] = eid
            elif e.domain == "switch" and "led_enabled" in low:
                reader_entities["led_enabled"] = eid
            elif e.domain == "switch" and "remove_sound" in low:
                reader_entities["remove_sound_enabled"] = eid
            elif e.domain == "sensor" and "active_tag" in low:
                reader_entities["active_tag"] = eid
            elif e.domain == "button" and "write_tag" in low:
                reader_entities["write_tag_random"] = eid
            elif e.domain == "button" and "clean_tag" in low:
                reader_entities["clean_tag"] = eid
            elif e.domain == "button" and "cancel" in low:
                reader_entities["cancel_writing"] = eid
            elif e.domain == "button" and "restart" in low:
                reader_entities["restart"] = eid
            elif e.domain == "sensor" and "version" in low:
                reader_entities["esphome_version"] = eid
            elif e.domain == "sensor" and "ssid" in low:
                reader_entities["ssid"] = eid
            elif e.domain == "sensor" and "ip_address" in low:
                reader_entities["ip_address"] = eid

        readers.append(
            {
                "device_id": device.id,
                "name": device.name_by_user or device.name or "NFC Tag Reader",
                "sw_version": device.sw_version or "",
                "entities": reader_entities,
            }
        )

    readers.sort(key=lambda r: r["name"].lower())

    return {
        "media_players": media_players,
        "notify_targets": notify_targets,
        "todo_lists": todo_lists,
        "alarm_panels": alarm_panels,
        "scripts_and_scenes": scripts_and_scenes,
        "readers": readers,
        "has_music_assistant": bool(hass.config_entries.async_entries("music_assistant")),
    }
