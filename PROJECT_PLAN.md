# KitchenBlock — Tactile NFC Kitchen Command & Workshop Pager

**Project Name:** `KitchenBlock`  
**Stack:** ESP32 + PN532 NFC Reader + ESPHome + Home Assistant  
**Core Concept:** A handcrafted wooden countertop block powered by an ESP32 and PN532 NFC reader. Using tactile wooden tokens (with embedded NTAG215 tags), anyone in the family—even with flour-, dough-, or oil-covered hands—can start cooking timers, control kitchen lighting & music, and silently page the wood workshop without shouting or touching a phone.

---

## 1. Goals & Design Philosophy

* **Messy-hands friendly:** Zero touchscreens, zero voice-assistant mishears over a range hood or blender. Just tap or rest a wooden token.
* **Safe workshop communication:** Replace shouting or walking into a noisy woodshop with a silent visual alert (flashing shop light / WLED beacon + watch notification) so nobody gets startled mid-cut while wearing ear protection.
* **Family-proof & tactile:** Looks like a piece of kitchen woodwork rather than an electronics project. Kids and guests can use it intuitively via engraved/printed icons on the tokens.
* **Dual-mode interaction:** Supports both **momentary taps** (start a timer, send a page) and **tag presence** (`on_tag` / `on_tag_removed`—rest a token on the block to keep a mode active, lift it off to revert).

---

## 2. Core Use Cases

### A. Cooking & Baking Timers
Keep a small magnetic rack or tray of wooden tokens next to the block:
* **Preset Timers:** *Soft-Boiled Egg (6 min)*, *Pasta (9 min)*, *Oven Check (15 min)*, *Dough Rise (60 min)*, *Tea Steep (3 min)*.
* **Quick Time Adders:** *+1 min*, *+5 min*, *+10 min* tokens—tap twice to stack (e.g., 2× `+5 min` = 10 minutes).
* **Control Tokens:** *Check Remaining Time* (speaks remaining time on kitchen speaker) and *Cancel / Silence Alarm*.
* **Completion Feedback:** Plays a chime on the kitchen speaker, pulses the KitchenBlock's LED ring (and/or under-cabinet lights), and stops automatically when tapped again.

### B. Workshop Silent Pager
* **Dinner's Ready:** Flashes a dedicated shop light or WLED strip in the wood workshop (e.g., 3× warm amber/green pulses), restores the workshop light to its previous brightness/color afterward, sends a notification to your phone/Garmin watch, and plays a dinner bell chime on house speakers.
* **Need a Hand / Quick Question:** Flashes a distinct color (e.g., blue pulse) in the workshop + sends an actionable notification (*"Coming in 2 min"* / *"Busy on a cut"*).
* **Acknowledge (Optional):** If you add a cheap Zigbee button or ESP32 in the workshop later, tapping it flashes the KitchenBlock LED green so Lotte knows you saw the page.

### C. Kitchen Scenes & Audio
* **Cooking Mode:** Boosts under-cabinet/prep lights to 100% cool white and starts a favorite cooking playlist or radio station.
* **Cleanup / Evening Mode:** Dims kitchen lights to warm cozy evening lighting and optionally plays a 10-minute "tidy up" playlist for the kids.
* **Morning Coffee:** Turns on warm morning lights and plays a brief weather/calendar/news briefing on the kitchen speaker.

### D. Family & Kids Routines
* **Set the Table / Tidy Up:** Plays a fun chime and triggers a gentle light cue in the living room/playroom.
* **Bedtime 10-Min Warning:** Starts a 10-minute countdown, gently dims living-room lights, and gives a friendly TTS reminder.
* **Blind-Draw Dinner Picker (Bonus):** Keep a small jar of meal tokens—pull one blindly and tap it to announce tonight's dinner (and optionally open the recipe on a kitchen tablet).

---

## 3. Hardware Requirements (BOM)

### Essential Components
| Component | Qty | Notes |
| :--- | :---: | :--- |
| **ESP32 Dev Board** (e.g., ESP32-WROOM / ESP32-S3 / ESP32-C3) | 1 | Already on hand. |
| **PN532 NFC Module** (13.56 MHz) | 1 | Already on hand. Supports I2C or SPI. |
| **NTAG215 NFC Stickers / Coin Tags (25 mm)** | 15–30 | 25 mm size gives reliable read range through 2–4 mm of wood. |
| **USB-C Power Supply (5V 1A+)** + braided cable | 1 | Clean countertop power. |

### Strongly Recommended Feedback Components
| Component | Qty | Notes |
| :--- | :---: | :--- |
| **Passive Piezo Buzzer** (e.g., 5V passive buzzer) | 1 | Plays crisp RTTTL tones (scan chirp, timer started, dinner bell, error buzz). |
| **WS2812B Addressable LED Ring (12 or 16 LEDs)** or short strip | 1 | Embed under a translucent acrylic/3D-printed diffuser ring for visual feedback & countdown progress. |

### Optional Upgrades
| Component | Qty | Notes |
| :--- | :---: | :--- |
| **0.96" or 1.3" I2C OLED Display (SSD1306 / SH1106)** | 1 | Shows active timer countdown, last scanned token name, and clock when idle. |
| **Workshop Beacon** (existing smart bulb, or spare ESP32 + WS2812B strip) | 1 | Receives the silent page in the woodshop. |

---

## 4. Wiring Guide (I2C Mode — Simplest)

> **Important PN532 Gotcha:** Set the tiny onboard DIP switches (or solder jumpers) on the PN532 module to **I2C mode**: `SEL0 = 1 (ON)`, `SEL1 = 0 (OFF)`.

| PN532 / Peripheral | Pin | ESP32 GPIO (Example) | Notes |
| :--- | :--- | :--- | :--- |
| **PN532** | VCC | `3.3V` (or `5V` if board has regulator) | Check your specific PN532 board silkscreen. |
| **PN532** | GND | `GND` | Common ground. |
| **PN532** | SDA | `GPIO 21` | I2C Data (shared with OLED if added). |
| **PN532** | SCL | `GPIO 22` | I2C Clock (shared with OLED if added). |
| **Piezo Buzzer** | `+` / Signal | `GPIO 25` | Driven via ESPHome `ledc` + `rtttl`. |
| **Piezo Buzzer** | `-` | `GND` | |
| **WS2812B LED Ring** | `5V` | `5V` / `VIN` | Limit brightness in ESPHome if powering via ESP32 USB. |
| **WS2812B LED Ring** | `DIN` | `GPIO 26` | Optional 330Ω resistor in series. |
| **WS2812B LED Ring** | `GND` | `GND` | |

*(If I2C proves finicky on your specific PN532 clone—some red/blue clones have weak I2C pull-ups—switching to **SPI mode** in ESPHome is rock-solid and only uses 2 extra wires.)*

---

## 5. Enclosure & Woodworking / 3D-Printing Design

Since you have both a **wood workshop** and a **3D printer**, this can look genuinely heirloom-quality:

1. **Main Block:**
   * Mill a solid hardwood block (walnut, oak, or beech), roughly **90 × 90 × 35 mm** (or an angled wedge/stand if adding an OLED screen).
   * Rout or CNC a recessed pocket from the underside so the **top wall above the PN532 antenna is 2.5–3.5 mm thick**. Test read reliability with your 25 mm NTAG215 stickers before final glue-up.
   * **Keep metal away from the PN532 antenna:** Avoid screws, magnets, or metal inlays within ~20 mm of the PN532 coil, as metal detunes the 13.56 MHz field.
2. **Diffused Light Ring:**
   * Cut a shallow rabbet around the bottom perimeter (underglow onto the countertop!) or inlay a 3D-printed frosted white PLA diffuser ring around the top pad.
3. **3D-Printed Internal Tray:**
   * Print a snap-in bottom cover with standoffs for the ESP32 and PN532, a USB-C strain-relief channel exiting the back, and rubber feet so the block doesn't slide when tapped one-handed.
4. **Wooden Tokens:**
   * Cut 35–40 mm hardwood discs (6–8 mm thick), drill a 26 mm shallow Forstner pocket on the back for the NTAG215 sticker, and seal with a thin cork pad or epoxy dot.
   * Mark the front with wood-burned, laser-engraved, or 3D-printed inlaid icons (egg, pasta pot, saw/hammer, music note, bell).
   * Store them on a matching **slotted wooden stand** or a small magnetized strip on the side of the cabinet (keep magnets far enough from the reader itself).

---

## 6. ESPHome Configuration (Starter Template)

```yaml
esphome:
  name: kitchenblock
  friendly_name: KitchenBlock

esp32:
  board: esp32dev
  framework:
    type: esp-idf

logger:
api:
  encryption:
    key: !secret kitchenblock_api_key
ota:
  - platform: esphome

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password

i2c:
  sda: GPIO21
  scl: GPIO22
  scan: true
  frequency: 100kHz

# Buzzer for instant tactile feedback
output:
  - platform: ledc
    pin: GPIO25
    id: buzzer_out

rtttl:
  output: buzzer_out
  id: kitchen_buzzer

# Status & visual feedback LED ring
light:
  - platform: esp32_rmt_led_strip
    id: status_led
    name: "KitchenBlock LED"
    rgb_order: GRB
    pin: GPIO26
    num_leds: 12
    chipset: ws2812
    effects:
      - pulse:
          name: "Timer Pulse"
          transition_length: 0.5s
          update_interval: 0.5s

# PN532 NFC Reader
pn532_i2c:
  update_interval: 500ms
  on_tag:
    then:
      - rtttl.play: "tap:d=16,o=6,b=180:c,g"
      - homeassistant.tag_scanned: !lambda 'return x;'
      # Brief visual flash on scan
      - light.turn_on:
          id: status_led
          brightness: 60%
          red: 0%
          green: 100%
          blue: 40%
      - delay: 600ms
      - light.turn_off: status_led
  on_tag_removed:
    then:
      - homeassistant.event:
          event: esphome.kitchenblock_tag_removed
          data:
            tag_id: !lambda 'return x;'
```

---

## 7. Home Assistant Integration Architecture

### A. Helpers to Create in Home Assistant
1. **Timers:**
   * `timer.kitchen_timer_1` (Primary cooking timer)
   * `timer.kitchen_timer_2` (Optional second concurrent timer)
2. **Input Text:**
   * `input_text.kitchen_timer_1_label` (Stores the human name, e.g., `"Pasta"`, `"Soft-Boiled Egg"`, so TTS announces *"Your Pasta timer is done!"*)
3. **Tag Registry (`Settings → Tags`):**
   * Tap each token once on KitchenBlock → it automatically appears in Home Assistant under `Settings → Tags` → give each tag a clear name (e.g., `KB - Egg 6m`, `KB - Workshop Dinner`, `KB - Cooking Mode`).

### B. Automation 1: Kitchen Timer Tokens (with Time Stacking)
* **Trigger:** `tag_scanned` filtered by `device_id` of `kitchenblock` (optional, or by tag ID).
* **Logic (`choose`):**
  * **Preset Token (e.g., `KB - Egg 6m`):** Sets `input_text.kitchen_timer_1_label` to `"Soft-Boiled Egg"`, starts `timer.kitchen_timer_1` for `00:06:00`, and speaks `"6 minute egg timer started"` on the kitchen speaker.
  * **Additive Token (e.g., `KB - +5m`):** If `timer.kitchen_timer_1` is already active, adds 5 minutes to its remaining time; if idle, starts a 5-minute timer.
  * **Cancel Token (`KB - Cancel`):** Cancels active timer(s) and turns off KitchenBlock LED.
* **Timer Finished Automation (`event: timer.finished`):**
  * Turns on `light.kitchenblock_led` with effect `"Timer Pulse"` (bright red/amber).
  * Plays chime + TTS: *"Your {{ states('input_text.kitchen_timer_1_label') }} timer is finished!"*
  * Optionally pulses kitchen under-cabinet lights twice.

### C. Automation 2: Workshop Silent Pager
* **Trigger:** `tag_scanned` for `KB - Workshop Dinner` or `KB - Workshop Help`.
* **Actions:**
  1. **Snapshot workshop light state** using `scene.create` (`snapshot_entities: light.workshop_beacon`).
  2. **Flash workshop light:** Repeat 4 times → set color (Green/Amber for Dinner, Blue for Need a Hand) at 100% brightness → delay 500ms → dim to 10% → delay 500ms.
  3. **Restore workshop light** using `scene.turn_on` so you're never left in the dark near spinning blades!
  4. **Notify phone / Garmin watch:** Send a push notification (`"Dinner is ready!"`) so your wrist vibrates even if your back is turned to the beacon light.
  5. **Confirm in kitchen:** Play a gentle confirmation tone on `kitchenblock` buzzer + green LED glow.

### D. Automation 3: Kitchen Scenes & Family Triggers
* Map `KB - Cooking Mode`, `KB - Cleanup`, and `KB - Set Table` to existing Home Assistant scripts/scenes and media players.

---

## 8. Phased Build Roadmap

1. **Phase 1 — Breadboard Prototype (1 evening)**
   * Wire ESP32 + PN532 + buzzer on a breadboard.
   * Flash ESPHome, verify I2C detection and NTAG215 scanning in HA (`Settings → Tags`).
2. **Phase 2 — Core Home Assistant Automations (1 evening)**
   * Build the timer helper + TTS + timer-finished automation.
   * Wire up the Workshop Silent Pager automation with `scene.create` state restore and test it live.
3. **Phase 3 — Woodworking & 3D-Printed Enclosure (1 weekend)**
   * Test read distance through a scrap piece of your chosen hardwood (target ~3 mm wall).
   * Mill the hardwood block, print the internal tray/diffuser, wire the WS2812B ring, and craft your first 8–10 wooden tokens.
4. **Phase 4 — Polish & Extensions**
   * Add live countdown feedback, workshop acknowledgment button, and extra tokens as you discover what the family reaches for most.

---

## 9. Future Extensions & Ideas

* **Live OLED Countdown Screen:** Add a 1.3" I2C OLED angled on the front face of the wooden block—subscribe to Home Assistant's `timer.kitchen_timer_1` `finishes_at` attribute to render a crisp, large live countdown (`04:32`) and token label.
* **LED Ring Progress Gauge:** Map the 12 WS2812B LEDs to remaining timer percentage—LEDs extinguish one by one as the timer counts down, giving an instant visual gauge from across the kitchen.
* **Dedicated Workshop WLED Beacon + Ack Button:** Use another spare ESP32 in the workshop with a short WLED strip mounted at eye level above your main bench + a big tactile arcade button to acknowledge ("Saw it, coming up!").
* **Presence-Based Coaster Mode:** Rest a *"Tea"* or *"Focus / Quiet"* token on top of the block (`on_tag`) to hold a mode active; lift it off (`on_tag_removed`) to automatically revert.
* **Pantry / Mealie Restock Integration:** Add a few tokens for staples you buy constantly (coffee beans, milk, eggs) that append directly to your Home Assistant / Mealie shopping list when tapped.
* **Kids' Blind-Draw Dinner / Chore Spinner:** Keep a small jar of wooden coins next to the block for fun random family picks.
