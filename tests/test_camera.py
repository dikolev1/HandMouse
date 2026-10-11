import os as _os, sys as _sys, tempfile as _tempfile
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import sys, time, os, types, logging, numpy as np
pass
logging.basicConfig(level=logging.INFO, format="   log: %(message)s")
import hand_mouse as hm
hm.STATE_PATH = _os.path.join(_tempfile.gettempdir(), "hm_test_state_cam.json")
if os.path.exists(hm.STATE_PATH): os.remove(hm.STATE_PATH)
def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name, info); assert cond
# a webcam like the user's: 1280x720 only at 10 fps; 960x540 at 15 fps with dshow, 25 with msmf; 640 at 30
SPEED = {("dshow", 1280): 10, ("msmf", 1280): 10, ("dshow", 960): 15, ("msmf", 960): 25, ("dshow", 640): 30, ("msmf", 640): 30}
opened = []
class FakeCap:
    def __init__(self, idx, backend):
        self.b = {700: "dshow", 1400: "msmf"}[backend]; self.w, self.h = 640, 480; self.last = time.monotonic()
        opened.append(self.b)
    def isOpened(self): return True
    def set(self, prop, v):
        if prop == 3: self.w = int(v)
        if prop == 4: self.h = int(v)
    def read(self):
        fps = SPEED[(self.b, self.w)]
        nxt = self.last + 1 / fps; time.sleep(max(0, nxt - time.monotonic())); self.last = nxt
        return True, np.zeros((self.h, self.w, 3), np.uint8)
    def release(self): pass
cv2 = types.SimpleNamespace(VideoCapture=FakeCap, CAP_DSHOW=700, CAP_MSMF=1400, CAP_PROP_FOURCC=6,
                            CAP_PROP_FRAME_WIDTH=3, CAP_PROP_FRAME_HEIGHT=4, CAP_PROP_FPS=5, CAP_PROP_BUFFERSIZE=38,
                            VideoWriter_fourcc=lambda *a: 0)
t0 = time.time(); cam = hm.open_camera(cv2, hm.load_state(), lambda m: print("   notify:", m))
check("first start: picks the sharpest mode that is fast enough", cam.name == "msmf 960x540", (cam.name, f"{time.time()-t0:.1f}s"))
# the reader keeps up and returns only new frames
n = 0; t1 = time.monotonic()
while time.monotonic() - t1 < 1.0:
    ok, f = cam.read(); n += ok
check("threaded reader delivers the camera's full rate", 21 <= n <= 27, n)
cam.release()
t0 = time.time(); opened.clear(); cam = hm.open_camera(cv2, hm.load_state(), lambda m: print("   notify:", m))
check("next start: uses the remembered mode straight away", cam.name == "msmf 960x540" and opened == ["msmf"], (cam.name, opened, f"{time.time()-t0:.1f}s"))
# processing slower than the camera: always the newest frame, no backlog
time.sleep(0.5); ok, f = cam.read(); a = cam.seq; time.sleep(0.3); ok, f = cam.read()
check("after slow processing it jumps to the newest frame", cam.last_read == cam.seq and cam.seq - a >= 6, cam.seq - a)
cam.release()
# camera unplugged -> read reports failure quickly
class DeadCap(FakeCap):
    def read(self): return False, None
cam2 = hm.Camera(DeadCap(0, 700), "dead"); ok, f = cam2.read(timeout=1.0)
check("a camera that stops is reported (so the app reopens it)", not ok)
cam2.release()
print("ALL CAMERA OK")
