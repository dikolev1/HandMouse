# Hand Mouse

Control the Windows mouse with your hands through the laptop webcam. Everything runs locally.

Windows asks for **administrator approval** when you launch the app, so gesture clicks can also
control the Windows on-screen keyboard. Approve the UAC prompt with your physical mouse or keyboard.
Cancelling leaves the app closed.

At every launch, the **camera is on and gestures are off** (orange tray badge). Hold **both fists for 1-3 seconds**, then keep **both palms open for 1 second**
to enable them. You can also use the tray icon's **Gestures on**.

## Start

- Double-click the **Hand Mouse** icon on your desktop. It runs in the background; its icon appears next to
  the clock (click the **^** arrow if Windows hides it, and drag it onto the taskbar to keep it visible).
- **Left-click** the tray icon: stop / resume tracking (grey icon with a red badge = stopped, camera off).
  A grey icon with an **orange** badge means gestures are off (two fists); the camera still watches for the
  fists held for 1-3 seconds → palms open for 1 second sequence to enable them.
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
  - **Cursor sensitivity...** opens a live slider from **25% to 250%** (100% = normal). Lower values need
    more index-finger movement; higher values move the cursor faster. Changes are saved automatically and
    remembered after restarting the app or PC. **Reset to 100%** restores normal sensitivity.
  - **Start with Windows** starts the app automatically when you log in.
  - **Re-learn my hand size**: hold your open hand up for a few seconds at your usual distance.
  - **Debug: save a picture of every gesture** (off by default, remembered): every gesture the app recognises
    (clicks, buttons, scroll, volume, left-hand shortcuts, two fists, and pinches it cancelled or found too short)
    saves a picture to the `debug` folder next to `hand_mouse.py`: 8 camera frames from the last 1.2 seconds with
    the hands drawn in, the log line as the title and each hand's numbers. The file name starts with the date and
    time, so it matches the line in `hand_mouse.log`. When a gesture misfires, the picture shows what the app saw.
    At most 500 pictures are kept: each new one deletes the oldest (`DEBUG_KEEP`). Turn it off when done.
  - **Close Hand Mouse**.
- Double-clicking the desktop icon while the app is running opens the camera & log window.

## Saved gesture profiles

Right-click the tray icon → **Gesture profiles...**. **Basic** preserves the existing gestures and
cannot be edited or deleted. Choose **Duplicate** or **New**, give the profile a name, then:

1. Select a gesture in the list.
2. Choose its action: a key/shortcut/media key, mouse button, on-screen keyboard, application/file,
   disabled, or its Basic action. Examples: `space`, `f5`, `ctrl+shift+c`, `win+shift+s`, `nexttrack`.
3. For a main-hand pinch, optionally choose **Hold keys / button until pinch is released**.
   Left L-pose bindings can optionally **Repeat while the left L pose is held**. Other custom actions
   fire once; Basic retains the original click/drag, Alt+Tab and Backspace behavior.
4. Click **Save binding**, then **Save & apply**. Applying releases held input and turns gestures off.
   Enable gestures when ready. The chosen profile and its bindings survive app/PC restarts.

Profiles support the existing main-hand button gestures, other-hand shortcuts/media gestures and both
physical L poses. Recognition and gesture timing stay the same. Cursor movement, fist scrolling,
volume control, main-hand swapping, pause and reactivation remain unchanged/reserved.
New-pose recording and user-defined gesture sequences are the next stage and are not part of this version.

Use the profile list and **Save & apply** to switch profiles. **Rename** and **Delete** manage saved
profiles. Deleting an active profile restores Basic with gestures off. Profile data is stored locally
in `gesture_profiles.json` beside the app, separately from sensitivity/camera settings and excluded from
Git. A malformed profile file falls back to Basic and is backed up before the next explicit save.

## Gestures

Your **main hand** is your **right hand**: it moves the cursor and makes the mouse gestures. The left hand gives
keyboard shortcuts (next section) and takes part in the two-fist on / off. Make a fist twice quickly with **either hand** to swap the main hand, with one or both hands visible.
Open between fists and after the second fist. This is remembered after a restart. Simultaneous gestures swap only once. The app tells
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
| Mouse button 5 (Forward) | Palm towards the camera, fingers up: fold the thumb across the palm onto the palm under the ring / little finger (anywhere from their base about halfway down to the wrist) |
| Volume | Thumbs-up (fingers folded, thumb out), held a moment. Thumb straight up = 100%; turn the hand until the thumb points down to lower it to 0%. Tuck the thumb in to stop. A fist with the thumb tucked in still scrolls |
| Scroll | Make a fist. Move it down to scroll down, up to scroll up, left / right to scroll sideways; the further from where you closed it, the faster. Only the direction you moved further scrolls, so a little drift doesn't scroll sideways. Open the hand to stop |
| Gestures off / on | Hold **both** hands as fists for a second (beep first). While off, nothing reacts to your hands except the deliberate activation sequence: both fists held for 1-3 seconds → both palms open for 1 second. Holding the fists switches only once; open a hand (or take your hands out of view) before switching again. A full stop (camera off) is on the tray icon or Ctrl+Alt+H |

## Left hand: keyboard shortcuts

**L-pose keys (both physical hands):** extend your index finger and thumb in an L, with the other three
fingers folded, and hold briefly (about 0.35 seconds). **Left hand = Backspace; right hand = Enter.**
Backspace deletes once, waits 0.5 seconds, then keeps deleting while the left pose is held. Release to
stop; unreadable/lost tracking pauses deletion. Right-hand Enter presses once per pose; release before
repeating it. These two keys keep their physical left/right
meaning even if you change which hand controls the mouse. The right-hand pose holds the cursor still.

Made with the other hand (the left one). A pinch acts when the thumb **lets go**, so a touch that slides onto two
fingertips counts as the two. Each one is logged (pink) in the camera & log window and shown big in the picture.

| Shortcut | Gesture |
|---|---|
| Alt+Tab (switch window) | Thumb on the index fingertip, let go: back to the last window. **Hold** it half a second: the window switcher stays open; move the hand left / right to pick a window (one window per few cm), let go to switch to it. The selection stops at the first and last window instead of jumping around to the other end; moving back goes back at once (`ALT_TAB_STOP_AT_ENDS`) |
| Ctrl+C (copy) | Thumb on the middle fingertip |
| Ctrl+V (paste) | Thumb on the ring fingertip |
| Ctrl+Z (undo) / Ctrl+Y (redo) | Palm to the camera, thumb across the palm on the base of the little finger (like button 5). Once = undo, twice quickly = redo. A single one waits about half a second to see whether a second follows |
| Print Screen | Thumb on the middle and ring fingertips together |
| Voice typing / on-screen keyboard | Thumb on the index and middle fingertips together: Windows voice typing on / off (Win+H). Twice quickly: the on-screen keyboard opens or closes; type on it with the right hand |
| Esc | Make a fist (thumb tucked in). Esc comes after 0.5 s while the fist is still closed, once per fist (open the hand before the next one). Only when it is the only fist in view: two fists are gestures off / on, and a right-hand fist is scrolling. Two quick fist-open cycles with either hand swap the main hand instead |
| Play / pause | Fold four fingers, keep the thumb clearly out (sideways is fine), hold briefly (0.12 seconds), then **open the hand**. It acts on opening, once, at most once per 1.5 s. Tucking the thumb into a fist cancels |
| Next / previous track | Make the same folded-fingers, thumb-out pose, hold it still about a third of a second, then move it right / left. **One song per swipe**, even if you move further or hold the hand out. Return near where you started and **wait there 0.5 seconds**, then swipe in **either direction**. Passing through the start does nothing; leaving early restarts the wait. Both directions use the same fixed distance. Opening after skipping does not also play / pause |

The shortcuts are set in `SECOND_KEYS` at the top of `hand_mouse.py` (e.g. `"middle": "ctrl+c"`), and
`SECOND_HAND_KEYS = False` turns them all off.

Keep the hand fully inside the camera picture. For a two-finger shortcut, touch both fingertips clearly;
for copy / paste, keep the neighbouring fingertip away from the thumb. Pinches take priority over track
gestures. Open the hand between separate thumbs-up gestures to reset the movement start point.
After a fingertip pinch, open fully for a moment before starting a music gesture. A pinch keeps control
until that release, so a misread during Alt+Tab movement cannot turn into a track swipe.
Pinches now require visible fingertip contact; moving the thumb near an open index finger does nothing.
The keyboard's double-pinch allows three quarters of a second between taps (voice typing waits that long
to check for the second tap). Undo/redo keeps its shorter double-tap timing.
If the on-screen keyboard cannot launch, the camera panel shows "on-screen keyboard: failed" instead of
claiming it opened.

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

Camera-edge safety border: the whole moving cursor box stays inside a visible blue inset,
roughly one hand-width from the image edges (14% horizontally, 18% vertically).
Following, resizing, distance scaling and saved positions all respect this boundary.
The screen edges remain reachable at the cursor-box edges. This reserves space for gestures;
it does not prevent the user from physically moving their hand outside the camera image.

L-pose recognition uses thumb spread relative to the index axis, normalized by palm size,
instead of the rotating finger bounding box. A narrower projected thumb/index angle is accepted
with release hysteresis; folded-finger, fingertip-separation and full-visibility checks remain.
Photo-derived landmark tests cover sizes, rotations, both sides and tucked/parallel-thumb rejection.

Update notifications (1.0.0 onward): a background check reads APP_VERSION from GitHub main,
20 seconds after launch and every six hours while running. Newer major.minor.patch versions
notify once per version, remembered across restarts. Tray: Check for updates / Download latest
version / installed version. Manual checks always report a result. Offline checks fail quietly;
no files are downloaded or replaced automatically. Older copies need this version installed once.
Before publishing a new version to main, increase APP_VERSION in hand_mouse.py. Develop versions
newer than main never prompt to downgrade. The check reads at most 16 KiB with an 8-second timeout
and never executes downloaded source. Update checks continue while gesture tracking is paused.

Camera selection (1.0.1): right-click the tray icon -> Camera -> Camera 1 through 10
(OpenCV indices 0 through 9; these are numbered choices, not a detected-device list).
Use Camera & log window to identify the feed. The choice persists as camera_index.
Choosing a different camera restarts the app with gestures off and clears the old mode,
probe time and hand calibration. Unavailable cameras can be changed from the tray even
while opening fails. Camera profiles include their index; legacy profiles apply only to index 0.

Windows mouse compatibility (1.0.2): movement, buttons and both wheel axes use checked
SendInput with the full native INPUT union. Absolute movement includes VIRTUALDESK for
negative monitor origins. Rejected delivery is logged at most once per five seconds;
there is no fallback that could duplicate a click. This improves input diagnostics and
uses a consistent input stream for overlays; it does not bypass UIPI, UIAccess or secure
desktop restrictions. Real OSK/Snipping Tool verification is still required. Recent logs
also showed 6-8 tracking FPS and long pinches; delivery acceptance does not prove a target
processed an event. Do not claim legacy mouse APIs alone caused the reported problem.

Administrator startup (1.0.3): the user confirmed OSK gesture clicks work when elevated.
Every actual app launch now checks elevation before log files, mutex and camera setup.
A normal launch requests standard Windows UAC approval using ShellExecuteW("runas"),
then the parent exits. The exact Python executable, script path and arguments are preserved
with Windows command-line quoting. Already-elevated launches and automatic restarts do not
request elevation again. Desktop shortcuts, batch launchers and Start with Windows all reach
this same startup check. Windows startup may require a physical approval of the UAC prompt;
this does not create an unattended elevated scheduled task or change UAC policy. Cancelling
leaves the app closed. Main starts camera on and gestures off after approval, as before.

Screenshot precision (1.0.4): Cursor sensitivity settings have a checkbox, enabled by default,
"Reduce sensitivity by 25% while selecting a screenshot". Saved as screenshot_precision.
Visible Windows capture overlays are probed at most every 0.2 seconds, including captures
opened with physical shortcuts. While selecting, CursorFilter.gain_multiplier is 0.75;
it returns to 1 on capture exit/cancel or disabling the checkbox. The normal slider value
is unchanged, including adjustments during capture. Snipping Tool's ordinary editor does
not count; detection checks the process and capture-class/full-monitor topmost geometry.
The temporary factor is never saved as the normal sensitivity, and detection errors restore it.

Deliberate reactivation (1.0.5): enabling by hands now requires BOTH palms open for 0.4 s,
BOTH fists held continuously for 2 s, then BOTH palms open for 0.3 s. Hands remain visible
and readable throughout. Resting fists, one hand, lost hands, thumb-out music poses and
partial sequences cannot enable gestures. Five-second timeouts apply before/after the hold.
The one-second two-fist pause stays available while enabled. Tray/manual enable remains.
Startup also requires the deliberate sequence. Completion emits no other actions that frame.
This supersedes older descriptions of two fists toggling gestures both ways.

Simplified reactivation (1.0.6), superseding 1.0.5: no initial open-palms stage. Hold both
fists continuously for 1.5 through 3 seconds, then both palms open continuously for 1 second.
Short or overlong holds do not enable. An overlong hold cannot start another timer while
fists remain closed; open palms for one second to reset before retrying. Hands must stay
visible/readable throughout. Normal finger-unfolding gets a 0.7-second transition window.
The one-second pause gesture and manual tray controls are unchanged.

Wake feedback (1.0.7): a short high beep at 1.5 seconds means the fist hold is sufficient:
open both palms and keep them open for one second. A longer low beep means the hold
exceeded three seconds or the palms did not open within the transition window. Gestures
stay off. Each cue fires once per attempt, not per frame; release/reset allows a new attempt.
Cues use the existing nonblocking beep helper and respect SOUNDS. Activation still has its
existing confirmation tones. Timing and safety rules are unchanged.

Wake retry fix (1.0.8): a failed/overlong attempt rearms after a brief 0.2-second opening,
not another full one-second opening. Reclosing fists after an incomplete final opening
starts a fresh 1-3-second attempt, with a new ready beep. Imperfect final palms restart
only the one-second continuous-open timer instead of entering blocked state. Overheld
fists still cannot rearm without a release; lost/unreadable hands still cancel attempts.
Regression tests reproduce all three formerly blocked retry cases.

Wake startup reliability (1.0.9): minimum fist hold is now 1 second (maximum still 3),
followed by both palms open for 1 second. Once fists are recognized, use FIST_KEEP like
normal fist tracking instead of restarting on every strict FIST_CURL misread. The wake
visibility check allows fully visible landmarks inside the image's old 2% edge margin.
Unreadable, missing or actually clipped hands still cancel. Once-per-second wake diagnostics
record phase, hand count, extensions, thumb spread and visibility to diagnose live failures.
