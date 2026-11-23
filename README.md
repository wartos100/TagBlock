# TagBlock

A room-aware, multi-reader NFC tag manager for Home Assistant with modular ESPHome firmware (ESP32 + PN532 + buzzer + LED/WS2812B ring) and a dedicated Home Assistant sidebar UI.

## Features

- **Room-Aware Multi-Reader Support:** Place 4–5 TagBlock readers around the house (Living Room, Kitchen, Bedroom, Workshop…). Configure each reader's **Default Speaker** and **Default Grocery List** on its card in the **Tag Readers** tab, then set a tag's target to **`📍 Reader's Room (Auto)`** so the exact same physical NFC token plays on the Living Speakers in the living room and the Kitchen Speakers in the kitchen.
- **Unlimited Multi-Action Tags (Combo Routines):** Every tag supports 1 action by default, or chain multiple actions with **`+ Add Another Action (Combo)`** (e.g., *Cooking Mode* = Kitchen Scene + Cooking Playlist). Stored in Home Assistant's native `.storage/tagblock.storage` with zero helper clutter.
- **Split-View Sidebar UI:** Searchable Mapped Tags list on the left; click any tag (or **+ Add Tag**, or tap an unmapped NFC tag) to open the Action Editor on the right.
- **Dynamic Action-Based Targets:**
  - **Play Music** (Music Assistant — Spotify links, URIs, or search text + optional speaker volume + all media players or `📍 Reader's Room`)
  - **Pause Speakers**
  - **Start Timer** (multiple simultaneous live timers, Companion App notification + reader buzzer chime on finish)
  - **Send Notification** (Companion App push notifications)
  - **Add to Grocery List** (`todo.*` lists such as Boodschappen / Mealie)
  - **Alarmo** (Arm Away, Arm Home, Arm Night, Disarm with optional masked PIN)
  - **Run Script or Scene**
- **Tap & Hold-to-Play:** Per-tag removal behavior (`Keep Running`, `Pause Music`, or `Cancel Timer`) that remembers which room's speaker was started.

## Installation

### Option A: HACS / HA Marketplace (Recommended)
1. Push this repository to GitHub (and update `documentation` in `custom_components/tagblock/manifest.json` to your repo URL).
2. In Home Assistant, open **HACS** → **Custom repositories**, add your GitHub URL with category **Integration**, and install **TagBlock**.
3. Restart Home Assistant.
4. Go to **Settings → Devices & Services → Add Integration** and add **TagBlock**.

### Option B: Manual Copy
1. Copy `custom_components/tagblock` into `/config/custom_components/tagblock`.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and add **TagBlock**.

## Modular ESPHome Firmware (4–5 Readers)

All shared logic lives in [`esphome/packages/tagblock_base.yaml`](esphome/packages/tagblock_base.yaml), paired with either [`led_binary.yaml`](esphome/packages/led_binary.yaml) (single-color LED) or [`led_ws2812.yaml`](esphome/packages/led_ws2812.yaml) (WS2812B LED ring).

Each room only needs a ~20-line file:
- [`esphome/tagblock-living-room.yaml`](esphome/tagblock-living-room.yaml) — Living Room (single-color LED)
- [`esphome/tagblock-kitchen.yaml`](esphome/tagblock-kitchen.yaml) — Kitchen wooden block (12-LED WS2812B ring)

Duplicate either room file for Bedroom, Workshop, etc. — every new reader adopted in Home Assistant automatically appears as its own card in the **Tag Readers** tab.

## Maintenance

- **CI checks:** [`.github/workflows/validate.yml`](.github/workflows/validate.yml) runs `hassfest`, HACS validation, and Python/JS syntax checks on every push and on the 1st of each month.
- **Cache busting:** Bump `FRONTEND_VERSION` in `custom_components/tagblock/const.py` whenever you edit `frontend/tagblock-panel.js`.
