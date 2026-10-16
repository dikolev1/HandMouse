"""
Hand Mouse - control the Windows mouse with your hands through the webcam.

  python hand_mouse.py --preview   window with the camera picture and live numbers (for testing/tuning)
  pythonw hand_mouse.py            runs in the background with no window

Gestures with the main hand = your RIGHT hand (to use the left hand instead, show only the left hand and
make a fist twice quickly - remembered until the right hand does the same):
  cursor          follows the index fingertip of the main hand (across all monitors)
  left click      thumb touches middle fingertip
  right click     thumb touches ring fingertip
  middle click    thumb touches middle AND ring fingertips
  mouse button 4  thumb tip to INDEX fingertip ("OK" sign), other fingers up (usually Back)
  mouse button 5  palm to the camera, fingers up, thumb folded across the palm onto the base of the ring /
                  little finger (usually Forward)
  (a click is held while the fingers touch, so touch-and-move drags)
  volume          thumbs-up (fingers folded, thumb out): thumb straight up = 100%, turn the hand
                  until the thumb points down to lower it to 0%
  scroll          make a fist and move it up / down (or left / right) from where you closed it;
                  further = faster. Open the hand to stop.
  gestures off/on hold BOTH hands as fists for about a second: all gestures stop except two fists, which
                  turn them back on. A full stop (camera off) is in the tray icon / Ctrl+Alt+H.

Keyboard shortcuts with the other hand (your LEFT hand); pinches act when the thumb lets go:
  Alt+Tab         thumb on index fingertip. Hold it: the window switcher stays open, move the hand left /
                  right to pick a window (stops at the first / last one), let go to switch to it
  Ctrl+C / Ctrl+V thumb on middle / ring fingertip
  Ctrl+Z          thumb across the palm on the base of the little finger; twice quickly = Ctrl+Y
  Print Screen    thumb on middle AND ring fingertips
  voice typing    thumb on index AND middle fingertips (Win+H); twice quickly = on-screen keyboard on / off
  Esc             make a fist (the only fist in view)
  play / pause    thumbs-up, then tuck the thumb into the fist
  next / previous thumbs-up moved right / left (one track per step)

Tray icon (next to the clock): left-click stops / resumes tracking; right-click for the menu
(Camera & log window, Gestures on, Stop / Resume tracking, Gestures help, Start with Windows, Re-learn my hand size,
Close). The camera & log window shows what the app sees and a list of the gestures it recognised.
Double-clicking the desktop icon while the app runs opens that window.

Hotkeys:
  Ctrl+Alt+H  pause / resume (camera turns off while paused)
  Ctrl+Alt+C  re-learn your normal hand size (hold an open hand up for a few seconds)
  Ctrl+Alt+Q  quit

The app restarts by itself when this file is saved, so setting changes apply right away.
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass

# Media Foundation (the camera driver that gives full speed on many webcams) opens much faster without its
# hardware conversion step; must be set before OpenCV is loaded.
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")
from functools import cached_property

# =============================== SETTINGS ===============================

CAMERA_INDEX = 0            # 0 = built-in webcam; try 1, 2 for external cameras
CAMERA_WIDTH = 1280         # largest camera resolution to use; higher keeps far-away fingers readable
CAMERA_HEIGHT = 720
CAMERA_FPS = 30
CAMERA_MODES = [(1280, 720), (960, 540), (640, 480)]  # tried in this order on first start (each driver)...
CAMERA_MIN_FPS = 20         # ...and the first one that really delivers this many frames per second is kept
                            # (the choice is remembered; many webcams drop to 10 fps at 1280x720)

# Far-away hands: when a hand is small in the picture, the app re-reads it from a zoomed-in crop
# (tests: fist recognised in 97-100% of frames at 3.6x the normal distance, versus 3% without).
DETECT_WIDTH = 640          # hands are first spotted on a smoothly shrunk copy of this width (finds small
                            # hands better and is faster); zoomed re-reads use the full camera picture
ZOOM_ENABLED = True
ZOOM_BELOW = 0.13           # zoom when the hand is narrower than this fraction of the picture width
ZOOM_CROP = 3.0             # crop size = hand size x this
ZOOM_INPUT = 256            # the crop is scaled to this many pixels for the re-read
RESCUE_TIME = 0.6           # a hand lost for less than this (s) is searched for in a zoomed crop where it was
SCAN_EVERY = 4              # with no hands in view, check the middle of the picture zoomed every N frames

# Distance: gestures scale with how big your hand looks, so they need the same real movement whether you
# sit close or further back. Your normal distance is learned in the first seconds of use (Ctrl+Alt+C or
# the tray menu re-learns it).
SCALE_WITH_DISTANCE = True
SCALE_LIMITS = (0.35, 1.6)  # how far the scaling may go (hand much smaller / bigger than normal)

# Which screens the cursor can reach: "all" = every monitor, "primary" = main screen only.
SCREENS = "all"

# The cursor box: the part of the camera picture that maps to the whole screen area (fractions of the
# picture), drawn grey in the camera window. Smaller box = less hand movement needed, but a little less precise.
# It starts like this and then moves and resizes by itself (BOX_* below).
CURSOR_BOX_WIDTH = 0.42
CURSOR_BOX_HEIGHT = 0.34
CURSOR_BOX_CENTER_X = 0.50
CURSOR_BOX_CENTER_Y = 0.42

# Moving box, like a game camera with a dead zone: it stays still while your pointing finger is inside it;
# when the finger stays outside it for BOX_FOLLOW_DELAY it glides after the finger until it is back inside.
# Its size slowly fits how far you really move: your usual range of movement becomes the box, so the screen
# edges are within easy reach. The cursor never jumps when the box moves or changes size.
BOX_FOLLOW = True
BOX_FOLLOW_DELAY = 0.5      # s outside the box before it starts following (quick pushes to the edge don't count)
BOX_FOLLOW_SPEED = 1.5      # how quickly it catches up (fraction of the gap per second)
BOX_FOLLOW_INSIDE = 0.08    # it stops once the finger is this far inside (fraction of the box)
BOX_FIT_SIZE = True
BOX_SIZE_LIMITS = (0.75, 1.3)   # x the size above
BOX_FIT_TIME = 20.0         # s: how slowly the size changes
BOX_FIT_SAMPLES = (400, 1500)   # finger positions remembered while pointing and moving (a few minutes of use;
                                # fitting starts once the first number is reached)

# Cursor steadiness.
#  SMOOTH_MIN_CUTOFF / SMOOTH_BETA: One Euro filter. Lower cutoff = steadier but more lag; higher beta = less lag on fast moves.
#  CURSOR_STEADY_RADIUS: finger wobble smaller than this (screen px) is ignored completely.
#  PRECISION_GAIN: slow movements move the cursor only this fraction as far (0.3 = 30%), for precise aiming.
#  PRECISION_SPEED / FULL_SPEED: below the first speed (screen px/s) precision applies fully, above the second
#     the cursor moves at full speed and re-aligns with where your finger points (REALIGN_RATE = how quickly).
SMOOTH_MIN_CUTOFF = 0.6
SMOOTH_BETA = 0.003
CURSOR_STEADY_RADIUS = 15
PRECISION_GAIN = 0.3
PRECISION_SPEED = 200
FULL_SPEED = 1000
REALIGN_RATE = 6.0
CURSOR_DEADZONE_PX = 1      # don't send cursor moves smaller than this
TIP_SPIKE = 0.035           # a one-frame fingertip jump bigger than this (fraction of the picture) is treated
                            # as a tracking glitch and ignored unless the next frame confirms it
DRAG_START_PX = 120         # while a button is held the cursor stays put until the finger clearly moves this
                            # far (screen px) - then it drags. Keeps clicks exactly where you aimed
CURSOR_REANCHOR_AFTER = 3.0 # hand gone longer than this (s): cursor restarts where the finger points;
                            # shorter gaps continue from where the cursor is (no jump)

# Touch detection: fingertip distance divided by palm length (wrist -> middle knuckle), in 3D.
# Watch the "t-mid" / "t-ring" numbers in --preview to tune these.
TOUCH_ON = 0.34             # closer than this = fingers touching
TOUCH_OFF = 0.46            # farther than this = fingers released (must be > TOUCH_ON)
BOTH_RATIO = 1.4            # 3-finger (middle click) when the two distances differ by less than this
                            # factor. Right click read as middle? lower it. Middle read as right/left? raise it.

CLICK_DELAY = 0.08          # a touch clicks when seen in 2 frames in a row, or after this long (s)
RELEASE_DELAY = 0.10        # fingers must stay apart this long before the button is released (s)
UPGRADE_WINDOW = 0.35       # a left/right press that turns into 3-finger within this time becomes a middle click
FREEZE_AFTER_RELEASE = 0.15 # ...and right after a release
DOUBLE_CLICK_WINDOW = 0.9   # a second pinch this soon (s) after a click's release makes a double-click; the
                            # cursor stays exactly where it clicked meanwhile (unless the finger clearly moves)
DOUBLE_TOUCH_SLACK = 0.06   # the second pinch may be this much looser than a normal touch
RELEASE_CLEAR = 0.10        # fingers this much wider than TOUCH_OFF release a short click at once (no waiting)
QUICK_RELEASE_HOLD = 0.6    # ...only for presses shorter than this (s) and not while dragging, so a misread
                            # frame can't break a drag

# Fist scroll: close either hand into a fist, then move it up or down. The spot where the fist closed is
# "zero"; the further you move from it, the faster the page scrolls. Open the hand to stop.
FIST_CURL = 1.35            # a finger counts as folded when fingertip->wrist < this x knuckle->wrist
FIST_KEEP = 1.55            # once a fist is recognised it stays a fist until a finger opens past this
FIST_ON_TIME = 0.15         # the fist must be held this long before scrolling starts (s)

# Volume (either hand): a "thumbs up" - fingers folded, thumb sticking out. Thumb straight up = 100%, turning
# the hand until the thumb points down lowers it step by step to 0%. Hold the pose a moment to start.
VOLUME_CONTROL = True
VOLUME_HOLD = 0.45          # s the thumbs-up must be held before the volume follows it
VOLUME_THUMB_OUT = 0.3      # thumb tip at least this far outside the folded fingers (x their size) = thumb out
VOLUME_THUMB_KEEP = 0.18    # ...and it stays "out" until closer than this
VOLUME_ENDS = 15            # degrees near straight up / straight down that already count as 100% / 0%
VOLUME_SPEED = 1.5          # how fast the volume may change (1.5 = 150% per second), so it never jumps

# Switch main hand: only the other hand in view, fist twice quickly (fold - open - fold - open).
GRAB_MAX = 0.35             # each fist must be shorter than this (s)
GRAB_GAP = 0.6              # the second fold must start within this time after opening (s)
GRAB_OPEN = 1.5             # fingers count as open again when straighter than this
FIST_OFF_TIME = 0.20        # the hand must be open this long before scrolling stops (s)
SCROLL_DEADZONE = 0.03      # moving the fist less than this (fraction of the camera picture) doesn't scroll
SCROLL_BASE_SPEED = 2.0     # wheel notches per second just outside the dead zone
SCROLL_GAIN = 80.0          # extra notches per second per full picture height of fist movement
SCROLL_MAX_SPEED = 25.0     # notches per second, upper limit
SCROLL_INVERT = False       # default: fist moves down = page scrolls down. True flips it.
HSCROLL = True              # moving the fist left / right scrolls sideways (only the direction moved further scrolls)
HSCROLL_INVERT = False      # default: fist moves right = page scrolls right. True flips it.
HSCROLL_DEADZONE = 0.04     # like SCROLL_DEADZONE, for sideways (the same real distance as up / down)
SCROLL_SMOOTH = True        # True = small smooth steps; False = whole wheel notches only
INDEX_STRAIGHT = 1.45       # clicks only count while the index finger is straighter than this (stops a
                            # closing fist from clicking); same measure as FIST_CURL

# Gestures off / on by holding both hands as fists. While off, the camera keeps watching but nothing is done
# except waiting for two fists again. (A full stop with the camera off is in the tray icon.)
STOP_WITH_TWO_FISTS = True
STOP_HOLD = 1.0             # both fists must be held this long (s); scrolling pauses meanwhile
STOP_REARM = 0.4            # after switching, open a hand (or take the hands out of view) this long before two
                            # fists can switch again - holding the fists never switches back and forth

# Mouse buttons 4 / 5 (either hand). Held while the thumb stays there.
#   button 4 (usually Back):    thumb tip to INDEX fingertip ("OK" sign), other fingers up
#   button 5 (usually Forward): palm towards the camera, thumb folded across the palm onto the base of the
#                               ring / little finger. Measured in the camera picture (the hand model's depth
#                               guess is too rough to tell whether the thumb touches the palm).
SIDE_BUTTONS = True
INDEX_PINCH_MARGIN = 0.6    # button 4: thumb must be this much closer to the index tip than to the middle /
                            # ring tips (they sit close together); touch limits are TOUCH_ON / TOUCH_OFF
SIDE_TOUCH_ON = 0.12        # button 5: thumb tip this close to the spot (x palm length, in the picture)
SIDE_TOUCH_OFF = 0.19       # ...released when farther than this
SIDE_MARGIN = 0.6           # button 5 spot must be clearly closer than any fingertip (so clicks never count)
SIDE_STRAIGHT = 1.45        # the fingers not used must be straighter than this (stops fists and clicks)
SIDE_FACING = 0.6           # button 5: how much the palm must face the camera (1 = straight at it, 0 = edge-on)

# The second hand (the left one when both are in view) gives keyboard shortcuts (SECOND_HAND_KEYS below) and
# takes part in the two-fist gestures on / off.
# True = instead it scrolls, swipes windows, presses buttons 4/5 and changes the volume like the main hand.
SECOND_HAND_GESTURES = False

# Keyboard shortcuts from the second hand (usually your LEFT hand). Pinches act when the thumb lets go, so a
# touch that slides onto two fingertips counts as the pair.
#   "index"         thumb on index fingertip. Alt+Tab: held ALT_TAB_HOLD the window switcher stays open; move
#                   the hand left / right to pick a window, let go to switch to it
#   "middle"        thumb on middle fingertip           "ring"          thumb on ring fingertip
#   "index+middle"  thumb on both fingertips             "middle+ring"   thumb on both fingertips
#   "little base"   palm to the camera, thumb across the palm on the base of the little finger (like button 5)
#   "fist"          fist with the thumb tucked in, held KEY_FIST_HOLD (no need to open it), once per fist. Only
#                   when it is the only fist (not two fists, not while the main hand scrolls). With this hand
#                   alone in view it waits GRAB_MAX + 0.15 s: two quick fists switch the main hand instead
#   "thumbs-up, thumb in"   thumbs-up (at least KEY_THUMB_MIN), then the thumb tucked into the fist
#   "thumbs-up right" / "thumbs-up left"   thumbs-up moved sideways, one per TRACK_STEP (tucking the thumb
#                   afterwards does nothing)
#   "... twice"     the same gesture twice quickly. The single one then waits KEY_DOUBLE_WINDOW to be sure.
# Keys: ctrl, alt, shift, win, a-z, 0-9, f1-f24, enter, esc, tab, space, backspace, delete, insert, home, end,
# pageup, pagedown, up, down, left, right, printscreen, playpause, nexttrack, prevtrack, mute, joined with +.
# "keyboard" opens / closes the Windows on-screen keyboard. "" = nothing.
SECOND_HAND_KEYS = True
SECOND_KEYS = {
    "index": "alt+tab",
    "middle": "ctrl+c",
    "ring": "ctrl+v",
    "little base": "ctrl+z",
    "little base twice": "ctrl+y",
    "middle+ring": "printscreen",
    "index+middle": "win+h",            # Windows voice typing on / off
    "index+middle twice": "keyboard",
    "fist": "esc",
    "thumbs-up, thumb in": "playpause",
    "thumbs-up right": "nexttrack",
    "thumbs-up left": "prevtrack",
}
KEY_DOUBLE_WINDOW = 0.45    # a second tap this soon (s) after letting go makes it "twice"
KEY_RELEASE_DELAY = 0.18    # the thumb must be away this long (s) before a pinch counts as let go, so a few
                            # misread frames don't split one pinch into two
ALT_TAB_RELEASE = 0.30      # ...while the window switcher is open (moving the hand blurs it)
ALT_TAB_HOLD = 0.5          # thumb held on the index fingertip this long (s) keeps the window switcher open
ALT_TAB_STEP = 0.05         # move the hand this far (fraction of the picture width) for each next window
ALT_TAB_STOP_AT_ENDS = True # the selection stops at the first / last window instead of wrapping around
SECOND_INDEX_ON = 0.40      # the second hand's index pinch ("OK" sign) starts below this in 3D (the clicks use
                            # TOUCH_ON 0.34): a held left "OK" reads 0.26-0.38, an open hand 0.45-0.8 (log 2026-10-14)
INDEX_START_2D = 0.30       # ...or when the thumb is this close to the index tip in the picture while 3D is under
INDEX_START_3D_MAX = 0.60   # this (a thumb behind the index, hand edge-on, reads far in 3D). Held: 2D < 0.3 in 61
                            # of 66 samples; open: 2D > 0.6
INDEX_HOLD_2D = 0.30        # a held index pinch also stays held while the thumb tip is this close to the index
                            # tip in the picture (x palm length in the picture). The hand model's depth guess
                            # reads 0.5-0.65 in 3D (= apart) while the "OK" sign is clearly held and the hand
                            # moves to pick a window (debug pictures 2026-10-14)
KEY_FIST_HOLD = 0.2         # the fist acts once it has been closed this long (s), without opening it
KEY_THUMB_MIN = 0.15        # the thumbs-up must be shown this long (s) before tucking the thumb counts (so a
                            # thumb flicking out while a fist opens or closes does nothing)
TRACK_STEP = 0.08           # thumbs-up moved this far left / right (fraction of the picture width) = one track

# Window swipe: with both hands in view, move the SECOND hand (the left one) quickly left or right.
# The main (right) hand never swipes.
SWIPE_ENABLED = True
SWIPE_ACTION = "apps"       # "apps"     = switch window (Alt+Tab / Alt+Shift+Tab)
                            # "desktops" = switch virtual desktop (Ctrl+Win+Left/Right)
                            # "monitor"  = move the active window to the other screen (Win+Shift+Left/Right)
SWIPE_DISTANCE = 0.15       # the hand must travel this far (fraction of the camera picture width)...
SWIPE_TIME = 0.30           # ...within this time (s)
SWIPE_SETTLE = 0.30         # the second hand must be in view this long before it can swipe (s)
SWIPE_REPEAT = 0.6          # wait at least this long before another swipe in the same direction (s)
SWIPE_RETURN_IGNORE = 1.2   # ignore the opposite direction this long (the hand coming back) (s)
SWIPE_INVERT = False        # swap left and right

LOST_GRACE = 0.40           # hand may disappear this long without dropping a held click (s)
HAND_MEMORY = 1.5           # a hand that reappears within this time keeps its identity (s)
MATCH_DISTANCE = 0.25       # a hand further than this (fraction of the picture) from where a known hand was
                            # is treated as a different hand
DUPLICATE_OVERLAP = 0.35    # two detections overlapping more than this are the same hand seen twice
NEW_HAND_CONFIRM = 0.3      # while one hand is in use, a newly appearing hand must stay this long (s) before
                            # it counts - brief false detections (e.g. on the forearm) are ignored
SWAP_HANDEDNESS = False     # set True if the app mixes up your left and right hand
# Which hand is which: by position when both hands are in view, otherwise by the hand model's left/right guess,
# averaged over the time the hand is followed (tests: the guess is right in 96-100% of frames).
RIGHT_HAND_LABEL = "Left"   # what the hand model calls your RIGHT hand in the mirrored camera picture
# The main hand (cursor, clicks, all gestures) is your right hand. To use your LEFT hand instead: show only
# the left hand and make a fist twice quickly; the right hand takes it back the same way. Remembered.

# Coloured light (a blue / RGB lamp, a screen glow): the hand model only knows natural skin colours, so a
# blue-lit hand is often not found at all. When no hand is found for a moment, the app also tries the picture
# with red and blue swapped (a blue-lit hand then looks like a warm-lit one) and a white-balanced copy, and keeps
# using whichever finds your hand (switching back the same way). The camera window still shows the real picture.
COLOR_FALLBACK = True
# Second hand finder (HaGRIDv2 YOLOv10n, trained on about a million webcam photos of people at home): when the
# hand model finds no hand, this finder looks for one and the hand model then reads the fingers from a zoomed
# crop around it. Used only if hand_finder.onnx is next to this file.
HAND_FINDER = True
HAND_FINDER_FILE = "hand_finder.onnx"
HAND_FINDER_CONFIDENCE = 0.35
HAND_FINDER_EVERY = 2         # while no hand is found, run it every N frames (it costs a little time)
BALANCE_GRID = (32, 18)     # areas the light colour is measured in for the white-balanced copy
LOW_LIGHT_FPS = 24            # the camera delivering fewer frames than this means dim light (tip shown once)
DETECTION_CONFIDENCE = 0.45   # a hand the tracker finds in the whole picture
PRESENCE_CONFIDENCE = 0.35    # keeping a hand that is already tracked (low: holds on in dim / blurry frames)
TRACKING_CONFIDENCE = 0.35
DISCOVER_CONFIDENCE = 0.7     # a hand found only by a zoomed-in search (not by the tracker): stricter, because a
                              # zoomed-in face or headphones can look like a hand (test on your dark camera
                              # picture, colours swapped: 18 of 189 zoomed spots at 0.45, none at 0.7)

HOTKEY_PAUSE = "<ctrl>+<alt>+h"
HOTKEY_CALIBRATE = "<ctrl>+<alt>+c"
HOTKEY_QUIT = "<ctrl>+<alt>+q"
SOUNDS = True               # short beeps on start / pause / resume
AUTO_RESTART_ON_EDIT = True # restart automatically when this file changes
TRAY_ICON = True            # icon next to the clock: left-click = stop / resume tracking, right-click = menu
DIAGNOSTICS = True          # write finger measurements to hand_mouse.log once a second (for tuning)
LOG_MAX_MB = 2              # the log file is rotated at this size (keeps 2 old copies)

# Debug pictures (also on / off in the tray menu, remembered): every gesture the app recognises - clicks, buttons,
# scroll, volume, second-hand shortcuts, two fists, also pinches that were cancelled or too short - saves one
# picture to the "debug" folder: the last DEBUG_SPAN seconds of camera frames as a strip of DEBUG_FRAMES
# pictures with the hands drawn in, the log line(s) as the title and each hand's live numbers. The file name
# starts with the date and time, so it matches the line in hand_mouse.log.
DEBUG_PICTURES = False      # off by default
DEBUG_FRAMES = 8            # pictures per strip (the last one is the moment the gesture was recognised)
DEBUG_SPAN = 1.2            # seconds of camera frames before the gesture
DEBUG_KEEP = 500            # at most this many debug pictures: each new one deletes the oldest beyond it

# ========================================================================

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.abspath(__file__)
MODEL_PATH = os.path.join(HERE, "hand_landmarker.task")
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/latest/hand_landmarker.task")
LOG_PATH = os.path.join(HERE, "hand_mouse.log")
WINDOW = "Hand Mouse - camera and log (p = stop/resume, s = save snapshot, Esc = close window)"

log = logging.getLogger("hand_mouse")


class EventFeed(logging.Handler):
    """Keeps the latest log messages in memory for the log panel of the camera window (the once-a-second
    measurement lines are left out)."""
    SKIP = ("diag ", "big cursor move", "camera test:")

    def __init__(self, size: int = 200):
        super().__init__(logging.INFO)
        from collections import deque
        self.items = deque(maxlen=size)
        self.lock2 = threading.Lock()

    def emit(self, record):
        try:
            msg = record.getMessage()
        except Exception:
            return
        if msg.startswith(self.SKIP):
            return
        with self.lock2:
            self.items.append((record.created, record.levelno, msg))

    def latest(self, n: int) -> list:
        with self.lock2:
            return list(self.items)[-n:]


EVENTS = EventFeed()

# MediaPipe hand landmark indices
WRIST, THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP = 0, 4, 8, 12, 16
INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP = 5, 9, 13, 17
HAND_CONNECTIONS = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
                    (5, 9), (9, 10), (10, 11), (11, 12), (9, 13), (13, 14), (14, 15),
                    (15, 16), (13, 17), (17, 18), (18, 19), (19, 20), (0, 17)]


def cursor_box(k: float = 1.0) -> tuple[float, float, float, float]:
    """(left, top, right, bottom) of the cursor box in picture fractions. k < 1 (hand further away than
    normal) makes the box smaller, so the same real hand movement still covers the screen."""
    w = min(CURSOR_BOX_WIDTH * k, 0.95)
    h = min(CURSOR_BOX_HEIGHT * k, 0.95)
    left = min(max(CURSOR_BOX_CENTER_X - w / 2, 0.0), 1.0 - w)
    top = min(max(CURSOR_BOX_CENTER_Y - h / 2, 0.0), 1.0 - h)
    return left, top, left + w, top + h


# ------------------------------------------------------------------ geometry

@dataclass(eq=False)
class Hand:
    label: str      # "Left" / "Right" as guessed by the tracker (unreliable; only used for display)
    img: list       # 21 (x, y) in 0..1, mirrored picture
    world: list     # 21 (x, y, z) in metres, centred on the hand
    key: str = ""   # stable id of this physical hand while it stays in view
    aspect: float = 0.5625      # picture height / width (to measure sizes in one unit)
    zoomed: bool = False        # landmarks were re-read from a zoomed crop (small / far hand)
    rescued: bool = False       # found again by the zoomed search after the tracker lost it
    unsure: bool = False        # small hand whose zoomed re-read failed: finger shapes are not trustworthy
    role: str = ""              # "main" (moves the cursor, clicks) or "second"
    found_by_finder: bool = False   # located by the second hand finder (already read zoomed)
    hand_side: str | None = None    # "right" / "left" (your hand), None while not sure yet

    @cached_property
    def ext(self) -> list:
        return finger_extension(self)

    @cached_property
    def pinch(self) -> tuple:
        return pinch_ratios(self)

    @cached_property
    def side(self) -> dict:
        return side_ratios(self)

    @cached_property
    def flat(self) -> list:
        """Landmarks in the picture with both axes in the same unit (fraction of the picture width)."""
        return [(x, y * self.aspect) for x, y in self.img]

    @cached_property
    def tip_min(self) -> float:
        """Thumb tip to the nearest other fingertip, in the picture (x palm length in the picture)."""
        f = self.flat
        p = max(math.dist(f[WRIST], f[MIDDLE_MCP]), 1e-4)
        return min(math.dist(f[THUMB_TIP], f[i]) for i in (INDEX_TIP, MIDDLE_TIP, RING_TIP, 20)) / p

    @cached_property
    def facing(self) -> float:
        """How much the palm faces the camera: palm width/length in the picture vs. in 3D (1 = facing it)."""
        f, w = self.flat, self.world
        ratio2 = math.dist(f[INDEX_MCP], f[PINKY_MCP]) / max(math.dist(f[WRIST], f[MIDDLE_MCP]), 1e-4)
        ratio3 = math.dist(w[INDEX_MCP], w[PINKY_MCP]) / max(math.dist(w[WRIST], w[MIDDLE_MCP]), 1e-4)
        return ratio2 / max(ratio3, 1e-4)

    @cached_property
    def center(self) -> tuple:
        return palm_center(self)

    @cached_property
    def size(self) -> float:
        """Hand outline (largest side) as a fraction of the picture width."""
        xs = [p[0] for p in self.img]
        ys = [p[1] for p in self.img]
        return max(max(xs) - min(xs), (max(ys) - min(ys)) * self.aspect)

    @cached_property
    def palm(self) -> float:
        """Palm size in the picture (fraction of width); used to tell how far away the hand is.
        Uses palm length and width so it holds up when the hand is turned."""
        def d(a, b):
            return math.hypot(self.img[a][0] - self.img[b][0], (self.img[a][1] - self.img[b][1]) * self.aspect)
        return max(d(WRIST, MIDDLE_MCP), 1.3 * d(INDEX_MCP, PINKY_MCP))


def palm_length(h: Hand) -> float:
    return max(math.dist(h.world[WRIST], h.world[MIDDLE_MCP]), 1e-4)


# Which fingers (0 index .. 3 little) must stay straight for each button.
SIDE_STRAIGHT_FINGERS = {"x1": (1, 2), "x2": (1, 2, 3)}
# Button 5 spot: the line from the ring knuckle to the little-finger knuckle, and how far beyond its ends
# (as a fraction of its length) still counts.
X2_ZONE = (RING_MCP, PINKY_MCP, -0.4, 1.5)


def _zone_distance(p, a, b, lo: float = -0.05, hi: float = 1.15) -> float:
    """Distance from p to the line a-b, but only if p is beside that part of the line (its projection falls
    between a and b, with the tolerance lo..hi); otherwise infinity."""
    n = len(p)
    ab = [b[i] - a[i] for i in range(n)]
    ap = [p[i] - a[i] for i in range(n)]
    L = sum(c * c for c in ab)
    if L <= 0:
        return math.inf
    t = sum(ap[i] * ab[i] for i in range(n)) / L
    if t < lo or t > hi:
        return math.inf
    t = min(max(t, 0.0), 1.0)
    return math.dist(p, [a[i] + ab[i] * t for i in range(n)])


def side_ratios(h: Hand) -> dict:
    """"x1" (button 4): thumb tip to index fingertip in 3D (x palm length), like the clicks.
    "x2" (button 5): thumb tip distance in the picture (x palm length in the picture) to the base of the ring /
    little finger; infinity when the thumb is not beside that spot."""
    f = h.flat
    p = max(math.dist(f[WRIST], f[MIDDLE_MCP]), 1e-4)
    a, b, lo, hi = X2_ZONE
    return {"x1": math.dist(h.world[THUMB_TIP], h.world[INDEX_TIP]) / palm_length(h),
            "x2": _zone_distance(f[THUMB_TIP], f[a], f[b], lo, hi) / p}


def thumb_on_palm_base(h: Hand, held: bool = False) -> bool:
    """Button 5 spot: palm to the camera, middle / ring / little finger straight, thumb across the palm on the
    base of the ring / little finger (and clearly not on a fingertip). held = already touching: looser limits."""
    if min(h.ext[i] for i in SIDE_STRAIGHT_FINGERS["x2"]) < SIDE_STRAIGHT * (0.93 if held else 1.0):
        return False
    if h.facing < SIDE_FACING * (0.85 if held else 1.0):
        return False                    # hand turned sideways: the thumb only looks like it is on the palm
    d = h.side["x2"]
    loose = 1 / 0.75 if held else 1.0
    return d < (SIDE_TOUCH_OFF if held else SIDE_TOUCH_ON) and d < SIDE_MARGIN * h.tip_min * loose


def pinch_ratios(h: Hand) -> tuple[float, float]:
    """(thumb-middle, thumb-ring) fingertip distances relative to palm length."""
    p = palm_length(h)
    t = h.world[THUMB_TIP]
    return math.dist(t, h.world[MIDDLE_TIP]) / p, math.dist(t, h.world[RING_TIP]) / p


# ------------------------------------------------------------------ smoothing

class OneEuro:
    def __init__(self, min_cutoff: float, beta: float, d_cutoff: float = 1.0):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.reset()

    def reset(self):
        self.x = None
        self.dx = 0.0
        self.t = None

    @staticmethod
    def _alpha(dt: float, cutoff: float) -> float:
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x: float, t: float) -> float:
        if self.x is None:
            self.x, self.t = x, t
            return x
        dt = max(t - self.t, 1e-3)
        dx = (x - self.x) / dt
        a_d = self._alpha(dt, self.d_cutoff)
        self.dx = a_d * dx + (1 - a_d) * self.dx
        a = self._alpha(dt, self.min_cutoff + self.beta * abs(self.dx))
        self.x = a * x + (1 - a) * self.x
        self.t = t
        return self.x


class CursorFilter:
    """Finger position (screen px) -> steady cursor position.
    1. One Euro smoothing, 2. a steady radius that ignores small wobble,
    3. precision gain: slow motion moves the cursor less (for aiming), fast motion moves it fully and
       pulls it back in line with where the finger points."""

    def __init__(self, bounds):
        self.x0, self.y0, self.x1, self.y1 = bounds
        self.fx = OneEuro(SMOOTH_MIN_CUTOFF, SMOOTH_BETA)
        self.fy = OneEuro(SMOOTH_MIN_CUTOFF, SMOOTH_BETA)
        self.reset()

    def reset(self, keep_position: bool = False):
        """Forget the finger history. With keep_position the cursor stays where it is and continues from
        there when the hand comes back, instead of jumping to where the finger points."""
        self.fx.reset()
        self.fy.reset()
        self.anchor = None
        if not keep_position:
            self.cur = None
            self.reason = "start"
        elif self.cur is not None:
            self.reason = "continue"
        self.prev = None
        self.t = None
        self.speed = 0.0

    def shift(self, dx: float, dy: float):
        """The finger-to-screen mapping moved by (dx, dy) px (the cursor box moved or changed size): shift the
        history with it, so the cursor itself does not move."""
        if self.fx.x is not None:
            self.fx.x += dx
        if self.fy.x is not None:
            self.fy.x += dy
        if self.anchor is not None:
            self.anchor[0] += dx
            self.anchor[1] += dy
        if self.prev is not None:
            self.prev = (self.prev[0] + dx, self.prev[1] + dy)

    def __call__(self, x: float, y: float, t: float, hold: bool = False,
                 edge: tuple = (False, False)) -> tuple:
        fx, fy = self.fx(x, t), self.fy(y, t)
        if self.anchor is None:
            self.anchor = [fx, fy]
        dx, dy = fx - self.anchor[0], fy - self.anchor[1]
        d = math.hypot(dx, dy)
        if d > CURSOR_STEADY_RADIUS:
            s = (d - CURSOR_STEADY_RADIUS) / d
            self.anchor[0] += dx * s
            self.anchor[1] += dy * s
        px, py = self.anchor
        if self.prev is None:
            if self.cur is None:
                self.cur = [px, py]
            self.prev, self.t = (px, py), t
            return tuple(self.cur)
        dt = max(t - self.t, 1e-3)
        mx, my = px - self.prev[0], py - self.prev[1]
        self.prev, self.t = (px, py), t
        if hold:            # clicking / gesturing: the finger moves, the cursor must not
            self.speed = 0.0
            return tuple(self.cur)
        self.speed = 0.5 * self.speed + 0.5 * math.hypot(mx, my) / dt
        k = min(max((self.speed - PRECISION_SPEED) / max(FULL_SPEED - PRECISION_SPEED, 1), 0.0), 1.0)
        g = PRECISION_GAIN + (1 - PRECISION_GAIN) * k
        self.reason = "edge of box" if (edge[0] or edge[1]) else ("fast move" if k > 0 else "slow move")
        self.cur[0] += g * mx
        self.cur[1] += g * my
        pull = min(1.0, REALIGN_RATE * k * dt)
        for i, (p, raw, at_edge) in enumerate(((px, fx, edge[0]), (py, fy, edge[1]))):
            # re-align during fast motion; when the finger is pushed past the edge of the box, go all the
            # way to the screen edge
            if at_edge:
                self.cur[i] += (raw - self.cur[i]) * min(1.0, REALIGN_RATE * dt)
            else:
                self.cur[i] += (p - self.cur[i]) * pull
        self.cur[0] = min(max(self.cur[0], self.x0), self.x1)
        self.cur[1] = min(max(self.cur[1], self.y0), self.y1)
        return tuple(self.cur)


class CursorBox:
    """The cursor box as a game-style camera: follows the pointing finger when it leaves the box (after a delay,
    gradually) and slowly fits its size to how far the finger usually moves. Sizes scale with distance (k)."""

    def __init__(self, saved: dict | None = None):
        self.reset()
        try:
            if saved:
                lo, hi = BOX_SIZE_LIMITS
                self.cx = min(max(float(saved["cx"]), 0.0), 1.0)
                self.cy = min(max(float(saved["cy"]), 0.0), 1.0)
                self.sx = min(max(float(saved["sx"]), lo), hi)
                self.sy = min(max(float(saved["sy"]), lo), hi)
        except Exception:
            self.reset()

    def reset(self):
        from collections import deque
        self.cx, self.cy = CURSOR_BOX_CENTER_X, CURSOR_BOX_CENTER_Y
        self.sx = self.sy = 1.0
        self.out_since = None
        self.following = False
        self.samples = deque(maxlen=BOX_FIT_SAMPLES[1])  # (x / k, y / k) of the pointing finger
        self.last_sample = None
        self.target = None              # (sx, sy) the size is easing towards
        self.reach = None               # (x0, y0, x1, y1) usual range of movement now, for the camera window
        self.next_fit = 0.0
        self.logged_size = (1.0, 1.0)
        self.last_follow_log = -1e9

    def state(self) -> dict:
        return {"cx": round(self.cx, 4), "cy": round(self.cy, 4), "sx": round(self.sx, 3), "sy": round(self.sy, 3)}

    def rect(self, k: float = 1.0) -> tuple[float, float, float, float]:
        """(left, top, right, bottom) in picture fractions."""
        w = min(CURSOR_BOX_WIDTH * k * self.sx, 0.95)
        h = min(CURSOR_BOX_HEIGHT * k * self.sy, 0.95)
        left = min(max(self.cx - w / 2, 0.0), 1.0 - w)
        top = min(max(self.cy - h / 2, 0.0), 1.0 - h)
        return left, top, left + w, top + h

    def update(self, finger: tuple, k: float, now: float, dt: float, pointing: bool):
        """finger = index fingertip (picture fractions); pointing = the hand is really pointing right now."""
        if not pointing:
            self.out_since = None
            return
        x, y = finger
        left, top, right, bottom = self.rect(k)
        w, h = right - left, bottom - top
        # 1. follow the finger when it has been outside for a moment (dead-zone camera)
        if BOX_FOLLOW:
            if left <= x <= right and top <= y <= bottom:
                self.out_since = None
            elif self.out_since is None:
                self.out_since = now
            elif not self.following and now - self.out_since >= BOX_FOLLOW_DELAY:
                self.following = True
                if now - self.last_follow_log > 20:
                    self.last_follow_log = now
                    log.info("cursor box follows your hand (it stayed outside the box)")
            if self.following:
                mx, my = BOX_FOLLOW_INSIDE * w, BOX_FOLLOW_INSIDE * h
                ex = x - (left + mx) if x < left + mx else (x - (right - mx) if x > right - mx else 0.0)
                ey = y - (top + my) if y < top + my else (y - (bottom - my) if y > bottom - my else 0.0)
                a = min(1.0, dt * BOX_FOLLOW_SPEED)
                self.cx = min(max(self.cx + ex * a, w / 2), 1.0 - w / 2)
                self.cy = min(max(self.cy + ey * a, h / 2), 1.0 - h / 2)
                if abs(ex) < 0.004 and abs(ey) < 0.004:
                    self.following = False
        # 2. learn how far the finger usually moves, and fit the size to it
        if not BOX_FIT_SIZE:
            return
        if self.last_sample is None or math.dist(self.last_sample, finger) > 0.004:
            self.samples.append((x / k, y / k))
            self.last_sample = finger
        if now >= self.next_fit and len(self.samples) >= BOX_FIT_SAMPLES[0]:
            self.next_fit = now + 0.5
            xs = sorted(p[0] for p in self.samples)
            ys = sorted(p[1] for p in self.samples)
            n = len(xs)
            lo_i, hi_i = int(n * 0.05), min(int(n * 0.95), n - 1)
            span_x, span_y = xs[hi_i] - xs[lo_i], ys[hi_i] - ys[lo_i]
            lo, hi = BOX_SIZE_LIMITS
            self.target = (min(max(span_x / CURSOR_BOX_WIDTH, lo), hi), min(max(span_y / CURSOR_BOX_HEIGHT, lo), hi))
            self.reach = (xs[lo_i] * k, ys[lo_i] * k, xs[hi_i] * k, ys[hi_i] * k)
        if self.target is not None:
            a = min(1.0, dt / BOX_FIT_TIME)
            self.sx += (self.target[0] - self.sx) * a
            self.sy += (self.target[1] - self.sy) * a
            if max(abs(self.sx - self.logged_size[0]), abs(self.sy - self.logged_size[1])) >= 0.08:
                self.logged_size = (self.sx, self.sy)
                log.info("cursor box fitted to how far you move: %.2f wide x %.2f high (1.00 = default)",
                         self.sx, self.sy)


# ------------------------------------------------------------------ gestures

FINGERS = ((8, 5), (12, 9), (16, 13), (20, 17))   # (fingertip, knuckle) for index, middle, ring, pinky


def finger_extension(h: Hand) -> list[float]:
    """For index, middle, ring, pinky: fingertip->wrist distance divided by knuckle->wrist distance.
    About 1.8-2.0 for a straight finger, about 1.0 for a finger folded into the palm."""
    w = h.world[WRIST]
    return [math.dist(h.world[tip], w) / max(math.dist(h.world[mcp], w), 1e-4) for tip, mcp in FINGERS]


def is_fist(h: Hand, keep: bool = False) -> bool:
    """All four fingers folded (and the thumb not sticking out: that is the volume thumbs-up). With
    keep=True (already a fist) a looser limit applies, so a fist seen from an angle or from far away doesn't
    flicker open and closed."""
    if max(h.ext) >= (FIST_KEEP if keep else FIST_CURL):
        return False
    return not (VOLUME_CONTROL and thumb_out(h) > VOLUME_THUMB_OUT)


def thumb_out(h: Hand) -> float:
    """How far the thumb tip sticks out of the folded fingers, in the picture (x the fingers' size).
    About 0 when the thumb is tucked in a fist, 0.5 and more for a thumbs-up."""
    f = h.flat
    xs = [f[j][0] for j in range(5, 21)]
    ys = [f[j][1] for j in range(5, 21)]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    size = max(x1 - x0, y1 - y0, 1e-4)
    tx, ty = f[THUMB_TIP]
    return math.hypot(max(x0 - tx, 0.0, tx - x1), max(y0 - ty, 0.0, ty - y1)) / size


def thumb_angle(h: Hand) -> float:
    """Angle of the thumb in the picture: 0 = straight up, 90 = sideways, 180 = straight down."""
    f = h.flat
    dx, dy = f[THUMB_TIP][0] - f[2][0], f[THUMB_TIP][1] - f[2][1]
    return abs(math.degrees(math.atan2(dx, -dy)))


class ThumbVolume:
    """One hand's thumbs-up volume control: idle -> pending (pose seen) -> active (held VOLUME_HOLD)."""

    def __init__(self):
        self.state = "idle"
        self.since = 0.0
        self.last_seen = -1e9
        self.angle = None

    def update(self, h: Hand, now: float):
        """Volume this hand asks for (0..1), or None when it isn't doing the gesture."""
        active = self.state == "active"
        pose = (max(h.ext) < (FIST_KEEP if active else FIST_CURL)
                and thumb_out(h) > (VOLUME_THUMB_KEEP if active else VOLUME_THUMB_OUT))
        if pose:
            self.last_seen = now
            a = thumb_angle(h)
            self.angle = a if self.angle is None else 0.6 * self.angle + 0.4 * a
            if self.state == "idle":
                self.state, self.since = "pending", now
            elif self.state == "pending" and now - self.since >= VOLUME_HOLD:
                self.state = "active"
                log.info("thumbs-up: volume control on")
        elif now - self.last_seen > 0.2:
            if active:
                log.info("thumb in: volume control off")
            self.state, self.angle = "idle", None
        if self.state != "active" or self.angle is None:
            return None
        a = min(max(self.angle, VOLUME_ENDS), 180 - VOLUME_ENDS)
        return 1.0 - (a - VOLUME_ENDS) / (180 - 2 * VOLUME_ENDS)

    @property
    def busy(self) -> bool:
        return self.state != "idle"


class DoubleGrab:
    """One hand's double quick fist -> switch main hand."""

    def __init__(self):
        self.phase = "idle"             # idle -> folded (1st) -> open -> folded (2nd) -> fires when it opens
        self.t = 0.0
        self.count = 0
        self.last_open = -1e9

    def update(self, h: Hand, now: float) -> bool:
        """True once when the double fold is complete."""
        e = sorted(h.ext)
        folded = e[-1] < FIST_CURL
        opened = e[1] > GRAB_OPEN       # at least three fingers straight again
        if self.phase == "idle":
            if opened:
                self.last_open = now
            elif folded and now - self.last_open < 0.35:      # closed quickly from an open hand
                self.phase, self.t, self.count = "folded", now, 1
        elif self.phase == "folded":
            if opened:
                self.last_open = now
                if now - self.t <= GRAB_MAX:
                    if self.count == 2:
                        self.phase = "idle"
                        return True
                    self.phase, self.t = "open", now
                else:
                    self.phase = "idle"
            elif now - self.t > GRAB_MAX + 0.15:
                self.phase = "idle"     # held: that's a fist (scroll), not a tap
        elif self.phase == "open":
            if folded:
                if now - self.t <= GRAB_GAP:
                    self.phase, self.t, self.count = "folded", now, 2
                else:
                    self.phase = "idle"
            elif now - self.t > GRAB_GAP:
                self.phase = "idle"
        return False

    @property
    def busy(self) -> bool:
        return self.phase != "idle"


class WinVolume:
    """Windows master volume (Core Audio through pycaw, installed on first use)."""

    def __init__(self):
        self.ep = None
        self.failed = False

    def _endpoint(self):
        if self.ep is None and not self.failed:
            try:
                if not ensure_package("pycaw", "pycaw"):
                    raise RuntimeError("pycaw not available")
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                dev = AudioUtilities.GetSpeakers()
                ep = getattr(dev, "EndpointVolume", None)
                if ep is None:
                    from ctypes import POINTER, cast
                    from comtypes import CLSCTX_ALL
                    ep = cast(dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None), POINTER(IAudioEndpointVolume))
                self.ep = ep
            except Exception:
                log.exception("volume control unavailable")
                self.failed = True
        return self.ep

    def refresh(self):
        """Look up the speakers again (the default device may have changed)."""
        self.ep = None
        self.failed = False

    def get(self) -> float | None:
        ep = self._endpoint()
        try:
            return float(ep.GetMasterVolumeLevelScalar()) if ep is not None else None
        except Exception:
            self.ep = None
            return None

    def set(self, level: float):
        ep = self._endpoint()
        if ep is None:
            return
        try:
            ep.SetMasterVolumeLevelScalar(min(max(level, 0.0), 1.0), None)
            if level > 0.005 and ep.GetMute():
                ep.SetMute(0, None)
        except Exception:
            self.ep = None


def palm_center(h: Hand) -> tuple[float, float]:
    pts = [h.img[i] for i in (WRIST, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP)]
    return sum(p[0] for p in pts) / 5, sum(p[1] for p in pts) / 5


def scroll_speed(d: float, deadzone: float) -> float:
    """Notches per second for a fist moved d (fraction of the picture height) from where it closed."""
    if abs(d) < deadzone:
        return 0.0
    return math.copysign(min(SCROLL_BASE_SPEED + SCROLL_GAIN * (abs(d) - deadzone), SCROLL_MAX_SPEED), d)


class FistScroll:
    """One hand's fist-scroll state: idle -> pending (fist seen) -> active (held FIST_ON_TIME) -> idle."""

    def __init__(self):
        self.state = "idle"
        self.quiet = False              # gestures are off: don't log scroll mode changes
        self.since = 0.0
        self.last_fist = -1e9
        self.anchor = None
        self.y = None
        self.x = self.anchor_x = None
        self.aspect = 0.5625
        self.axis = None                # "v" / "h": the direction scrolling now
        self.hrate = 0.0                # sideways scroll rate (notches per second, positive = right)

    def follow(self, h: Hand):
        """Smoothed fist position (also on frames whose finger shapes are unreadable)."""
        x, y = h.center
        self.y = y if self.y is None else 0.5 * y + 0.5 * self.y
        self.x = x if self.x is None else 0.5 * x + 0.5 * self.x
        self.aspect = h.aspect

    def update(self, h: Hand, now: float, k: float = 1.0) -> float:
        """Returns the scroll rate in notches per second (positive = scroll down); the sideways rate is in
        self.hrate. k = hand size relative to normal (smaller when further away), so the same real movement
        scrolls the same amount at any distance."""
        fist = is_fist(h, keep=self.state != "idle")
        self.follow(h)
        if fist:
            self.last_fist = now
            if self.state == "idle":
                self.state, self.since = "pending", now
            elif self.state == "pending" and now - self.since >= FIST_ON_TIME:
                self.state, self.anchor, self.anchor_x, self.axis = "active", self.y, self.x, None
                if not self.quiet:
                    log.info("fist: scroll mode on")
        elif now - self.last_fist >= (FIST_OFF_TIME if self.state == "active" else 0.05):
            if self.state == "active" and not self.quiet:
                log.info("hand opened: scroll mode off")
            self.state, self.anchor, self.anchor_x, self.axis = "idle", None, None, None
        return self.hold_rate(k)

    def hold_rate(self, k: float = 1.0) -> float:
        """Scroll rates from the current fist position (vertical returned, sideways in self.hrate). Only the
        direction the fist moved further scrolls; it stays that way until the other one is clearly bigger."""
        self.hrate = 0.0
        if self.state != "active" or self.anchor is None:
            return 0.0
        dy = (self.y - self.anchor) / k
        dx = (self.x - self.anchor_x) / k / self.aspect if HSCROLL and self.anchor_x is not None else 0.0
        vy, vx = abs(dy) / SCROLL_DEADZONE, abs(dx) / HSCROLL_DEADZONE    # 1 = at the edge of the dead zone
        if max(vx, vy) < 1.0:
            self.axis = None
        elif self.axis is None or (self.axis == "v" and vx > 1.5 * vy) or (self.axis == "h" and vy > 1.5 * vx):
            self.axis = "h" if vx > vy else "v"
        if self.axis == "h":
            self.hrate = scroll_speed(dx, HSCROLL_DEADZONE)
            return 0.0
        return scroll_speed(dy, SCROLL_DEADZONE) if self.axis == "v" else 0.0

    @property
    def busy(self) -> bool:
        return self.state != "idle"


class Swiper:
    """Fast left/right movement of the second hand -> window swipe."""

    def __init__(self):
        self.reset()
        self.last_dir = 0
        self.last_time = -1e9

    def reset(self):
        self.track = []         # (time, second-hand x, main-hand x or None)
        self.since = None

    def update(self, h: Hand | None, now: float, main: Hand | None = None, k: float = 1.0) -> str | None:
        """h = second hand. Movement is measured relative to the main hand (so moving your whole body or
        the laptop doesn't swipe) and relative to hand size k (so it works the same further away)."""
        if h is None:
            self.reset()
            return None
        x = h.center[0]
        mx = main.center[0] if main is not None else None
        if self.since is None or (self.track and now - self.track[-1][0] > 0.25):
            self.track, self.since = [], now
        self.track.append((now, x, mx))
        self.track = [e for e in self.track if now - e[0] <= SWIPE_TIME]
        if now - self.since < SWIPE_SETTLE or len(self.track) < 2:
            return None
        t0, x0, m0 = self.track[0]
        dx = x - x0
        if mx is not None and m0 is not None:
            dx -= (mx - m0)
        dx /= k
        if abs(dx) < SWIPE_DISTANCE:
            return None
        d = 1 if dx > 0 else -1
        wait = SWIPE_REPEAT if d == self.last_dir else SWIPE_RETURN_IGNORE
        if now - self.last_time < wait:
            return None
        self.last_dir, self.last_time = d, now
        self.track = [(now, x, mx)]
        if SWIPE_INVERT:
            d = -d
        return "right" if d > 0 else "left"


class ClickTracker:
    """Pinch -> mouse button.
    A touch starts when the thumb gets close to the middle or ring fingertip and ends when the fingers stay
    apart for RELEASE_DELAY (or clearly open in a single frame), so one noisy frame doesn't end it. Which
    button it is gets decided from the average of the whole touch.
    Double-click: a second pinch soon after a click presses at once, with the same button; if it still
    comes too late for Windows' double-click time, a proper double-click is sent."""

    def __init__(self, mouse, double_click_time: float = 0.5):
        self.mouse = mouse
        self.double_click_time = double_click_time
        self.touching = False
        self.touch_start = 0.0
        self.last_raw_touch = -1e9
        self.sum_dm = self.sum_dr = 0.0
        self.n = 0
        self.edm = self.edr = None      # recent (smoothed) distances, for the middle-click upgrade
        self.cand = None
        self.cand_since = 0.0
        self.pressed = None
        self.pressed_at = -1e9
        self.released_at = -1e9
        self.fired = False              # this touch already produced a click
        self.quick = False              # this touch is the second pinch of a double-click
        self.last_button = None
        self.last_down = -1e9
        self.double_clicks = 0

    @staticmethod
    def classify(dm: float, dr: float) -> str:
        """Which click a touch is. Middle and ring fingertips sit close together, so a thumb on
        one is always fairly near the other: compare the two distances instead of using fixed limits."""
        near, far = min(dm, dr), max(dm, dr)
        if far < TOUCH_OFF and far / max(near, 1e-3) < BOTH_RATIO:
            return "middle"
        return "left" if dm <= dr else "right"

    def in_double_window(self, now: float) -> bool:
        return self.last_button is not None and now - self.released_at <= DOUBLE_CLICK_WINDOW

    def update(self, dm: float, dr: float, now: float, suppress: bool, dragging: bool = False):
        if suppress:
            if self.pressed:
                self._release(now)
            self.touching, self.fired, self.cand = False, False, None
            return
        d = min(dm, dr)
        raw = d < (TOUCH_OFF if self.touching else TOUCH_ON)
        if not self.touching and not raw and self.in_double_window(now) and d < TOUCH_ON + DOUBLE_TOUCH_SLACK:
            raw = True                  # second pinch of a double-click: a slightly looser touch is enough
        if raw:
            self.last_raw_touch = now
            if not self.touching:
                self.touching, self.touch_start, self.fired = True, now, False
                self.quick = self.in_double_window(now)
                self.sum_dm = self.sum_dr = 0.0
                self.n = 0
                self.edm = self.edr = None
                self.recent = []
            self.sum_dm += dm
            self.sum_dr += dr
            self.n += 1
            self.recent = (self.recent + [(dm, dr)])[-2:]
            self.edm = dm if self.edm is None else 0.5 * dm + 0.5 * self.edm
            self.edr = dr if self.edr is None else 0.5 * dr + 0.5 * self.edr
        elif self.touching and (now - self.last_raw_touch >= RELEASE_DELAY or (
                d > TOUCH_OFF + RELEASE_CLEAR and not dragging
                and (self.pressed is None or now - self.pressed_at < QUICK_RELEASE_HOLD))):
            # released: fingers apart long enough, or clearly wide open in one frame (catches the short
            # opening between the two pinches of a double-click even at a low frame rate)
            self.touching = False
            if self.pressed:
                self._release(now)
            elif not self.fired and self.n >= 2 and not self.quick:
                self._press(self._choose(), now)       # a quick tap that ended before CLICK_DELAY: click now
                self._release(now)
            elif not self.fired and DIAGNOSTICS:
                log.info("touch ended without a click: fingers touched only %.2f s (needs %.2f s)",
                         self.last_raw_touch - self.touch_start, CLICK_DELAY)

        cand = self.classify(self.edm, self.edr) if self.touching and self.edm is not None else None
        if cand != self.cand:
            self.cand, self.cand_since = cand, now

        # a new touch clicks after 2 frames AND CLICK_DELAY: at 27+ fps two frames are only ~40 ms, and the ring
        # finger of a middle click often arrives a frame after the middle finger
        if (self.touching and raw and not self.fired and self.n
                and (self.quick or (self.n >= 2 and now - self.touch_start >= CLICK_DELAY))):
            if self.quick:
                button = self.last_button       # a double-click repeats the same button
                late = now - self.last_down > self.double_click_time * 0.85
                if late:
                    # too slow for Windows to see a double-click: send a quick click first, so this press
                    # becomes the second click of a real double-click
                    self.mouse.button(button, True)
                    self.mouse.button(button, False)
                self.double_clicks += 1
                if DIAGNOSTICS:
                    log.info("double-click: second pinch %.2f s after the first%s", now - self.last_down,
                             " (helped: extra click sent)" if late else "")
            else:
                button = self._choose()
            self._press(button, now)
        elif (self.pressed in ("left", "right") and cand == "middle"
              and now - self.cand_since >= RELEASE_DELAY and now - self.pressed_at <= UPGRADE_WINDOW):
            # the third finger arrived a moment late: it was meant as a middle click (also when this pinch came
            # right after a click and started as its double-click, which repeats the button)
            self._release(now)
            self.quick = False
            self._press("middle", now)

    def _choose(self) -> str:
        """Which button this touch is: from the average of the whole touch, but middle if the latest two frames
        have both fingers on (the ring finger often arrives a frame after the middle finger)."""
        button = self.classify(self.sum_dm / self.n, self.sum_dr / self.n)
        rm = sum(d[0] for d in self.recent) / len(self.recent)
        rr = sum(d[1] for d in self.recent) / len(self.recent)
        return "middle" if self.classify(rm, rr) == "middle" else button

    def _press(self, button: str, now: float):
        self.mouse.button(button, True)
        self.pressed, self.pressed_at, self.fired = button, now, True
        if not self.quick:
            log.info("%s click", button)

    def _release(self, now: float):
        self.mouse.button(self.pressed, False)
        if now - self.pressed_at >= 0.5:
            log.info("%s button held %.1f s (drag / long press)", self.pressed, now - self.pressed_at)
        if not self.quick and now - self.pressed_at < QUICK_RELEASE_HOLD:
            self.last_button, self.last_down = self.pressed, self.pressed_at    # a click: a double may follow
        else:
            self.last_button = None     # a finished double-click, or a hold / drag: the next pinch starts fresh
        self.pressed, self.released_at = None, now

    def freezing(self, now: float) -> bool:
        if self.touching and not self.fired:
            return True     # waiting to decide which click it is
        return now - self.released_at < FREEZE_AFTER_RELEASE

    def reset(self, now: float):
        if self.pressed:
            self._release(now)
        self.touching = False
        self.fired = False
        self.quick = False
        self.cand = None
        self.last_button = None


class SideButtonTracker:
    """One hand's thumb-on-finger-middle buttons (mouse 4 / 5). Like a click: needs 2 frames of touching,
    stays down while the thumb stays there, lets go after the thumb has been away for RELEASE_DELAY."""
    BUTTONS = {"x1": "button 4", "x2": "button 5"}

    def __init__(self, mouse):
        self.mouse = mouse
        self.touching = None            # "x1" / "x2" while the thumb is on a finger's middle
        self.frames = 0
        self.last_raw = -1e9
        self.pressed = None

    def wants(self, h: Hand) -> str | None:
        """Which side button the thumb is on now (None if none)."""
        cur = self.touching
        for name in ([cur] if cur else []) + [n for n in ("x1", "x2") if n != cur]:
            held = name == cur
            if min(h.ext[i] for i in SIDE_STRAIGHT_FINGERS[name]) < SIDE_STRAIGHT * (0.93 if held else 1.0):
                continue                # a finger folded: a fist, a closing hand or a click
            d = h.side[name]
            loose = 1 / 0.75 if held else 1.0
            if name == "x1":            # thumb on the index fingertip, clearly not on the middle / ring tip
                if d < (TOUCH_OFF if held else TOUCH_ON) and d < INDEX_PINCH_MARGIN * min(h.pinch) * loose:
                    return name
            elif thumb_on_palm_base(h, held):   # thumb across the palm on the base of the ring / little finger
                return name
        return None

    def update(self, h: Hand, now: float, suppress: bool = False):
        name = None if suppress else self.wants(h)
        if name is not None:
            self.last_raw = now
            if name != self.touching:
                if self.pressed and self.pressed != name:
                    self.release()
                self.touching, self.frames = name, 0
            self.frames += 1
            if self.pressed is None and self.frames >= 2:
                self.mouse.button(name, True)
                self.pressed = name
                log.info("%s pressed (thumb on the %s)", self.BUTTONS[name],
                         "index fingertip" if name == "x1" else "base of the ring / little finger")
        elif self.touching and (suppress or now - self.last_raw >= RELEASE_DELAY):
            self.release()

    def release(self):
        if self.pressed:
            self.mouse.button(self.pressed, False)
        self.pressed, self.touching, self.frames = None, None, 0


_VK_NAMES = {"ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B, "tab": 0x09, "enter": 0x0D,
             "esc": 0x1B, "escape": 0x1B, "space": 0x20, "backspace": 0x08, "delete": 0x2E, "del": 0x2E,
             "insert": 0x2D, "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22, "left": 0x25,
             "up": 0x26, "right": 0x27, "down": 0x28, "printscreen": 0x2C, "prtsc": 0x2C, "playpause": 0xB3,
             "nexttrack": 0xB0, "prevtrack": 0xB1, "mute": 0xAD}


def parse_keys(text: str):
    """"ctrl+c" -> [VK_CONTROL, VK_C]; "keyboard" -> "keyboard"; "" -> None. ValueError for unknown key names."""
    t = text.strip().lower().replace(" ", "")
    if not t:
        return None
    if t == "keyboard":
        return t
    vks = []
    for part in t.split("+"):
        if part in _VK_NAMES:
            vks.append(_VK_NAMES[part])
        elif len(part) == 1 and part.isascii() and part.isalnum():
            vks.append(ord(part.upper()))
        elif part[:1] == "f" and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            vks.append(0x6F + int(part[1:]))
        else:
            raise ValueError(f"unknown key {part!r}")
    return vks


_MEDIA_LABELS = {"playpause": "Play/Pause", "nexttrack": "Next track", "prevtrack": "Previous track",
                 "mute": "Mute"}


def key_label(text: str) -> str:
    """"ctrl+c" -> "Ctrl+C", "keyboard" -> "on-screen keyboard"."""
    t = text.strip().lower()
    if t == "keyboard":
        return "on-screen keyboard"
    if t in _MEDIA_LABELS:
        return _MEDIA_LABELS[t]
    return "+".join(p.strip().capitalize() for p in text.split("+"))


def tip_distances(h: Hand) -> dict:
    """Thumb tip to the index, middle and ring fingertips (3D, x palm length), like the clicks."""
    return {"index": h.side["x1"], "middle": h.pinch[0], "ring": h.pinch[1]}


def classify_tips(d: dict) -> str:
    """Which fingertip(s) the thumb is on, from the three distances. Fingertips side by side sit close, so a
    pair is told from a single tip by comparing the distances (like the middle click), not by fixed limits."""
    (n1, d1), (n2, d2), _ = sorted(d.items(), key=lambda kv: kv[1])
    pair = "+".join(n for n in d if n in (n1, n2))
    if pair in ("index+middle", "middle+ring") and d2 < TOUCH_OFF and d2 / max(d1, 1e-3) < BOTH_RATIO:
        return pair
    return n1


def thumb_index_2d(h: Hand) -> float:
    """Thumb tip to index fingertip in the picture (x palm length in the picture)."""
    f = h.flat
    return math.dist(f[THUMB_TIP], f[INDEX_TIP]) / max(math.dist(f[WRIST], f[MIDDLE_MCP]), 1e-4)


def second_contact(h: Hand, held: str | None = None) -> str | None:
    """What the thumb of the second hand touches now: "index", "middle", "ring", "index+middle", "middle+ring",
    "little base", or None. held = the touch going on already: looser limits, and bent fingers don't end it
    (the hand model often reads the pinching and the relaxed fingers as bent)."""
    if max(h.ext) < (FIST_CURL if held else SIDE_STRAIGHT):
        return None                     # no finger straight: a fist or a closing hand
    if thumb_on_palm_base(h, held == "little base"):
        return "little base"
    d = tip_distances(h)
    if min(d.values()) >= (TOUCH_OFF if held else TOUCH_ON):
        if held == "index" and thumb_index_2d(h) < INDEX_HOLD_2D:
            return "index"              # depth misread while the "OK" sign is held: the picture decides
        if held is None and d["index"] == min(d.values()) and (
                d["index"] < SECOND_INDEX_ON
                or (d["index"] < INDEX_START_3D_MAX and thumb_index_2d(h) < INDEX_START_2D)):
            return classify_tips(d)     # the left "OK" sign reads further apart than a click: easier to start
        return None
    return classify_tips(d)


class SecondHandKeys:
    """Keyboard shortcuts from the second hand (SECOND_KEYS). A pinch acts when the thumb lets go, decided from
    the median distances over the whole touch (a few misread frames don't change it); "twice" gestures wait for
    a possible second tap; the Alt+Tab pinch held keeps the window switcher open; a fist presses its key when
    the hand opens; a thumbs-up when the thumb is tucked in, or moved sideways for the tracks."""

    def __init__(self, mouse):
        self.mouse = mouse
        self.actions = {}
        for name, text in SECOND_KEYS.items():
            try:
                keys = parse_keys(text)
            except ValueError as e:
                log.warning("SECOND_KEYS[%r] = %r: %s - ignored", name, text, e)
                continue
            if keys is not None:
                self.actions[name] = (keys, key_label(text))
        self.last_text, self.last_time, self.fresh = "", -1e9, False
        self.pending = None             # (gesture, time, wait): a single tap waiting to see whether a second comes
        self.switcher = False           # Alt is held down: the window switcher is open
        self._clear()

    def _clear(self):
        self.touching, self.counts, self.start, self.last_raw = False, {}, 0.0, -1e9
        self.dists, self.spoiled, self.fist_reads = {}, "", 0     # distances of the touch's fingertip frames
        self.sw_x, self.sw_index, self.sw_count = None, 0, None
        self.fist_since, self.fist_frames, self.fist_ok = None, 0, False
        self.thumb_since, self.thumb_last, self.thumb_x, self.thumb_moved = None, -1e9, None, False
        self.thumb_real = -1e9          # last time a thumbs-up held at least KEY_THUMB_MIN was seen

    def reset(self):
        """Let go of everything (hand lost, gestures off, pause, quit). A waiting single tap still acts."""
        if self.switcher:
            self._close_switcher()
        if self.pending:
            name, self.pending = self.pending[0], None
            self._do(name)
        self._clear()

    def dominant(self) -> str | None:
        """What this touch is so far: the base of the little finger if the thumb was there in at least half of
        the frames, otherwise the fingertip(s) from the median distances."""
        frames = sum(self.counts.values())
        if not frames:
            return None
        if self.counts.get("little base", 0) * 2 >= frames or not self.dists:
            return "little base"
        return classify_tips(self._medians())

    def _medians(self) -> dict:
        return {n: sorted(v)[len(v) // 2] for n, v in self.dists.items()}

    def update(self, h: Hand | None, now: float, k: float = 1.0, main_in_view: bool = True,
               two_fists: bool = False):
        if self.pending and not self.touching and now - self.pending[1] > self.pending[2]:
            name, self.pending = self.pending[0], None
            self._do(name)
        if h is None:
            if self.touching and now - self.last_raw > LOST_GRACE:
                self._end_touch(now, fire=False)        # hand gone mid-touch: let go, don't act
            self.fist_since = self.thumb_since = None
            return
        if h.unsure:                    # finger shapes unreadable this frame: keep the state
            if self.touching:
                self.last_raw = now
            return
        self._pinch(h, now, k)
        self._thumbs_up(h, now, k)
        self._fist(h, now, main_in_view, two_fists)

    # ---- pinches
    def _pinch(self, h: Hand, now: float, k: float):
        held = self.dominant() if self.touching else None
        c = second_contact(h, held)
        if self.touching and max(h.ext) < FIST_CURL:
            self.fist_reads += 1        # one misread frame doesn't cancel a pinch; two in a row do
            if self.fist_reads >= 2:
                self.spoiled = "the hand closed into a fist"
        else:
            self.fist_reads = 0
        if c is not None:
            self.last_raw = now
            if not self.touching:
                self.touching, self.counts, self.start = True, {}, now
                self.dists, self.spoiled = {}, ""
            self.counts[c] = self.counts.get(c, 0) + 1
            if c != "little base":
                for n, v in tip_distances(h).items():
                    self.dists.setdefault(n, []).append(v)
            if self.switcher:
                self._switch_step(h, k)
            elif (self.actions.get(self.dominant(), (None, ""))[1] == "Alt+Tab"
                  and now - self.start >= ALT_TAB_HOLD and sum(self.counts.values()) >= 3):
                self._open_switcher(h)
        elif self.touching:
            # let go: the thumb away long enough, or (a short pinch) clearly wide open in one frame, so the two
            # taps of a "twice" don't merge
            wide = (min(tip_distances(h).values()) > TOUCH_OFF + RELEASE_CLEAR
                    and not h.side["x2"] < SIDE_TOUCH_OFF * 1.5)
            wait = ALT_TAB_RELEASE if self.switcher else KEY_RELEASE_DELAY
            if (self.spoiled or now - self.last_raw >= wait
                    or (wide and not self.switcher and now - self.start < QUICK_RELEASE_HOLD)):
                self._end_touch(now)

    def _end_touch(self, now: float, fire: bool = True):
        name, frames = self.dominant(), sum(self.counts.values())
        if DIAGNOSTICS and frames:
            med = self._medians() if self.dists else {}
            log.info("second hand touch %.2f s, %d frames: thumb to index %s middle %s ring %s (median), on the "
                     "palm base %d -> %s%s", self.last_raw - self.start, frames, _num(med.get("index", math.inf)),
                     _num(med.get("middle", math.inf)), _num(med.get("ring", math.inf)),
                     self.counts.get("little base", 0), name,
                     f" (cancelled: {self.spoiled})" if self.spoiled else (" (too short)" if frames < 2 else ""))
        spoiled = self.spoiled
        self.touching, self.counts, self.dists, self.spoiled = False, {}, {}, ""
        if self.switcher:
            self._close_switcher()
            return
        if not fire or spoiled or frames < 2 or name not in self.actions:
            return                      # brushed past, closed into a fist, or nothing set for it
        waiting, self.pending = self.pending, None
        if waiting and waiting[0] == name:
            self._do(name + " twice")
            return
        if waiting:
            self._do(waiting[0])
        if name + " twice" in self.actions:
            self.pending = (name, now, KEY_DOUBLE_WINDOW)
        else:
            self._do(name)

    def _open_switcher(self, h: Hand):
        self.switcher, self.sw_x = True, h.center[0]
        count = getattr(self.mouse, "alt_tab_count", None)
        self.sw_count = count() if ALT_TAB_STOP_AT_ENDS and count is not None else None
        self.sw_index = 1 if self.sw_count is None or self.sw_count > 1 else 0   # Alt+Tab selects the 2nd one
        if hasattr(self.mouse, "key"):
            self.mouse.key(_VK_NAMES["alt"], True)
            self.mouse.keys([_VK_NAMES["tab"]])
        log.info("second hand: Alt+Tab held (%s windows) - move the hand left / right to pick one, let go to switch",
                 self.sw_count if self.sw_count is not None else "?")

    def _switch_step(self, h: Hand, k: float):
        step = ALT_TAB_STEP * k
        dx = h.center[0] - self.sw_x
        for _ in range(3):              # at most 3 windows per frame
            if abs(dx) < step:
                break
            d = 1 if dx > 0 else -1
            # at the first / last window: no key (Windows would wrap around), but the start point still follows
            # the hand, so moving back goes back at once
            if self.sw_count is None or 0 <= self.sw_index + d < self.sw_count:
                self.sw_index += d
                if hasattr(self.mouse, "keys"):
                    self.mouse.keys([_VK_NAMES["right" if d > 0 else "left"]])
            self.sw_x += d * step
            dx -= d * step

    def _close_switcher(self):
        if hasattr(self.mouse, "key"):
            self.mouse.key(_VK_NAMES["alt"], False)
        self.switcher, self.sw_x = False, None
        self._show("Alt+Tab: switched")
        log.info("second hand: Alt+Tab let go - switched window")

    # ---- fist and thumbs-up
    def _thumbs_up(self, h: Hand, now: float, k: float = 1.0):
        """Thumbs-up, then the thumb tucked into the fist -> play / pause. A thumbs-up moved left / right ->
        previous / next track, one per TRACK_STEP (tucking the thumb afterwards does nothing then)."""
        on = self.thumb_since is not None
        pose = (max(h.ext) < (FIST_KEEP if on else FIST_CURL)
                and thumb_out(h) > (VOLUME_THUMB_KEEP if on else VOLUME_THUMB_OUT))
        if pose:
            self.thumb_last = now
            if not on:
                self.thumb_since, self.thumb_x, self.thumb_moved = now, h.center[0], False
                return
            if now - self.thumb_since >= KEY_THUMB_MIN:
                self.thumb_real = now
            step = TRACK_STEP * k
            dx = h.center[0] - self.thumb_x
            if abs(dx) >= step:
                d = 1 if dx > 0 else -1
                self.thumb_x += d * step        # the start point follows: each further step is one more track
                self.thumb_moved = True
                self._do("thumbs-up right" if d > 0 else "thumbs-up left")
        elif on:
            if (is_fist(h, keep=True) and not self.thumb_moved
                    and self.thumb_last - self.thumb_since >= KEY_THUMB_MIN):
                self.thumb_since = None
                self._do("thumbs-up, thumb in")
            elif now - self.thumb_last > 0.3:
                self.thumb_since = None         # thumbs-up gone without tucking the thumb (hand opened)

    def _fist(self, h: Hand, now: float, main_in_view: bool, two_fists: bool):
        tucked = is_fist(h, keep=self.fist_since is not None)
        if self.fist_since is None:
            if tucked:
                # a fist made by tucking the thumb of a thumbs-up is play / pause, not Esc
                self.fist_since, self.fist_frames, self.fist_ok = now, 1, now - self.thumb_real > 0.4
            return
        self.fist_frames += tucked
        if two_fists or now - self.thumb_real < 0.05:
            self.fist_ok = False        # two fists (gestures off / on) or a real thumbs-up: not this
        if sorted(h.ext)[2] > SIDE_STRAIGHT:            # hand open again (two fingers straight): next fist counts
            self.fist_since = None
            return
        # acts while the fist is still closed, once per fist. Alone in view a quick fist may be half of the
        # main-hand switch (two quick fists), so it waits until the fist is held longer than one of those
        wait = KEY_FIST_HOLD if main_in_view else GRAB_MAX + 0.15
        if self.fist_ok and self.fist_frames >= 2 and now - self.fist_since >= wait:
            self.fist_ok = False
            self._do("fist")

    # ---- output
    def _do(self, name: str):
        act = self.actions.get(name)
        if act is None:
            return
        keys, label = act
        fn = getattr(self.mouse, "toggle_keyboard" if keys == "keyboard" else "keys", None)
        if fn is not None:
            try:
                if keys == "keyboard":
                    fn()
                else:
                    fn(keys)
            except Exception as e:
                log.warning("second hand %s -> %s failed: %s", name, label, e)
        self._show(label)
        log.info("second hand %s -> %s", name, label)

    def _show(self, text: str):
        self.last_text, self.fresh = text, True     # timed with the frame clock in display()

    def display(self, now: float) -> str:
        """What to show in the camera window (empty when nothing is going on)."""
        if self.fresh:
            self.fresh, self.last_time = False, now
        if self.switcher:
            return "ALT+TAB - move the hand to pick, let go to switch"
        if now - self.last_time < 0.8:
            return self.last_text.upper()
        if self.pending and self.pending[0] + " twice" in self.actions:
            return f"{self.pending[0]}... (again for {self.actions[self.pending[0] + ' twice'][1]})"
        return ""


class Track:
    """A physical hand followed from frame to frame by its position."""

    def __init__(self, key: str, h: Hand, now: float):
        self.key, self.center, self.first_seen, self.last_seen = key, h.center, now, now
        self.palm = h.palm
        self.side_score = 0             # > 0: your right hand, < 0: your left hand (votes over the frames)


class Engine:
    """Turns tracked hands into mouse actions. Independent of camera and OS (testable)."""

    def __init__(self, mouse, screen_x: int, screen_y: int, screen_w: int, screen_h: int,
                 ref_palm: float | None = None, on_ref_learned=None, box_state: dict | None = None,
                 main_side: str = "right", on_main_side=None):
        self.mouse = mouse
        self.boxcam = CursorBox(box_state)
        self.clicks = ClickTracker(mouse, getattr(mouse, "double_click_time", 0.5))
        self.cursor = CursorFilter((0, 0, 1, 1))
        self.sides: dict[str, SideButtonTracker] = {}   # mouse buttons 4/5, one per hand
        self.release_seen = -1e9        # last click release already handled by the cursor lock
        self.release_point = None       # where the finger pointed when the button was released
        self.set_screen(screen_x, screen_y, screen_w, screen_h)
        self.fists: dict[str, FistScroll] = {}
        self.thumbs: dict[str, ThumbVolume] = {}
        self.volume = getattr(mouse, "volume", None)     # WinVolume (or a test double)
        self.volume_level = None        # volume being set now (moves towards the hand's target smoothly)
        self.volume_target = None
        self.swiper = Swiper()
        self.keys = SecondHandKeys(mouse)
        self.tracks: dict[str, Track] = {}
        self.next_id = 0
        self.main_key = None            # key of the hand that moves the cursor
        self.main_side = main_side if main_side in ("right", "left") else "right"
        self.on_main_side = on_main_side
        self.switchers: dict[str, "DoubleGrab"] = {}
        self.ref_palm = ref_palm        # your normal hand size (learned)
        self.ref_samples: list[float] = []
        self.on_ref_learned = on_ref_learned
        self.k_cursor = 1.0             # distance factor for the cursor box (smoothed)
        self.last_seen = -1e9
        self.last_t = None
        self.scroll_acc = 0.0
        self.hscroll_acc = 0.0
        self.hscroll_marks: list[tuple] = []    # (anchor_x, current_x) for the preview
        self.last_cursor = None
        self.last_swipe = ""
        self.gesture = ""               # what the main hand is doing, for the preview
        self.want_status = True         # build the text lines (preview / diagnostics)
        self.status: list[str] = []
        self.diag = None
        self.scroll_marks: list[tuple] = []     # (anchor_y, current_y) for the preview
        self.both_fists_since = None
        self.gestures_off = False       # two fists turned the gestures off (camera still on)
        self.gestures_request = None    # True / False: turn gestures on / off (from the tray, another thread)
        self.gestures_changed = None    # "on" / "off" once after a change, for the main loop (beep, tray)
        self.fist_stop_armed = False    # a hand must be seen open (or out of view) before two fists count
        self.rearm_since = None
        self.last_two_fists = -1e9
        self.last_tip = None            # last accepted index fingertip (picture coords)
        self.pending_tip = None         # a suspicious jump waiting for confirmation
        self.drag_origin = None         # finger position when the button went down
        self.dragging = False

    # ---- setup
    def set_screen(self, x: int, y: int, w: int, h: int):
        """Screen area the cursor can reach (called again when monitors are added or removed)."""
        self.sx0, self.sy0, self.sw, self.sh = x, y, w, h
        self.cursor.x0, self.cursor.y0, self.cursor.x1, self.cursor.y1 = x, y, x + w - 1, y + h - 1

    def recalibrate(self):
        self.release_all(self.last_t or 0.0)
        self.ref_palm, self.ref_samples = None, []
        self.boxcam.reset()
        self.cursor.reset(keep_position=True)
        log.info("gesture state reset; re-learning your normal hand size; cursor box back to its start size")

    def _rearm(self, released: bool, now: float):
        """Two fists may switch again only after a hand was open, or no hands were seen, for STOP_REARM."""
        if self.fist_stop_armed or not released:
            self.rearm_since = None
            return
        if self.rearm_since is None:
            self.rearm_since = now
        if now - self.rearm_since >= STOP_REARM:
            self.fist_stop_armed, self.rearm_since = True, None

    def set_gestures(self, on: bool):
        """Ask for gestures on / off (safe to call from another thread; applied on the next frame)."""
        self.gestures_request = on

    def _set_gestures_off(self, off: bool, now: float, how: str):
        if off == self.gestures_off:
            return
        self.gestures_off = off
        self.both_fists_since = None
        self.release_all(now, keep_fists=True)
        for key in self.fists:              # forget fist states, but keep the hands known (mid-frame)
            self.fists[key] = FistScroll()
        if off:
            log.info("gestures off (%s) - hold both fists again to turn them back on", how)
        else:
            self.cursor.reset(keep_position=True)
            self.last_tip = self.pending_tip = None
            log.info("gestures on (%s)", how)
        self.gestures_changed = "off" if off else "on"

    def _volume(self, target, dt: float):
        """Move the system volume towards target (0..1) at VOLUME_SPEED; None = not controlling it."""
        if target is None:
            self.volume_target = None
            return
        if self.volume_target is None:          # just started: begin from the current volume
            cur = self.volume.get() if self.volume is not None else None
            self.volume_level = cur if cur is not None else target
            if self.volume is not None and hasattr(self.volume, "show"):
                self.volume.show()
        self.volume_target = target
        step = VOLUME_SPEED * max(dt, 0.0)
        new = self.volume_level + max(min(target - self.volume_level, step), -step)
        if abs(new - self.volume_level) >= 0.004 or new in (0.0, 1.0):
            self.volume_level = new
            if self.volume is not None:
                self.volume.set(new)

    def release_all(self, now: float, keep_fists: bool = False):
        self.clicks.reset(now)
        for st in self.sides.values():
            st.release()
        self.sides.clear()
        if not keep_fists:
            self.fists.clear()
        self.swiper.reset()
        self.keys.reset()
        self.scroll_acc = self.hscroll_acc = 0.0

    # ---- which hand is which
    def _match(self, hands: list[Hand], now: float):
        """Give every hand the key of the known hand it continues (nearest position), or a new key."""
        self.tracks = {k: t for k, t in self.tracks.items() if now - t.last_seen <= HAND_MEMORY}
        pairs = sorted((math.dist(h.center, t.center), i, k)
                       for i, h in enumerate(hands) for k, t in self.tracks.items())
        used_h, used_t = set(), set()
        for d, i, k in pairs:
            if i in used_h or k in used_t or d > MATCH_DISTANCE:
                continue
            hands[i].key = k
            used_h.add(i)
            used_t.add(k)
        for i, h in enumerate(hands):
            if i not in used_h:
                self.next_id += 1
                h.key = f"hand{self.next_id}"
                self.tracks[h.key] = Track(h.key, h, now)
        for h in hands:
            t = self.tracks[h.key]
            t.center, t.last_seen = h.center, now
            t.palm = 0.8 * t.palm + 0.2 * h.palm

    def _roles(self, hands: list[Hand], now: float) -> Hand | None:
        """Which hand is your right / left one, and which is the main hand (your right hand, or the left one
        if you chose it). Both hands in view: decided by position. One hand: by the hand model's left/right
        guess, averaged over the frames the hand has been followed, so one wrong guess changes nothing."""
        lock = 12
        if len(hands) >= 2:
            rightmost = max(hands, key=lambda h: h.center[0])
            for h in hands:
                t = self.tracks[h.key]
                vote = (2 if h is rightmost else -2) + (1 if h.label == RIGHT_HAND_LABEL else -1)
                t.side_score = max(min(t.side_score + vote, lock), -lock)
        else:
            for h in hands:
                t = self.tracks[h.key]
                t.side_score = max(min(t.side_score + (1 if h.label == RIGHT_HAND_LABEL else -1), lock), -lock)
        for h in hands:
            sc = self.tracks[h.key].side_score
            h.hand_side = "right" if sc >= 2 else ("left" if sc <= -2 else None)
        candidates = [h for h in hands if h.hand_side == self.main_side]
        main = None
        if candidates:
            pick = max if self.main_side == "right" else min
            main = pick(candidates, key=lambda h: h.center[0])
        if main is not None and main.key != self.main_key:
            if self.main_key is not None:
                self.cursor.reset(keep_position=True)   # continue from where the cursor is
                self.last_tip = self.pending_tip = None
            self.main_key = main.key
        for h in hands:
            h.role = "main" if h is main else "second"
        return main

    def _switch_main(self, hands: list[Hand], now: float):
        """Only the other hand in view, fist twice quickly -> it becomes the main hand (remembered)."""
        h = hands[0] if len(hands) == 1 else None
        if h is None or h.hand_side is None or h.hand_side == self.main_side:
            self.switchers.clear()
            return
        sw = self.switchers.setdefault(h.key, DoubleGrab())
        if not h.unsure and sw.update(h, now):
            self.switchers.clear()
            self.main_side, self.main_key = h.hand_side, None
            log.info("your %s hand is now the main hand (fist twice with the other hand to switch back)",
                     h.hand_side.upper())
            if self.on_main_side:
                self.on_main_side(h.hand_side)

    # ---- distance
    def _k(self, h: Hand) -> float:
        """Hand size relative to your normal size (1 = normal, 0.5 = twice as far away)."""
        if not SCALE_WITH_DISTANCE or not self.ref_palm:
            return 1.0
        t = self.tracks.get(h.key)
        palm = t.palm if t is not None else h.palm
        lo, hi = SCALE_LIMITS
        return min(max(palm / self.ref_palm, lo), hi)

    def _learn_ref(self, main: Hand):
        if not SCALE_WITH_DISTANCE or self.ref_palm is not None:
            return
        if min(main.ext) < 1.5 or min(main.pinch) < TOUCH_OFF:     # only a relaxed open hand
            return
        self.ref_samples.append(main.palm)
        if len(self.ref_samples) >= 45:
            self.ref_palm = sorted(self.ref_samples)[len(self.ref_samples) // 2]
            log.info("normal hand size learned: %.3f of the picture width", self.ref_palm)
            if self.on_ref_learned:
                self.on_ref_learned(self.ref_palm)

    def box(self) -> tuple:
        return self.boxcam.rect(self.k_cursor)

    # ---- per frame
    def update(self, hands: list[Hand], now: float):
        dt = 0.0 if self.last_t is None else min(max(now - self.last_t, 0.0), 0.1)
        self.last_t = now
        self.status = []
        self.scroll_marks = []
        self.hscroll_marks = []
        self.gesture = ""
        req, self.gestures_request = self.gestures_request, None
        if req is not None:
            self._set_gestures_off(not req, now, "tray")
            self.fist_stop_armed = False    # don't count fists that were already closed

        if not hands:
            self._rearm(True, now)              # hands out of view also allows the next two-fist switch
            if SECOND_HAND_KEYS and not self.gestures_off:
                self.keys.update(None, now)     # a waiting single tap still acts; a held Alt is let go
            if now - self.last_seen > LOST_GRACE:
                self.release_all(now)
                self.cursor.reset(keep_position=True)
                self.last_tip = self.pending_tip = None
            if self.want_status:
                self.status.append("no hands")
                if self.gestures_off:
                    self.status.insert(0, "GESTURES OFF - hold both fists 1 s to turn them back on")
            if self.gestures_off:
                self.gesture = "gestures off"
            return
        prev_seen, self.last_seen = self.last_seen, now
        if now - prev_seen > CURSOR_REANCHOR_AFTER:
            self.cursor.reset()                 # hand was away a while: start where the finger points
            self.cursor.reason = "hand back"
            self.last_tip = self.pending_tip = None
        self._match(hands, now)
        # a hand that just appeared next to one already in use must last a moment before it counts
        settled = [h for h in hands if now - self.tracks[h.key].first_seen >= NEW_HAND_CONFIRM]
        if settled and len(settled) < len(hands):
            for h in hands:
                if h not in settled:
                    h.role = ""
            hands = settled
        main = self._roles(hands, now)
        second = next((h for h in hands if h is not main), None) if main is not None else None
        acting = hands if SECOND_HAND_GESTURES else [h for h in hands if h is main]    # hands whose gestures count

        # --- fist scroll (either hand)
        rate = hrate = 0.0
        for key in list(self.fists):
            if key not in self.tracks:
                del self.fists[key]
        for h in hands:
            fs = self.fists.setdefault(h.key, FistScroll())
            fs.quiet = self.gestures_off or h not in acting     # (still followed: two fists need both hands)
            if h.unsure:                        # finger shapes unreadable this frame: keep the last state
                fs.follow(h)
                fs.last_fist = now if fs.state != "idle" else fs.last_fist
            r = fs.hold_rate(self._k(h)) if h.unsure else fs.update(h, now, self._k(h))
            if h not in acting:
                continue
            if abs(r) > abs(rate):
                rate = r
            if abs(fs.hrate) > abs(hrate):
                hrate = fs.hrate
            if fs.state == "active":
                if fs.axis == "h":
                    self.hscroll_marks.append((fs.anchor_x, fs.x))
                else:
                    self.scroll_marks.append((fs.anchor, fs.y))
        main_fist = main is not None and self.fists[main.key].busy

        # --- thumbs-up volume (either hand)
        for key in list(self.thumbs):
            if key not in self.tracks:
                del self.thumbs[key]
        target = None
        if VOLUME_CONTROL and not self.gestures_off:
            for h in acting:
                tv = self.thumbs.setdefault(h.key, ThumbVolume())
                t = None if h.unsure else tv.update(h, now)
                if t is None and h.unsure and tv.state == "active":
                    t = self.volume_target          # unreadable frame: keep the level
                if t is not None:
                    target = t
        self._volume(target, dt)
        main_thumb = main is not None and main.key in self.thumbs and self.thumbs[main.key].busy

        # --- both hands fists held STOP_HOLD -> gestures off / on; no scrolling meanwhile
        two_fists = len(hands) >= 2 and all(self.fists[h.key].busy for h in hands)
        if two_fists:
            self.last_two_fists = now
        self._rearm(any(not h.unsure and sorted(h.ext)[1] > GRAB_OPEN for h in hands), now)
        holding = two_fists or (self.both_fists_since is not None and now - self.last_two_fists < 0.25)
        if STOP_WITH_TWO_FISTS and holding and self.fist_stop_armed:
            if self.both_fists_since is None:
                self.both_fists_since = now
                log.info("both fists: gestures %s in %.1f s unless a hand opens",
                         "on" if self.gestures_off else "off", STOP_HOLD)
            rate = hrate = 0.0
            self.scroll_marks, self.hscroll_marks = [], []
            if now - self.both_fists_since >= STOP_HOLD:
                self.fist_stop_armed = False
                self._set_gestures_off(not self.gestures_off, now, "two fists")
        else:
            if self.both_fists_since is not None:
                log.info("both fists released: nothing changed")
                self.both_fists_since = None
            if two_fists and STOP_WITH_TWO_FISTS:
                rate = hrate = 0.0              # still holding the fists from the last stop

        if not self.gestures_off:
            self._switch_main(hands, now)
        if self.gestures_off:                   # only two fists count now
            self.scroll_acc = self.hscroll_acc = 0.0
            self.scroll_marks, self.hscroll_marks = [], []
            self.gesture = "gestures off"
            if self.want_status:
                self._status(hands, main, 0.0, frozen=True)
                self.status.insert(0, "GESTURES OFF - hold both fists 1 s to turn them back on")
            return

        if self.volume_target is not None:
            self.gesture = f"VOLUME {self.volume_level * 100:.0f}%"
        if rate:
            delta = -rate * 120.0 * dt          # Windows: positive wheel = up
            if SCROLL_INVERT:
                delta = -delta
            self.scroll_acc += delta
            step = int(self.scroll_acc) if SCROLL_SMOOTH else int(self.scroll_acc / 120) * 120
            if step:
                self.mouse.wheel(step)
                self.scroll_acc -= step
            self.gesture = f"SCROLL {'down' if rate > 0 else 'up'}"
        else:
            self.scroll_acc = 0.0
        if hrate:
            delta = hrate * 120.0 * dt          # Windows: positive sideways wheel = right
            if HSCROLL_INVERT:
                delta = -delta
            self.hscroll_acc += delta
            step = int(self.hscroll_acc) if SCROLL_SMOOTH else int(self.hscroll_acc / 120) * 120
            if step and hasattr(self.mouse, "hwheel"):
                self.mouse.hwheel(step)
                self.hscroll_acc -= step
            self.gesture = f"SCROLL {'right' if hrate > 0 else 'left'}"
        else:
            self.hscroll_acc = 0.0

        # --- side buttons (mouse 4 / 5), every hand in use
        for key in list(self.sides):          # a hand that left: let go of its button after LOST_GRACE
            t = self.tracks.get(key)
            if t is None or now - t.last_seen > LOST_GRACE:
                self.sides.pop(key).release()
        for h in hands:
            if h not in acting and h.key in self.sides:
                self.sides.pop(h.key).release()
        if SIDE_BUTTONS:
            for h in acting:
                st = self.sides.setdefault(h.key, SideButtonTracker(self.mouse))
                if h.unsure:
                    continue                    # finger shapes unreadable this frame: keep the state
                busy = self.fists[h.key].busy or (h is main and (self.clicks.touching or self.clicks.pressed is not None))
                st.update(h, now, suppress=busy)
                if st.pressed:
                    self.gesture = "BUTTON 4 (back)" if st.pressed == "x1" else "BUTTON 5 (forward)"

        # --- window swipe (second hand only, both hands in view, not while it is making a fist)
        if (SWIPE_ENABLED and SECOND_HAND_GESTURES and second is not None and not self.fists[second.key].busy
                and not (second.key in self.thumbs and self.thumbs[second.key].busy)):
            direction = self.swiper.update(second, now, main, self._k(second))
            if direction:
                self.do_swipe(direction, now)
        else:
            self.swiper.update(None, now)

        # --- keyboard shortcuts (second hand; also when it is the only hand in view)
        if SECOND_HAND_KEYS and not SECOND_HAND_GESTURES:
            kh = second
            if main is None:
                others = [h for h in hands if h.hand_side is not None and h.hand_side != self.main_side]
                kh = others[0] if len(others) == 1 else None
            self.keys.update(kh, now, self._k(kh) if kh is not None else 1.0, main_in_view=main is not None,
                             two_fists=two_fists or self.both_fists_since is not None)
            shown = self.keys.display(now)
            if shown:
                side = kh.hand_side if kh is not None and kh.hand_side else "second"
                self.gesture = f"{side.upper()} HAND: {shown}"

        if main is None:                        # main hand briefly gone: hold everything
            self._status(hands, main, rate, frozen=True)
            return
        self._learn_ref(main)

        # --- clicks (main hand; not while it makes a fist or the index finger is folding)
        dm, dr = main.pinch
        side_busy = main.key in self.sides and self.sides[main.key].touching is not None
        if not main.unsure:                     # unreadable finger shapes: keep the current click state
            self.clicks.update(dm, dr, now, suppress=main_fist or side_busy or main.ext[0] < INDEX_STRAIGHT,
                               dragging=self.dragging)
        if self.clicks.pressed:
            self.gesture = f"{self.clicks.pressed.upper()} CLICK"
        elif side_busy and not self.gesture:
            self.gesture = "thumb on finger..."
        elif main_fist and not self.gesture:
            self.gesture = "fist"

        d = self.diag or {"frames": 0, "min_dm": 9.0, "min_dr": 9.0, "busy": 0, "hands": 0,
                          "pressed": set(), "zoomed": 0, "rescued": 0, "k": []}
        d["frames"] += 1
        d["hands"] = max(d["hands"], len(hands))
        d["min_dm"], d["min_dr"] = min(d["min_dm"], dm), min(d["min_dr"], dr)
        d["busy"] += bool(rate)
        d["zoomed"] += any(h.zoomed for h in hands)
        d["rescued"] += any(h.rescued for h in hands)
        d["k"].append(self._k(main))
        if self.clicks.pressed:
            d["pressed"].add(self.clicks.pressed)
        self.diag = d

        # --- cursor (main hand index fingertip). The box shrinks when you are further away, follows the finger
        # when it leaves the box, and fits its size to how far you move; the cursor doesn't jump when it does.
        ix, iy = self._fingertip(main.img[INDEX_TIP])
        old_box = self.box()
        self.k_cursor += (self._k(main) - self.k_cursor) * min(1.0, dt / 1.5)
        pointing = (not main_fist and not main.unsure and main.ext[0] >= INDEX_STRAIGHT
                    and not self.clicks.touching and self.clicks.pressed is None)
        self.boxcam.update((ix, iy), self.k_cursor, now, dt, pointing)
        left, top, right, bottom = self.box()
        if (left, top, right, bottom) != old_box:
            def to_screen(b):
                return (self.sx0 + min(max((ix - b[0]) / (b[2] - b[0]), 0.0), 1.0) * (self.sw - 1),
                        self.sy0 + min(max((iy - b[1]) / (b[3] - b[1]), 0.0), 1.0) * (self.sh - 1))
            (ax, ay), (bx, by) = to_screen(old_box), to_screen((left, top, right, bottom))
            self.cursor.shift(bx - ax, by - ay)
        rx, ry = (ix - left) / (right - left), (iy - top) / (bottom - top)
        nx, ny = min(max(rx, 0.0), 1.0), min(max(ry, 0.0), 1.0)
        # button held: the cursor stays exactly where it clicked until the finger clearly moves (drag)
        if self.clicks.pressed:
            finger = (rx * self.sw, ry * self.sh)     # where the finger points, in screen px
            if self.drag_origin is None:
                self.drag_origin, self.dragging = finger, False
            elif not self.dragging and math.dist(self.drag_origin, finger) > DRAG_START_PX:
                self.dragging = True
        else:
            self.drag_origin, self.dragging = None, False
        # after a click the cursor stays exactly put while a double-click is still possible (Windows needs
        # both clicks within a few pixels), unless the finger clearly moves away
        finger = (rx * self.sw, ry * self.sh)
        if self.clicks.released_at != self.release_seen:
            self.release_seen, self.release_point = self.clicks.released_at, finger
        locked = False
        if self.release_point is not None and self.clicks.in_double_window(now):
            if math.dist(self.release_point, finger) > DRAG_START_PX:
                self.release_point = None
            else:
                locked = True
        side_main = self.sides.get(main.key)
        frozen = (main_fist or main_thumb or max(main.ext) < FIST_CURL or self.clicks.freezing(now)
                  or locked
                  or (self.clicks.pressed is not None and not self.dragging)
                  or (side_main is not None and side_main.touching == "x1"))     # "OK" pinch bends the index
        sx, sy = self.cursor(self.sx0 + nx * (self.sw - 1), self.sy0 + ny * (self.sh - 1), now,
                             hold=frozen, edge=(rx <= 0.0 or rx >= 1.0, ry <= 0.0 or ry >= 1.0))
        if not frozen:
            if (self.last_cursor is None or
                    math.dist(self.last_cursor, (sx, sy)) >= CURSOR_DEADZONE_PX):
                if DIAGNOSTICS and self.last_cursor is not None and math.dist(self.last_cursor, (sx, sy)) > 300:
                    log.info("big cursor move %.0f px (reason: %s, hands %d, speed %.0f px/s)",
                             math.dist(self.last_cursor, (sx, sy)), self.cursor.reason, len(hands),
                             self.cursor.speed)
                self.mouse.move(sx, sy)
                self.last_cursor = (sx, sy)
            if not self.gesture:
                self.gesture = "drag" if self.dragging else "move"
        self._status(hands, main, rate, frozen)

    def _status(self, hands, main, rate, frozen):
        if not self.want_status:
            return
        for h in hands:
            fs = self.fists.get(h.key) or FistScroll()
            state = {"idle": "", "pending": "fist...", "active": "fist" if self.gestures_off else "SCROLL"}[fs.state]
            tv = self.thumbs.get(h.key)
            if tv is not None and tv.busy:
                state = f"THUMB {tv.angle or 0:.0f} deg" + (" VOLUME" if tv.state == "active" else "...")
            if fs.state == "active" and rate:
                state += f" {'down' if rate > 0 else 'up'} {abs(rate):.0f}/s"
            extra = " zoom" if h.zoomed else ""
            extra += " found-again" if h.rescued else ""
            self.status.append(f"{h.role.upper():6s} fingers {' '.join(f'{v:.1f}' for v in h.ext)}  "
                               f"t-mid {h.pinch[0]:.2f}  t-ring {h.pinch[1]:.2f}  "
                               f"t-idx {_num(h.side['x1'])} (2d {thumb_index_2d(h):.2f})  "
                               f"t-ring-base {_num(h.side['x2'])}  "
                               f"size {self._k(h):.2f}{extra}  {state}")
        if main is None:
            other = [h for h in hands if h.hand_side and h.hand_side != self.main_side]
            if other:
                self.status.append(f"your {other[0].hand_side} hand is not the main hand - only it in view, "
                                   "make a fist twice to make it the main hand")
            else:
                self.status.append(f"waiting for your {self.main_side} hand (the main hand)")
        self.status.append(f"button: {self.clicks.pressed or '-'}   "
                           f"cursor {'FROZEN' if frozen else 'moving'}   {self.last_swipe}")
        b = self.boxcam
        fit = (f"{b.sx:.2f} x {b.sy:.2f}" if b.target is not None
               else f"learning your reach {len(b.samples)}/{BOX_FIT_SAMPLES[0]}")
        self.status.append(f"cursor box: size {fit}{'   FOLLOWING your hand' if b.following else ''}")
        if self.ref_palm is None and SCALE_WITH_DISTANCE:
            self.status.append(f"learning your normal hand size... ({len(self.ref_samples)}/45)")
        if self.both_fists_since is not None:
            left_s = max(STOP_HOLD - (self.last_t - self.both_fists_since), 0.0)
            self.status.append(f"BOTH FISTS: gestures {'on' if self.gestures_off else 'off'} in {left_s:.1f} s"
                               " - open a hand to cancel")

    def _fingertip(self, tip: tuple) -> tuple:
        """Index fingertip with one-frame tracking glitches removed: a sudden jump is held back for a frame
        and only accepted if the next frame agrees (real fast movement), otherwise it's dropped."""
        last = self.last_tip
        if last is None:
            self.last_tip = tip
            return tip
        d = math.dist(tip, last)
        if d <= TIP_SPIKE or (self.pending_tip is not None and math.dist(tip, self.pending_tip) < d):
            self.last_tip, self.pending_tip = tip, None
            return tip
        self.pending_tip = tip
        return last

    def pop_diag(self):
        d, self.diag = self.diag, None
        return d

    def do_swipe(self, direction: str, now: float):
        self.clicks.reset(now)
        self.mouse.swipe(SWIPE_ACTION, direction)
        self.last_swipe = f"last swipe: {direction}"
        self.gesture = f"SWIPE {direction}"
        log.info("swipe %s (%s)", direction, SWIPE_ACTION)


# ------------------------------------------------------------------ Windows glue

VK_SHIFT, VK_CONTROL, VK_MENU, VK_TAB, VK_LWIN, VK_LEFT, VK_RIGHT = 0x10, 0x11, 0x12, 0x09, 0x5B, 0x25, 0x27
SWIPE_KEYS = {
    ("apps", "right"): [VK_MENU, VK_TAB],
    ("apps", "left"): [VK_MENU, VK_SHIFT, VK_TAB],
    ("desktops", "right"): [VK_CONTROL, VK_LWIN, VK_RIGHT],
    ("desktops", "left"): [VK_CONTROL, VK_LWIN, VK_LEFT],
    ("monitor", "right"): [VK_LWIN, VK_SHIFT, VK_RIGHT],
    ("monitor", "left"): [VK_LWIN, VK_SHIFT, VK_LEFT],
}


def alt_tab_windows() -> list:
    """Top-level windows the Alt+Tab switcher lists (current virtual desktop), the way Windows picks them:
    visible, not a tool window, not cloaked (other desktop / suspended app), and the window Alt+Tab shows for its
    owner chain (an app with a dialog open is listed once)."""
    import ctypes
    import ctypes.wintypes as wt
    u, dwm = ctypes.windll.user32, ctypes.windll.dwmapi
    u.GetAncestor.restype = u.GetLastActivePopup.restype = wt.HWND
    u.GetAncestor.argtypes = [wt.HWND, ctypes.c_uint]
    u.GetLastActivePopup.argtypes = [wt.HWND]
    found = []

    def listed(h) -> bool:
        if not u.IsWindowVisible(h) or u.GetWindowLongW(h, -20) & 0x80:      # WS_EX_TOOLWINDOW
            return False
        walk, tried = None, u.GetAncestor(h, 3)                             # GA_ROOTOWNER
        while tried != walk:
            walk, tried = tried, u.GetLastActivePopup(tried)
            if u.IsWindowVisible(tried):
                break
        if walk != h:
            return False
        cloaked = ctypes.c_int(0)
        dwm.DwmGetWindowAttribute(h, 14, ctypes.byref(cloaked), 4)         # DWMWA_CLOAKED
        if cloaked.value:
            return False
        cls = ctypes.create_unicode_buffer(64)
        u.GetClassNameW(h, cls, 64)
        return cls.value not in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd")

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def each(h, _):
        if listed(h):
            found.append(h)
        return True
    u.EnumWindows(each, 0)
    return found


class WinMouse:
    _FLAGS = {"left": (0x0002, 0x0004), "right": (0x0008, 0x0010), "middle": (0x0020, 0x0040),
              "x1": (0x0080, 0x0100), "x2": (0x0080, 0x0100)}     # x1 = mouse button 4, x2 = button 5
    _XDATA = {"x1": 1, "x2": 2}

    def __init__(self):
        import ctypes
        ok = False                      # real pixels on scaled displays (every monitor)
        try:
            ok = bool(ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)))
        except Exception:
            pass
        if not ok:
            try:
                ok = ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0
            except Exception:
                pass
        if not ok:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
        self.u = ctypes.windll.user32
        self.left, self.top, self.width, self.height = self.bounds()
        try:
            self.double_click_time = max(self.u.GetDoubleClickTime() / 1000.0, 0.2)   # Windows setting
        except Exception:
            self.double_click_time = 0.5

    def bounds(self) -> tuple:
        """(left, top, width, height) of the area the cursor may use (all monitors or the main one)."""
        if SCREENS == "primary":
            return 0, 0, self.u.GetSystemMetrics(0), self.u.GetSystemMetrics(1)
        return (self.u.GetSystemMetrics(76), self.u.GetSystemMetrics(77),
                self.u.GetSystemMetrics(78), self.u.GetSystemMetrics(79))

    def move(self, x: float, y: float):
        self.u.SetCursorPos(int(round(x)), int(round(y)))

    def button(self, name: str, down: bool):
        self.u.mouse_event(self._FLAGS[name][0 if down else 1], 0, 0, self._XDATA.get(name, 0), 0)

    def wheel(self, delta: int):
        self.u.mouse_event(0x0800, 0, 0, int(delta), 0)

    def hwheel(self, delta: int):
        self.u.mouse_event(0x01000, 0, 0, int(delta), 0)     # MOUSEEVENTF_HWHEEL, positive = right

    @property
    def volume(self):
        if getattr(self, "_volume", None) is None:
            self._volume = WinVolume()
            u = self.u

            def show():                 # volume up + down: Windows shows its volume indicator
                for vk in (0xAF, 0xAE):
                    u.keybd_event(vk, 0, 0, 0)
                    u.keybd_event(vk, 0, 0x2, 0)
            self._volume.show = show
        return self._volume

    _EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E}   # page/home/end/arrows/ins/del

    def key(self, vk: int, down: bool):
        flags = (0x1 if vk in self._EXTENDED else 0) | (0 if down else 0x2)
        self.u.keybd_event(vk, self.u.MapVirtualKeyW(vk, 0) & 0xFF, flags, 0)

    def keys(self, vks: list):
        """A shortcut: keys down in order, then up in reverse order."""
        for vk in vks:
            self.key(vk, True)
            time.sleep(0.01)
        for vk in reversed(vks):
            self.key(vk, False)
            time.sleep(0.01)

    def alt_tab_count(self) -> int | None:
        """How many windows the Alt+Tab switcher lists (None if it can't be told)."""
        try:
            return len(alt_tab_windows())
        except Exception as e:
            log.warning("could not count the Alt+Tab windows: %s", e)
            return None

    def toggle_keyboard(self):
        """Open the Windows on-screen keyboard, or close it when it is open."""
        import ctypes
        self.u.FindWindowW.restype = ctypes.c_void_p
        hwnd = self.u.FindWindowW("OSKMainClass", None)
        if hwnd:
            self.u.PostMessageW(ctypes.c_void_p(hwnd), 0x0112, 0xF060, 0)     # WM_SYSCOMMAND, SC_CLOSE
        else:
            os.startfile(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "osk.exe"))

    def swipe(self, action: str, direction: str):
        keys = SWIPE_KEYS.get((action, direction))
        if not keys:
            return
        for vk in keys:
            self.u.keybd_event(vk, 0, 0x1 if vk in (VK_LEFT, VK_RIGHT) else 0, 0)
            time.sleep(0.01)
        for vk in reversed(keys):
            self.u.keybd_event(vk, 0, (0x1 if vk in (VK_LEFT, VK_RIGHT) else 0) | 0x2, 0)
            time.sleep(0.01)


def message_box(text: str):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, text, "Hand Mouse", 0x10)
    except Exception:
        print(text, file=sys.stderr)


def beep(freq: int, ms: int = 90):
    if not SOUNDS:
        return
    def _beep():
        try:
            import winsound
            winsound.Beep(freq, ms)
        except Exception:
            pass
    threading.Thread(target=_beep, daemon=True).start()


_mutex = None


def single_instance(wait: float = 0.0) -> bool:
    """Only one copy may run. `wait` gives a restarting copy time to let the old one exit."""
    global _mutex
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        deadline = time.monotonic() + wait
        while True:
            h = k32.CreateMutexW(None, False, "Global\\HandMouseSingleInstance")
            if k32.GetLastError() != 183:   # ERROR_ALREADY_EXISTS
                _mutex = h
                return True
            k32.CloseHandle(h)
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.2)
    except Exception:
        return True


SHOW_EVENT = "Local\\HandMouseShowView"


def signal_running_instance() -> bool:
    """Ask the already running Hand Mouse to show its camera view (used when the icon is double-clicked
    while it runs)."""
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        k32.OpenEventW.restype = wintypes.HANDLE
        k32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
        k32.SetEvent.argtypes = [wintypes.HANDLE]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        h = k32.OpenEventW(0x0002, False, SHOW_EVENT)      # EVENT_MODIFY_STATE
        if not h:
            return False
        k32.SetEvent(h)
        k32.CloseHandle(h)
        return True
    except Exception:
        return False


def listen_for_show_requests(on_show, stop_evt):
    """Background thread: when the desktop icon is double-clicked while running, show the camera view."""
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        k32.CreateEventW.restype = wintypes.HANDLE
        k32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k32.WaitForSingleObject.restype = wintypes.DWORD
        h = k32.CreateEventW(None, False, False, SHOW_EVENT)
        if not h:
            return
        while not stop_evt.is_set():
            if k32.WaitForSingleObject(h, 500) == 0:
                on_show()
        k32.CloseHandle(h)
    except Exception:
        log.exception("show-request listener stopped")


def release_instance():
    global _mutex
    if _mutex:
        try:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(_mutex)
        except Exception:
            pass
        _mutex = None


def _pythonw() -> str:
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return pyw if os.path.exists(pyw) else sys.executable


def make_shortcut(path: str, description: str):
    """Create a Windows shortcut at `path` that starts Hand Mouse in the background."""
    icon = os.path.join(HERE, "hand_mouse.ico")

    def q(text: str) -> str:   # PowerShell single-quoted string
        return "'" + text.replace("'", "''") + "'"

    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut({q(path)});"
          f"$s.TargetPath={q(_pythonw())};"
          f"$s.Arguments={q(chr(34) + SCRIPT + chr(34))};"
          f"$s.WorkingDirectory={q(HERE)};"
          + (f"$s.IconLocation={q(icon)};" if os.path.exists(icon) else "")
          + f"$s.Description={q(description)};$s.Save()")
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                    "-Command", ps], creationflags=0x08000000, timeout=60, check=True)


def desktop_folder() -> str:
    try:
        import ctypes
        from ctypes import wintypes
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf)   # CSIDL_DESKTOPDIRECTORY
        if buf.value:
            return buf.value
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Desktop")


def create_desktop_shortcut(force: bool = False):
    """Put a 'Hand Mouse' icon on the desktop that starts the app in the background. Done once;
    delete the icon and it won't come back (run with --create-shortcut to make it again)."""
    marker = os.path.join(HERE, ".shortcut_created")
    if os.path.exists(marker) and not force:
        return
    make_shortcut(os.path.join(desktop_folder(), "Hand Mouse.lnk"),
                  "Control the mouse with your hands (Ctrl+Alt+Q quits)")
    with open(marker, "w") as f:
        f.write("created\n")
    log.info("desktop shortcut created")


def startup_shortcut_path() -> str:
    return os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs",
                        "Startup", "Hand Mouse.lnk")


def autostart_enabled() -> bool:
    return os.path.exists(startup_shortcut_path())


def set_autostart(on: bool):
    path = startup_shortcut_path()
    if on:
        make_shortcut(path, "Start Hand Mouse when Windows starts")
        log.info("start with Windows: on")
    elif os.path.exists(path):
        os.remove(path)
        log.info("start with Windows: off")


STATE_PATH = os.path.join(HERE, "hand_mouse_state.json")


def load_state() -> dict:
    try:
        import json
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(**values):
    try:
        import json
        state = load_state()
        state.update(values)
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=1)
    except Exception:
        log.exception("could not save settings")


HELP_PATH = os.path.join(HERE, "gestures.html")
HELP_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Hand Mouse gestures</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 :root{--bg:#f6f7fb;--card:#fff;--ink:#1d2433;--muted:#5b6475;--accent:#2f62d8;--line:#e3e6ee}
 @media (prefers-color-scheme:dark){:root{--bg:#14161c;--card:#1d2029;--ink:#e8ebf2;--muted:#a3abbb;--accent:#7aa2ff;--line:#2c3140}}
 body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 "Segoe UI",system-ui,sans-serif}
 main{max-width:860px;margin:0 auto;padding:28px 16px 48px}
 h1{font-size:28px;margin:0 0 4px} p.lead{color:var(--muted);margin:0 0 24px}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
 .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}
 .card h2{font-size:17px;margin:0 0 6px;color:var(--accent)} .card p{margin:0;color:var(--ink)}
 h3{margin:30px 0 10px;font-size:19px} ul{margin:0;padding-left:20px} li{margin:4px 0}
 kbd{background:var(--card);border:1px solid var(--line);border-bottom-width:2px;border-radius:5px;padding:0 6px;font:13px Consolas,monospace}
</style></head><body><main>
<h1>Hand Mouse</h1>
<p class="lead">Your <b>main hand</b> is your right hand when both hands are in view, otherwise whichever hand is in view.</p>
<div class="grid">
 <div class="card"><h2>Move the cursor</h2><p>Point with the index finger of your main hand. Slow movements are precise, fast movements cover the whole screen.</p></div>
 <div class="card"><h2>Left click</h2><p>Touch your thumb to your <b>middle</b> fingertip. Keep touching and move to drag.</p></div>
 <div class="card"><h2>Right click</h2><p>Touch your thumb to your <b>ring</b> fingertip.</p></div>
 <div class="card"><h2>Middle click</h2><p>Touch your thumb to your middle <b>and</b> ring fingertips together.</p></div>
 <div class="card"><h2>Mouse button 4 (Back)</h2><p>Touch your thumb tip to your <b>index fingertip</b> (an "OK" sign), other fingers up.</p></div>
 <div class="card"><h2>Mouse button 5 (Forward)</h2><p>Palm towards the camera, fingers up. Fold your thumb across the palm onto the <b>base of your ring / little finger</b>.</p></div>
 <div class="card"><h2>Volume</h2><p><b>Thumbs-up</b> (fingers folded, thumb out) and hold it a moment. Thumb straight up = 100%. Turn your hand until the thumb points down to lower the volume step by step to 0%. Tuck the thumb in to stop.</p></div>
 <div class="card"><h2>Scroll</h2><p>Make a <b>fist</b>. Move the fist down to scroll down, up to scroll up, left / right to scroll sideways. The further from where you closed it, the faster. Open the hand to stop.</p></div>
 <div class="card"><h2>Gestures off / on</h2><p>Hold <b>both</b> hands as fists for a second (beep first). Gestures turn off (orange badge on the tray icon): the cursor and all gestures ignore your hands, except two fists, which turn them back on the same way. To stop the camera completely, click the tray icon.</p></div>
</div>
<h3>Left hand: keyboard shortcuts</h3>
<p class="lead">With your other hand (the left one). A pinch acts when the thumb lets go. These are the default shortcuts; they can be changed in <code>SECOND_KEYS</code> at the top of hand_mouse.py.</p>
<div class="grid">
 <div class="card"><h2>Switch window (Alt+Tab)</h2><p>Thumb on the <b>index</b> fingertip and let go: back to the last window. <b>Hold</b> it: the window switcher stays open; move the hand left / right to pick a window (it stops at the first and last one), let go to switch to it.</p></div>
 <div class="card"><h2>Copy (Ctrl+C)</h2><p>Thumb on the <b>middle</b> fingertip.</p></div>
 <div class="card"><h2>Paste (Ctrl+V)</h2><p>Thumb on the <b>ring</b> fingertip.</p></div>
 <div class="card"><h2>Undo / redo (Ctrl+Z / Ctrl+Y)</h2><p>Palm to the camera, thumb across the palm on the <b>base of the little finger</b> (like button 5). Once = undo, <b>twice quickly</b> = redo.</p></div>
 <div class="card"><h2>Print Screen</h2><p>Thumb on the <b>middle and ring</b> fingertips together.</p></div>
 <div class="card"><h2>Voice typing / keyboard</h2><p>Thumb on the <b>index and middle</b> fingertips together: voice typing on / off (Win+H). <b>Twice quickly</b>: the on-screen keyboard opens / closes; type on it with the right hand.</p></div>
 <div class="card"><h2>Esc</h2><p>Make a <b>fist</b> (thumb tucked in): Esc comes once it has been closed a moment, no need to open it. Only when it is the only fist in view (two fists = gestures off / on). With only the left hand in view hold it about half a second (two quick fists would make the left hand the main hand instead).</p></div>
 <div class="card"><h2>Play / pause, tracks</h2><p><b>Thumbs-up</b>, then tuck the thumb into the fist: play / pause. Thumbs-up moved <b>right</b>: next track, <b>left</b>: previous track (a longer move skips more).</p></div>
</div>
<h3>Main hand</h3>
<p>Your <b>right hand</b> moves the cursor and clicks; the left one gives keyboard shortcuts (below). To use your <b>left hand</b> instead: show only the left hand and make a <b>fist twice</b> quickly. The app remembers it, also after a restart, until your right hand does the same.</p>
<h3>Tray icon (next to the clock)</h3>
<ul><li><b>Left-click</b>: stop / resume tracking, camera off (red badge = stopped, orange badge = gestures off).</li>
<li><b>Right-click</b>: Camera &amp; log window, Gestures on, Stop/Resume, Gestures help, Start with Windows, Re-learn my hand size, Close.</li></ul>
<h3>Tips</h3>
<ul><li>Good light on your hands helps more than anything else.</li>
<li>You can sit further back: small hands are read from a zoomed view, and movements scale with distance.</li>
<li>If gestures feel too big or too small after you change where you sit, use <b>Re-learn my hand size</b> and hold your open hand up for a few seconds.</li>
<li>The cursor box (grey rectangle in the camera window) follows your hand when your finger stays outside it, and slowly fits its size to how far you usually move. The cursor doesn't jump when it does.</li>
<li><b>Camera &amp; log window</b> shows what the app sees (green = main hand, orange = second hand), what it is doing right now, and a log of every click, button, scroll and swipe it recognised. <kbd>P</kbd> stops/resumes, <kbd>Esc</kbd> closes the window (the app keeps running).</li>
<li><b>Debug: save a picture of every gesture</b> (tray menu, off by default): each recognised gesture saves a strip of camera frames to the <code>debug</code> folder, to find out why a gesture misfired.</li>
<li>Keys: <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>H</kbd> stop/resume, <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>C</kbd> re-learn hand size, <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>Q</kbd> quit.</li></ul>
</main></body></html>
"""


def open_help():
    try:
        with open(HELP_PATH, "w", encoding="utf-8") as f:
            f.write(HELP_HTML)
        os.startfile(HELP_PATH)
    except Exception:
        log.exception("could not open the gestures help")


def ensure_package(module: str, package: str) -> bool:
    """Import `module`, installing `package` with pip first if it is missing (small, one time)."""
    try:
        __import__(module)
        return True
    except ImportError:
        pass
    py = os.path.join(os.path.dirname(sys.executable), "python.exe")
    if not os.path.exists(py):
        py = sys.executable
    log.info("installing %s ...", package)
    try:
        subprocess.run([py, "-m", "pip", "install", "--disable-pip-version-check", package],
                       creationflags=0x08000000, timeout=300, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        __import__(module)
        log.info("%s installed", package)
        return True
    except Exception:
        log.exception("could not install %s", package)
        return False


class TrayIcon:
    """Icon in the Windows notification area (next to the clock).
    Left-click: stop / resume tracking.  Right-click: menu."""

    def __init__(self, is_paused, on_toggle, on_close, view_shown=None, on_view=None, on_relearn=None,
                 gestures_off=None, on_gestures=None, debug_on=None, on_debug=None):
        self.is_paused, self.on_toggle, self.on_close = is_paused, on_toggle, on_close
        self.debug_on = debug_on or (lambda: False)
        self.on_debug = on_debug or (lambda: None)
        self.gestures_off = gestures_off or (lambda: False)
        self.on_gestures = on_gestures or (lambda: None)
        self.view_shown = view_shown or (lambda: False)
        self.on_view = on_view or (lambda: None)
        self.on_relearn = on_relearn or (lambda: None)
        self.icon = None
        if not TRAY_ICON:
            return
        try:
            if not ensure_package("pystray", "pystray"):
                return
            import pystray
            item = pystray.MenuItem
            self.images = self._make_images()

            def toggle_autostart(icon, it):
                try:
                    set_autostart(not autostart_enabled())
                except Exception:
                    log.exception("could not change start with Windows")
                self.refresh()

            menu = pystray.Menu(
                item(lambda it: "Hand Mouse: " + self._state_text(), lambda icon, it: None, enabled=False),
                pystray.Menu.SEPARATOR,
                item("Camera && log window", lambda icon, it: self.on_view(), checked=lambda it: self.view_shown()),
                item("Gestures on (two fists = on / off)", lambda icon, it: self.on_gestures(),
                     checked=lambda it: not self.gestures_off(), enabled=lambda it: not self.is_paused()),
                item(lambda it: "Resume tracking" if self.is_paused() else "Stop tracking",
                     lambda icon, it: self.on_toggle(), default=True),
                item("Gestures help", lambda icon, it: open_help()),
                pystray.Menu.SEPARATOR,
                item("Start with Windows", toggle_autostart, checked=lambda it: autostart_enabled()),
                item("Re-learn my hand size", lambda icon, it: self.on_relearn()),
                item("Debug: save a picture of every gesture", lambda icon, it: self.on_debug(),
                     checked=lambda it: self.debug_on()),
                pystray.Menu.SEPARATOR,
                item("Close Hand Mouse", lambda icon, it: self.on_close()),
            )
            self.icon = pystray.Icon("HandMouse", self.images["on"], self._title(), menu)
            threading.Thread(target=self._run, daemon=True, name="tray").start()
        except Exception:
            log.exception("could not create the tray icon")
            self.icon = None

    def _run(self):
        try:
            self.icon.run()
        except Exception:
            log.exception("tray icon stopped with an error")

    def _state(self) -> str:
        if self.is_paused():
            return "paused"
        return "sleep" if self.gestures_off() else "on"

    def _state_text(self) -> str:
        return {"paused": "stopped", "sleep": "gestures off (two fists to turn on)", "on": "tracking"}[self._state()]

    def _title(self) -> str:
        return {"paused": "Hand Mouse - stopped (click to resume)",
                "sleep": "Hand Mouse - gestures off: two fists turn them on (click: stop camera)",
                "on": "Hand Mouse - tracking (click to stop)"}[self._state()]

    @staticmethod
    def _make_images() -> dict:
        from PIL import Image, ImageDraw, ImageOps
        path = os.path.join(HERE, "hand_mouse.ico")
        try:
            on = Image.open(path).convert("RGBA").resize((64, 64), Image.LANCZOS)
        except Exception:     # fallback: plain blue tile with a white dot
            on = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            d = ImageDraw.Draw(on)
            d.rounded_rectangle([2, 2, 62, 62], radius=14, fill=(45, 95, 220, 255))
            d.ellipse([20, 20, 44, 44], fill=(255, 255, 255, 255))
        def badged(color):
            grey = ImageOps.grayscale(on.convert("RGB")).convert("RGBA")
            grey = Image.blend(grey, Image.new("RGBA", grey.size, (128, 128, 128, 255)), 0.35)
            grey.putalpha(on.getchannel("A"))
            d = ImageDraw.Draw(grey)        # pause badge
            d.ellipse([30, 30, 63, 63], fill=color, outline=(255, 255, 255, 255), width=3)
            d.rectangle([40, 39, 44, 54], fill=(255, 255, 255, 255))
            d.rectangle([49, 39, 53, 54], fill=(255, 255, 255, 255))
            return grey
        return {"on": on, "paused": badged((210, 45, 45, 255)), "sleep": badged((235, 150, 20, 255))}

    def refresh(self):
        if self.icon is None:
            return
        try:
            self.icon.icon = self.images[self._state()]
            self.icon.title = self._title()
            self.icon.update_menu()
        except Exception:
            log.exception("could not update the tray icon")

    def notify(self, text: str):
        if self.icon is None:
            return
        try:
            self.icon.notify(text, "Hand Mouse")
        except Exception:
            pass

    def stop(self):
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None


def ensure_model():
    if os.path.exists(MODEL_PATH):
        return
    log.info("downloading hand model...")
    tmp = MODEL_PATH + ".part"
    urllib.request.urlretrieve(MODEL_URL, tmp)
    os.replace(tmp, MODEL_PATH)
    log.info("model saved to %s", MODEL_PATH)


def create_landmarker(video: bool = True, num_hands: int = 2, detection: float | None = None):
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision
    with open(MODEL_PATH, "rb") as f:   # buffer avoids problems with non-English folder names
        model = f.read()
    opts = vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_buffer=model),
        running_mode=vision.RunningMode.VIDEO if video else vision.RunningMode.IMAGE,
        num_hands=num_hands,
        min_hand_detection_confidence=DETECTION_CONFIDENCE if detection is None else detection,
        min_hand_presence_confidence=PRESENCE_CONFIDENCE if detection is None else max(PRESENCE_CONFIDENCE, detection),
        min_tracking_confidence=TRACKING_CONFIDENCE,
    )
    return vision.HandLandmarker.create_from_options(opts)


def result_to_hands(res, aspect: float = 0.5625, x0: float = 0.0, y0: float = 0.0,
                    sx: float = 1.0, sy: float = 1.0) -> list[Hand]:
    """MediaPipe result -> Hands. For a crop, (x0, y0, sx, sy) map crop coordinates back to the picture."""
    hands = []
    for i, lms in enumerate(res.hand_landmarks):
        label = "Right"
        if res.handedness and i < len(res.handedness) and res.handedness[i]:
            label = res.handedness[i][0].category_name
        if SWAP_HANDEDNESS:
            label = "Left" if label == "Right" else "Right"
        world = res.hand_world_landmarks[i]
        hands.append(Hand(label, [(x0 + p.x * sx, y0 + p.y * sy) for p in lms],
                          [(p.x, p.y, p.z) for p in world], aspect=aspect))
    return hands


def _overlap(a: Hand, b: Hand) -> float:
    """Intersection over union of the two hands' outlines."""
    def box(h):
        xs = [p[0] for p in h.img]
        ys = [p[1] * h.aspect for p in h.img]
        return min(xs), min(ys), max(xs), max(ys)
    ax0, ay0, ax1, ay1 = box(a)
    bx0, by0, bx1, by1 = box(b)
    iw, ih = max(0.0, min(ax1, bx1) - max(ax0, bx0)), max(0.0, min(ay1, by1) - max(ay0, by0))
    inter = iw * ih
    area_a, area_b = (ax1 - ax0) * (ay1 - ay0), (bx1 - bx0) * (by1 - by0)
    union = area_a + area_b - inter
    iou = inter / union if union > 0 else 0.0
    inside = inter / min(area_a, area_b) if min(area_a, area_b) > 0 else 0.0
    return max(iou, 0.6 * inside)       # also catches a small detection sitting inside a bigger one


def _inside(h: Hand) -> bool:
    """False for a 'hand' that is mostly outside the picture (typically a false detection at the edge)."""
    out = sum(1 for x, y in h.img if not (-0.02 <= x <= 1.02 and -0.02 <= y <= 1.02))
    return out <= 5


def dedupe(hands: list[Hand]) -> list[Hand]:
    """The tracker sometimes reports one hand twice (two detections on top of each other), which would
    look like a phantom second hand. Keep one of each overlapping pair (the zoomed, more accurate one)."""
    out: list[Hand] = []
    for h in sorted(hands, key=lambda h: (not h.zoomed, -h.size)):
        if all(_overlap(h, o) < DUPLICATE_OVERLAP and
               math.dist(h.center, o.center) > 0.5 * max(h.size, o.size) for o in out):
            out.append(h)
    return out


class HandFinder:
    """Second hand detector (HaGRIDv2 YOLOv10n hands, exported to ONNX). Returns boxes
    [(x0, y0, x1, y1, score)] in picture fractions."""

    def __init__(self, path: str, size: int = 320, conf: float = 0.35):
        import cv2
        import numpy as np
        import onnxruntime as ort
        self.cv2, self.np = cv2, np
        so = ort.SessionOptions()
        so.intra_op_num_threads = 2
        self.session = ort.InferenceSession(path, so, providers=["CPUExecutionProvider"])
        self.input = self.session.get_inputs()[0].name
        self.size, self.conf = size, conf

    def __call__(self, rgb) -> list:
        cv2, np = self.cv2, self.np
        H, W = rgb.shape[:2]
        S = self.size
        k = S / max(H, W)
        nw, nh = int(round(W * k)), int(round(H * k))
        img = np.full((S, S, 3), 114, np.uint8)
        img[:nh, :nw] = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)
        x = img.astype(np.float32).transpose(2, 0, 1)[None] / 255.0
        out = self.session.run(None, {self.input: x})[0][0]      # (4 + classes, N): cx, cy, w, h, scores
        scores = out[4:].max(0)
        keep = scores >= self.conf
        if not keep.any():
            return []
        cx, cy, w, h, scores = out[0][keep], out[1][keep], out[2][keep], out[3][keep], scores[keep]
        boxes = [[float(a - c / 2), float(b - d / 2), float(c), float(d)] for a, b, c, d in zip(cx, cy, w, h)]
        idx = cv2.dnn.NMSBoxes(boxes, scores.tolist(), self.conf, 0.45)
        result = []
        for i in np.array(idx).flatten():
            bx, by, bw, bh = boxes[i]
            result.append((bx / k / W, by / k / H, (bx + bw) / k / W, (by + bh) / k / H, float(scores[i])))
        return result


def create_hand_finder():
    path = os.path.join(HERE, HAND_FINDER_FILE)
    if not HAND_FINDER or not os.path.exists(path):
        return None
    if not ensure_package("onnxruntime", "onnxruntime"):
        return None
    try:
        finder = HandFinder(path, conf=HAND_FINDER_CONFIDENCE)
        log.info("second hand finder loaded (%s)", HAND_FINDER_FILE)
        return finder
    except Exception:
        log.exception("could not load the second hand finder")
        return None


class HandSensor:
    """Finds hands in a camera frame.
    1. The video tracker runs on the whole picture (fast, follows hands frame to frame).
    2. A hand that looks small (far away) is re-read from a zoomed-in crop around it: the tracker's
       finger shapes become unreliable when a hand is small, the zoomed re-read keeps them accurate.
    3. A hand the tracker just lost is searched for in a zoomed crop where it was.
    4. With no hand in view, the middle of the picture is checked zoomed every few frames, so a far-away
       hand is noticed in the first place."""

    def __init__(self, video_lm, image_lm=None, finder_lm=None, hand_finder=None):
        import cv2
        import numpy as np
        import mediapipe as mp
        self.cv2, self.np, self.mp = cv2, np, mp
        self.video, self.image = video_lm, image_lm
        self.finder = finder_lm or image_lm     # stricter model for hands not seen by the tracker
        self.hand_finder = hand_finder          # HandFinder (second detector) or None
        self.finder_frames = 0
        self.finder_hit = False
        self.recent: list[tuple] = []       # (center, size, time) of hands seen lately
        self.gain = None                    # per-area colour gains of the current frame (white-balanced view)
        self.view = "normal"                # what the hand model sees: "normal", "swapped" (red <-> blue), "balanced"
        self.lost_frames = 0
        self.view_frames = 0
        self.tries = 0
        self.idle_frames = 0
        self.ms_total = 0.0
        self.frames = 0

    def process(self, rgb, ts_ms: int, now: float) -> list[Hand]:
        t0 = time.perf_counter()
        H, W = rgb.shape[:2]
        aspect = H / W
        small = rgb
        if W > DETECT_WIDTH:
            small = self.cv2.resize(rgb, (DETECT_WIDTH, int(round(H * DETECT_WIDTH / W))),
                                    interpolation=self.cv2.INTER_AREA)
        plain = small
        if COLOR_FALLBACK:
            self._measure_light(small)
            small = self._colors(small, self.view, 0.0, 0.0, 1.0, 1.0)
        res = self.video.detect_for_video(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=small), ts_ms)
        hands = result_to_hands(res, aspect)
        if COLOR_FALLBACK and self.image is not None:
            self.lost_frames = 0 if hands else self.lost_frames + 1
            self.view_frames += 1
            view = None
            if self.lost_frames % 3 == 2:   # nothing found for a moment: try the picture in other colours
                others = [v for v in ("normal", "swapped", "balanced") if v != self.view]
                view = others[self.tries % len(others)]
                self.tries += 1
            elif self.view != "normal" and self.view_frames % 60 == 0:
                view = "normal"             # every few seconds: do normal colours work again?
            if view is not None:
                try:
                    found = result_to_hands(self.image.detect(self.mp.Image(     # whole picture: lenient is safe
                        image_format=self.mp.ImageFormat.SRGB,
                        data=self._colors(plain, view, 0.0, 0.0, 1.0, 1.0))), aspect)
                except Exception:
                    found = []
                if found:
                    self.view, self.lost_frames, self.view_frames = view, 0, 0
                    log.info("coloured light: hands now found in the %s picture",
                             {"normal": "normal", "swapped": "red/blue swapped", "balanced": "white-balanced"}[view])
                    if not hands:
                        hands = found
        if not hands and self.hand_finder is not None and self.image is not None:
            self.finder_frames += 1
            if self.finder_hit or self.finder_frames % max(HAND_FINDER_EVERY, 1) == 1 % max(HAND_FINDER_EVERY, 1):
                hands = self._find_with_finder(rgb)     # every frame while it is the one finding the hand
                self.finder_hit = bool(hands)
        else:
            self.finder_frames, self.finder_hit = 0, False
        if self.image is not None and ZOOM_ENABLED:
            for i, h in enumerate(hands):
                if h.found_by_finder:
                    continue
                if h.size < ZOOM_BELOW:
                    z = self._read_crop(rgb, h.center, h.size * ZOOM_CROP, near=h.center, max_d=max(h.size, 0.03))
                    if z is None:       # second try with more of the surroundings in view
                        z = self._read_crop(rgb, h.center, h.size * ZOOM_CROP * 1.7, near=h.center,
                                            max_d=max(h.size, 0.03))
                    if z is not None:
                        z.zoomed = True
                        hands[i] = z
                    else:
                        h.unsure = True
            live = [r for r in self.recent if now - r[2] <= RESCUE_TIME]
            missing = [r for r in live if all(math.dist(r[0], h.center) > max(r[1], 0.05) for h in hands)]
            if missing and len(hands) < 2:
                r = max(missing, key=lambda r: r[2])
                z = self._read_crop(rgb, r[0], max(r[1] * ZOOM_CROP, 0.15), near=r[0], max_d=max(r[1] * 1.5, 0.1),
                                    lm=self.finder)
                if z is not None and all(math.dist(z.center, h.center) > 0.05 for h in hands):
                    z.zoomed = z.rescued = True
                    hands.append(z)
            if not hands and not live:
                self.idle_frames += 1
                if self.idle_frames % SCAN_EVERY == 0:
                    # look at one of three zoomed spots across the middle of the picture, in turn
                    spot = (self.idle_frames // SCAN_EVERY) % 3
                    cx = CURSOR_BOX_CENTER_X + (spot - 1) * 0.16
                    z = self._read_crop(rgb, (cx, CURSOR_BOX_CENTER_Y + 0.05), 0.32, near=None, lm=self.finder)
                    if z is not None:
                        z.zoomed = z.rescued = True
                        hands.append(z)
            else:
                self.idle_frames = 0
        hands = [h for h in dedupe(hands) if _inside(h)]
        keep = [r for r in self.recent if now - r[2] <= RESCUE_TIME
                and all(math.dist(r[0], h.center) > max(r[1], 0.05) for h in hands)]
        self.recent = [(h.center, h.size, now) for h in hands] + keep
        self.ms_total += (time.perf_counter() - t0) * 1000
        self.frames += 1
        return hands

    def _measure_light(self, img):
        """Colour of the light in each area of the picture -> per-area gains that make it neutral."""
        cv2, np = self.cv2, self.np
        tiny = cv2.resize(img, BALANCE_GRID, interpolation=cv2.INTER_AREA).astype(np.float32) + 1.0
        if min(BALANCE_GRID) > 2:
            tiny = cv2.GaussianBlur(tiny, (0, 0), 2)
        else:
            tiny = tiny.reshape(BALANCE_GRID[1], BALANCE_GRID[0], 3)
        gain = np.clip(tiny.mean(axis=2, keepdims=True) / tiny, 0.33, 3.0)
        self.gain = cv2.resize(gain, (320, 180), interpolation=cv2.INTER_LINEAR)

    def _colors(self, img, view: str, fx0: float, fy0: float, fx1: float, fy1: float):
        """img (the part (fx0, fy0)-(fx1, fy1) of the picture) as the hand model should see it."""
        if view == "swapped":
            return self.np.ascontiguousarray(img[:, :, ::-1])
        if view == "balanced":
            return self._balance(img, fx0, fy0, fx1, fy1)
        return img

    def _balance(self, img, fx0: float, fy0: float, fx1: float, fy1: float):
        """img = the part (fx0, fy0)-(fx1, fy1) of the picture (fractions); returns it white-balanced."""
        if self.gain is None:
            return img
        cv2, np = self.cv2, self.np
        gh, gw = self.gain.shape[:2]
        x0, y0 = min(int(fx0 * gw), gw - 1), min(int(fy0 * gh), gh - 1)
        x1, y1 = max(int(round(fx1 * gw)), x0 + 1), max(int(round(fy1 * gh)), y0 + 1)
        g = cv2.resize(self.gain[y0:y1, x0:x1], (img.shape[1], img.shape[0]), interpolation=cv2.INTER_LINEAR)
        return np.ascontiguousarray(np.clip(img.astype(np.float32) * g, 0, 255).astype(np.uint8))

    def _find_with_finder(self, rgb) -> list:
        """Ask the second hand finder where hands are, and read each one with the hand model (trying the other
        colour views too, and switching to the one that works)."""
        try:
            boxes = self.hand_finder(rgb)
        except Exception:
            log.exception("hand finder failed; switching it off")
            self.hand_finder = None
            return []
        H, W = rgb.shape[:2]
        found = []
        for x0, y0, x1, y1, score in sorted(boxes, key=lambda b: -b[4])[:2]:
            center = ((x0 + x1) / 2, (y0 + y1) / 2)
            side = max(x1 - x0, (y1 - y0) * H / W) * 2.2
            views = [self.view] + ([v for v in ("swapped", "normal", "balanced") if v != self.view]
                                   if COLOR_FALLBACK else [])
            for view in views:
                z = self._read_crop(rgb, center, side, near=center, max_d=max(x1 - x0, 0.05), view=view)
                if z is not None:
                    if view != self.view:
                        self.view, self.view_frames = view, 0
                        log.info("coloured light: hands now found in the %s picture", view)
                    z.zoomed = z.rescued = z.found_by_finder = True
                    if all(math.dist(z.center, h.center) > 0.05 for h in found):
                        found.append(z)
                    break
        return found

    def _read_crop(self, rgb, center, side_frac, near=None, max_d=1.0, lm=None, view=None):
        """Run the hand model on a square crop (side = side_frac of the picture width) scaled up to
        ZOOM_INPUT pixels; returns the hand nearest `near`, mapped back to picture coordinates."""
        cv2, np = self.cv2, self.np
        H, W = rgb.shape[:2]
        side = int(min(max(side_frac * W, 96), min(W, H)))
        x0 = int(round(center[0] * W - side / 2))
        y0 = int(round(center[1] * H - side / 2))
        x0, y0 = min(max(x0, 0), W - side), min(max(y0, 0), H - side)
        crop = rgb[y0:y0 + side, x0:x0 + side]
        crop = cv2.resize(crop, (ZOOM_INPUT, ZOOM_INPUT),
                          interpolation=cv2.INTER_LINEAR if side < ZOOM_INPUT else cv2.INTER_AREA)
        if COLOR_FALLBACK:
            crop = self._colors(crop, view or self.view, x0 / W, y0 / H, (x0 + side) / W, (y0 + side) / H)
        try:
            img = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=np.ascontiguousarray(crop))
            res = (lm or self.image).detect(img)
        except Exception:
            log.exception("zoomed hand read failed")
            return None
        found = result_to_hands(res, H / W, x0 / W, y0 / H, side / W, side / H)
        if not found:
            return None
        ref = near if near is not None else center
        best = min(found, key=lambda h: math.dist(h.center, ref))
        if near is not None and math.dist(best.center, near) > max_d:
            return None
        return best

    def avg_ms(self) -> float:
        v = self.ms_total / max(self.frames, 1)
        self.ms_total, self.frames = 0.0, 0
        return v


class Camera:
    """Reads camera frames in a background thread, so waiting for the next frame overlaps with processing
    the current one, and the newest frame is always used."""

    def __init__(self, cap, name: str = ""):
        self.cap, self.name = cap, name
        self.frame = None
        self.seq = 0
        self.last_read = 0
        self.failed = False
        self.cond = threading.Condition()
        self.stop_flag = False
        self.thread = threading.Thread(target=self._run, daemon=True, name="camera")
        self.thread.start()

    def _run(self):
        while not self.stop_flag:
            ok, frame = self.cap.read()
            with self.cond:
                if not ok or frame is None:
                    self.failed = True
                    self.cond.notify_all()
                    return
                self.frame, self.seq = frame, self.seq + 1
                self.cond.notify_all()

    def read(self, timeout: float = 2.0):
        """The newest frame not returned before (waits for it). (False, None) if the camera stopped."""
        with self.cond:
            end = time.monotonic() + timeout
            while self.seq == self.last_read and not self.failed:
                left = end - time.monotonic()
                if left <= 0:
                    return False, None
                self.cond.wait(left)
            if self.seq == self.last_read:
                return False, None
            self.last_read = self.seq
            return True, self.frame

    def measure_fps(self, seconds: float = 1.2) -> float:
        """Frames per second actually delivered (after a short warm-up)."""
        ok, _ = self.read(timeout=4.0)
        if not ok:
            return 0.0
        time.sleep(0.3)
        start_seq, t0 = self.seq, time.monotonic()
        time.sleep(seconds)
        return (self.seq - start_seq) / (time.monotonic() - t0)

    def size(self) -> tuple:
        f = self.frame
        return (f.shape[1], f.shape[0]) if f is not None else (0, 0)

    def release(self):
        self.stop_flag = True
        self.thread.join(timeout=2.0)
        try:
            self.cap.release()
        except Exception:
            pass


def _open_capture(cv2, backend, w: int, h: int):
    cap = cv2.VideoCapture(CAMERA_INDEX, backend) if backend is not None else cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        cap.release()
        return None
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))   # needed for HD at full speed on most webcams
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def open_camera(cv2, state: dict | None = None, notify=None, verify: bool = True):
    """Open the camera in the sharpest mode that is still fast. The modes are tested once (a few seconds) and
    the result is remembered; it is tested again (at most once a day) if the remembered mode got much slower."""
    state = state if state is not None else {}
    backends = {"dshow": getattr(cv2, "CAP_DSHOW", None), "msmf": getattr(cv2, "CAP_MSMF", None)}
    backends = {k: v for k, v in backends.items() if v is not None} or {"default": None}
    modes = [(w, h) for w, h in CAMERA_MODES if w <= CAMERA_WIDTH] or [(CAMERA_WIDTH, CAMERA_HEIGHT)]

    def try_mode(bname, w, h):
        cap = _open_capture(cv2, backends.get(bname), w, h)
        if cap is None:
            return None, 0.0
        cam = Camera(cap, f"{bname} {w}x{h}")
        fps = cam.measure_fps()
        aw, ah = cam.size()
        log.info("camera test: %s asked %dx%d, got %dx%d at %.1f fps", bname, w, h, aw, ah, fps)
        if fps <= 0:
            cam.release()
            return None, 0.0
        return cam, fps

    saved = state.get("camera")
    if saved and saved.get("backend") in backends and not verify:
        cap = _open_capture(cv2, backends.get(saved["backend"]), saved["w"], saved["h"])   # resume: no test
        if cap is not None:
            log.info("camera: %s %dx%d", saved["backend"], saved["w"], saved["h"])
            return Camera(cap, f"{saved['backend']} {saved['w']}x{saved['h']}")
    if saved and saved.get("backend") in backends:
        cam, fps = try_mode(saved["backend"], saved["w"], saved["h"])
        if cam is not None:
            recent_probe = time.time() - state.get("camera_probe_time", 0) < 24 * 3600
            if fps >= 0.6 * saved.get("fps", 0) or recent_probe:
                return cam
            cam.release()
            log.info("camera got much slower than before: testing the modes again")
    if notify:
        notify("Setting up the camera (one time, a few seconds)...")
    results = []
    for w, h in modes:
        for bname in backends:
            cam, fps = try_mode(bname, w, h)
            if cam is None:
                continue
            if fps >= CAMERA_MIN_FPS:
                save_state(camera={"backend": bname, "w": w, "h": h, "fps": round(fps, 1)},
                           camera_probe_time=time.time())
                log.info("camera mode chosen: %s %dx%d (%.0f fps)", bname, w, h, fps)
                return cam
            cam.release()
            results.append((fps, -w, bname, w, h))
    if results:                                         # nothing fast enough: take the fastest
        fps, _, bname, w, h = max(results)
        cam, fps2 = try_mode(bname, w, h)
        if cam is not None:
            save_state(camera={"backend": bname, "w": w, "h": h, "fps": round(fps2, 1)},
                       camera_probe_time=time.time())
            log.info("camera mode chosen: %s %dx%d (%.0f fps, the fastest available)", bname, w, h, fps2)
            return cam
    return None


def _num(v: float) -> str:
    return f"{v:.2f}" if v < 9 else "--"


ROLE_COLORS = {"main": (60, 220, 60), "second": (255, 170, 30)}


def draw_preview(cv2, frame, hands, engine, fps, paused, extra="", text_on_image=True):
    """Camera picture with what the app sees: hands (green = main, orange = second), the cursor box,
    what is happening now, and the live numbers."""
    h, w = frame.shape[:2]
    f = max(w / 960.0, 0.67)                    # text / line size relative to the picture
    left, top, right, bottom = engine.box()
    reach = engine.boxcam.reach
    if reach is not None:                       # your usual range of movement (what the size fits to)
        x0, y0, x1, y1 = reach
        for i in range(int(x0 * w), int(x1 * w), 12):
            cv2.line(frame, (i, int(y0 * h)), (min(i + 5, int(x1 * w)), int(y0 * h)), (200, 160, 80), 1)
            cv2.line(frame, (i, int(y1 * h)), (min(i + 5, int(x1 * w)), int(y1 * h)), (200, 160, 80), 1)
        for i in range(int(y0 * h), int(y1 * h), 12):
            cv2.line(frame, (int(x0 * w), i), (int(x0 * w), min(i + 5, int(y1 * h))), (200, 160, 80), 1)
            cv2.line(frame, (int(x1 * w), i), (int(x1 * w), min(i + 5, int(y1 * h))), (200, 160, 80), 1)
    box_color = (0, 200, 255) if engine.boxcam.following else (140, 140, 140)
    cv2.rectangle(frame, (int(left * w), int(top * h)), (int(right * w), int(bottom * h)), box_color,
                  2 if engine.boxcam.following else 1)
    for hand in hands:
        pts = [(int(x * w), int(y * h)) for x, y in hand.img]
        color = ROLE_COLORS.get(hand.role, (150, 150, 150))
        for a, b in HAND_CONNECTIONS:
            cv2.line(frame, pts[a], pts[b], color, max(1, int(2 * f)))
        for i, p in enumerate(pts):
            r = int((6 if i in (THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP) else 3) * f)
            cv2.circle(frame, p, r, (255, 255, 255) if i == INDEX_TIP else color, -1)
        tag = hand.role or "hand"
        if hand.zoomed:
            tag += " (zoom)"
        cv2.putText(frame, tag, (pts[WRIST][0] - int(30 * f), pts[WRIST][1] + int(28 * f)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6 * f, color, max(1, int(2 * f)))
    for anchor, cur in engine.scroll_marks:     # fist scroll: zero line and how far the fist moved
        ay, cy = int(anchor * h), int(cur * h)
        x = w - int(50 * f)
        cv2.line(frame, (x - int(30 * f), ay), (x + int(30 * f), ay), (0, 200, 255), 2)
        dz = int(SCROLL_DEADZONE * h)
        cv2.rectangle(frame, (x - int(20 * f), ay - dz), (x + int(20 * f), ay + dz), (0, 200, 255), 1)
        cv2.arrowedLine(frame, (x, ay), (x, cy), (0, 200, 255), 3, tipLength=0.3)
    for anchor, cur in getattr(engine, "hscroll_marks", []):   # sideways fist scroll
        ax, cx = int(anchor * w), int(cur * w)
        y = h - int(50 * f)
        cv2.line(frame, (ax, y - int(30 * f)), (ax, y + int(30 * f)), (0, 200, 255), 2)
        dz = int(HSCROLL_DEADZONE * h)
        cv2.rectangle(frame, (ax - dz, y - int(20 * f)), (ax + dz, y + int(20 * f)), (0, 200, 255), 1)
        cv2.arrowedLine(frame, (ax, y), (cx, y), (0, 200, 255), 3, tipLength=0.3)
    big = "STOPPED" if paused else (engine.gesture.upper() if engine.gesture else "")
    if big:
        (tw, th), _ = cv2.getTextSize(big, cv2.FONT_HERSHEY_SIMPLEX, 1.1 * f, 3)
        cv2.putText(frame, big, (w - tw - int(16 * f), int(44 * f)), cv2.FONT_HERSHEY_SIMPLEX, 1.1 * f,
                    (0, 0, 0), int(6 * f))
        cv2.putText(frame, big, (w - tw - int(16 * f), int(44 * f)), cv2.FONT_HERSHEY_SIMPLEX, 1.1 * f,
                    (255, 255, 255), max(2, int(2 * f)))
    lines = [f"{fps:4.1f} fps   {'STOPPED' if paused else 'tracking'}   {extra}"]
    if text_on_image:
        lines += engine.status
    for i, text in enumerate(lines):
        y = int((22 + i * 22) * f)
        cv2.putText(frame, text, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5 * f, (0, 0, 0), max(3, int(3 * f)))
        cv2.putText(frame, text, (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5 * f, (255, 255, 255), 1)


# log lines that are a recognised gesture (any line containing one of these), and lines that are not
DEBUG_EVENTS = ("click", "button", "scroll mode", "volume control", "second hand", "both fists", "gestures off",
                "gestures on", "main hand", "swipe")
DEBUG_IGNORE = ("second hand finder", "snapshot saved", "debug pictures", "diag ")
DEBUG_TILE_W = 480              # width of one picture in the strip


class GestureRecorder(logging.Handler):
    """Debug mode (DEBUG_PICTURES): a picture of every gesture the app recognised. It listens to the log for
    gesture lines, keeps the last DEBUG_SPAN seconds of small camera frames with the hands' positions, and after
    each frame with gesture lines draws a strip of frames and saves it (in a background thread)."""

    def __init__(self, folder: str, on: bool = False):
        super().__init__(logging.INFO)
        from collections import deque
        self.folder, self.on = folder, on
        self.frames = deque()           # (time, small picture, [(role, points, zoomed)], status lines)
        self.events = deque()           # gesture log lines waiting for their picture
        self.saved = 0
        self.last_save = -1e9
        self.jobs = None                # queue of (path, picture) for the writer thread

    def emit(self, record):
        if not self.on:
            return
        try:
            msg = record.getMessage()
        except Exception:
            return
        m = msg.lower()
        if any(k in m for k in DEBUG_EVENTS) and not any(k in m for k in DEBUG_IGNORE):
            self.events.append((record.created, msg))

    def add(self, cv2, frame, hands, status, now: float):
        """Every frame while on (before anything is drawn on the frame)."""
        if not self.on:
            self.frames.clear()
            self.events.clear()
            return
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (DEBUG_TILE_W, int(h * DEBUG_TILE_W / w)), interpolation=cv2.INTER_AREA)
        self.frames.append((now, small, [(hd.role, list(hd.img), hd.zoomed, self.numbers(hd)) for hd in hands],
                            list(status)))
        while self.frames and now - self.frames[0][0] > DEBUG_SPAN:
            self.frames.popleft()

    def save_pending(self, cv2, np, now: float):
        """After the frame's gestures were handled: one picture for the gesture lines that came in. Returns
        the file path (or None)."""
        if not self.on or not self.events or not self.frames or now - self.last_save < 0.25:
            return None
        events = []
        while self.events:
            events.append(self.events.popleft())
        msgs = [m for _, m in events]
        sheet = self.sheet(cv2, np, msgs)
        t = events[0][0]
        stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(t)) + f"_{int(t * 1000) % 1000:03d}"
        path = os.path.join(self.folder, f"{stamp} {self.short(msgs)}.jpg")
        self.last_save = now
        self._write(cv2, path, sheet)
        return path

    @staticmethod
    def numbers(h: Hand) -> str:
        """The thumb distances of one frame, written under it (3D / picture for the index)."""
        try:
            return (f"idx {h.side['x1']:.2f}/{thumb_index_2d(h):.2f} mid {h.pinch[0]:.2f} ring {h.pinch[1]:.2f}"
                    + (" unsure" if h.unsure else ""))
        except Exception:
            return ""

    @staticmethod
    def short(msgs: list) -> str:
        """A few words for the file name: the last line, or what a second-hand touch was read as."""
        m = msgs[-1]
        if m.startswith("second hand touch") and "->" in m:
            m = "second hand touch -> " + m.split("->", 1)[1]
        m = re.sub(r"[^A-Za-z0-9+ ,.()-]+", " ", m)
        return re.sub(r"\s+", " ", m).strip()[:70] or "gesture"

    def sheet(self, cv2, np, msgs: list):
        """The strip: up to DEBUG_FRAMES frames spread over the last DEBUG_SPAN seconds (the last one = now),
        hands drawn in, with the time before the gesture; the log lines and the live numbers on top."""
        frames = list(self.frames)
        n = min(DEBUG_FRAMES, len(frames))
        picks = [frames[round(i * (len(frames) - 1) / max(n - 1, 1))] for i in range(n)]
        t_end = frames[-1][0]
        tiles = []
        for i, (t, img, hands, _) in enumerate(picks):
            img = img.copy()
            th, tw = img.shape[:2]
            for k, (role, pts, zoomed, nums) in enumerate(hands):
                pts = [(int(x * tw), int(y * th)) for x, y in pts]
                color = ROLE_COLORS.get(role, (150, 150, 150))
                for a, b in HAND_CONNECTIONS:
                    cv2.line(img, pts[a], pts[b], color, 1)
                for j in (THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, 20):
                    cv2.circle(img, pts[j], 3, (255, 255, 255) if j == THUMB_TIP else color, -1)
                cv2.putText(img, role + (" zoom" if zoomed else ""),
                            (pts[WRIST][0] - 20, min(pts[WRIST][1] + 16, th - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                            color, 1)
                y = th - 8 - 18 * k
                cv2.putText(img, f"{role}: {nums}", (6, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3)
                cv2.putText(img, f"{role}: {nums}", (6, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
            label = "now" if i == n - 1 else f"-{t_end - t:.2f} s"
            cv2.putText(img, label, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3)
            cv2.putText(img, label, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
            if i == n - 1:
                cv2.rectangle(img, (0, 0), (tw - 1, th - 1), (0, 0, 255), 3)
            tiles.append(img)
        cols = min(4, len(tiles))
        while len(tiles) % cols:
            tiles.append(np.zeros_like(tiles[0]))
        grid = np.vstack([np.hstack(tiles[r:r + cols]) for r in range(0, len(tiles), cols)])
        lines = [(m, (255, 255, 255)) for msg in msgs for m in _wrap(msg, 150)]
        lines += [(m, (190, 190, 190)) for st in frames[-1][3] for m in _wrap(st, 150)]
        head = np.full((14 + 20 * len(lines), grid.shape[1], 3), 30, np.uint8)
        for i, (text, color) in enumerate(lines):
            cv2.putText(head, text, (8, 22 + 20 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        return np.vstack([head, grid])

    def _write(self, cv2, path: str, img):
        if self.jobs is None:
            import queue
            self.jobs = queue.Queue(maxsize=30)
            threading.Thread(target=self._writer, args=(cv2,), daemon=True, name="debug-pictures").start()
        try:
            self.jobs.put_nowait((path, img))
        except Exception:
            pass                        # writer far behind: skip this picture rather than slow the tracking

    def _writer(self, cv2):
        while True:
            path, img = self.jobs.get()
            try:
                os.makedirs(self.folder, exist_ok=True)
                ok, data = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ok:
                    with open(path, "wb") as f:
                        f.write(data.tobytes())
                    self.saved += 1
                    self.prune()
            except Exception as e:
                log.warning("could not save a debug picture: %s", e)
            finally:
                self.jobs.task_done()

    def prune(self):
        """Keep the newest DEBUG_KEEP pictures, delete the older ones (the names start with date and time)."""
        try:
            files = sorted(e.name for e in os.scandir(self.folder) if e.name.endswith(".jpg"))
            for name in files[:max(len(files) - DEBUG_KEEP, 0)]:
                os.remove(os.path.join(self.folder, name))
        except OSError:
            pass

    def wait(self):
        """Wait until every picture is written (tests, quitting)."""
        if self.jobs is not None:
            self.jobs.join()


RECORDER = GestureRecorder(os.path.join(HERE, "debug"), DEBUG_PICTURES)

PANEL_W = 470


def _wrap(text: str, width: int) -> list:
    out, line = [], ""
    for word in text.split(" "):
        if len(line) + len(word) + 1 > width and line:
            out.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    out.append(line)
    return out


def _event_color(msg: str) -> tuple:
    m = msg.lower()
    if "click" in m or "button" in m:
        return (120, 220, 255)          # clicks and buttons: orange-yellow
    if "scroll" in m or "swipe" in m:
        return (255, 200, 120)          # scroll / swipe: light blue
    if m.startswith("second hand"):
        return (230, 150, 230)          # keyboard shortcuts: pink
    if "stopp" in m or "paused" in m or "fists" in m:
        return (110, 110, 255)          # stop: red
    if "hand" in m:
        return (150, 230, 150)          # hand changes: green
    return (200, 200, 200)


def draw_panel(cv2, np, height: int, engine, paused: bool):
    """Side panel of the camera window: what each hand is doing right now, and the latest events."""
    panel = np.full((height, PANEL_W, 3), (32, 30, 28), np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    y = 30
    now_text = "STOPPED" if paused else (engine.gesture.upper() if engine.gesture else "-")
    cv2.putText(panel, "NOW:", (14, y), font, 0.6, (170, 170, 170), 1, cv2.LINE_AA)
    cv2.putText(panel, now_text, (80, y), font, 0.75, (255, 255, 255), 2, cv2.LINE_AA)
    y += 26
    limit = height * 0.5 - 64
    for line in engine.status:
        color = (150, 230, 150) if line.startswith("MAIN") else (
            (120, 190, 255) if line.startswith("SECOND") else (210, 210, 210))
        for part in _wrap(line, 58):
            if y > limit:
                break
            cv2.putText(panel, part, (14, y), font, 0.42, color, 1, cv2.LINE_AA)
            y += 18
    hint = (f"t- numbers = thumb distance: clicks and button 4 (t-idx) fire below {TOUCH_ON:.2f}, button 5 "
            f"(t-ring-base) below {SIDE_TOUCH_ON:.2f}. fingers (index..pinky): below {FIST_CURL:.2f} = folded.")
    hy = int(height * 0.5) - 52
    for part in _wrap(hint, 64):
        cv2.putText(panel, part, (14, hy), font, 0.36, (130, 130, 130), 1, cv2.LINE_AA)
        hy += 15
    y = int(height * 0.5) + 6
    cv2.line(panel, (10, y - 18), (PANEL_W - 10, y - 18), (80, 80, 80), 1)
    cv2.putText(panel, "LOG (newest at the bottom)", (14, y), font, 0.5, (170, 170, 170), 1, cv2.LINE_AA)
    y += 8
    rows = []
    for created, level, msg in EVENTS.latest(40):
        stamp = time.strftime("%H:%M:%S", time.localtime(created))
        parts = _wrap(msg, 46)
        rows.append((stamp, parts[0], _event_color(msg)))
        rows += [("", p, _event_color(msg)) for p in parts[1:]]
    max_rows = max((height - y - 10) // 18, 1)
    for stamp, text, color in rows[-max_rows:]:
        y += 18
        cv2.putText(panel, stamp, (14, y), font, 0.4, (140, 140, 140), 1, cv2.LINE_AA)
        cv2.putText(panel, text, (92, y), font, 0.42, color, 1, cv2.LINE_AA)
    return panel


class ViewWindow:
    """The camera & log window, run by its own thread. Windows pauses a window's thread while the window is
    dragged by its title bar; the hand tracking must keep running meanwhile (it has to let go of the mouse
    button that is dragging the window). The window can be resized and moved; its place is remembered."""

    def __init__(self, cv2, on_pause, rect=None, screen=None, on_snapshot=None):
        self.cv2, self.on_pause = cv2, on_pause
        self.on_snapshot = on_snapshot or (lambda: None)
        self.rect = rect                    # outer window (x, y, w, h) to restore, remembered when it closes
        self.screen = screen                # (left, top, width, height) of all monitors, to check rect
        self.lock = threading.Lock()
        self.frame, self.seq = None, 0
        self.want = False
        self.closed_by_user = False
        self.stop_flag = False
        self.thread = threading.Thread(target=self._run, daemon=True, name="camera-window")
        self.thread.start()

    def show(self, img):
        with self.lock:
            if self.closed_by_user:         # closed a moment ago: the main loop hasn't noticed yet
                return
            self.frame, self.seq, self.want = img, self.seq + 1, True

    def hide(self):
        with self.lock:
            self.want, self.frame = False, None

    def take_closed(self) -> bool:
        """True once after the user closed the window (X button, Esc or q)."""
        with self.lock:
            closed, self.closed_by_user = self.closed_by_user, False
            return closed

    def stop(self):
        self.stop_flag = True
        self.thread.join(timeout=2.0)

    def _restore_rect(self):
        r, sc = self.rect, self.screen
        if not r or not sc:
            return None
        try:
            x, y, w, h = (int(v) for v in r)
        except Exception:
            return None
        inside = sc[0] - 50 <= x <= sc[0] + sc[2] - 100 and sc[1] - 20 <= y <= sc[1] + sc[3] - 100
        return (x, y, w, h) if inside and 300 <= w <= 8000 and 150 <= h <= 5000 else None

    def _run(self):
        cv2 = self.cv2
        try:                                # crisp on every monitor, whatever its scaling
            import ctypes
            ctypes.windll.user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            pass
        is_open, shown, offset, last_rect_check = False, -1, (0, 0), 0.0

        def remember():
            try:
                x, y, w, h = cv2.getWindowImageRect(WINDOW)
                if w > 0 and h > 0:
                    self.rect = (x - offset[0], y - offset[1], w, h)
            except Exception:
                pass

        def destroy():
            nonlocal is_open
            if is_open:
                remember()
                is_open = False
                try:
                    cv2.destroyWindow(WINDOW)
                    cv2.waitKey(1)
                except Exception:           # already gone (closed with its X button)
                    pass

        while not self.stop_flag:
            with self.lock:
                want, frame, seq = self.want, self.frame, self.seq
            try:
                if not (want and frame is not None):
                    destroy()
                    time.sleep(0.05)
                    continue
                if not is_open:
                    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
                    r = self._restore_rect()
                    w, h = (r[2], r[3]) if r else (frame.shape[1], frame.shape[0])
                    cv2.resizeWindow(WINDOW, w, h)
                    offset = (0, 0)
                    if r:
                        cv2.moveWindow(WINDOW, r[0], r[1])
                        try:                # the picture starts below the title bar: measure by how much
                            cx, cy, _, _ = cv2.getWindowImageRect(WINDOW)
                            offset = (cx - r[0], cy - r[1])
                        except Exception:
                            pass
                    is_open, shown = True, -1
                if seq != shown:
                    cv2.imshow(WINDOW, frame)
                    shown = seq
                key = cv2.waitKey(15) & 0xFF
                visible = True
                try:
                    visible = cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) >= 1
                except Exception:
                    visible = False
                if key in (ord("q"), 27) or not visible:
                    if visible:
                        destroy()
                    else:
                        is_open = False     # closed with its X button: Windows already destroyed it
                    with self.lock:
                        self.want, self.frame, self.closed_by_user = False, None, True
                    continue
                if key == ord("p"):
                    self.on_pause()
                elif key == ord("s"):
                    self.on_snapshot()
                if time.monotonic() - last_rect_check > 1.0:
                    last_rect_check = time.monotonic()
                    remember()
            except Exception:
                log.exception("camera window problem; closing the window")
                destroy()
                with self.lock:
                    self.want, self.frame, self.closed_by_user = False, None, True
                time.sleep(0.2)
        destroy()


# ------------------------------------------------------------------ main loop

def run(preview: bool) -> bool:
    """Runs until quit. Returns True if the app should restart (its file was edited)."""
    import cv2
    import numpy as np

    mouse = WinMouse()
    state = load_state()
    engine = Engine(mouse, mouse.left, mouse.top, mouse.width, mouse.height,
                    ref_palm=state.get("ref_palm"), on_ref_learned=lambda v: save_state(ref_palm=v),
                    box_state=state.get("box"), main_side=state.get("main_side", "right"),
                    on_main_side=lambda side: main_side_changed(side))
    def main_side_changed(side: str):
        save_state(main_side=side)
        beep(660)
        beep(990)
        if tray is not None:
            tray.notify(f"Your {side} hand is now the main hand. To switch back, show only the other hand "
                        "and make a fist twice.")

    ensure_model()
    sensor = HandSensor(create_landmarker(True, 2), create_landmarker(False, 1) if ZOOM_ENABLED else None,
                        create_landmarker(False, 1, detection=DISCOVER_CONFIDENCE) if ZOOM_ENABLED else None,
                        create_hand_finder() if ZOOM_ENABLED else None)

    quit_evt = threading.Event()
    pause_evt = threading.Event()
    calib_evt = threading.Event()
    view_evt = threading.Event()        # camera view window shown
    if preview:
        view_evt.set()
    restart = False
    tray = None

    def toggle_pause():
        if pause_evt.is_set():
            pause_evt.clear()
            log.info("resumed")
            engine.set_gestures(True)   # resuming means: use the hands again
            beep(880)
        else:
            pause_evt.set()
            log.info("paused")
            beep(440)
        if tray is not None:
            tray.refresh()

    def toggle_view():
        if view_evt.is_set():
            view_evt.clear()
        else:
            view_evt.set()
        if tray is not None:
            tray.refresh()

    def relearn():
        calib_evt.set()
        beep(660)
        beep(660)
        if tray is not None:
            tray.notify("Hold your open hand up for a few seconds at your normal distance.")

    hotkeys = None
    try:
        from pynput import keyboard
        hotkeys = keyboard.GlobalHotKeys({HOTKEY_PAUSE: toggle_pause,
                                          HOTKEY_CALIBRATE: relearn,
                                          HOTKEY_QUIT: quit_evt.set})
        hotkeys.daemon = True
        hotkeys.start()
    except Exception:
        log.exception("could not register hotkeys")

    def toggle_gestures():
        engine.set_gestures(engine.gestures_off)

    RECORDER.on = bool(state.get("debug_pictures", DEBUG_PICTURES))

    def toggle_debug():
        RECORDER.on = not RECORDER.on
        save_state(debug_pictures=RECORDER.on)
        log.info("debug pictures %s (folder %s)", "on" if RECORDER.on else "off", RECORDER.folder)
        tray.refresh()
        if RECORDER.on:
            tray.notify("Debug on: every gesture saves a picture to the debug folder in the Hand Mouse folder. "
                        "Turn it off in this menu when you are done.")

    tray = TrayIcon(pause_evt.is_set, toggle_pause, quit_evt.set,
                    view_shown=view_evt.is_set, on_view=toggle_view, on_relearn=relearn,
                    gestures_off=lambda: engine.gestures_off, on_gestures=toggle_gestures,
                    debug_on=lambda: RECORDER.on, on_debug=toggle_debug)

    def show_requested():
        view_evt.set()
        tray.refresh()
    threading.Thread(target=listen_for_show_requests, args=(show_requested, quit_evt),
                     daemon=True, name="show-listener").start()
    if not state.get("welcomed_v4"):
        open_help()                     # first start of this version: show the gestures once
        save_state(welcomed_v4=True)
        tray.notify("Hand Mouse is running. Click this icon to stop / resume, right-click for options.")

    cap = None
    camera_verified = False             # the camera speed is tested once per start, not on every resume
    last_ts = 0
    fps, frames, fps_t = 0.0, 0, time.monotonic()
    fails = 0
    stop_warned = False
    fists_tip_shown = False
    cam_fps, cam_seq, dim_since, light_tip_shown, frames_total = 0.0, 0, None, False, 0
    script_mtime = os.path.getmtime(SCRIPT)
    last_file_check = last_screen_check = time.monotonic()
    log.info("started (screens %dx%d at %d,%d, preview=%s, normal hand size %s)",
             mouse.width, mouse.height, mouse.left, mouse.top, preview,
             f"{engine.ref_palm:.3f}" if engine.ref_palm else "not learned yet")
    beep(880)

    def preinstall_volume():            # install pycaw in the background, so the first thumbs-up doesn't wait
        import importlib.util
        if VOLUME_CONTROL and importlib.util.find_spec("pycaw") is None:
            py = os.path.join(os.path.dirname(sys.executable), "python.exe")
            py = py if os.path.exists(py) else sys.executable
            log.info("installing pycaw (volume control) in the background ...")
            try:
                subprocess.run([py, "-m", "pip", "install", "--disable-pip-version-check", "pycaw"],
                               creationflags=0x08000000, timeout=300, check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                log.info("pycaw installed")
            except Exception:
                log.exception("could not install pycaw")
    threading.Thread(target=preinstall_volume, daemon=True, name="install-pycaw").start()

    snap_evt = threading.Event()
    view = ViewWindow(cv2, toggle_pause, rect=state.get("window"),
                      screen=(mouse.left, mouse.top, mouse.width, mouse.height), on_snapshot=snap_evt.set)

    def compose(frame):
        """Camera picture (960 wide) with the side panel, ready for the window."""
        h, w = frame.shape[:2]
        if w != 960:
            frame = cv2.resize(frame, (960, int(h * 960 / w)), interpolation=cv2.INTER_AREA)
        return np.hstack([frame, draw_panel(cv2, np, frame.shape[0], engine, pause_evt.is_set())])

    try:
        while not quit_evt.is_set():
            mono = time.monotonic()
            if AUTO_RESTART_ON_EDIT and mono - last_file_check > 1.0:
                last_file_check = mono
                try:
                    if os.path.getmtime(SCRIPT) != script_mtime:
                        time.sleep(1.0)   # let the save finish
                        log.info("hand_mouse.py changed, restarting")
                        restart = True
                        break
                except OSError:
                    pass
            if mono - last_screen_check > 3.0:        # monitors plugged in / removed
                last_screen_check = mono
                b = mouse.bounds()
                if b != (engine.sx0, engine.sy0, engine.sw, engine.sh):
                    engine.set_screen(*b)
                    log.info("screen area changed: %dx%d at %d,%d", b[2], b[3], b[0], b[1])

            if calib_evt.is_set():
                calib_evt.clear()
                engine.recalibrate()
                save_state(ref_palm=None)

            if view.take_closed():
                if preview:
                    break
                view_evt.clear()
                tray.refresh()
            if not view_evt.is_set():
                view.hide()

            if pause_evt.is_set():
                if cap is not None:
                    engine.release_all(time.monotonic())
                    cap.release()
                    cap = None
                if view_evt.is_set():
                    blank = np.zeros((540, 960, 3), np.uint8)
                    engine.status = ["stopped - click the tray icon, press p or Ctrl+Alt+H to resume"]
                    engine.gesture = ""
                    draw_preview(cv2, blank, [], engine, 0.0, True, text_on_image=False)
                    view.show(compose(blank))
                    time.sleep(0.1)
                else:
                    time.sleep(0.1)
                continue

            if cap is None:
                t_open = time.monotonic()
                cap = open_camera(cv2, load_state(), tray.notify, verify=not camera_verified)
                if cap is not None:
                    camera_verified = True
                    cam_seq = 0
                    log.info("camera ready in %.1f s", time.monotonic() - t_open)
                    try:                # for diagnosing dim-light problems
                        c = cap.cap
                        log.info("camera settings: auto exposure %s, exposure %s, gain %s, brightness %s",
                                 *(c.get(p) for p in (cv2.CAP_PROP_AUTO_EXPOSURE, cv2.CAP_PROP_EXPOSURE,
                                                      cv2.CAP_PROP_GAIN, cv2.CAP_PROP_BRIGHTNESS)))
                    except Exception:
                        pass
                if cap is None:
                    fails += 1
                    if fails == 1:
                        log.error("camera %d could not be opened, retrying", CAMERA_INDEX)
                    if fails == 10:
                        msg = (f"Camera {CAMERA_INDEX} could not be opened. Is another app using it, or is "
                               "camera access off in Windows Privacy settings?")
                        tray.notify(msg) if tray.icon is not None else message_box(msg)
                    time.sleep(1.0)
                    continue
                fails = 0

            ok, frame = cap.read()
            if not ok:
                log.warning("camera stopped delivering frames, reopening")
                cap.release()
                cap = None
                time.sleep(0.5)
                continue

            frame = cv2.flip(frame, 1)   # mirror: moving right moves cursor right
            now = time.monotonic()
            ts = max(int(now * 1000), last_ts + 1)
            last_ts = ts
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            hands = sensor.process(rgb, ts, now)
            frames += 1
            frames_total += 1
            tick = now - fps_t >= 1.0
            engine.want_status = view_evt.is_set() or (tick and DIAGNOSTICS) or RECORDER.on
            engine.update(hands, now)
            if RECORDER.on or RECORDER.frames:
                RECORDER.add(cv2, frame, hands, engine.status, now)
                RECORDER.save_pending(cv2, np, now)
            if engine.both_fists_since is not None and not stop_warned:
                stop_warned = True
                beep(520, 120)          # countdown started
            elif engine.both_fists_since is None:
                stop_warned = False
            changed, engine.gestures_changed = engine.gestures_changed, None
            if changed == "off":
                beep(440)
                beep(330)
                tray.refresh()
                if not fists_tip_shown:
                    fists_tip_shown = True
                    tray.notify("Gestures off: only two fists are watched now. Hold both fists again to turn "
                                "them back on. To stop the camera, use this icon.")
            elif changed == "on":
                beep(660)
                beep(880)
                tray.refresh()

            if tick:
                elapsed = max(now - fps_t, 1e-3)
                fps, frames, fps_t = frames / elapsed, 0, now
                seq = getattr(cap, "seq", 0)
                cam_fps, cam_seq = (seq - cam_seq) / elapsed, seq
                light = float(frame[::16, ::16].mean())
                # dim light: webcams lengthen the exposure (fewer frames per second, moving hands blur)
                if cam_fps < LOW_LIGHT_FPS and frames_total > 60:
                    dim_since = dim_since or now
                    if now - dim_since > 10 and not light_tip_shown:
                        light_tip_shown = True
                        log.info("dim light: camera slowed to %.0f fps (picture brightness %.0f)", cam_fps, light)
                        tray.notify(f"Dim light: the camera slowed down to {cam_fps:.0f} frames per second, so "
                                    "moving hands blur and can get lost. A lamp in front of you or at your side "
                                    "(not behind you) helps most.")
                else:
                    dim_since = None
                d = engine.pop_diag()
                ms = sensor.avg_ms()
                if DIAGNOSTICS and d:
                    k = sorted(d["k"])[len(d["k"]) // 2] if d["k"] else 1.0
                    log.info("diag fps %.0f hands %d | %.0f ms/frame | camera %.0f fps light %.0f | min t-mid %.2f "
                             "min t-ring %.2f | scrolling frames %d/%d | zoomed %d found-again %d | size %.2f | "
                             "pressed %s | %s",
                             fps, d["hands"], ms, cam_fps, light, d["min_dm"], d["min_dr"], d["busy"], d["frames"],
                             d["zoomed"], d["rescued"], k, ",".join(sorted(d["pressed"])) or "-",
                             " / ".join(engine.status[:-1]))

            if view_evt.is_set():
                if RECORDER.on:
                    engine.status.append(f"DEBUG ON: {RECORDER.saved} gesture pictures saved to the debug folder")
                if snap_evt.is_set():       # the plain camera picture, for finding out why a gesture isn't seen
                    snap_evt.clear()
                    try:
                        folder = os.path.join(HERE, "snapshots")
                        os.makedirs(folder, exist_ok=True)
                        path = os.path.join(folder, time.strftime("snap_%Y%m%d_%H%M%S.png"))
                        cv2.imwrite(path, frame)
                        log.info("snapshot saved: snapshots\\%s | %s", os.path.basename(path),
                                 " / ".join(engine.status[:2]))
                        beep(990, 60)
                    except Exception:
                        log.exception("could not save the snapshot")
                draw_preview(cv2, frame, hands, engine, fps, False,
                             f"hand model {sensor.ms_total / max(sensor.frames, 1):.0f} ms   camera {cam_fps:.0f} fps"
                             f"{'  DIM LIGHT' if dim_since else ''}"
                             f"{'' if sensor.view == 'normal' else '  colours: ' + sensor.view}", text_on_image=False)
                view.show(compose(frame))
    finally:
        engine.release_all(time.monotonic())
        RECORDER.wait()
        if cap is not None:
            cap.release()
        view.stop()
        if view.rect:
            save_state(window=list(view.rect))
        if hotkeys is not None:
            hotkeys.stop()
        tray.stop()
        for lm in (sensor.video, sensor.image, sensor.finder):
            if lm is not None:
                lm.close()
        save_state(box=engine.boxcam.state())   # the box continues where it was next time
        log.info("stopped")
    return restart


def main():
    parser = argparse.ArgumentParser(description="Control the mouse with your hands.")
    parser.add_argument("--preview", action="store_true", help="show camera window with live values")
    parser.add_argument("--debug", action="store_true", help="log every click to hand_mouse.log")
    parser.add_argument("--restarted", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--create-shortcut", action="store_true", help="(re)create the desktop icon and exit")
    args = parser.parse_args()

    from logging.handlers import RotatingFileHandler
    handlers = [RotatingFileHandler(LOG_PATH, maxBytes=int(LOG_MAX_MB * 1024 * 1024), backupCount=2,
                                    encoding="utf-8")]
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", handlers=handlers)
    log.addHandler(EVENTS)
    log.addHandler(RECORDER)

    if sys.platform != "win32":
        print("This app controls the Windows mouse and must run on Windows.")
        return 1
    if args.create_shortcut:
        create_desktop_shortcut(force=True)
        return 0
    try:
        create_desktop_shortcut()
    except Exception:
        log.exception("could not create the desktop shortcut")
    if not single_instance(wait=10.0 if args.restarted else 0.0):
        if not args.restarted and signal_running_instance():
            return 0                    # the running app shows its camera view instead
        message_box("Hand Mouse is already running (see the icon next to the clock).\n\n"
                    "Click that icon to stop / resume, right-click it for the menu.")
        return 1
    try:
        restart = run(args.preview)
    except Exception as e:
        log.exception("fatal error")
        message_box(f"Hand Mouse stopped because of an error:\n\n{e}\n\nDetails are in {LOG_PATH}")
        return 1
    if restart:
        release_instance()
        argv = [a for a in sys.argv[1:] if a != "--restarted"] + ["--restarted"]
        subprocess.Popen([sys.executable, SCRIPT] + argv, cwd=HERE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
