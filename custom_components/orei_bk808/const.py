"""Constants for Orei BK808 HDMI Matrix."""

DOMAIN = "orei_bk808"
CONF_HOST = "host"
CONF_INPUT_NAMES = "input_names"
CONF_OUTPUT_NAMES = "output_names"

DEFAULT_TIMEOUT = 10

# How long (seconds) to wait after a routing command before confirming
# against the device. The matrix needs a moment to register a switch before
# it reflects the change in `allsource`.
ROUTE_SETTLE_DELAY = 0.6

DEFAULT_INPUT_NAMES = [
    "Input 1",
    "Input 2",
    "Input 3",
    "Input 4",
    "Input 5",
    "Input 6",
    "Input 7",
    "Input 8",
]

DEFAULT_OUTPUT_NAMES = [
    "Output 1",
    "Output 2",
    "Output 3",
    "Output 4",
    "Output 5",
    "Output 6",
    "Output 7",
    "Output 8",
]

NUM_PORTS = 8

# --- Command names (comhead values) ---
CM_QUERY_VIDEO = "get video status"
CM_QUERY_CEC = "get cec status"
CM_ROUTE = "video switch"
CM_POWER = "set poweronoff"
CM_MUTE = "set output audio mute"
CM_CEC_INDEX = "set cec index"
CM_CEC_CMD = "cec command"
CM_PRESET_SET = "preset set"
CM_PRESET_SAVE = "preset save"
CM_PRESET_CLEAR = "preset clear"
CM_PRESET_NAME = "preset name"

# --- CEC command indices (device-specific) ---
#
# These are the raw index values that `cec command` accepts.
# Extracted from the matrix's own web UI (CEC.vue). The index space
# differs for inputs (object=0) and outputs (object=1).
#
# INPUT side (object=0):
#   1=power-toggle, 2=power-off, 3=power/pause, 4=left, 5=enter,
#   6=right, 7=menu/up, 8=down, 9=loop, 10=prev-track, 11=play,
#   12=next-track, 13=rewind, 14=pause, 15=ffwd, 16=stop,
#   17=mute, 18=volume-down, 19=volume-up
#
# OUTPUT side (object=1):
#   0=power-on, 1=power-off, 2=mute, 3=volume-down, 4=volume-up,
#   5=enter, 7=left, 8=enter, 9=right, 10=down, 11=menu,
#   12=loop, 13=play, 15=prev, 16=next
#
# We expose a single friendly set; the coordinator maps each name
# to the correct index for the target object side.

CEC_INPUT_COMMANDS = {
    # index matches the matrix web UI (CEC.vue inputData) icon-for-icon:
    # 1=power(green) 2=power(red) 3=caret-top(up) 4=caret-left 5=enter
    # 6=caret-right 7=menu 8=caret-bottom(down) 9=loop 10=previous
    # 11=play 12=next 13=rewind 14=pause 15=ffwd 16=stop 17=mute
    # 18=vol-down 19=vol-up
    "power_on": (1, "mdi:power-cycle", "Power On"),
    "power_off": (2, "mdi:power-off", "Power Off"),
    "up": (3, "mdi:arrow-up", "Up"),
    "left": (4, "mdi:arrow-left", "Left"),
    "enter": (5, "mdi:check", "Enter"),
    "right": (6, "mdi:arrow-right", "Right"),
    "menu": (7, "mdi:menu", "Menu"),
    "down": (8, "mdi:arrow-down", "Down"),
    "loop": (9, "mdi:loop", "Loop"),
    "prev_track": (10, "mdi:skip-previous", "Previous"),
    "play": (11, "mdi:play", "Play"),
    "next_track": (12, "mdi:skip-next", "Next"),
    "rewind": (13, "mdi:rewind", "Rewind"),
    "pause": (14, "mdi:pause", "Pause"),
    "fast_forward": (15, "mdi:fast-forward", "Fast Forward"),
    "stop": (16, "mdi:stop", "Stop"),
    "mute": (17, "mdi:speaker-off", "Mute"),
    "volume_down": (18, "mdi:volume-minus", "Volume Down"),
    "volume_up": (19, "mdi:volume-plus", "Volume Up"),
}

CEC_OUTPUT_COMMANDS = {
    # index matches the matrix web UI (CEC.vue outputData) icon-for-icon:
    # 0=power-on(green) 1=power-off(red) 2=mute 3=vol-down 4=vol-up
    # 5=enter 7=caret-left 8=enter 9=caret-right 10=down 11=menu
    # 12=loop 13=play 15=prev 16=next
    "power_on": (0, "mdi:power-cycle", "Power On"),
    "power_off": (1, "mdi:power-off", "Power Off"),
    "mute": (2, "mdi:speaker-off", "CEC Mute"),
    "volume_down": (3, "mdi:volume-minus", "Volume Down"),
    "volume_up": (4, "mdi:volume-plus", "Volume Up"),
    "enter": (5, "mdi:check", "Enter"),
    "left": (7, "mdi:arrow-left", "Left"),
    "right": (9, "mdi:arrow-right", "Right"),
    "down": (10, "mdi:arrow-down", "Down"),
    "menu": (11, "mdi:menu", "Menu"),
    "loop": (12, "mdi:loop", "Loop"),
    "play": (13, "mdi:play", "Play"),
    "prev_track": (15, "mdi:skip-previous", "Previous"),
    "next_track": (16, "mdi:skip-next", "Next"),
}

# Friendly names for services
CEC_COMMAND_NAMES = sorted(set(CEC_INPUT_COMMANDS) | set(CEC_OUTPUT_COMMANDS))

PLATFORMS = ["button", "media_player", "remote", "select", "sensor", "switch"]
