"""Constants for the TagBlock integration."""

DOMAIN = "tagblock"
STORAGE_KEY = "tagblock.storage"
STORAGE_VERSION = 1

PANEL_URL = "tagblock"
PANEL_TITLE = "TagBlock"
PANEL_ICON = "mdi:nfc-variant"
STATIC_URL = "/tagblock_static"
FRONTEND_VERSION = "0.1.0"

TARGET_READER_DEFAULT = "reader_default"

ACTION_PLAY_MUSIC = "play_music"
ACTION_PAUSE_SPEAKERS = "pause_speakers"
ACTION_START_TIMER = "start_timer"
ACTION_SEND_NOTIFICATION = "send_notification"
ACTION_ADD_GROCERY = "add_grocery"
ACTION_ALARMO_ARM_AWAY = "alarmo_arm_away"
ACTION_ALARMO_ARM_HOME = "alarmo_arm_home"
ACTION_ALARMO_ARM_NIGHT = "alarmo_arm_night"
ACTION_ALARMO_DISARM = "alarmo_disarm"
ACTION_RUN_SCRIPT_SCENE = "run_script_scene"

VALID_ACTIONS = {
    ACTION_PLAY_MUSIC,
    ACTION_PAUSE_SPEAKERS,
    ACTION_START_TIMER,
    ACTION_SEND_NOTIFICATION,
    ACTION_ADD_GROCERY,
    ACTION_ALARMO_ARM_AWAY,
    ACTION_ALARMO_ARM_HOME,
    ACTION_ALARMO_ARM_NIGHT,
    ACTION_ALARMO_DISARM,
    ACTION_RUN_SCRIPT_SCENE,
}

REMOVE_KEEP_RUNNING = "keep_running"
REMOVE_PAUSE_MUSIC = "pause_music"
REMOVE_CANCEL_TIMER = "cancel_timer"

VALID_REMOVE_MODES = {
    REMOVE_KEEP_RUNNING,
    REMOVE_PAUSE_MUSIC,
    REMOVE_CANCEL_TIMER,
}

# Pre-seeded with your 2 existing tags migrated cleanly into multi-action format
INITIAL_MIGRATED_TAGS = [
    {
        "id": "migrated-1",
        "tag_id": "6E-E2-3E-00",
        "name": "Boodschappen - Melk",
        "on_remove": REMOVE_KEEP_RUNNING,
        "reader_filter": "",
        "actions": [
            {
                "action_type": ACTION_ADD_GROCERY,
                "target": "todo.boodschappen",
                "value": "Melk",
                "volume": 0,
            }
        ],
    },
    {
        "id": "migrated-2",
        "tag_id": "9A-7C-40-05",
        "name": "Music",
        "on_remove": REMOVE_PAUSE_MUSIC,
        "reader_filter": "",
        "actions": [
            {
                "action_type": ACTION_PLAY_MUSIC,
                "target": TARGET_READER_DEFAULT,
                "value": "https://open.spotify.com/playlist/37i9dQZF1DX3WdioUzkg8I?si=9e6338001a8d47be",
                "volume": 5,
            }
        ],
    },
]
