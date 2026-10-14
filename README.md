# Hand Mouse

Control the Windows mouse with your hands through the laptop webcam. Everything runs locally.

## Start

- Double-click the **Hand Mouse** icon on your desktop. It runs in the background; its icon appears next to
  the clock (click the **^** arrow if Windows hides it, and drag it onto the taskbar to keep it visible).
- **Left-click** the tray icon: stop / resume tracking (grey icon with a red badge = stopped, camera off).
  A grey icon with an **orange** badge means gestures are off (two fists); the camera still watches for two
  fists to turn them back on.
- **Right-click** the tray icon:
  - **Camera & log window** shows what the app sees: green = main hand, orange = second hand, big text = what
    is happening now. The panel on the right shows each hand's live numbers and a log of every click,
    button 4/5, scroll and swipe the app recognised (newest at the bottom). In that window **P** stops /
    resumes, **S** saves the plain camera picture to the `snapshots` folder (handy to show what a missed
    gesture looks like), **Esc** closes it (the app keeps running). The window can be resized and moved to
    another screen (also with a gesture drag); its size and place are remembered.
  - **Gestures on**: tick / untick to turn gestures on or off (same as holding two fists).
  - **Stop / Resume tracking**: camera off / on. Resuming also turns gestures back on.
  - **Gestures help** opens a one-page summary of all gestures.
  - **Start with Windows** starts the app automatically when you log in.
  - **Re-learn my hand size**: hold your open hand up for a few seconds at your usual distance.
  - **Close Hand Mouse**.
- Double-clicking the desktop icon while the app is running opens the camera & log window.

## Gestures

Your **main hand** is your **right hand**: it moves the cursor and makes the mouse gestures. The left hand gives
keyboard shortcuts (next section) and takes part in the two-fist on / off. To use your **left hand** as the main hand: show only the left hand and make a
fist twice quickly. This is remembered (also after a restart) until the right hand does the same. The app tells
the hands apart by position when both are in view, otherwise by the hand model's left / right guess averaged over
time (`SWAP_HANDEDNESS = True` if it mixes them up). `SECOND_HAND_GESTURES = True` makes the other hand
scroll, swipe windows, press buttons 4/5 and change the volume instead of giving keyboard shortcuts.

| Action | Gesture |
|---|---|
| Move cursor | Point with the index finger of the main hand. Slow movements are precise, fast ones cover the whole screen (all monitors) |
| Left click | Thumb touches middle fingertip. Keep touching and move to drag |
| Double-click | Two quick pinches (thumb to middle fingertip twice). The cursor stays put between them |
| Right click | Thumb touches ring fingertip |
| Middle click | Thumb touches middle and ring fingertips together |
| Mouse button 4 (Back) | Thumb tip to the index fingertip ("OK" sign), other fingers up |
| Mouse button 5 (Forward) | Palm towards the camera, fingers up: fold the thumb across the palm onto the base of the ring / little finger |
| Volume | Thumbs-up (fingers folded, thumb out), held a moment. Thumb straight up = 100%; turn the hand until the thumb points down to lower it to 0%. Tuck the thumb in to stop. A fist with the thumb tucked in still scrolls |
| Scroll | Make a fist. Move it down to scroll down, up to scroll up; the further from where you closed it, the faster. Open the hand to stop |
| Gestures off / on | Hold **both** hands as fists for a second (beep first). While off, nothing reacts to your hands except two fists, which turn gestures back on. Holding the fists switches only once; open a hand (or take your hands out of view) before switching again. A full stop (camera off) is on the tray icon or Ctrl+Alt+H |

## Left hand: keyboard shortcuts

Made with the other hand (the left one). A pinch acts when the thumb **lets go**, so a touch that slides onto two
fingertips counts as the two. Each one is logged (pink) in the camera & log window and shown big in the picture.

| Shortcut | Gesture |
|---|---|
| Alt+Tab (switch window) | Thumb on the index fingertip, let go: back to the last window. **Hold** it half a second: the window switcher stays open; move the hand left / right to pick a window (one window per few cm), let go to switch to it |
| Ctrl+C (copy) | Thumb on the middle fingertip |
| Ctrl+V (paste) | Thumb on the ring fingertip |
| Ctrl+Z (undo) / Ctrl+Y (redo) | Palm to the camera, thumb across the palm on the base of the little finger (like button 5). Once = undo, twice quickly = redo. A single one waits about half a second to see whether a second follows |
| Print Screen | Thumb on the middle and ring fingertips together |
| Voice typing / on-screen keyboard | Thumb on the index and middle fingertips together: Windows voice typing on / off (Win+H). Twice quickly: the on-screen keyboard opens or closes; type on it with the right hand |
| Esc | Make a fist (thumb tucked in) and open it again, while the right hand is in view. Not when it is part of two fists, and not after holding the fist longer than 1.5 s |
| Play / pause | Thumbs-up, held a moment |

The shortcuts are set in `SECOND_KEYS` at the top of `hand_mouse.py` (e.g. `"middle": "ctrl+c"`), and
`SECOND_HAND_KEYS = False` turns them all off.

## The cursor box moves with you

The grey box in the camera window is the part of the picture that maps to the whole screen. It adapts by
itself, like a game camera:

- **Follows your hand:** it stays still while your pointing finger is inside it. If the finger stays outside
  for half a second (you moved in your chair, or you keep reaching past an edge), the box glides after it
  (drawn thick orange while it moves) until the finger is back inside. Quick pushes to a screen edge don't
  move it.
- **Fits how far you move:** over a few minutes of use it learns your usual range of movement (dotted
  rectangle) and slowly sizes the box to it, so the screen edges are within your normal reach: smaller if
  you never get to the edges, bigger if you keep reaching past them (0.75x to 1.3x of the start size).
- The cursor never jumps when the box moves or resizes, and fists, clicks and buttons don't move it. Its
  position and size are remembered. **Re-learn my hand size** in the tray puts it back to the start.
- Only the main hand counts for the box.

## Distance and angles

- You can sit further back: hands that look small are re-read from a zoomed-in view of the camera picture,
  which keeps finger shapes readable.
- Movements scale with distance: the same real hand movement moves the cursor, scrolls and swipes about the
  same whether you are close or further away. Your normal hand size is learned in the first seconds of use.
- False detections (e.g. on your forearm), the same hand reported twice, and the tracker mixing up left and
  right are filtered out: hands are followed by position, and a hand that briefly disappears keeps its role.
- **Light:** in dim light the webcam lengthens its exposure: it delivers fewer frames per second (the camera
  window shows the camera's real rate) and moving hands smear, so the hand model loses them. The app now
  accepts less certain hand detections (tests with darkened videos: hands found in up to 75-83% of frames
  instead of 1-18%) and shows a tip once when the camera slows down because of dim light. What helps most:
  a lamp **in front of you or at your side** lighting your hands. A bright lamp or window **behind** you
  makes the camera darken everything else, including your hands.

## Coloured light

The hand model only knows natural skin colours, so a hand lit by a blue (or purple, RGB...) lamp is often not
found at all. When no hand is found for a moment, the app also tries the picture with red and blue swapped (a
blue-lit hand then looks warm-lit) and a white-balanced copy, and keeps using whichever finds your hand. The
camera window shows `colours: swapped` / `colours: balanced` while that is in use. In tests with videos where
only the hand was lit blue, hands were found in 53-99% of frames instead of 0-8%. `COLOR_FALLBACK = False`
turns it off.

Hands found only by the zoomed-in search (used for far-away hands and for a hand that was just lost) must
pass a stricter check (`DISCOVER_CONFIDENCE`), because a zoomed-in face or headphones in a dark room can look
like a small hand, especially in swapped colours.

## Second hand finder

`hand_finder.onnx` is a second hand detector (YOLOv10n from the HaGRIDv2 project, trained on about a million
webcam photos of people at home). When the main hand model finds no hand, this finder looks for one and the
hand model then reads the fingers from a zoomed view around it. On pictures from this laptop's camera: dark
room 0% -> 80-100% of frames with the hand found, no false hands on pictures without hands. It only runs
while no hand is found. `HAND_FINDER = False` turns it off (or delete the file). Model from
https://github.com/hukenovs/hagrid (free for non-commercial use).

## Camera speed

On first start the app tests which camera resolution really runs fast (many webcams drop to 10 frames per
second at 1280x720) and keeps the sharpest one that reaches 20 frames per second. This takes a few seconds once;
the choice is remembered in `hand_mouse_state.json` (delete the `camera` entry there to test again).

## Hotkeys

| Hotkey | Action |
|---|---|
| Ctrl+Alt+H | Stop / resume tracking |
| Ctrl+Alt+C | Re-learn your normal hand size |
| Ctrl+Alt+Q | Quit |

## Setup on a new computer

Double-click **setup.bat**. It finds Python (or installs Python 3.12 with winget), installs the libraries,
downloads the hand-tracking model (about 8 MB) and opens the camera view. Windows must allow desktop apps to
use the camera: Settings > Privacy & security > Camera > "Let desktop apps access your camera".

## Tuning

All settings are at the top of `hand_mouse.py`. Open it in Notepad, change a number and save: the app restarts
by itself.

- **Something fired that you didn't mean (or didn't fire):** open the camera & log window; the log says
  exactly what was recognised and when.
- **Clicks fire by accident or don't fire:** watch `t-mid` / `t-ring` in the camera window. Touching fingers
  should be clearly below `TOUCH_ON`, relaxed fingers clearly above `TOUCH_OFF`.
- **Buttons 4/5 fire too easily / not at all:** the camera window shows `t-idx` (button 4, fires below
  `TOUCH_ON` like the clicks; `INDEX_PINCH_MARGIN` keeps it apart from a left click) and `t-ring-base`
  (button 5, fires below `SIDE_TOUCH_ON`). `SIDE_BUTTONS = False` turns them off.
- **Middle click becomes left click:** raise `CLICK_DELAY` a little (e.g. 0.12).
- **Double-click:** `DOUBLE_CLICK_WINDOW` (how soon the second pinch must come). Uses your Windows
  double-click speed setting.
- **Drag starts too easily / too hard:** `DRAG_START_PX`.
- **Cursor too shaky:** raise `CURSOR_STEADY_RADIUS` (e.g. 25) or lower `PRECISION_GAIN` (e.g. 0.2).
  **Too sluggish:** the opposite.
- **Have to reach too far / too little:** the box fits itself over a few minutes; its start size is
  `CURSOR_BOX_WIDTH`, `CURSOR_BOX_HEIGHT` and `BOX_SIZE_LIMITS` sets how far it may adapt. `BOX_FOLLOW = False`
  / `BOX_FIT_SIZE = False` turn the following / size fitting off; `BOX_FOLLOW_DELAY` and `BOX_FOLLOW_SPEED`
  change how lazily it follows.
- **Movements shouldn't scale with distance:** `SCALE_WITH_DISTANCE = False`.
- **Slow computer:** `ZOOM_ENABLED = False` (far-away hands get less reliable) or `CAMERA_WIDTH = 640`,
  `CAMERA_HEIGHT = 480`.
- **Cursor on one monitor only:** `SCREENS = "primary"`.
- **Swipe action:** `SWIPE_ACTION = "apps"` (switch window), `"desktops"` (virtual desktops) or `"monitor"`
  (move the window to the other screen). Too easy / too hard: `SWIPE_DISTANCE`.
- **Scroll:** wrong way: `SCROLL_INVERT = True`; speed: `SCROLL_GAIN`, `SCROLL_BASE_SPEED`; scrolls when the
  fist is held still: raise `SCROLL_DEADZONE`.
- **Fist not recognised:** raise `FIST_CURL` a little (e.g. 1.45); the four `fingers` numbers in the camera
  view drop to about 1.0 when a finger is folded.
- **Two-fist gestures off / on:** `STOP_WITH_TWO_FISTS = False` turns it off, `STOP_HOLD` makes it slower.
- **No tray icon:** `TRAY_ICON = False`. **Wrong camera:** `CAMERA_INDEX = 1`.

## Notes

- Windows blocks normal apps from clicking inside windows running as administrator (Task Manager, some
  installers). Stop tracking and use the real mouse there.
- The log is `hand_mouse.log` in this folder (kept small automatically). Your learned hand size is in
  `hand_mouse_state.json`.
