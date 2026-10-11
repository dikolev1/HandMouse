import os as _os, sys as _sys, tempfile as _tempfile
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import sys, types, logging, time as _t, io, contextlib, os, numpy as np, threading
pass
logging.basicConfig(level=logging.INFO, format="%(message)s")
import hand_mouse as hm
hm.SOUNDS = False
hm.open_help = lambda: None
with contextlib.redirect_stdout(io.StringIO()):
    from test_core import make, FakeMouse
P = types.SimpleNamespace
calls = {"imshow": 0, "destroy": 0, "bounds": 0}
class M(FakeMouse):
    left, top, width, height = 0, 0, 1920, 1080
    def bounds(self):
        calls["bounds"] += 1
        return (0, 0, 3840, 1080) if calls["bounds"] > 1 else (0, 0, 1920, 1080)
hm.WinMouse = M
hm.ensure_model = lambda: None
hm.STATE_PATH = _os.path.join(_tempfile.gettempdir(), "hm_test_state.json")
if os.path.exists(hm.STATE_PATH): os.remove(hm.STATE_PATH)
def to_res(hs):
    return P(hand_landmarks=[[P(x=x, y=y, z=0) for x, y in h.img] for h in hs],
             hand_world_landmarks=[[P(x=x, y=y, z=z) for x, y, z in h.world] for h in hs],
             handedness=[[P(category_name=h.label)] for h in hs])
class FakeLm:
    n = 0
    def __init__(self, video): self.video = video
    def detect_for_video(self, img, ts):
        FakeLm.n += 1
        return to_res([make(px=0.5)])
    def detect(self, img): return to_res([])
    def close(self): pass
hm.create_landmarker = lambda video=True, num_hands=2, detection=None: FakeLm(video)
class Cap:
    k = 0
    def read(self):
        Cap.k += 1; _t.sleep(0.03)
        return True, np.zeros((720, 1280, 3), np.uint8)
    def release(self): print("camera released")
    def get(self, p): return 0
hm.open_camera = lambda cv2, *a, **k: Cap()
import cv2
cv2.namedWindow = lambda *a, **k: None
cv2.imshow = lambda *a, **k: calls.__setitem__("imshow", calls["imshow"] + 1)
block = {"on": False}
def fake_wait(*a):
    if block["on"]:
        block["on"] = False; _t.sleep(2.0)     # Windows' title-bar drag loop holds the window thread
    _t.sleep(0.015); return 255
cv2.waitKey = fake_wait
cv2.resizeWindow = lambda *a: None
cv2.moveWindow = lambda *a: calls.__setitem__("moved", a)
cv2.getWindowImageRect = lambda *a: (100, 130, 1430, 540)
cv2.getWindowProperty = lambda *a: 1
cv2.destroyWindow = lambda *a: calls.__setitem__("destroy", calls["destroy"] + 1)
# drive the app from "outside" like the tray would: toggle the view, pause/resume, then quit
orig_tray = hm.TrayIcon
holder = {}
class SpyTray(orig_tray):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); holder["t"] = self
hm.TrayIcon = SpyTray
res = {}
def script():
    _t.sleep(4.0); holder["t"].on_view(); _t.sleep(0.5)
    n0 = FakeLm.n; block["on"] = True; _t.sleep(1.8); res["during"] = FakeLm.n - n0
    _t.sleep(1.0); holder["t"].on_close()
threading.Thread(target=script, daemon=True).start()
r = hm.run(preview=False)
print("run returned restart =", r)
print("frames processed", FakeLm.n, "| window frames shown", calls["imshow"], "| window closed", calls["destroy"])
print("saved state:", open(hm.STATE_PATH).read().replace("\n", " ") if os.path.exists(hm.STATE_PATH) else None)
print("hand frames processed while the window was being dragged (1.8 s):", res.get("during"))
assert res.get("during", 0) > 20, "tracking stalled"
print("PASS tracking keeps running while the window is dragged")
