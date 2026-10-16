# Hand Mouse: notes for Claude Code

You are taking over an existing, working app. Read this file first. It explains what the app does, how it is
built, how to test it safely, and what we learned along the way (most settings exist for a measured reason).

## What it is

**Hand Mouse** is a single-file Python app (`hand_mouse.py`, about 3,200 lines) that turns the laptop webcam into a
mouse on **Windows 11**. It tracks the user's hands with **MediaPipe Hand Landmarker** and moves the cursor,
clicks, scrolls, and controls the volume with hand gestures. It runs in the background with a tray icon,
starts from a desktop shortcut, and can start with Windows.

The user is the only user. They test by using it live and report problems with screenshots of the camera
window. Their English is not their first language, so read requests generously and reply in plain words. They
care that it works reliably; when unsure, measure before claiming something helps.

## Files in this folder

| File | What it is |
|---|---|
| `hand_mouse.py` | The whole app. Settings are the UPPER_CASE constants at the top (lines ~57-260), each with a comment. |
| `tests/` | Test suites with fake hands, fake mouse, fake camera and fake window. Run `python tests/run_tests.py`. |
| `README.md` | User-facing guide (gestures, tray, tuning). Keep it in sync when gestures change. |
| `hand_landmarker.task` | MediaPipe model (downloaded automatically if missing). |
| `hand_finder.onnx` | Second hand detector: HaGRIDv2 YOLOv10n "hands", exported to ONNX at 320x320 (see below). |
| `hand_mouse.ico` | Tray / shortcut icon. |
| `hand_mouse_state.json` | Learned state: `ref_palm` (normal hand size), `camera` (chosen backend/mode/fps), `box` (cursor box), `window` (camera window rect), `main_side` ("right"/"left"), `welcomed_v*` flags. Safe to delete keys. |
| `hand_mouse.log` (+ `.1`, `.2`) | Log, rotated at 2 MB. Has a `diag` line every second (see Diagnostics). |
| `hand_mouse_previous.py` | Backup of the version before the last change (by convention, refreshed before every deploy). |
| `gestures.html` | Help page, regenerated from `HELP_HTML` in the code every time it is opened. |
| `snapshots/` | Plain camera frames saved with **S** in the camera window, for debugging missed gestures. |
| `debug/` | Debug mode pictures (tray: "Debug: save a picture of every gesture", state key `debug_pictures`, off by default). One JPEG per recognised gesture: 8 frames over the last 1.2 s with landmarks, the log line(s) as title, per-hand numbers. Named `YYYYMMDD_HHMMSS_mmm <what>.jpg` to match the log. **Ask the user for these when a gesture misfires.** Not in git. |
| `setup.bat`, `run_preview.bat`, `start_background.bat`, `requirements.txt`, `python_path.txt` | Install / launch helpers. `python_path.txt` holds the Python used (Python 3.12 in `%LOCALAPPDATA%\Programs\Python\Python312`). |
| `YOLOv10n_hands.pt` | Original PyTorch weights of the hand finder. Not used by the app; can be deleted. |

## Running

- **Normal use:** the desktop shortcut runs `pythonw.exe hand_mouse.py` (no console). There is a single instance,
  enforced by a named mutex. Double-clicking the shortcut while it runs opens the camera window of the running
  instance (named event `Local\HandMouseShowView`).
- **With the camera window from the start:** `python hand_mouse.py --preview` (or `run_preview.bat`).
- **IMPORTANT: auto-restart on edit.** `AUTO_RESTART_ON_EDIT = True` means the running app restarts itself about
  1 s after `hand_mouse.py` is saved. Every save you make restarts the user's live app.
  - A syntax error or crash-at-import kills it, and the user loses their mouse until they start it again.
  - Before saving, check with `python -m pyflakes hand_mouse.py` (or write to a temp file, check, then replace).
  - Copy the current file to `hand_mouse_previous.py` before a risky change.
- **After a deploy,** confirm in `hand_mouse.log`: `hand_mouse.py changed, restarting` -> `started (...)` ->
  `camera ready in N s`, with no `ERROR` / `fatal error`.
- **Dependencies** (`requirements.txt`): mediapipe (Tasks API, 0.10.x), opencv-python (5.0 on this laptop),
  numpy, pynput (hotkeys), pystray + Pillow (tray), onnxruntime (hand finder) and pycaw + comtypes (volume).
  `ensure_package()` pip-installs pystray/onnxruntime/pycaw on first use; pycaw is pre-installed in a
  background thread at start, so the first thumbs-up doesn't block.

## Gestures (current behaviour)

The **main hand** is the user's **right hand**. All mouse gestures are made with the main hand. The other hand
gives keyboard shortcuts (`SECOND_HAND_KEYS`, table below) and takes part in the two-fist on/off
(`SECOND_HAND_GESTURES = False`; True gives it the main-hand gestures instead of the keys). To make the **left** hand the main hand:
show only the left hand and make a fist twice quickly. This is remembered in state (`main_side`) until the right
hand does the same.

| Action | Gesture | Key settings / code |
|---|---|---|
| Move cursor | Index fingertip of the main hand inside the cursor box | `CursorBox`, `CursorFilter` |
| Left / right click | Thumb touches middle / ring fingertip (3D distance / palm length < `TOUCH_ON` 0.34) | `ClickTracker` |
| Middle click | Thumb on middle and ring tips together | `BOTH_RATIO`, `UPGRADE_WINDOW` |
| Drag | Keep touching and move (cursor stays put until moved `DRAG_START_PX`) | |
| Double-click | Two quick pinches; adds a helper click if the second comes later than the Windows double-click time | `DOUBLE_CLICK_WINDOW`, only after a short click (< `QUICK_RELEASE_HOLD`) |
| Mouse button 4 | Thumb tip on **index fingertip** ("OK"), middle and ring straight | `SideButtonTracker`, `INDEX_PINCH_MARGIN` |
| Mouse button 5 | Palm to camera, thumb folded across the palm onto the palm area under the ring/little finger (2D): from their knuckle line (widened `X2_WIDEN`) down `X2_DEPTH` 0.55 toward the wrist; distance 0 inside. Was only the knuckle line until 2026-10-16 (a thumb held on the palm under the little finger read 0.3-0.5 and did nothing) | `x2_area`, `SIDE_TOUCH_ON` 0.12, `SIDE_FACING`, `tests/test_button5_area.py` |
| Volume | Thumbs-up held `VOLUME_HOLD` 0.45 s; thumb up = 100%, turned to down = 0%; changes at most 150%/s | `ThumbVolume`, `thumb_out`, `thumb_angle`, `WinVolume` (pycaw) |
| Scroll | Fist (thumb tucked) and move up/down, or left/right (`HSCROLL`, horizontal wheel), from where it closed. Only the axis moved further scrolls (`FistScroll.axis`, switches when the other is 1.5x bigger); sideways distance is converted to height units (`/ aspect`) so the same real move scrolls the same | `FistScroll`, `SCROLL_*`, `HSCROLL_*`, `tests/test_hscroll.py` |
| Gestures off / on | Both hands as fists for `STOP_HOLD` 1 s; switches once per hold; open a hand (or hide hands) `STOP_REARM` 0.4 s to switch again | `Engine` two-fist block, `_rearm` |
| Switch main hand | Only the non-main hand in view, fist twice quickly | `_switch_main`, `DoubleGrab` |
| Window swipe | Disabled (it was second-hand-only); code is still there behind `SECOND_HAND_GESTURES` | `Swiper` |

**Second-hand keyboard shortcuts** (`SecondHandKeys`, map in `SECOND_KEYS`, tests in `test_second_keys.py`).
`second_contact()` reads which tip(s) the thumb touches with the click logic (3D, `TOUCH_ON`/`TOUCH_OFF`,
pairs by `BOTH_RATIO`) and the button-5 spot (`thumb_on_palm_base`, 2D). A pinch acts on **release**, decided
from the **median** thumb-to-tip distances over the touch (`classify_tips`), and needs 2 frames. It ends after
`KEY_RELEASE_DELAY` 0.18 s apart (`ALT_TAB_RELEASE` 0.3 s with the switcher open), or at once when a short pinch
is clearly wide open (so "twice" taps don't merge); 2 fist frames in a row cancel it. Every touch is logged
(`second hand touch ... -> name`, with the medians) when `DIAGNOSTICS` is on. A gesture with a `"... twice"` entry waits
`KEY_DOUBLE_WINDOW` 0.45 s before its single action.

| Gesture (second hand) | Default | Notes |
|---|---|---|
| Thumb on index tip | Alt+Tab | Held `ALT_TAB_HOLD` 0.5 s: Alt stays down, hand moves `ALT_TAB_STEP` -> Left/Right arrow, release -> Alt up. `ALT_TAB_STOP_AT_ENDS`: the app counts the switcher's windows (`alt_tab_windows`: Raymond Chen's owner-chain rule + not cloaked + not tool window; matched the switcher on the laptop), follows the selection itself (starts at index 1) and sends no arrow past either end; the start point still follows the hand so moving back works at once. Reading the switcher with UI Automation was tried: it returned 0 items in 3 of 4 tries, so it isn't used. Alt is also let go on hand lost, gestures off, `release_all` |
| Thumb on middle / ring tip | Ctrl+C / Ctrl+V | |
| Thumb on little-finger base | Ctrl+Z; twice Ctrl+Y | Same spot test as button 5 |
| Thumb on middle + ring | Print Screen | |
| Thumb on index + middle | Win+H (voice typing); twice: on-screen keyboard | `WinMouse.toggle_keyboard`: `osk.exe` via `os.startfile` (no admin needed), closed with `WM_SYSCOMMAND/SC_CLOSE` to `OSKMainClass` (both checked on the laptop) |
| Fist (held `KEY_FIST_HOLD` 0.2 s) | Esc | Acts while closed, once per fist; re-armed when two fingers are straight again. Only the only fist in view (`two_fists` blocks it, incl. a right-hand scroll fist). Alone in view (no main hand) waits `GRAB_MAX`+0.15 s, since two quick fists are the main-hand switch. Was "on opening" until 2026-10-15; the user asked for it on closing |
| Thumbs-up (>= `KEY_THUMB_MIN` 0.15 s), then thumb tucked (`is_fist(keep=True)`) | Play/pause | Fires on the tuck. The resulting fist is not Esc (`thumb_real` within 0.4 s); a thumb that only flicks out (< 0.15 s) blocks nothing |
| Thumbs-up moved right / left | Next / previous track | Counts only after the thumbs-up is steady `KEY_THUMB_MIN`; smoothed x; one per `TRACK_STEP` 0.12 (x hand size, never below 0.8: a sideways fist reads small and made the step tiny); `TRACK_REPEAT` 0.4 s between skips; one direction per thumbs-up (moving back re-anchors, no opposite skip). First version (step 0.08, no limits) fired 5 skips in 1.6 s on 2026-10-16. After a skip the tuck does nothing |

There are also hotkeys (Ctrl+Alt+H stop/resume, Ctrl+Alt+C re-learn hand size, Ctrl+Alt+Q quit) and a tray
menu: Camera & log window, Gestures on, Stop/Resume, Gestures help, Start with Windows, Re-learn my hand size,
Close. In the tray icon an orange badge means gestures are off (camera on), and a red badge means stopped
(camera off).

## Architecture (one frame)

1. **`Camera`** is a thread that always keeps only the newest frame. **`open_camera`** probes backends and
   modes (MSMF 1280x720 gives 30 fps here; DSHOW gave only 10) and caches the choice in state.
   `OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0` cuts the open time from 9 s to about 2.8 s. The frame is
   mirrored (`cv2.flip`) before anything else.
2. **`HandSensor.process(rgb)`** returns a list of `Hand` objects:
   - **Full-frame tracker:** a VIDEO-mode landmarker on a 640-wide INTER_AREA downscale (`DETECT_WIDTH`).
   - **Zoomed re-read:** small hands (`size < ZOOM_BELOW`) are re-read from a zoomed full-resolution crop by an
     IMAGE-mode landmarker; there is a second try with a larger crop. If both fail the hand is marked `unsure`,
     and gesture states are held instead of updated.
   - **Rescue:** a hand lost less than `RESCUE_TIME` ago is searched for in a zoomed crop where it was.
   - **Centre scan:** with no hands in view, the middle of the picture is scanned every `SCAN_EVERY` frames.
     Rescue and scan use the **strict** `finder` model, `DISCOVER_CONFIDENCE` 0.7.
   - **Colour fallback:** when nothing is found for a moment, the app tries the picture with red and blue
     swapped, then a per-area white-balanced copy, and keeps whichever works (`self.view`). Every ~60 frames it
     re-checks whether normal colours work again.
   - **`HandFinder`** (ONNX YOLO) runs when still nothing is found. MediaPipe then reads a crop of 2.2x the
     finder's box. It runs every frame while it is the one finding the hand, otherwise every `HAND_FINDER_EVERY`
     frames.
   - **Cleanup:** `dedupe` removes duplicate detections and `_inside` drops hands that are mostly outside the
     frame.
3. **`Hand`** fields:
   - `img`: 21 normalised (x, y) points in the mirrored picture.
   - `flat`: the same points with y scaled by aspect, so both axes share one unit.
   - `world`: 3D metres from MediaPipe.
   - `label`: MediaPipe handedness.
   - Cached properties: `ext` (finger extension: tip-wrist / knuckle-wrist; about 1.0 folded, 1.8 straight),
     `pinch`, `side` (button 4/5 distances; **not** left/right), `tip_min`, `facing`, `palm`, `size`.
   - `hand_side` ("right"/"left") is set by the `Engine`.
4. **`Engine.update(hands, now)`** runs in this order:
   1. Match hands to tracks by position (`Track`).
   2. Roles via `_roles`:
      - Track `side_score` votes: position +/-2 when both hands are in view, and the label +/-1, clamped at
        +/-12. `RIGHT_HAND_LABEL = "Left"`, because MediaPipe calls the user's right hand "Left" in the
        mirrored picture.
      - The main hand is the one whose side equals `main_side`.
   3. Fist states for all hands (needed for two fists); scrolling counts only for the main hand.
   4. Volume (main hand).
   5. Two-fist on/off.
   6. Main-hand switch.
   7. If gestures are off: return.
   8. Scroll, side buttons, then swipe (off).
   9. Second-hand keys (`SecondHandKeys.update`; the non-main hand, also when it is alone in view).
   10. If there is no main hand: hold everything and return.
   11. Clicks, then cursor (fingertip spike filter, `CursorBox` update with compensation, `CursorFilter`).
5. **Cursor:**
   - **Mapping:** the fingertip position inside the cursor box maps to the virtual screen (all monitors).
   - **`CursorFilter`:**
     - One-Euro smoothing.
     - A steady radius.
     - Precision gain for slow motion.
     - Realignment to the absolute position during fast motion and at the box edge.
     - A hold (frozen) during clicks, fists and the thumbs-up.
   - **`CursorBox`:**
     - Behaves like a dead-zone game camera: it follows the finger after it has been outside for 0.5 s.
     - Its size slowly fits the 5th–95th percentile of the finger's movement range (0.75–1.3x).
     - `CursorFilter.shift()` compensates every box change, so the cursor never jumps.
6. **`WinMouse`** uses `SetCursorPos`, `mouse_event` (including XBUTTON 1/2) and `keybd_event` (shortcuts, media
   and volume keys). The process is per-monitor-v2 DPI aware.
7. **UI:**
   - `TrayIcon` (pystray).
   - **`ViewWindow` runs the OpenCV window in its own thread.** Windows blocks a window's thread while its title
     bar is dragged. Before this, dragging the camera window with a gesture deadlocked: the app could not see the
     release, so the mouse button stayed down.
   - `draw_preview` (camera picture) plus `draw_panel` (right-hand panel: current gesture, per-hand numbers,
     and a colour-coded log fed by the `EventFeed` logging handler).

## Lessons learned (please keep these)

- **3D depth from MediaPipe is unreliable for "thumb touches a finger's side or palm".** Button 4 on the middle
  of the index finger, and button 5 on the palm, read 0.36–0.62 in 3D while touching. 2D picture distance worked
  (0.02–0.05). Fingertip-to-fingertip pinches are fine in 3D.
- **Gestures on the path of another gesture misfire.** Button 4 on the middle of the index finger fired before
  every click, because the thumb crosses it, so it moved to the index fingertip. When adding a gesture, think
  about which hand shapes the hand passes through on the way to other gestures.
- **Fist vs thumbs-up:** `thumb_out` (thumb tip outside the folded fingers' 2D box) separated the two perfectly
  on real video: fists ≤ 0.13, thumbs-ups ≥ 0.5. `is_fist` excludes thumb-out, so a thumbs-up never scrolls.
- **Left-hand pinches split in the first live test (2026-10-14):** one held pinch fired Alt+Tab 2-4 times and
  the switcher let go after 0.1-0.2 s. Causes: a start rule "two fingers straight" (the hand model reads the
  pinching finger and relaxed ring/little as bent, ~1.3-1.4), a 0.10 s release, and a per-frame label vote.
  Fixed with: only "not a fist" to start / nothing to continue, 0.18 s release, median distances. The index,
  middle and ring tips sit within ~0.3 palm lengths of each other, so tip vs pair decisions are close calls:
  check the `second hand touch` log lines before changing `BOTH_RATIO`.
- **3D depth also breaks the held "OK" sign when the hand moves** (Alt+Tab switcher, 2026-10-14 debug
  pictures): thumb clearly on the index tip, but `t-idx` read 0.53-0.65 (> `TOUCH_OFF`), so the switcher let go
  after 0.5-0.8 s. A held "index" touch now also stays held while the thumb is within `INDEX_HOLD_2D` 0.30 of
  the index tip in the picture (`thumb_index_2d`; shown as "(2d ...)" in the live numbers).
- **The left "OK" sign also reads too far apart to start** (same day, "need to hold every gesture", 14 of 83
  touches "too short"): held, 3D was 0.26-0.38 against the click limit 0.34. The log's 3D/2D pairs (203 samples)
  separate well in 2D: held < 0.3, open > 0.6. So the index touch starts at 3D < `SECOND_INDEX_ON` 0.40, or
  2D < `INDEX_START_2D` 0.30 with 3D < `INDEX_START_3D_MAX` 0.60. Middle / ring keep `TOUCH_ON` (they read
  0.16-0.27 held). Debug pictures print each frame's thumb distances ("idx 3D/2D mid ring") under it,
  because re-reading hands from the saved frames doesn't work (drawn skeleton, 480 px).
- **Middle click read as left at high frame rates (2026-10-15).** The app went from ~14 to ~27 fps, so "2 frames
  or `CLICK_DELAY`" decided a click after ~40 ms, before the ring finger arrived (debug picture: first frame
  middle 0.19, ring 0.61). And every retry within `DOUBLE_CLICK_WINDOW` was a "quick" double-click press that
  repeated "left" and was never upgraded. Now: a new touch clicks after 2 frames **and** `CLICK_DELAY`; the
  button is middle if the latest 2 frames say middle (`ClickTracker._choose`); a 2+ frame tap that ends before
  the delay still clicks on release; the late-ring upgrade also works on a double-click press
  (`tests/test_middle_click.py`). Timing rules in frames change meaning when the frame rate changes.
- **Left copy / paste read as Win+H / Print Screen (2026-10-16).** Debug picture: thumb on the middle tip, 3D
  index 0.35 < middle 0.40 (so "index+middle"), picture middle 0.14 / index 0.45. The touch's finger(s) are now
  chosen from per-frame min(3D, picture) distances (picture ignored when 3D >= `INDEX_START_3D_MAX`); the touch
  log line shows both. And a left-hand touch can't start while the hand is cut off by the picture edge
  (`fully_in_view`): a hand coming up from the bottom was read as middle+ring.
- **Toggles need a real release.** Two fists used to switch on and off forever, because one dropped frame looked
  like "released". Re-arming now needs an open hand, or no hands, for 0.4 s.
- **Image enhancement made detection worse.** CLAHE, gamma and grayscale were tried and measured: they
  amplify noise or remove the skin colour the model needs.
- **What did help in the dark:**
  - Lower detection/presence confidence (dark test videos: 1–18% -> 75–83% of frames found).
  - The red/blue swap for coloured light (a blue-lit hand 0% -> 53–99%).
  - The HaGRID hand finder (the user's dark frames: 0% -> 80–100%).
- **Lower thresholds bring false hands.** Zoomed crops of a face or headphones in swapped colours produced false
  hands at 0.45 confidence. Discovery searches use 0.7, which gave none.
- **A crop-tracking VIDEO landmarker is a trap.** Using one for zoomed re-reads was faster, but it misread finger
  shapes in 80% of frames when the gesture changed, so it was reverted.
- **The handedness label is right in 96–100% of frames,** with wrong runs of up to 7 frames. That is why sides
  are vote-averaged per track.
- **In dim light the camera lowers its fps** (longer exposure), which blurs the hand. Software can't recover
  blur. The app shows "DIM LIGHT" and a one-time tip; the real fix is a lamp in front of or beside the user.
- **OpenCV 5:** `destroyWindow` on a window already closed with X raises an exception. All window calls are
  guarded.
- **Mixed-DPI monitors:** the camera window uses `WINDOW_NORMAL | WINDOW_KEEPRATIO`. Its rect is remembered in
  state.

## Testing

- **`python tests/run_tests.py [filter]`** runs everything in a few minutes on any OS. Each file prints
  PASS/FAIL lines and stops at the first FAIL.
- **`tests/test_core.py`** holds the synthetic hand model (`make(px, py, pinch, fist, fold, label, jitter)`),
  `FakeMouse` and helpers, and the other tests import it.
  - It sets `hm.RIGHT_HAND_LABEL = "Right"`, because synthetic hands are labelled with the real side.
  - `TV.thumbs(angle)` in `test_volume.py` builds a thumbs-up turned to an angle.
- **Loop tests** (`test_loop_*`) run the real `run()` main loop with a fake landmarker, camera and cv2 window
  functions. `test_loop_window_drag` checks that tracking continues while the window thread is blocked.
- **Real-video checks** were run during development on the MediaPipe sample videos (`gesture_video.mp4`,
  `hand_video.mp4` from google-ai-edge/mediapipe-samples), shrunk to simulate distance and darkened or tinted to
  simulate light, by comparing found % and "shape ok %" against the full-quality reference. They are not
  included here (too large), but this method is how to judge detection changes. For anything about real
  detection, prefer the user's `snapshots/` frames.
- **When you change behaviour:** update or add a test, run the whole suite, run pyflakes, then deploy and check
  the log.

## Diagnostics

- `hand_mouse.log` `diag` line every second:
  `diag fps F hands N | M ms/frame | camera C fps light L | min t-mid … | scrolling frames a/b | zoomed z found-again r | size k | pressed … | <status lines>`.
  - `size` is the distance factor: 1 = the normal distance learned in `ref_palm`, 0.5 = twice as far.
  - `light` is the mean picture brightness (about 30 = a very dark room).
- **Camera window** (tray -> Camera & log window): the right-hand panel shows live numbers per hand:
  - fingers: extension of index, middle, ring, little
  - `t-mid`, `t-ring`: click distances
  - `t-idx`: button 4
  - `t-ring-base`: button 5
  - `size`, the state of each gesture, and the cursor box
  - **S** saves a clean frame to `snapshots/`, **P** stops/resumes, **Esc** closes the window.
- **Debug pictures** (`GestureRecorder`, a logging handler): gesture log lines (`DEBUG_EVENTS`) are queued; the
  main loop keeps the last `DEBUG_SPAN` s of 480-wide frames + landmarks (`add`) and after each frame saves one
  strip for the queued lines (`save_pending`, at most one per 0.25 s, written by a background thread, folder pruned
  to the newest `DEBUG_KEEP` 500 after every save, oldest by file name). Don't name a handler method `flush`: logging calls it with no arguments at exit.
- **Events in the log:** clicks, buttons, scroll on/off, volume on/off, gestures off/on, main hand
  switch, colour-view switches, the hand finder loading, camera settings at open.

## Known open issues and ideas

- **Play / pause gesture removed (2026-10-11)** at the user's request (thumb out + double finger fold). The
  version that still had it is in `hand_mouse_previous.py` from that date.

- **Pinch missed with a bent middle finger: mostly fixed 2026-10-16.** The depth guess read t-mid 0.39 while the
  thumb was visibly on the middle tip (~0.14 apart in the picture). `click_distances`: while 3D < `TOUCH_OFF`, a
  picture distance < `CLICK_2D` 0.20 counts (`tests/test_click_2d.py`). Live numbers / debug pictures now show
  the 2D middle and ring distances too: check them for false clicks (a thumb resting near the middle tip in
  the picture) before loosening `CLICK_2D`.
- **Dim-light blur.** Possibly try a shorter camera exposure (`CAP_PROP_EXPOSURE`). At open, MSMF reports
  auto exposure 0.0, exposure -5. This was never tested, so verify on the laptop and revert if the picture gets
  too dark.
- **Second-hand keys are new (2026-10-14) and not yet tested live.** Watch for: Esc from a left fist when the user
  only meant to rest the hand, Ctrl+C/V misfires if the hand roles flip, the Alt+Tab step size (`ALT_TAB_STEP`).
  The help page lists the default keys; it doesn't follow edits to `SECOND_KEYS`.
- **Spurious "main hand changed" log lines** used to be common. The newer role logic logs only real side
  switches; keep it quiet.
- **Hand finder licence.** It is free for non-commercial use (HaGRID, Ultralytics export), which is fine for this
  personal app.

## Working style that worked well

- **Measure, then change.** Reproduce with the user's own screenshots or snapshots, or a synthetic test, and
  report numbers (before -> after).
- **One change at a time:** deploy, then check the log right away. Tell the user in simple words what changed,
  how to use it, and what still won't work.
- **Keep `README.md`, the module docstring and `HELP_HTML` in sync with gesture changes.**
