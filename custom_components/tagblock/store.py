"""Persistent JSON storage for TagBlock (unlimited multi-action tags & reader room profiles)."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
import uuid

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    ACTION_PLAY_MUSIC,
    REMOVE_KEEP_RUNNING,
    RETAP_RESTART,
    STORAGE_KEY,
    STORAGE_VERSION,
    TARGET_READER_DEFAULT,
    VALID_ACTIONS,
    VALID_ENQUEUE_MODES,
    VALID_REMOVE_MODES,
    VALID_RETAP_MODES,
)


def _normalize_action(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a single action item."""
    action_type = str(raw.get("action_type") or ACTION_PLAY_MUSIC)
    if action_type not in VALID_ACTIONS:
        action_type = ACTION_PLAY_MUSIC
    try:
        volume = max(0, min(100, int(raw.get("volume") or 0)))
    except (TypeError, ValueError):
        volume = 0
    enqueue = str(raw.get("enqueue") or "replace").strip().lower()
    if enqueue not in VALID_ENQUEUE_MODES:
        enqueue = "replace"
    return {
        "action_type": action_type,
        "target": str(raw.get("target") or "").strip(),
        "value": str(raw.get("value") or "").strip(),
        "volume": volume,
        "shuffle": bool(raw.get("shuffle", False)),
        "radio_mode": bool(raw.get("radio_mode", False)),
        "enqueue": enqueue,
    }


def _normalize_tag(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a tag record (supporting multi-action combos)."""
    entry_id = str(payload.get("id") or "").strip() or str(uuid.uuid4())
    tag_id = str(payload.get("tag_id") or "").strip()
    name = str(payload.get("name") or "").strip() or tag_id or "Untitled Tag"

    on_remove = str(payload.get("on_remove") or REMOVE_KEEP_RUNNING)
    if on_remove not in VALID_REMOVE_MODES:
        on_remove = REMOVE_KEEP_RUNNING

    retap_mode = str(payload.get("retap_mode") or RETAP_RESTART)
    if retap_mode not in VALID_RETAP_MODES:
        retap_mode = RETAP_RESTART

    raw_actions = payload.get("actions")
    if isinstance(raw_actions, list) and len(raw_actions) > 0:
        actions = [_normalize_action(a) for a in raw_actions if isinstance(a, dict)]
    else:
        actions = [
            _normalize_action(
                {
                    "action_type": payload.get("action_type", ACTION_PLAY_MUSIC),
                    "target": payload.get("target", TARGET_READER_DEFAULT),
                    "value": payload.get("value", ""),
                    "volume": payload.get("volume", 0),
                    "shuffle": payload.get("shuffle", False),
                    "radio_mode": payload.get("radio_mode", False),
                    "enqueue": payload.get("enqueue", "replace"),
                }
            )
        ]

    if not actions:
        actions = [_normalize_action({})]

    return {
        "id": entry_id,
        "tag_id": tag_id,
        "name": name,
        "on_remove": on_remove,
        "retap_mode": retap_mode,
        "reader_filter": str(payload.get("reader_filter") or "").strip(),
        "actions": actions,
    }


class TagBlockStore:
    """Manages unlimited TagBlock tag mappings, reader room defaults, and live UI state."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store."""
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY
        )
        self._tags: list[dict[str, Any]] = []
        self._reader_configs: dict[str, dict[str, str]] = {}
        self._listeners: list[Callable[[], None]] = []
        self.last_scanned: dict[str, Any] | None = None
        self.active_timers: dict[str, dict[str, Any]] = {}

    async def async_load(self) -> None:
        """Load stored tags & reader configs."""
        data = await self._store.async_load()
        if data is None:
            self._tags = []
            self._reader_configs = {}
            await self._async_persist()
        else:
            self._tags = [_normalize_tag(t) for t in data.get("tags", [])]
            self._reader_configs = dict(data.get("reader_configs", {}))

    async def _async_persist(self) -> None:
        """Persist tags and reader room profiles to .storage/tagblock.storage."""
        await self._store.async_save(
            {
                "tags": self._tags,
                "reader_configs": self._reader_configs,
            }
        )

    def get_tags(self) -> list[dict[str, Any]]:
        """Return a copy of all mapped tags."""
        return deepcopy(self._tags)

    def get_reader_configs(self) -> dict[str, dict[str, str]]:
        """Return a copy of all per-reader room profiles."""
        return deepcopy(self._reader_configs)

    def get_reader_config(self, device_id: str | None) -> dict[str, str]:
        """Return room defaults for a specific reader device_id."""
        if device_id and device_id in self._reader_configs:
            return deepcopy(self._reader_configs[device_id])
        return {}

    def get_snapshot(self) -> dict[str, Any]:
        """Return full live state snapshot for subscribed UI panels."""
        return {
            "tags": self.get_tags(),
            "reader_configs": self.get_reader_configs(),
            "last_scanned": deepcopy(self.last_scanned),
            "active_timers": list(self.active_timers.values()),
        }

    def add_listener(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Subscribe to state updates; returns an unsubscribe callback."""
        self._listeners.append(callback)

        def _unsub() -> None:
            if callback in self._listeners:
                self._listeners.remove(callback)

        return _unsub

    def notify_listeners(self) -> None:
        """Push state updates to all subscribed UI panels."""
        for cb in list(self._listeners):
            cb()

    def set_last_scanned(
        self, tag_id: str, device_id: str | None, matched_id: str | None
    ) -> None:
        """Record the latest scanned NFC tag."""
        self.last_scanned = {
            "tag_id": tag_id,
            "device_id": device_id or "",
            "matched_id": matched_id or "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.notify_listeners()

    def find_by_tag_id(
        self, tag_id: str, device_id: str | None = None
    ) -> dict[str, Any] | None:
        """Find a mapping matching tag_id (preferring reader-specific match)."""
        needle = tag_id.strip()
        if not needle:
            return None
        fallback: dict[str, Any] | None = None
        for tag in self._tags:
            if tag.get("tag_id", "").strip() != needle:
                continue
            reader_filter = tag.get("reader_filter", "").strip()
            if reader_filter and device_id and reader_filter == device_id:
                return deepcopy(tag)
            if not reader_filter and fallback is None:
                fallback = deepcopy(tag)
        return fallback

    async def async_save_tag(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create or update a tag mapping."""
        record = _normalize_tag(payload)

        updated = False
        for idx, existing in enumerate(self._tags):
            if existing.get("id") == record["id"]:
                self._tags[idx] = record
                updated = True
                break

        if not updated:
            self._tags.append(record)

        await self._async_persist()
        self.notify_listeners()
        return deepcopy(record)

    async def async_delete_tag(self, entry_id: str) -> bool:
        """Delete a tag mapping by internal ID."""
        before = len(self._tags)
        self._tags = [t for t in self._tags if t.get("id") != entry_id]
        if len(self._tags) == before:
            return False
        await self._async_persist()
        self.notify_listeners()
        return True

    async def async_save_reader_config(
        self, device_id: str, config: dict[str, Any]
    ) -> dict[str, str]:
        """Save per-reader room defaults (speaker, grocery list, etc.)."""
        clean = {
            "default_speaker": str(config.get("default_speaker") or "").strip(),
            "default_todo": str(config.get("default_todo") or "").strip(),
        }
        self._reader_configs[device_id] = clean
        await self._async_persist()
        self.notify_listeners()
        return deepcopy(clean)
