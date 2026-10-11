import os as _os, sys as _sys, tempfile as _tempfile
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import sys, io, contextlib
pass
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
hm, N, check = V.hm, V.N, V.check
F = lambda: [V.make(px=0.3, fist=True, label="Left"), V.make(px=0.7, fist=True)]
O = lambda: [V.make(px=0.3, label="Left"), V.make(px=0.7)]
class Sim:
    def __init__(s): s.m = V.FakeMouse(); s.e = hm.Engine(s.m, 0, 0, 1920, 1080); s.t = 0.0; s.changes = []
    def go(s, frames, fps=20):
        for f in frames:
            s.e.update(f(), s.t); s.t += 1 / fps
            if s.e.gestures_changed: s.changes.append(s.e.gestures_changed); s.e.gestures_changed = None
        return s
def flickery_fists(sec, fps=20):
    out = []
    for i in range(int(sec * fps)):
        if i % 14 == 7: out.append(lambda: [V.make(px=0.7, fist=True)])               # one hand lost for a frame
        elif i % 14 == 3: out.append(lambda: [V.make(px=0.3, label="Left"), V.make(px=0.7, fist=True)])  # one reads open a frame
        else: out.append(F)
    return out
s = Sim().go(N(10, O) + flickery_fists(8))
check("both fists held 8 s (with tracking flickers) -> switches once", s.changes == ["off"], s.changes)
s.go(N(4, O) + flickery_fists(3))
check("hands open only 0.2 s, fists again -> no switch", s.changes == ["off"], s.changes)
s.go(N(10, O) + flickery_fists(3))
check("hands open 0.5 s, fists again -> switches back once", s.changes == ["off", "on"], s.changes)
s.go(N(10, lambda: []) + flickery_fists(3))
check("hands out of view 0.5 s, fists again -> switches once more", s.changes == ["off", "on", "off"], s.changes)
s = Sim().go(N(10, O) + N(15, F) + N(1, O) + N(10, F))
check("one open frame during the countdown doesn't cancel it", s.changes == ["off"], s.changes)
print("ALL REARM OK")
