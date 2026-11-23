"""TagBlock custom integration for Home Assistant."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    FRONTEND_VERSION,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL,
    STATIC_URL,
)
from .engine import TagBlockEngine
from .store import TagBlockStore
from .websocket_api import async_register_websocket_commands


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TagBlock from a config entry."""
    store = TagBlockStore(hass)
    await store.async_load()

    engine = TagBlockEngine(hass, store)
    engine.start()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["store"] = store
    hass.data[DOMAIN]["engine"] = engine

    if not hass.data[DOMAIN].get("ws_registered"):
        async_register_websocket_commands(hass)
        hass.data[DOMAIN]["ws_registered"] = True

    if not hass.data[DOMAIN].get("static_registered"):
        frontend_dir = Path(__file__).parent / "frontend"
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    STATIC_URL,
                    str(frontend_dir),
                    cache_headers=False,
                )
            ]
        )
        hass.data[DOMAIN]["static_registered"] = True

    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        frontend_url_path=PANEL_URL,
        config={
            "_panel_custom": {
                "name": "tagblock-panel",
                "module_url": f"{STATIC_URL}/tagblock-panel.js?v={FRONTEND_VERSION}",
            }
        },
        require_admin=False,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload TagBlock config entry."""
    data = hass.data.get(DOMAIN, {})
    engine: TagBlockEngine | None = data.pop("engine", None)
    if engine:
        engine.stop()
    data.pop("store", None)

    frontend.async_remove_panel(hass, PANEL_URL)
    return True
