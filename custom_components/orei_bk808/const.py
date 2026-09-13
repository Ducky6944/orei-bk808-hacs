"""Constants for Orei BK808 integration."""

DOMAIN = "orei_bk808"
CONF_HOST = "host"
CONF_INPUT_NAMES = "input_names"
CONF_OUTPUT_NAMES = "output_names"
DEFAULT_TIMEOUT = 10

DEFAULT_INPUT_NAMES = [
    "Input 1", "Input 2", "Input 3", "Input 4",
    "Input 5", "Input 6", "Input 7", "Input 8",
]

DEFAULT_OUTPUT_NAMES = [
    "Output 1", "Output 2", "Output 3", "Output 4",
    "Output 5", "Output 6", "Output 7", "Output 8",
]

SERVICE_ROUTE = "route"
SERVICE_SAVE_PRESET = "save_preset"
SERVICE_RECALL_PRESET = "recall_preset"
SERVICE_GET_STATUS = "get_status"
SERVICE_CEC_COMMAND = "cec_command"

ATTR_INPUT = "input"
ATTR_OUTPUT = "output"
ATTR_PRESET = "preset"
ATTR_INDEX = "index"
ATTR_OBJECT = "object"

CEC_OPCODES = {
    "standby": 36,
    "play": 44,
    "pause": 11,
    "stop": 17,
    "fast_forward": 16,
    "fast_reverse": 15,
    "next_track": 12,
    "prev_track": 13,
    "record_on": 27,
    "select": 8,
    "back": 9,
    "up": 4,
    "down": 5,
    "left": 6,
    "right": 7,
    "menu_request": 106,
    "contents_menu": 108,
    "power_on": 124,
    "image_view_on": 4,
    "volume_up": 41,
    "volume_down": 42,
    "volume_mute": 43,
    "mute_audio": 19,
    "unmute_audio": 18,
}

INPUT_CEC_GROUPS = {
    "basic_navigation": [
        ("select", "mdi:check"),
        ("back", "mdi:arrow-back"),
        ("up", "mdi:arrow-up"),
        ("down", "mdi:arrow-down"),
        ("left", "mdi:arrow-left"),
        ("right", "mdi:arrow-right"),
    ],
    "transport": [
        ("play", "mdi:play"),
        ("pause", "mdi:pause"),
        ("stop", "mdi:stop"),
        ("fast_forward", "mdi:fast-forward"),
        ("fast_reverse", "mdi:rewind"),
        ("next_track", "mdi:skip-next"),
        ("prev_track", "mdi:skip-previous"),
    ],
    "media": [
        ("record_on", "mdi:record-rec"),
        ("contents_menu", "mdi:netflix"),
        ("menu_request", "mdi:menu"),
    ],
    "power": [
        ("standby", "mdi:power-off"),
        ("image_view_on", "mdi:television"),
    ],
}

OUTPUT_CEC_GROUPS = {
    "power": [
        ("power_on", "mdi:power-on"),
        ("standby", "mdi:power-off"),
        ("image_view_on", "mdi:eye"),
    ],
    "volume": [
        ("volume_up", "mdi:volume-plus"),
        ("volume_down", "mdi:volume-minus"),
        ("volume_mute", "mdi:speaker-off"),
    ],
}

QUICK_ACTIONS = {
    "game_mode": [
        ("power_on", "All outputs"),
    ],
    "movie_night": [
        ("power_on", "All outputs"),
    ],
    "all_off": [
        ("standby", "All outputs"),
    ],
}

PLATFORMS = ["switch", "select", "button", "sensor"]
