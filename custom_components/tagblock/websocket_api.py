"""WebSocket API for the TagBlock sidebar panel."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .engine import TagBlockEngine, get_targets_and_readers
from .store import TagBlockStore


def _get_runtime(hass: HomeAssistant) -> tuple[TagBlockStore, TagBlockEngine]:
    """Retrieve store and engine from hass.data."""
    data = hass.data[DOMAIN]
    return data["store"], data["engine"]


@websocket_api.websocket_command({vol.Required("type"): "tagblock/subscribe"})
@callback
def ws_subscribe(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Subscribe to live TagBlock tag, reader config, scan, and timer updates."""
    store, _ = _get_runtime(hass)

    @callback
    def _push_update() -> None:
        connection.send_message(
            websocket_api.event_message(msg["id"], store.get_snapshot())
        )

    unsub = store.add_listener(_push_update)
    connection.subscriptions[msg["id"]] = unsub
    connection.send_result(msg["id"], store.get_snapshot())


@websocket_api.websocket_command({vol.Required("type"): "tagblock/get_targets"})
@callback
def ws_get_targets(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return all dynamically discovered targets and NFC tag readers."""
    connection.send_result(msg["id"], get_targets_and_readers(hass))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "tagblock/save_tag",
        vol.Required("tag"): dict,
    }
)
@websocket_api.async_response
async def ws_save_tag(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Create or update a TagBlock NFC tag mapping."""
    store, _ = _get_runtime(hass)
    saved = await store.async_save_tag(msg["tag"])
    connection.send_result(msg["id"], {"tag": saved})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "tagblock/delete_tag",
        vol.Required("id"): str,
    }
)
@websocket_api.async_response
async def ws_delete_tag(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Delete a TagBlock NFC tag mapping."""
    store, _ = _get_runtime(hass)
    deleted = await store.async_delete_tag(msg["id"])
    connection.send_result(msg["id"], {"deleted": deleted})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "tagblock/test_tag",
        vol.Required("tag"): dict,
        vol.Optional("device_id"): str,
    }
)
@websocket_api.async_response
async def ws_test_tag(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Test-run a tag's action(s) directly from the UI."""
    _, engine = _get_runtime(hass)
    status = await engine.async_execute_tag(
        msg["tag"], device_id=msg.get("device_id")
    )
    connection.send_result(msg["id"], {"status": status})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "tagblock/save_reader_config",
        vol.Required("device_id"): str,
        vol.Required("config"): dict,
    }
)
@websocket_api.async_response
async def ws_save_reader_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Save room defaults (speaker, grocery list) for a specific NFC reader."""
    store, _ = _get_runtime(hass)
    saved = await store.async_save_reader_config(msg["device_id"], msg["config"])
    connection.send_result(msg["id"], {"config": saved})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "tagblock/cancel_timer",
        vol.Required("timer_id"): str,
    }
)
@callback
def ws_cancel_timer(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Cancel an active TagBlock timer."""
    _, engine = _get_runtime(hass)
    cancelled = engine.cancel_timer(msg["timer_id"])
    connection.send_result(msg["id"], {"cancelled": cancelled})


def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register all TagBlock WebSocket commands."""
    websocket_api.async_register_command(hass, ws_subscribe)
    websocket_api.async_register_command(hass, ws_get_targets)
    websocket_api.async_register_command(hass, ws_save_tag)
    websocket_api.async_register_command(hass, ws_delete_tag)
    websocket_api.async_register_command(hass, ws_test_tag)
    websocket_api.async_register_command(hass, ws_save_reader_config)
    websocket_api.async_register_command(hass, ws_cancel_timer)
