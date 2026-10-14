import os as _os, sys as _sys, tempfile as _tempfile
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import io, contextlib, os, shutil
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
    import test_second_keys as T
hm, N, check = V.hm, V.N, V.check
import cv2
import numpy as np


def run(frames, on=True, fps=16):
    """Engine + debug recorder with fake camera frames (a grey picture with a moving bar)."""
    folder = _tempfile.mkdtemp(prefix="hm_debug_")
    rec = hm.GestureRecorder(folder, on)
    hm.log.addHandler(rec); hm.log.setLevel(hm.logging.INFO)
    m = V.FakeMouse(); e = hm.Engine(m, 0, 0, 1920, 1080); t = 0.0
    try:
        for k, f in enumerate(frames):
            hs = f(t); hs = hs if isinstance(hs, list) else [hs]
            img = np.full((720, 1280, 3), 90, np.uint8); img[:, (k * 20) % 1280:(k * 20) % 1280 + 10] = 200
            e.update(hs, t)
            rec.add(cv2, img, hs, e.status, t)
            rec.save_pending(cv2, np, t)
            t += 1 / fps
        rec.wait()
    finally:
        hm.log.removeHandler(rec)
    files = sorted(f for f in os.listdir(folder) if f.endswith(".jpg"))
    return folder, files, rec


open_ = lambda t: V.make(px=0.7)
click = N(10, open_) + N(6, lambda t: V.make(px=0.7, pinch="m")) + N(10, open_)

folder, files, rec = run(click, on=False)
check("debug off -> no pictures", files == [], files)
shutil.rmtree(folder)

folder, files, rec = run(click)
check("debug on, one left click -> one picture", len(files) == 1 and files[0].endswith(" left click.jpg"), files)
img = cv2.imread(os.path.join(folder, files[0]))
check("...a strip of 8 frames (2 rows of 4) under a title", img is not None and img.shape[1] == 4 * hm.DEBUG_TILE_W
      and img.shape[0] > 2 * 270, None if img is None else img.shape)
check("...file name starts with date and time like the log", files[0][:8].isdigit() and files[0][8] == "_", files[0])
shutil.rmtree(folder)

folder, files, rec = run([lambda t: V.make(px=0.7, jitter=0.002)] * 80)
check("relaxed hand for 5 s -> no pictures (no gestures)", files == [], files)
shutil.rmtree(folder)

pinch = T.START + N(5, T.both("middle")) + T.REST
folder, files, rec = run(pinch)
check("left-hand Ctrl+C -> one picture (touch line and action line together)",
      len(files) == 1 and "Ctrl+C" in files[0], files)
shutil.rmtree(folder)

brush = T.START + N(2, T.both("index")) + N(8, T.both("fist")) + T.REST
folder, files, rec = run(brush)
check("cancelled touch and Esc are both caught", any("cancelled" in f for f in files) and any("Esc" in f for f in files),
      files)
shutil.rmtree(folder)

# keep the folder small: oldest pictures go first
keep = hm.DEBUG_KEEP
folder = _tempfile.mkdtemp(prefix="hm_debug_")
for i in range(6):
    with open(os.path.join(folder, f"2026010{i}_000000_000 old.jpg"), "wb") as f:
        f.write(b"x")
open(os.path.join(folder, "notes.txt"), "w").close()
hm.DEBUG_KEEP = 3
hm.GestureRecorder(folder, True).prune()
left = sorted(os.listdir(folder))
check("more than DEBUG_KEEP pictures -> the oldest deleted, the newest 3 kept (other files untouched)",
      left == ["20260103_000000_000 old.jpg", "20260104_000000_000 old.jpg", "20260105_000000_000 old.jpg", "notes.txt"],
      left)
folder2, files, rec = run(click)          # a new picture with the limit reached -> one old one goes
for f in files:
    shutil.copy(os.path.join(folder2, f), folder)
rec.folder = folder
rec.prune()
left = sorted(f for f in os.listdir(folder) if f.endswith(".jpg"))
check("...a new picture on a full folder deletes the oldest one", len(left) == 3 and left[-1] == files[-1]
      and "20260103_000000_000 old.jpg" not in left, left)
hm.DEBUG_KEEP = keep
shutil.rmtree(folder); shutil.rmtree(folder2)

check("file name from a second-hand touch line",
      hm.GestureRecorder.short(["second hand touch 0.05 s, 2 frames: thumb to index 0.45 -> index (cancelled: x)"])
      == "second hand touch - index (cancelled x)", hm.GestureRecorder.short(["second hand touch 0.05 s -> index (cancelled: x)"]))
folder = _tempfile.mkdtemp(prefix="hm_debug_")
rec = hm.GestureRecorder(folder, True); hm.log.addHandler(rec); hm.log.setLevel(hm.logging.INFO)
hm.log.info("diag fps 28 hands 1 | pressed - | MAIN ... button: -   cursor moving")
hm.log.removeHandler(rec)
check("the once-a-second diag line is not a gesture (it says 'button')", len(rec.events) == 0, list(rec.events))
shutil.rmtree(folder)
print("ALL DEBUG PICTURES OK")
