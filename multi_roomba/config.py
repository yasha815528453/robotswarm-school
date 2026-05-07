ROWS = 5
COLS = 7
CELL_SIZE = 80
MARGIN = 2

# Cell colors
COLOR_DIRTY   = (210, 170, 100)
COLOR_CLEAN   = (245, 245, 245)
COLOR_ROBOT   = ( 50, 100, 220)
COLOR_TARGET  = (255, 200,   0)
COLOR_BG      = ( 40,  40,  40)
COLOR_STATUS_BG = (25, 25, 25)
COLOR_TEXT    = (220, 220, 220)

# Zone overlay colors (RGBA)
ZONE_COLORS = [
    (255, 180, 180, 55),
    (180, 180, 255, 55),
    (180, 255, 180, 55),
    (255, 255, 160, 55),
    (220, 180, 255, 55),
]

# Network
UDP_PORT       = 5007
BROADCAST_ADDR = "255.255.255.255"

# Timing (seconds)
TICK_INTERVAL      = 1.0    # how often a robot moves/cleans (wall-clock-synced)
BROADCAST_INTERVAL = 0.25   # how often each robot broadcasts STATE (~4 Hz, smooth + dropout-tolerant)
PEER_TIMEOUT       = 4.0    # drop a peer after this much silence
RESET_DELAY        = 3.0    # idle wait before re-dirtying a fully-clean grid

# Window
STATUS_BAR_HEIGHT = 65
WINDOW_WIDTH  = COLS * (CELL_SIZE + MARGIN) + MARGIN
WINDOW_HEIGHT = ROWS * (CELL_SIZE + MARGIN) + MARGIN + STATUS_BAR_HEIGHT
