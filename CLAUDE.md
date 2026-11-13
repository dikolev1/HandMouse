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

- **Startup:** `run()` uses `gestures_on=False` every launch/reload. The camera still opens and tracks;
  orange tray badge and two-fist wake-up work. Engine default stays on for direct model tests.
- **Sensitivity:** tray -> Cursor sensitivity opens `SensitivityWindow` (Tk in its own lazy UI thread).
  Range 25%-250%, `cursor_sensitivity` in saved state, 100% default. `Engine.set_sensitivity` updates only
  cursor gain and never moves it at setting time. UI saves debounce 250 ms and flush on close/quit.
  State writes use an RLock plus atomic replace so concurrent slider/camera/box/hand-side saves preserve
  each other's fields. Tk cycles are collected on the owning UI thread after shutdown; otherwise
  Tcl_AsyncDelete can abort Python. Standalone UI checks covered save, reopen, reset and clean shutdown.

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
(`SECOND_HAND_GESTURES = False`; True gives it the main-hand gestures instead of the keys). To swap the main hand, make two quick fist-open cycles with either hand, with one or both visible.
This is remembered in state (`main_side`). Simultaneous gestures swap once; the switch frame releases held actions.

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
| Switch main hand | Either hand, one or both visible, fist twice quickly; toggles sides once | `_switch_main`, `DoubleGrab` |
| Window swipe | Disabled (it was second-hand-only); code is still there behind `SECOND_HAND_GESTURES` | `Swiper` |

**Second-hand keyboard shortcuts** (`SecondHandKeys`, map in `SECOND_KEYS`, tests in `test_second_keys.py`).
`second_contact()` reads which tip(s) the thumb touches with the click logic (3D, `TOUCH_ON`/`TOUCH_OFF`,
pairs by `BOTH_RATIO`, or both below `SECOND_PAIR_ON` 0.25 with ratio < `SECOND_PAIR_RATIO` 2.5) and the
button-5 spot (`thumb_on_palm_base`, 2D). A pinch acts on **release**, decided
from the **median** thumb-to-tip distances over the touch (`classify_tips`), and needs 2 frames. It ends after
`KEY_RELEASE_DELAY` 0.18 s apart (`ALT_TAB_RELEASE` 0.3 s with the switcher open), or at once when a short pinch
is clearly wide open (so "twice" taps don't merge); 2 fist frames in a row cancel it. Every touch is logged
(`second hand touch ... -> name`, with the medians) when `DIAGNOSTICS` is on. A gesture with a `"... twice"` entry waits
`KEY_DOUBLE_WINDOW` 0.45 s before its single action (keyboard / voice pair: `KEYBOARD_DOUBLE_WINDOW` 0.75 s).

| Gesture (second hand) | Default | Notes |
|---|---|---|
| Thumb on index tip | Alt+Tab | Held `ALT_TAB_HOLD` 0.5 s: Alt stays down, hand moves `ALT_TAB_STEP` -> native Tab / Shift+Tab cycling, release -> Alt up. `WinMouse.switch_window_step` reasserts Alt if its key-down state was lost. `ALT_TAB_STOP_AT_ENDS` counts windows, tracks selection from index 1 and sends no step past either end; the anchor follows so moving back works at once. No bare arrows are sent. Alt is let go on hand lost, gestures off, `release_all` |
| Thumb on middle / ring tip | Ctrl+C / Ctrl+V | |
| Thumb on little-finger base | Ctrl+Z; twice Ctrl+Y | Same spot test as button 5 |
| Thumb on middle + ring | Print Screen | |
| Thumb on index + middle | Win+H (voice typing); twice: on-screen keyboard | `WinMouse.toggle_keyboard`: `osk.exe` via `os.startfile` (no admin needed), closed with `WM_SYSCOMMAND/SC_CLOSE` to `OSKMainClass` (both checked on the laptop) |
| Fist (held `KEY_FIST_HOLD` 0.5 s) | Esc | Acts while closed, once per fist; re-armed when two fingers are straight again. Only the only fist in view (`two_fists` blocks it, incl. a right-hand scroll fist). Two quick fist-open cycles with either hand switch the main hand instead. Was "on opening" until 2026-10-15; the user asked for it on closing |
| Four fingers folded, thumb out (>= `PLAYPAUSE_HOLD` 0.12 s and peak >= `THUMB_REAL_OUT` 0.5), then open the hand | Play/pause | User clarified with a photo 2026-11-06: sideways thumb-out is valid; OPENING (at least 3 fingers straight) acts, not tucking the thumb. At most once per `PLAYPAUSE_REPEAT` 1.5 s. Tucking cancels without Esc. Repeat/peak guards still protect resting hands. Track arming remains 0.3 s |
| Thumb-out pose moved right / left | Next / previous track | Steady `KEY_THUMB_MIN`, smoothed x. One skip when distance from the fixed origin reaches `TRACK_STEP` 0.12 x max(hand scale, 0.8), frozen when arming. `thumb_ready` stays false until raw AND smoothed x stay within `TRACK_RETURN` 0.4 of that distance for `TRACK_RETURN_HOLD` 0.5 s continuously. Leaving the zone or unreadable frames reset `thumb_return_since`. Either direction can then act. `TRACK_REPEAT` 0.4 s is an extra guard. Never advance the origin during the pose. Opening after any skip does not also play/pause |

There are also hotkeys (Ctrl+Alt+H stop/resume, Ctrl+Alt+C re-learn hand size, Ctrl+Alt+Q quit) and a tray
menu: Camera & log window, Gestures on, Stop/Resume, Gestures help, Start with Windows, Re-learn my hand size,
Close. In the tray icon an orange badge means gestures are off (camera on), and a red badge means stopped
(camera off).

## Architecture (one frame)

**Physical-hand L keys (approved 2026-11-06):** `is_l_pose` needs straight index, folded middle/ring/little,
thumb extended sideways and separated from index. `LKeyPose` waits `L_POSE_HOLD` 0.35 s for its first key.
LEFT Backspace then waits `BACKSPACE_REPEAT_DELAY` 0.5 s and repeats at `BACKSPACE_REPEAT_INTERVAL` 0.08 s;
RIGHT Enter fires once, requiring `L_POSE_RELEASE` 0.18 s release to rearm. Mapping is physical even when main_side is
left. Engine gives it priority over clicks, side buttons, scrolling, volume and second-hand shortcuts,
freezes the main cursor/box, and releases held Alt BEFORE the new key. Unreadable frames never produce
key presses. Repeats require a currently clear left L-pose and matching side;
they stop on release even during release debounce, hand loss, pause or gestures-off. Keys are complete
press/release pulses, not a held OS key; delayed frames never replay a backlog. `tests/test_backspace_repeat.py`
covers initial delay, cadence, no catchup burst, Enter once and deletion stopping.
`tests/test_l_pose_settings.py` covers mapping, no conflicts, short/long/repeated poses,
startup off/two-fist wake, sensitivity gain and persisted/concurrent settings. The loop-window-drag test
checks real run() starts with camera on and gestures off. Normal Stop/Resume still resumes gestures.

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
- **Second-hand recognition fixes (2026-11-06, phone reports).** Tests replay November 5 screenshot distances
  (middle/ring .14/.23, .08/.14, .11/.18) and keyboard-pair distances (.15/.19 in the picture). Both tips below
  0.25 can be a pair even when the old ratio 1.4 fails (up to 2.5). `second_distances` uses picture distances
  consistently, retaining the per-tip 3D guard (< 0.60). A pinch must start with picture distance < 0.30;
  there is no 3D-only start fallback. Starting and deciding a pinch use the same distances, rather than per-tip minima that
  let a falsely close index in depth steal copy/paste or screenshot. A clear index contact with a protruding
  thumb is allowed even when all four fingers read folded. Pinches and fingertip contacts block media gestures;
  opening the hand or leaving the picture ends a media session immediately. A tuck at thumb_out 0.18-0.30 now
  ends the thumbs-up and can trigger play/pause (the old keep threshold hid it). OSK closes only when visible;
  a hidden OSK window is reopened. Failed shortcut output is displayed as failed. Synthetic regressions live
  in `tests/test_phone_reports.py`. First live trial failed: repeated Alt+Tab while open (3D index .37-.42,
  picture .41-.54). The October 3D-only easier-index start was the cause; it is removed, including the
  corresponding historical test expectation. Labelled live copy succeeded three times at 14:43:50-56;
  screenshot succeeded once at 14:44:47 (.15/.24 picture) but the following open-hand phases triggered
  Alt+Tab at 14:44:53-58. Those exact false readings are now regressions. Repeat live verification after deploy.
  Keyboard opened at 14:47:36 (confirmed by the user), but other double pinches split into Win+H and Alt+Tab.
  Keyboard double-tap now waits 0.75 s. Further live keyboard taps at 14:55:33-51 measured index .19/.06/.12
  and middle .29/.32/.31; those still became Alt+Tab. For an index-closest pair with index < 0.30,
  middle < `VOICE_MIDDLE_ON` 0.34 now counts as the pair, even if the first tap is uneven. A clear
  middle-closest copy remains separate. Both first and second taps use the same classifier.
  Second live trial: no Alt+Tab/track outputs after restart through 14:53:05, but some screenshots became
  copy: picture middle/ring .14/.33, .17/.36, .17/.28 and .04/.14. Debug strips show both fingers folded
  onto the thumb. Screenshot now accepts both below 0.25 without a ratio test, or middle < 0.25 with
  ring < `SCREENSHOT_RING_ON` 0.40 and ratio < 2.5, only when middle is closer and index >= 0.30. This asymmetric extension
  preserves ring-only paste (e.g. middle .26, ring .16) and labelled copy (ring .65+).
- **Music gesture clarified by the user (2026-11-06).** The photo shows four fingers folded and thumb out;
  holding briefly then OPENING should play/pause; moving sideways should skip tracks. The previous tuck
  implementation did not match this. `SECOND_KEYS` now names the action `thumbs-up, hand open`; opening
  needs 3 straight fingers, permits a short unfolding transition, and never plays after a track skip.
  Tucking cancels. Pinches latch `media_blocked` until an open hand with fingertips apart is held for
  `KEY_RELEASE_DELAY`: a lost pinch during movement cannot re-arm as a media pose. Resetting on hand loss
  still releases held Alt; physical-hand identity changes remain a possible limitation. Tests cover an
  index pinch misread as a moving thumb-out fist, then a clear release and a successful music gesture.
  Live run after the 15:08 restart logged repeated `thumbs-up, hand open -> Play/Pause` on the user's
  opening hand (15:09:23 onward). Held Alt+Tab versus tracks still awaits the user's confirmation.
  Screenshot reliability was inconsistent in earlier live trials (reported 0/3, 3/3, 1/3); the final
  pair calibration covers those recorded distances, but do not claim all live issues are resolved.
  User then confirmed play/pause works and requested faster response: split `PLAYPAUSE_HOLD` 0.12 s from
  track arming (`KEY_THUMB_MIN` 0.30 s). Peak/repeat guards remain. Held Alt+Tab is still reported unreliable;
  switcher navigation now uses native Tab/Shift+Tab with Alt held instead of app-visible arrow keys,
  reasserting Alt if GetAsyncKeyState's high bit is clear. Direction and end limits are unchanged.
  INDEX_HOLD_2D is 0.44 (start still 0.30) for moderate movement/depth drift; each emitted switcher step
  now logs its direction and selected window index, making the next live trial diagnosable.
  Latest user confirmation: play/pause and Alt+Tab work well, track switching works, and left-hand gestures
  no longer conflict. User requested one song per swipe, return near the start to rearm either direction.
  Implemented `thumb_ready`, fixed `thumb_x` and frozen `thumb_step` for the pose: long/held excursions
  skip once; return within 40% of the trigger distance rearms without itself skipping. The old advancing
  anchor and one-direction lock are removed. `tests/test_track_recenter.py` covers long swipes both ways,
  approximate return, partial return, repeat/reverse after return, and changing scale readings.
  Follow-up: passing through the start rearmed too soon and skipped backwards. User requested a 0.5 s
  wait near the start. `thumb_return_since` now requires continuous readable residence in the zone, with
  both raw and smoothed positions inside; leaving or an uncertain frame resets the full wait. Regression
  tests cover passing through, short waits, interrupted waits, and valid half-second-or-longer returns.
- **Left copy / paste read as Win+H / Print Screen (2026-10-16).** Debug picture: thumb on the middle tip, 3D
  index 0.35 < middle 0.40 (so "index+middle"), picture middle 0.14 / index 0.45. Initially fixed with per-frame
  min(3D, picture); superseded by `second_distances` on 2026-11-06 (see above). The touch
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
  the picture) before loosening `CLICK_2D`. 2026-10-17: the depth guess read 0.60-1.09 with the thumb on the middle tip
  (screenshot: t-mid 0.76, 2d 0.16), so a picture distance < `CLICK_2D_FAR` 0.18 now counts whatever 3D says,
  but only with the palm facing the camera (`facing >= SIDE_FACING`): turned sideways, a thumb behind the
  finger looks like touching. The log's 2D-near / 3D-far MAIN samples were all real clicks or fists.
- **Dim-light blur.** Possibly try a shorter camera exposure (`CAP_PROP_EXPOSURE`). At open, MSMF reports
  auto exposure 0.0, exposure -5. This was never tested, so verify on the laptop and revert if the picture gets
  too dark.
- **Second-hand keys tested live (2026-11-06).** User confirms no left-hand gesture conflicts after the fixes.
  Preserve that separation; watch for Esc from a resting fist, role flips and Alt+Tab step size (`ALT_TAB_STEP`).
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

Saved profiles, first stage (1.1.0): gesture_profiles.py owns validated, atomic JSON persistence,
Basic protection, ProfileMouse output routing/reference counts, and apply_profile_to_engine.
gesture_profiles_ui.py is a real Tk editor on its own lazy thread, with owning-thread GC like the
sensitivity UI. Deploy both helper files before replacing hand_mouse.py. Include them in downloads.
The local gesture_profiles.json/recovery files are gitignored. Existing recognition/timing remains;
main-hand button gestures, SECOND_KEYS and physical L-pose outputs can be rebound. Key shortcuts,
media keys, mouse buttons, OSK toggle, open file/application and Disabled are supported. Holding is
available for main-hand key/mouse pinches; optional repeat for left-L key/mouse actions. Custom open
or keyboard-toggle actions do not repeat on left L by default. Basic retains Backspace repeat and
native Alt+Tab hold/navigation. Read-only Basic defaults apply wherever no override exists.
UI Save binding edits a draft; Save & apply persists and queues a snapshot to the gesture thread.
Application discards old pending taps, releases old outputs, replaces bindings, and turns gestures
off. Active-profile deletion falls back to Basic. Pause/reactivation/hand swapping remain reserved;
scroll/volume/cursor movement keep existing behavior. No recording of novel poses or arbitrary new
sequences in this first stage; that remains the next stage of the previously discussed design.
Tests cover default compatibility, file failure/recovery, validation, input release, queued apply,
and real Tk edit/apply/duplicate/rename/delete workflow. UI tests must use plain patched dialog
functions: MagicMock call history retains parent Tk objects and can destroy them on the wrong thread.
