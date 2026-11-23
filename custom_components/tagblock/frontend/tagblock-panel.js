const TARGET_READER_DEFAULT = "reader_default";

const ACTIONS = [
  {
    value: "play_music",
    label: "Play Music",
    icon: "🎵",
    targetKind: "media_players",
    supportsReaderDefault: true,
    valueLabel: "Media URI, Link, or Search Query",
    valuePlaceholder: "Search Music Assistant below or paste a Spotify link/URI...",
    hint: "Search Music Assistant below or paste any Spotify/media URI. Choose 'Reader's Room (Auto)' to play on whichever room's reader you tap.",
    showVolume: true,
    showMusicOpts: true,
    showValue: true,
  },
  {
    value: "start_timer",
    label: "Start Timer",
    icon: "⏱️",
    targetKind: "notify_targets",
    supportsReaderDefault: false,
    valueLabel: "Duration (minutes)",
    valuePlaceholder: "10",
    hint: "Starts a countdown timer and sends a Companion App notification (plus a buzzer chime on the reader) when done.",
    showVolume: false,
    showMusicOpts: false,
    showValue: true,
  },
  {
    value: "send_notification",
    label: "Send Notification",
    icon: "📱",
    targetKind: "notify_targets",
    supportsReaderDefault: false,
    valueLabel: "Notification Message",
    valuePlaceholder: "Dinner is ready!",
    hint: "Sends a push notification to the selected phone(s). The tag's Friendly Name is used as the title.",
    showVolume: false,
    showMusicOpts: false,
    showValue: true,
  },
  {
    value: "add_grocery",
    label: "Add to Grocery List",
    icon: "🛒",
    targetKind: "todo_lists",
    supportsReaderDefault: true,
    valueLabel: "Item Name",
    valuePlaceholder: "Milk",
    hint: "Adds the item to the selected to-do/shopping list (defaults to the tag's Friendly Name if left blank).",
    showVolume: false,
    showMusicOpts: false,
    showValue: true,
  },
  {
    value: "alarmo_arm_away",
    label: "Alarmo — Arm Away",
    icon: "🛡️",
    targetKind: "alarm_panels",
    supportsReaderDefault: false,
    valueLabel: "Alarmo PIN (optional)",
    valuePlaceholder: "Leave blank if no PIN is required",
    hint: "Arms Alarmo in Away mode.",
    showVolume: false,
    showMusicOpts: false,
    showValue: true,
    isSecret: true,
  },
  {
    value: "alarmo_arm_home",
    label: "Alarmo — Arm Home",
    icon: "🛡️",
    targetKind: "alarm_panels",
    supportsReaderDefault: false,
    valueLabel: "Alarmo PIN (optional)",
    valuePlaceholder: "Leave blank if no PIN is required",
    hint: "Arms Alarmo in Home mode.",
    showVolume: false,
    showMusicOpts: false,
    showValue: true,
    isSecret: true,
  },
  {
    value: "alarmo_arm_night",
    label: "Alarmo — Arm Night",
    icon: "🛡️",
    targetKind: "alarm_panels",
    supportsReaderDefault: false,
    valueLabel: "Alarmo PIN (optional)",
    valuePlaceholder: "Leave blank if no PIN is required",
    hint: "Arms Alarmo in Night mode.",
    showVolume: false,
    showMusicOpts: false,
    showValue: true,
    isSecret: true,
  },
  {
    value: "alarmo_disarm",
    label: "Alarmo — Disarm",
    icon: "🔓",
    targetKind: "alarm_panels",
    supportsReaderDefault: false,
    valueLabel: "Alarmo PIN (optional)",
    valuePlaceholder: "Leave blank if no PIN is required",
    hint: "Disarms Alarmo.",
    showVolume: false,
    showMusicOpts: false,
    showValue: true,
    isSecret: true,
  },
  {
    value: "run_script_scene",
    label: "Run Script or Scene",
    icon: "⚡",
    targetKind: "scripts_and_scenes",
    supportsReaderDefault: false,
    valueLabel: "",
    valuePlaceholder: "",
    hint: "Runs any Home Assistant Script or activates a Scene.",
    showVolume: false,
    showMusicOpts: false,
    showValue: false,
  },
  {
    value: "pause_speakers",
    label: "Pause Speakers",
    icon: "⏸️",
    targetKind: "media_players",
    supportsReaderDefault: true,
    valueLabel: "",
    valuePlaceholder: "",
    hint: "Pauses playback on the selected speaker (or whichever room's reader you tap).",
    showVolume: false,
    showMusicOpts: false,
    showValue: false,
  },
];

const ACTION_MAP = Object.fromEntries(ACTIONS.map((a) => [a.value, a]));

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatRemaining(endsAtIso) {
  const diffMs = new Date(endsAtIso).getTime() - Date.now();
  const totalSec = Math.max(0, Math.ceil(diffMs / 1000));
  const mins = Math.floor(totalSec / 60);
  const secs = totalSec % 60;
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

class TagBlockPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._narrow = false;
    this._tab = "tags";
    this._tags = [];
    this._readerConfigs = {};
    this._activeTimers = [];
    this._lastScanned = null;
    this._targets = {
      media_players: [],
      notify_targets: [],
      todo_lists: [],
      alarm_panels: [],
      scripts_and_scenes: [],
      readers: [],
      has_music_assistant: false,
    };
    this._search = "";
    this._editing = null;
    this._isNew = false;
    this._maSearchQuery = {};
    this._maSearchResults = {};
    this._maSearching = {};
    this._toast = "";
    this._toastTimer = null;
    this._unsub = null;
    this._tickInterval = null;
    this._lastScanTs = "";
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._init();
    } else if (this._tab === "readers") {
      this._renderReadersTabOnly();
    }
  }

  set narrow(val) {
    this._narrow = Boolean(val);
    this._render();
  }

  connectedCallback() {
    this._tickInterval = window.setInterval(() => {
      if (this._activeTimers.length > 0 && this._tab === "tags") {
        this._updateTimerCountdowns();
      }
    }, 1000);
  }

  disconnectedCallback() {
    if (this._unsub) {
      this._unsub();
      this._unsub = null;
    }
    if (this._tickInterval) {
      window.clearInterval(this._tickInterval);
      this._tickInterval = null;
    }
  }

  async _init() {
    this._render();
    try {
      this._targets = await this._hass.callWS({ type: "tagblock/get_targets" });
      this._unsub = await this._hass.connection.subscribeMessage(
        (msg) => this._onSnapshot(msg),
        { type: "tagblock/subscribe" }
      );
      const initial = await this._hass.callWS({ type: "tagblock/subscribe" }).catch(() => null);
      if (initial) this._onSnapshot(initial);
    } catch (err) {
      console.error("TagBlock init error:", err);
      this._showToast("Could not connect to TagBlock backend.");
    }
    this._render();
  }

  _onSnapshot(snapshot) {
    if (!snapshot) return;
    if (Array.isArray(snapshot.tags)) this._tags = snapshot.tags;
    if (snapshot.reader_configs && typeof snapshot.reader_configs === "object") {
      this._readerConfigs = snapshot.reader_configs;
    }
    if (Array.isArray(snapshot.active_timers)) this._activeTimers = snapshot.active_timers;

    const scan = snapshot.last_scanned;
    if (scan && scan.timestamp && scan.timestamp !== this._lastScanTs) {
      this._lastScanTs = scan.timestamp;
      this._lastScanned = scan;

      if (this._editing && !this._editing.tag_id) {
        this._editing.tag_id = scan.tag_id;
        this._showToast(`Captured tag ID: ${scan.tag_id}`);
      } else if (!scan.matched_id) {
        this._openNewTag(scan.tag_id);
        this._showToast(`Unmapped tag scanned (${scan.tag_id}) — ready to configure!`);
      } else {
        const matched = this._tags.find((t) => t.id === scan.matched_id);
        if (matched) {
          this._showToast(`Triggered "${matched.name}"`);
        }
      }
    }
    this._render();
  }

  _showToast(msg) {
    this._toast = msg;
    if (this._toastTimer) window.clearTimeout(this._toastTimer);
    this._toastTimer = window.setTimeout(() => {
      this._toast = "";
      const el = this.shadowRoot?.querySelector(".toast");
      if (el) el.classList.remove("visible");
    }, 3500);
    const el = this.shadowRoot?.querySelector(".toast");
    if (el) {
      el.textContent = msg;
      el.classList.add("visible");
    }
  }

  _getTargetOptions(actionType) {
    const meta = ACTION_MAP[actionType] || ACTIONS[0];
    const base = this._targets[meta.targetKind] || [];
    if (meta.supportsReaderDefault) {
      return [
        { value: TARGET_READER_DEFAULT, label: "📍 Reader's Room (Auto)" },
        ...base,
      ];
    }
    return base;
  }

  _getTargetLabel(actionType, targetVal) {
    if (targetVal === TARGET_READER_DEFAULT) return "📍 Reader's Room";
    const opts = this._getTargetOptions(actionType);
    const found = opts.find((o) => o.value === targetVal);
    return found ? found.label : targetVal || "—";
  }

  _makeDefaultAction(actionType = "play_music") {
    const opts = this._getTargetOptions(actionType);
    return {
      action_type: actionType,
      target: opts[0]?.value || "",
      value: "",
      volume: 0,
      shuffle: false,
      radio_mode: false,
      enqueue: "replace",
    };
  }

  _openNewTag(prefillTagId = "") {
    this._isNew = true;
    this._maSearchQuery = {};
    this._maSearchResults = {};
    this._editing = {
      id: "",
      tag_id: prefillTagId,
      name: "",
      on_remove: "keep_running",
      retap_mode: "toggle_pause",
      reader_filter: "",
      actions: [this._makeDefaultAction("play_music")],
    };
    this._tab = "tags";
    this._render();
  }

  _openEditTag(tag) {
    this._isNew = false;
    this._maSearchQuery = {};
    this._maSearchResults = {};
    this._editing = {
      ...tag,
      retap_mode: tag.retap_mode || "restart",
      actions: (tag.actions && tag.actions.length > 0
        ? tag.actions
        : [this._makeDefaultAction()]
      ).map((a) => ({
        shuffle: false,
        radio_mode: false,
        enqueue: "replace",
        ...a,
      })),
    };
    this._render();
  }

  _closeEditor() {
    this._editing = null;
    this._isNew = false;
    this._maSearchResults = {};
    this._render();
  }

  async _searchMedia(stepIdx) {
    const q = (this._maSearchQuery[stepIdx] || "").trim();
    if (!q) return;
    this._maSearching[stepIdx] = true;
    this._render();
    try {
      const res = await this._hass.callWS({
        type: "tagblock/search_media",
        query: q,
      });
      this._maSearchResults[stepIdx] = res?.items || [];
      if (this._maSearchResults[stepIdx].length === 0) {
        this._showToast(`No Music Assistant results for "${q}".`);
      }
    } catch (err) {
      console.error(err);
      this._showToast("Music Assistant search failed.");
    } finally {
      this._maSearching[stepIdx] = false;
      this._render();
    }
  }

  async _saveEditing() {
    if (!this._editing) return;
    if (!this._editing.tag_id.trim()) {
      this._showToast("Please enter or scan a Tag ID first.");
      return;
    }
    try {
      const res = await this._hass.callWS({
        type: "tagblock/save_tag",
        tag: this._editing,
      });
      if (res?.tag) {
        this._openEditTag(res.tag);
        this._showToast(`Saved "${res.tag.name}"`);
      }
    } catch (err) {
      console.error(err);
      this._showToast("Failed to save tag.");
    }
    this._render();
  }

  async _deleteEditing() {
    if (!this._editing || !this._editing.id) return;
    const name = this._editing.name || this._editing.tag_id;
    try {
      await this._hass.callWS({
        type: "tagblock/delete_tag",
        id: this._editing.id,
      });
      this._editing = null;
      this._isNew = false;
      this._showToast(`Deleted "${name}"`);
    } catch (err) {
      console.error(err);
      this._showToast("Failed to delete tag.");
    }
    this._render();
  }

  async _testTag(tag) {
    try {
      const res = await this._hass.callWS({
        type: "tagblock/test_tag",
        tag,
      });
      this._showToast(res?.status || `Executed "${tag.name}"`);
    } catch (err) {
      console.error(err);
      this._showToast("Action test failed.");
    }
  }

  async _saveReaderConfig(deviceId, patch) {
    const current = this._readerConfigs[deviceId] || {};
    const next = { ...current, ...patch };
    try {
      await this._hass.callWS({
        type: "tagblock/save_reader_config",
        device_id: deviceId,
        config: next,
      });
      this._readerConfigs[deviceId] = next;
      this._showToast("Saved room defaults for reader.");
    } catch (err) {
      console.error(err);
      this._showToast("Failed to save reader room defaults.");
    }
  }

  async _cancelTimer(timerId) {
    try {
      await this._hass.callWS({
        type: "tagblock/cancel_timer",
        timer_id: timerId,
      });
      this._showToast("Timer cancelled.");
    } catch (err) {
      console.error(err);
    }
  }

  async _refreshTargets() {
    this._targets = await this._hass.callWS({ type: "tagblock/get_targets" });
    this._render();
  }

  _updateTimerCountdowns() {
    const els = this.shadowRoot?.querySelectorAll("[data-timer-ends]");
    if (!els) return;
    els.forEach((el) => {
      el.textContent = formatRemaining(el.getAttribute("data-timer-ends"));
    });
  }

  _renderReadersTabOnly() {
    const container = this.shadowRoot?.querySelector("#readers-grid");
    if (!container) return;
    if (this.shadowRoot.activeElement?.tagName === "SELECT") return;
    container.innerHTML = this._buildReadersCardsHtml();
    this._bindReaderEvents(container);
  }

  _buildReadersCardsHtml() {
    const readers = this._targets.readers || [];
    const states = this._hass?.states || {};
    const speakers = this._targets.media_players || [];
    const todos = this._targets.todo_lists || [];

    const cards = readers.map((reader) => {
      const e = reader.entities || {};
      const cfg = this._readerConfigs[reader.device_id] || {};
      const online = e.status ? states[e.status]?.state === "on" : false;
      const tagPresent = e.tag_present ? states[e.tag_present]?.state === "on" : false;
      const activeTag = e.active_tag ? states[e.active_tag]?.state || "" : "";
      const ledOn = e.led ? states[e.led]?.state === "on" : false;
      const buzzerOn = e.buzzer_enabled ? states[e.buzzer_enabled]?.state === "on" : false;
      const ledFbOn = e.led_enabled ? states[e.led_enabled]?.state === "on" : false;
      const removeSndOn = e.remove_sound_enabled
        ? states[e.remove_sound_enabled]?.state === "on"
        : false;
      const ip = e.ip_address ? states[e.ip_address]?.state : "";
      const ssid = e.ssid ? states[e.ssid]?.state : "";
      const ver = e.esphome_version ? states[e.esphome_version]?.state : reader.sw_version;

      return `
        <div class="card reader-card">
          <div class="reader-head">
            <div>
              <div class="reader-title">${escapeHtml(reader.name)}</div>
              <div class="reader-sub">${escapeHtml(ip || "ESPHome NFC Reader")}${ssid ? ` · ${escapeHtml(ssid)}` : ""}</div>
            </div>
            <div class="pill-row">
              ${tagPresent ? `<span class="pill accent">Tag: ${escapeHtml(activeTag || "Present")}</span>` : ""}
              <span class="pill ${online ? "ok" : "off"}">${online ? "Online" : "Offline"}</span>
            </div>
          </div>

          <div class="room-defaults">
            <div class="room-defaults-title">📍 Room Defaults (used by "Reader's Room" tags & rotary knob)</div>
            <div class="room-defaults-grid">
              <div>
                <label class="mini-label">Default Speaker</label>
                <select class="form-select compact" data-reader-speaker="${escapeHtml(reader.device_id)}">
                  <option value="">Not set</option>
                  ${speakers
                    .map(
                      (s) =>
                        `<option value="${escapeHtml(s.value)}" ${cfg.default_speaker === s.value ? "selected" : ""}>${escapeHtml(s.label)}</option>`
                    )
                    .join("")}
                </select>
              </div>
              <div>
                <label class="mini-label">Default To-Do List</label>
                <select class="form-select compact" data-reader-todo="${escapeHtml(reader.device_id)}">
                  <option value="">Not set</option>
                  ${todos
                    .map(
                      (t) =>
                        `<option value="${escapeHtml(t.value)}" ${cfg.default_todo === t.value ? "selected" : ""}>${escapeHtml(t.label)}</option>`
                    )
                    .join("")}
                </select>
              </div>
            </div>
          </div>

          <div class="toggle-grid">
            ${
              e.led
                ? `<button class="toggle-chip ${ledOn ? "on" : ""}" data-svc="light.toggle" data-eid="${escapeHtml(e.led)}">
                     <span>💡 Status LED</span><strong>${ledOn ? "ON" : "OFF"}</strong>
                   </button>`
                : ""
            }
            ${
              e.buzzer_enabled
                ? `<button class="toggle-chip ${buzzerOn ? "on" : ""}" data-svc="switch.toggle" data-eid="${escapeHtml(e.buzzer_enabled)}">
                     <span>🔊 Buzzer</span><strong>${buzzerOn ? "ON" : "OFF"}</strong>
                   </button>`
                : ""
            }
            ${
              e.led_enabled
                ? `<button class="toggle-chip ${ledFbOn ? "on" : ""}" data-svc="switch.toggle" data-eid="${escapeHtml(e.led_enabled)}">
                     <span>✨ LED Feedback</span><strong>${ledFbOn ? "ON" : "OFF"}</strong>
                   </button>`
                : ""
            }
            ${
              e.remove_sound_enabled
                ? `<button class="toggle-chip ${removeSndOn ? "on" : ""}" data-svc="switch.toggle" data-eid="${escapeHtml(e.remove_sound_enabled)}">
                     <span>🔉 Lift Sound</span><strong>${removeSndOn ? "ON" : "OFF"}</strong>
                   </button>`
                : ""
            }
          </div>

          <div class="reader-actions">
            ${
              e.write_tag_random
                ? `<button class="btn secondary" data-svc="button.press" data-eid="${escapeHtml(e.write_tag_random)}">Write Random Tag</button>`
                : ""
            }
            ${
              e.clean_tag
                ? `<button class="btn secondary" data-svc="button.press" data-eid="${escapeHtml(e.clean_tag)}">Clean Tag</button>`
                : ""
            }
            ${
              e.cancel_writing
                ? `<button class="btn secondary" data-svc="button.press" data-eid="${escapeHtml(e.cancel_writing)}">Cancel Write</button>`
                : ""
            }
            ${
              e.restart
                ? `<button class="btn danger-ghost" data-svc="button.press" data-eid="${escapeHtml(e.restart)}">Restart</button>`
                : ""
            }
          </div>

          ${ver ? `<div class="reader-foot">ESPHome ${escapeHtml(ver)}</div>` : ""}
        </div>
      `;
    });

    cards.push(`
      <div class="card reader-card add-reader-card">
        <div class="add-reader-icon">📡</div>
        <div class="reader-title">Multi-Reader Ready</div>
        <p class="muted">
          Adopt additional ESPHome TagBlock readers in Home Assistant and they will automatically appear here with their own room defaults.
        </p>
        <button class="btn secondary" id="btn-refresh-readers">Refresh Readers</button>
      </div>
    `);

    return cards.join("");
  }

  _bindReaderEvents(root) {
    root.querySelectorAll("[data-svc][data-eid]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const [domain, service] = btn.getAttribute("data-svc").split(".");
        const eid = btn.getAttribute("data-eid");
        try {
          await this._hass.callService(domain, service, { entity_id: eid });
          this._showToast(`Triggered ${service.replace("_", " ")}`);
        } catch (err) {
          console.error(err);
          this._showToast("Could not control reader entity.");
        }
      });
    });

    root.querySelectorAll("[data-reader-speaker]").forEach((sel) => {
      sel.addEventListener("change", (e) => {
        const did = sel.getAttribute("data-reader-speaker");
        this._saveReaderConfig(did, { default_speaker: e.target.value });
      });
    });

    root.querySelectorAll("[data-reader-todo]").forEach((sel) => {
      sel.addEventListener("change", (e) => {
        const did = sel.getAttribute("data-reader-todo");
        this._saveReaderConfig(did, { default_todo: e.target.value });
      });
    });

    root.querySelector("#btn-refresh-readers")?.addEventListener("click", () =>
      this._refreshTargets()
    );
  }

  _render() {
    const root = this.shadowRoot;
    if (!root) return;

    const q = this._search.trim().toLowerCase();
    const filteredTags = this._tags.filter((t) => {
      if (!q) return true;
      const valMatch = (t.actions || []).some((a) =>
        (a.value || "").toLowerCase().includes(q)
      );
      return (
        (t.name || "").toLowerCase().includes(q) ||
        (t.tag_id || "").toLowerCase().includes(q) ||
        valMatch
      );
    });

    const readersCount = (this._targets.readers || []).length;
    const hasMusicOrTimer = this._editing
      ? this._editing.actions.some(
          (a) => a.action_type === "play_music" || a.action_type === "start_timer"
        )
      : false;
    const hasMusic = this._editing
      ? this._editing.actions.some((a) => a.action_type === "play_music")
      : false;
    const hasTimer = this._editing
      ? this._editing.actions.some((a) => a.action_type === "start_timer")
      : false;

    root.innerHTML = `
      <style>
        :host {
          display: block;
          min-height: 100vh;
          background: var(--primary-background-color, #111);
          color: var(--primary-text-color, #fff);
          font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
          box-sizing: border-box;
        }
        * { box-sizing: border-box; }
        .topbar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 12px 20px;
          background: var(--app-header-background-color, var(--card-background-color));
          color: var(--app-header-text-color, var(--primary-text-color));
          border-bottom: 1px solid var(--divider-color, rgba(255,255,255,0.1));
          position: sticky;
          top: 0;
          z-index: 10;
        }
        .topbar-left { display: flex; align-items: center; gap: 10px; }
        .brand { font-size: 20px; font-weight: 600; letter-spacing: -0.2px; }
        .tabs { display: flex; gap: 6px; }
        .tab-btn {
          border: 1px solid transparent;
          background: transparent;
          color: inherit;
          padding: 8px 14px;
          border-radius: 999px;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          opacity: 0.78;
          transition: all 0.15s ease;
        }
        .tab-btn:hover { opacity: 1; background: rgba(127,127,127,0.14); }
        .tab-btn.active {
          opacity: 1;
          background: var(--primary-color);
          color: var(--text-primary-color, #fff);
        }
        .container { max-width: 1280px; margin: 0 auto; padding: 20px; }
        .split-layout {
          display: grid;
          grid-template-columns: minmax(320px, 1fr) minmax(380px, 1.25fr);
          gap: 20px;
          align-items: start;
        }
        @media (max-width: 900px) { .split-layout { grid-template-columns: 1fr; } }
        .card {
          background: var(--card-background-color, #1e1e1e);
          border-radius: var(--ha-card-border-radius, 14px);
          border: 1px solid var(--divider-color, rgba(255,255,255,0.08));
          box-shadow: var(--ha-card-box-shadow, 0 2px 8px rgba(0,0,0,0.15));
          padding: 18px;
        }
        .card-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 14px;
        }
        .card-title { font-size: 17px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
        .count-badge {
          font-size: 12px;
          font-weight: 600;
          padding: 2px 8px;
          border-radius: 999px;
          background: rgba(127,127,127,0.18);
          color: var(--secondary-text-color);
        }
        .search-box {
          width: 100%;
          padding: 9px 12px;
          border-radius: 10px;
          border: 1px solid var(--divider-color, rgba(255,255,255,0.15));
          background: var(--primary-background-color, rgba(0,0,0,0.12));
          color: var(--primary-text-color);
          font-size: 14px;
          margin-bottom: 12px;
        }
        .tag-list { display: flex; flex-direction: column; gap: 8px; }
        .tag-row {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 12px;
          border-radius: 12px;
          border: 1px solid var(--divider-color, rgba(255,255,255,0.08));
          background: var(--primary-background-color, rgba(127,127,127,0.05));
          cursor: pointer;
          transition: border-color 0.15s ease, background 0.15s ease;
        }
        .tag-row:hover { border-color: var(--primary-color); background: rgba(127,127,127,0.1); }
        .tag-row.selected {
          border-color: var(--primary-color);
          box-shadow: 0 0 0 1px var(--primary-color);
          background: rgba(127,127,127,0.14);
        }
        .tag-icon {
          width: 40px;
          height: 40px;
          border-radius: 10px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 20px;
          background: rgba(127,127,127,0.14);
          flex-shrink: 0;
        }
        .tag-info { flex: 1; min-width: 0; }
        .tag-name { font-size: 15px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .tag-meta { font-size: 12px; color: var(--secondary-text-color); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .tag-uid { font-family: monospace; font-size: 11px; opacity: 0.7; }
        .icon-btn {
          border: 1px solid var(--divider-color, rgba(255,255,255,0.14));
          background: var(--card-background-color);
          color: var(--primary-text-color);
          border-radius: 8px;
          padding: 6px 10px;
          font-size: 12px;
          cursor: pointer;
          flex-shrink: 0;
        }
        .icon-btn:hover { border-color: var(--primary-color); color: var(--primary-color); }
        .btn {
          border: none;
          border-radius: 10px;
          padding: 9px 15px;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: opacity 0.15s ease;
        }
        .btn:hover { opacity: 0.9; }
        .btn.primary { background: var(--primary-color); color: var(--text-primary-color, #fff); }
        .btn.secondary { background: rgba(127,127,127,0.16); color: var(--primary-text-color); }
        .btn.danger-ghost {
          background: transparent;
          color: var(--error-color, #ef5350);
          border: 1px solid var(--error-color, #ef5350);
        }
        .form-group { margin-bottom: 12px; }
        .form-label {
          display: flex;
          justify-content: space-between;
          font-size: 13px;
          font-weight: 500;
          color: var(--secondary-text-color);
          margin-bottom: 5px;
        }
        .mini-label { display: block; font-size: 11px; color: var(--secondary-text-color); margin-bottom: 4px; }
        .form-input, .form-select {
          width: 100%;
          padding: 9px 12px;
          border-radius: 10px;
          border: 1px solid var(--divider-color, rgba(255,255,255,0.18));
          background: var(--primary-background-color, rgba(0,0,0,0.12));
          color: var(--primary-text-color);
          font-size: 14px;
        }
        .form-select.compact { padding: 7px 10px; font-size: 13px; }
        .form-range { width: 100%; accent-color: var(--primary-color); }
        .action-block {
          border: 1px solid var(--divider-color, rgba(255,255,255,0.12));
          border-radius: 12px;
          padding: 14px;
          margin-bottom: 12px;
          background: rgba(127,127,127,0.05);
        }
        .action-block-head {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 10px;
          font-size: 13px;
          font-weight: 600;
          color: var(--secondary-text-color);
        }
        .ma-search-row { display: flex; gap: 8px; }
        .ma-results {
          margin-top: 8px;
          max-height: 220px;
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .ma-item {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 8px 10px;
          border-radius: 9px;
          border: 1px solid var(--divider-color, rgba(255,255,255,0.1));
          background: var(--card-background-color);
          cursor: pointer;
          text-align: left;
          color: var(--primary-text-color);
        }
        .ma-item:hover { border-color: var(--primary-color); }
        .ma-thumb {
          width: 34px;
          height: 34px;
          border-radius: 6px;
          object-fit: cover;
          background: rgba(127,127,127,0.2);
          flex-shrink: 0;
        }
        .ma-item-info { flex: 1; min-width: 0; }
        .ma-item-title { font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .ma-item-sub { font-size: 11px; color: var(--secondary-text-color); }
        .music-opts-row {
          display: grid;
          grid-template-columns: 1fr 1fr 1fr;
          gap: 8px;
          align-items: center;
          margin-top: 8px;
        }
        .check-pill {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 13px;
          padding: 8px 10px;
          border-radius: 9px;
          border: 1px solid var(--divider-color, rgba(255,255,255,0.14));
          background: var(--primary-background-color, rgba(0,0,0,0.1));
          cursor: pointer;
        }
        .hint-box {
          padding: 8px 10px;
          border-radius: 8px;
          background: rgba(127,127,127,0.1);
          font-size: 12px;
          color: var(--secondary-text-color);
          margin-bottom: 12px;
          line-height: 1.4;
        }
        .scan-hint { font-size: 12px; color: var(--primary-color); margin-top: 5px; }
        .editor-footer {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
          margin-top: 16px;
          padding-top: 14px;
          border-top: 1px solid var(--divider-color, rgba(255,255,255,0.1));
        }
        .editor-footer-left { display: flex; gap: 8px; }
        .empty-state { text-align: center; padding: 36px 18px; color: var(--secondary-text-color); }
        .empty-icon { font-size: 40px; margin-bottom: 10px; }
        .muted { color: var(--secondary-text-color); font-size: 13px; line-height: 1.5; }
        .timers-box { margin-bottom: 14px; display: flex; flex-direction: column; gap: 8px; }
        .timer-pill {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 12px;
          border-radius: 10px;
          background: rgba(127,127,127,0.14);
          border-left: 3px solid var(--primary-color);
        }
        .readers-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
          gap: 18px;
        }
        .reader-card { display: flex; flex-direction: column; gap: 14px; }
        .reader-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
        .reader-title { font-size: 16px; font-weight: 600; }
        .reader-sub { font-size: 12px; color: var(--secondary-text-color); margin-top: 2px; }
        .room-defaults {
          padding: 12px;
          border-radius: 10px;
          background: rgba(127,127,127,0.08);
          border: 1px solid var(--divider-color, rgba(255,255,255,0.08));
        }
        .room-defaults-title { font-size: 12px; font-weight: 600; margin-bottom: 8px; }
        .room-defaults-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
        .pill-row { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
        .pill { font-size: 11px; font-weight: 600; padding: 3px 9px; border-radius: 999px; }
        .pill.ok { background: rgba(76, 175, 80, 0.2); color: #66bb6a; }
        .pill.off { background: rgba(244, 67, 54, 0.2); color: #ef5350; }
        .pill.accent { background: rgba(66, 165, 245, 0.2); color: #42a5f5; }
        .toggle-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
        .toggle-chip {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 10px 12px;
          border-radius: 10px;
          border: 1px solid var(--divider-color, rgba(255,255,255,0.12));
          background: var(--primary-background-color, rgba(0,0,0,0.1));
          color: var(--primary-text-color);
          font-size: 13px;
          cursor: pointer;
        }
        .toggle-chip.on { border-color: var(--primary-color); background: rgba(127,127,127,0.16); }
        .reader-actions { display: flex; flex-wrap: wrap; gap: 8px; }
        .reader-foot {
          font-size: 12px;
          color: var(--secondary-text-color);
          border-top: 1px solid var(--divider-color, rgba(255,255,255,0.08));
          padding-top: 10px;
        }
        .add-reader-card {
          border-style: dashed;
          align-items: center;
          justify-content: center;
          text-align: center;
          min-height: 240px;
        }
        .add-reader-icon { font-size: 32px; }
        .toast {
          position: fixed;
          bottom: 20px;
          right: 20px;
          background: var(--primary-color);
          color: var(--text-primary-color, #fff);
          padding: 10px 16px;
          border-radius: 10px;
          font-size: 14px;
          font-weight: 500;
          box-shadow: 0 4px 14px rgba(0,0,0,0.3);
          opacity: 0;
          pointer-events: none;
          transform: translateY(10px);
          transition: all 0.2s ease;
          z-index: 100;
        }
        .toast.visible { opacity: 1; transform: translateY(0); }
      </style>

      <div class="topbar">
        <div class="topbar-left">
          <ha-menu-button .hass=${this._hass} .narrow=${this._narrow}></ha-menu-button>
          <span class="brand">TagBlock</span>
        </div>
        <div class="tabs">
          <button class="tab-btn ${this._tab === "tags" ? "active" : ""}" id="tab-tags">
            Mapped Tags (${this._tags.length})
          </button>
          <button class="tab-btn ${this._tab === "readers" ? "active" : ""}" id="tab-readers">
            Tag Readers (${readersCount})
          </button>
        </div>
      </div>

      <div class="container">
        ${
          this._tab === "tags"
            ? `
          <div class="split-layout">
            <!-- LEFT: Mapped Tags List -->
            <div class="card">
              <div class="card-header">
                <div class="card-title">
                  Mapped Tags <span class="count-badge">${this._tags.length}</span>
                </div>
                <button class="btn primary" id="btn-add-tag">+ Add Tag</button>
              </div>

              ${
                this._activeTimers.length > 0
                  ? `<div class="timers-box">
                      ${this._activeTimers
                        .map(
                          (tm) => `
                        <div class="timer-pill">
                          <div>
                            <strong>⏱️ ${escapeHtml(tm.name)}</strong>
                            <span style="margin-left:8px;font-family:monospace;" data-timer-ends="${escapeHtml(tm.ends_at)}">${formatRemaining(tm.ends_at)}</span>
                          </div>
                          <button class="icon-btn" data-cancel-timer="${escapeHtml(tm.id)}">Cancel</button>
                        </div>
                      `
                        )
                        .join("")}
                    </div>`
                  : ""
              }

              <input
                class="search-box"
                id="search-input"
                type="text"
                placeholder="Search tags by name, ID, or value..."
                value="${escapeHtml(this._search)}"
              />

              <div class="tag-list">
                ${
                  filteredTags.length === 0
                    ? `<div class="empty-state">
                         <div class="empty-icon">🏷️</div>
                         <div>${this._tags.length === 0 ? "No tags mapped yet." : "No matching tags."}</div>
                         <p class="muted">Click <strong>+ Add Tag</strong> or tap an NFC tag on any reader.</p>
                       </div>`
                    : filteredTags
                        .map((tag) => {
                          const steps = tag.actions || [];
                          const first = steps[0] || {};
                          const meta = ACTION_MAP[first.action_type] || ACTIONS[0];
                          const isSelected = this._editing && this._editing.id === tag.id;
                          const targetLbl = this._getTargetLabel(first.action_type, first.target);
                          const volTxt =
                            first.action_type === "play_music" && first.volume > 0
                              ? ` · ${first.volume}%`
                              : "";
                          const shufTxt = first.shuffle ? " · 🔀" : "";
                          const extraTxt = steps.length > 1 ? ` · +${steps.length - 1} more` : "";
                          const remTxt =
                            tag.on_remove === "pause_music"
                              ? " · ↩ Pause"
                              : tag.on_remove === "cancel_timer"
                              ? " · ↩ Cancel"
                              : "";
                          return `
                            <div class="tag-row ${isSelected ? "selected" : ""}" data-select-id="${escapeHtml(tag.id)}">
                              <div class="tag-icon">${meta.icon}</div>
                              <div class="tag-info">
                                <div class="tag-name">${escapeHtml(tag.name)}</div>
                                <div class="tag-meta">
                                  ${escapeHtml(meta.label)} · ${escapeHtml(targetLbl)}${escapeHtml(volTxt)}${shufTxt}${escapeHtml(extraTxt)}${escapeHtml(remTxt)}
                                </div>
                                <div class="tag-uid">${escapeHtml(tag.tag_id)}</div>
                              </div>
                              <button class="icon-btn" data-test-id="${escapeHtml(tag.id)}" title="Test action">▶</button>
                            </div>
                          `;
                        })
                        .join("")
                }
              </div>
            </div>

            <!-- RIGHT: Multi-Action Edit Card -->
            <div class="card">
              ${
                !this._editing
                  ? `<div class="empty-state">
                       <div class="empty-icon">✨</div>
                       <div style="font-size:16px;font-weight:600;color:var(--primary-text-color);margin-bottom:6px;">
                         Action Editor
                       </div>
                       <p class="muted">
                         Click any mapped tag on the left to edit its actions, click <strong>+ Add Tag</strong>, or tap an unmapped NFC tag on any reader.
                       </p>
                       <button class="btn primary" id="btn-empty-add" style="margin-top:8px;">+ Add Tag</button>
                     </div>`
                  : `
                    <div class="card-header">
                      <div class="card-title">
                        ${this._isNew ? "Add New Tag" : "Edit Tag Actions"}
                      </div>
                      <button class="icon-btn" id="btn-close-editor" title="Close">✕</button>
                    </div>

                    <div class="form-group">
                      <label class="form-label"><span>NFC Tag ID</span></label>
                      <input class="form-input" id="f-tag-id" type="text" placeholder="Tap a tag on any reader or paste UID..." value="${escapeHtml(this._editing.tag_id)}" />
                      ${!this._editing.tag_id ? `<div class="scan-hint">📡 Waiting for tap — scan any NFC tag to auto-fill</div>` : ""}
                    </div>

                    <div class="form-group">
                      <label class="form-label"><span>Friendly Name</span></label>
                      <input class="form-input" id="f-name" type="text" placeholder="e.g. Morning Jazz, Cooking Mode, Pasta Timer" value="${escapeHtml(this._editing.name)}" />
                    </div>

                    ${this._editing.actions
                      .map((step, idx) => {
                        const meta = ACTION_MAP[step.action_type] || ACTIONS[0];
                        const opts = this._getTargetOptions(step.action_type);
                        const maRes = this._maSearchResults[idx] || [];
                        return `
                          <div class="action-block" data-action-idx="${idx}">
                            <div class="action-block-head">
                              <span>${meta.icon} Action ${idx + 1}</span>
                              ${
                                this._editing.actions.length > 1
                                  ? `<button class="icon-btn" data-remove-step="${idx}">✕ Remove</button>`
                                  : ""
                              }
                            </div>

                            <div class="form-group">
                              <label class="form-label"><span>Action Type</span></label>
                              <select class="form-select" data-step-action="${idx}">
                                ${ACTIONS.map(
                                  (a) =>
                                    `<option value="${a.value}" ${step.action_type === a.value ? "selected" : ""}>${a.icon} ${escapeHtml(a.label)}</option>`
                                ).join("")}
                              </select>
                            </div>

                            <div class="hint-box">${escapeHtml(meta.hint)}</div>

                            <div class="form-group">
                              <label class="form-label"><span>Target</span></label>
                              <select class="form-select" data-step-target="${idx}">
                                ${
                                  opts.length === 0
                                    ? `<option value="">No targets found</option>`
                                    : opts
                                        .map(
                                          (opt) =>
                                            `<option value="${escapeHtml(opt.value)}" ${step.target === opt.value ? "selected" : ""}>${escapeHtml(opt.label)}</option>`
                                        )
                                        .join("")
                                }
                              </select>
                            </div>

                            ${
                              meta.showMusicOpts && this._targets.has_music_assistant
                                ? `<div class="form-group">
                                     <label class="form-label"><span>🔍 Search Music Assistant</span></label>
                                     <div class="ma-search-row">
                                       <input class="form-input" data-ma-input="${idx}" type="text" placeholder="Search playlist, album, artist, or track..." value="${escapeHtml(this._maSearchQuery[idx] || "")}" />
                                       <button class="btn secondary" data-ma-search="${idx}">${this._maSearching[idx] ? "..." : "Search"}</button>
                                     </div>
                                     ${
                                       maRes.length > 0
                                         ? `<div class="ma-results">
                                              ${maRes
                                                .map(
                                                  (item, rIdx) => `
                                                <button class="ma-item" data-ma-pick-step="${idx}" data-ma-pick-idx="${rIdx}">
                                                  ${item.image ? `<img class="ma-thumb" src="${escapeHtml(item.image)}" alt="" />` : `<div class="ma-thumb"></div>`}
                                                  <div class="ma-item-info">
                                                    <div class="ma-item-title">${escapeHtml(item.name)}</div>
                                                    <div class="ma-item-sub">${escapeHtml(item.media_type.toUpperCase())}${item.artist ? ` · ${escapeHtml(item.artist)}` : ""}</div>
                                                  </div>
                                                </button>
                                              `
                                                )
                                                .join("")}
                                            </div>`
                                         : ""
                                     }
                                   </div>`
                                : ""
                            }

                            ${
                              meta.showValue
                                ? `<div class="form-group">
                                     <label class="form-label"><span>${escapeHtml(meta.valueLabel)}</span></label>
                                     <input class="form-input" data-step-value="${idx}" type="${meta.isSecret ? "password" : "text"}" placeholder="${escapeHtml(meta.valuePlaceholder)}" value="${escapeHtml(step.value)}" />
                                   </div>`
                                : ""
                            }

                            ${
                              meta.showVolume
                                ? `<div class="form-group">
                                     <label class="form-label">
                                       <span>Music Volume</span>
                                       <strong id="vol-readout-${idx}">${step.volume > 0 ? `${step.volume}%` : "Unchanged"}</strong>
                                     </label>
                                     <input class="form-range" data-step-volume="${idx}" type="range" min="0" max="100" step="5" value="${Number(step.volume || 0)}" />
                                   </div>`
                                : ""
                            }

                            ${
                              meta.showMusicOpts
                                ? `<div class="music-opts-row">
                                     <label class="check-pill">
                                       <input type="checkbox" data-step-shuffle="${idx}" ${step.shuffle ? "checked" : ""} />
                                       <span>🔀 Shuffle</span>
                                     </label>
                                     <label class="check-pill">
                                       <input type="checkbox" data-step-radio="${idx}" ${step.radio_mode ? "checked" : ""} />
                                       <span>📻 Radio</span>
                                     </label>
                                     <select class="form-select compact" data-step-enqueue="${idx}" title="Queue Mode">
                                       <option value="replace" ${step.enqueue === "replace" ? "selected" : ""}>Replace Queue</option>
                                       <option value="add" ${step.enqueue === "add" ? "selected" : ""}>Add to Queue</option>
                                       <option value="next" ${step.enqueue === "next" ? "selected" : ""}>Play Next</option>
                                     </select>
                                   </div>`
                                : ""
                            }
                          </div>
                        `;
                      })
                      .join("")}

                    <div class="form-group">
                      <button class="btn secondary" id="btn-add-step" style="width:100%;">+ Add Another Action (Combo)</button>
                    </div>

                    ${
                      hasMusic
                        ? `<div class="form-group">
                             <label class="form-label"><span>When Same Tag Is Tapped Again</span></label>
                             <select class="form-select" id="f-retap">
                               <option value="toggle_pause" ${this._editing.retap_mode === "toggle_pause" ? "selected" : ""}>Toggle Play / Pause</option>
                               <option value="restart" ${this._editing.retap_mode === "restart" ? "selected" : ""}>Restart from Beginning</option>
                             </select>
                           </div>`
                        : ""
                    }

                    ${
                      hasMusicOrTimer
                        ? `<div class="form-group">
                             <label class="form-label"><span>When Tag Is Removed</span></label>
                             <select class="form-select" id="f-remove">
                               <option value="keep_running" ${this._editing.on_remove === "keep_running" ? "selected" : ""}>Keep Running (Tap Mode)</option>
                               ${hasMusic ? `<option value="pause_music" ${this._editing.on_remove === "pause_music" ? "selected" : ""}>Pause Music (Hold-to-Play)</option>` : ""}
                               ${hasTimer ? `<option value="cancel_timer" ${this._editing.on_remove === "cancel_timer" ? "selected" : ""}>Cancel Timer</option>` : ""}
                             </select>
                           </div>`
                        : ""
                    }

                    ${
                      readersCount > 1
                        ? `<div class="form-group">
                             <label class="form-label"><span>Limit to Specific Reader (Optional)</span></label>
                             <select class="form-select" id="f-reader">
                               <option value="" ${!this._editing.reader_filter ? "selected" : ""}>Any TagBlock Reader</option>
                               ${this._targets.readers
                                 .map(
                                   (r) =>
                                     `<option value="${escapeHtml(r.device_id)}" ${this._editing.reader_filter === r.device_id ? "selected" : ""}>${escapeHtml(r.name)}</option>`
                                 )
                                 .join("")}
                             </select>
                           </div>`
                        : ""
                    }

                    <div class="editor-footer">
                      <div class="editor-footer-left">
                        <button class="btn primary" id="btn-save">Save Tag</button>
                        <button class="btn secondary" id="btn-test-draft">Test Action${this._editing.actions.length > 1 ? "s" : ""}</button>
                      </div>
                      ${!this._isNew ? `<button class="btn danger-ghost" id="btn-delete">Delete</button>` : ""}
                    </div>
                  `
              }
            </div>
          </div>
        `
            : `
          <div class="readers-grid" id="readers-grid">
            ${this._buildReadersCardsHtml()}
          </div>
        `
        }
      </div>

      <div class="toast ${this._toast ? "visible" : ""}">${escapeHtml(this._toast)}</div>
    `;

    const menuBtn = root.querySelector("ha-menu-button");
    if (menuBtn) {
      menuBtn.hass = this._hass;
      menuBtn.narrow = this._narrow;
    }

    root.querySelector("#tab-tags")?.addEventListener("click", () => {
      this._tab = "tags";
      this._render();
    });
    root.querySelector("#tab-readers")?.addEventListener("click", () => {
      this._tab = "readers";
      this._refreshTargets();
    });

    if (this._tab === "tags") {
      root.querySelector("#btn-add-tag")?.addEventListener("click", () => this._openNewTag());
      root.querySelector("#btn-empty-add")?.addEventListener("click", () => this._openNewTag());
      root.querySelector("#btn-close-editor")?.addEventListener("click", () => this._closeEditor());

      const searchInput = root.querySelector("#search-input");
      if (searchInput) {
        searchInput.addEventListener("input", (e) => {
          this._search = e.target.value;
          const pos = e.target.selectionStart;
          this._render();
          const next = this.shadowRoot.querySelector("#search-input");
          if (next) {
            next.focus();
            next.setSelectionRange(pos, pos);
          }
        });
      }

      root.querySelectorAll("[data-select-id]").forEach((row) => {
        row.addEventListener("click", () => {
          const id = row.getAttribute("data-select-id");
          const tag = this._tags.find((t) => t.id === id);
          if (tag) this._openEditTag(tag);
        });
      });

      root.querySelectorAll("[data-test-id]").forEach((btn) => {
        btn.addEventListener("click", (e) => {
          e.stopPropagation();
          const id = btn.getAttribute("data-test-id");
          const tag = this._tags.find((t) => t.id === id);
          if (tag) this._testTag(tag);
        });
      });

      root.querySelectorAll("[data-cancel-timer]").forEach((btn) => {
        btn.addEventListener("click", () => {
          this._cancelTimer(btn.getAttribute("data-cancel-timer"));
        });
      });

      if (this._editing) {
        root.querySelector("#f-tag-id")?.addEventListener("input", (e) => {
          this._editing.tag_id = e.target.value;
        });
        root.querySelector("#f-name")?.addEventListener("input", (e) => {
          this._editing.name = e.target.value;
        });

        root.querySelector("#btn-add-step")?.addEventListener("click", () => {
          this._editing.actions.push(this._makeDefaultAction("run_script_scene"));
          this._render();
        });

        root.querySelectorAll("[data-remove-step]").forEach((btn) => {
          btn.addEventListener("click", () => {
            const idx = Number(btn.getAttribute("data-remove-step"));
            this._editing.actions.splice(idx, 1);
            delete this._maSearchResults[idx];
            this._render();
          });
        });

        root.querySelectorAll("[data-step-action]").forEach((sel) => {
          sel.addEventListener("change", (e) => {
            const idx = Number(sel.getAttribute("data-step-action"));
            const nextType = e.target.value;
            this._editing.actions[idx] = this._makeDefaultAction(nextType);
            delete this._maSearchResults[idx];
            this._render();
          });
        });

        root.querySelectorAll("[data-step-target]").forEach((sel) => {
          sel.addEventListener("change", (e) => {
            const idx = Number(sel.getAttribute("data-step-target"));
            this._editing.actions[idx].target = e.target.value;
          });
        });

        root.querySelectorAll("[data-step-value]").forEach((inp) => {
          inp.addEventListener("input", (e) => {
            const idx = Number(inp.getAttribute("data-step-value"));
            this._editing.actions[idx].value = e.target.value;
          });
        });

        root.querySelectorAll("[data-step-volume]").forEach((rng) => {
          rng.addEventListener("input", (e) => {
            const idx = Number(rng.getAttribute("data-step-volume"));
            const v = Number(e.target.value);
            this._editing.actions[idx].volume = v;
            const readout = root.querySelector(`#vol-readout-${idx}`);
            if (readout) readout.textContent = v > 0 ? `${v}%` : "Unchanged";
          });
        });

        root.querySelectorAll("[data-step-shuffle]").forEach((chk) => {
          chk.addEventListener("change", (e) => {
            const idx = Number(chk.getAttribute("data-step-shuffle"));
            this._editing.actions[idx].shuffle = e.target.checked;
          });
        });

        root.querySelectorAll("[data-step-radio]").forEach((chk) => {
          chk.addEventListener("change", (e) => {
            const idx = Number(chk.getAttribute("data-step-radio"));
            this._editing.actions[idx].radio_mode = e.target.checked;
          });
        });

        root.querySelectorAll("[data-step-enqueue]").forEach((sel) => {
          sel.addEventListener("change", (e) => {
            const idx = Number(sel.getAttribute("data-step-enqueue"));
            this._editing.actions[idx].enqueue = e.target.value;
          });
        });

        root.querySelectorAll("[data-ma-input]").forEach((inp) => {
          inp.addEventListener("input", (e) => {
            const idx = Number(inp.getAttribute("data-ma-input"));
            this._maSearchQuery[idx] = e.target.value;
          });
          inp.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              this._searchMedia(Number(inp.getAttribute("data-ma-input")));
            }
          });
        });

        root.querySelectorAll("[data-ma-search]").forEach((btn) => {
          btn.addEventListener("click", () => {
            this._searchMedia(Number(btn.getAttribute("data-ma-search")));
          });
        });

        root.querySelectorAll("[data-ma-pick-step]").forEach((btn) => {
          btn.addEventListener("click", () => {
            const stepIdx = Number(btn.getAttribute("data-ma-pick-step"));
            const resIdx = Number(btn.getAttribute("data-ma-pick-idx"));
            const picked = (this._maSearchResults[stepIdx] || [])[resIdx];
            if (!picked) return;
            this._editing.actions[stepIdx].value = picked.uri;
            if (!this._editing.name.trim()) {
              this._editing.name = picked.name;
            }
            this._maSearchResults[stepIdx] = [];
            this._showToast(`Selected "${picked.name}"`);
            this._render();
          });
        });

        root.querySelector("#f-retap")?.addEventListener("change", (e) => {
          this._editing.retap_mode = e.target.value;
        });
        root.querySelector("#f-remove")?.addEventListener("change", (e) => {
          this._editing.on_remove = e.target.value;
        });
        root.querySelector("#f-reader")?.addEventListener("change", (e) => {
          this._editing.reader_filter = e.target.value;
        });

        root.querySelector("#btn-save")?.addEventListener("click", () => this._saveEditing());
        root.querySelector("#btn-test-draft")?.addEventListener("click", () =>
          this._testTag(this._editing)
        );
        root.querySelector("#btn-delete")?.addEventListener("click", () => this._deleteEditing());
      }
    } else {
      const grid = root.querySelector("#readers-grid");
      if (grid) this._bindReaderEvents(grid);
    }
  }
}

customElements.define("tagblock-panel", TagBlockPanel);
