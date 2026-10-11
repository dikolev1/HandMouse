import os as _os, sys as _sys, tempfile as _tempfile
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import sys, io, contextlib, math, random
pass
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
hm, N, check = V.hm, V.N, V.check
FPS = 20
class Sim:
    def __init__(s, **kw):
        s.m = V.FakeMouse(); s.e = hm.Engine(s.m, 0, 0, 1920, 1080, ref_palm=None, **kw); s.t = 0.0; s.track = []
    def go(s, poses):
        for px, py in poses:
            s.e.update([V.make(px=px + 0.1152, py=py + 0.3771)], s.t); s.t += 1 / FPS
            s.track.append(s.m.pos)
        return s
def still(px, py, sec): return [(px, py)] * int(sec * FPS)
def path(a, b, sec): n = int(sec * FPS); return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(1, n + 1)]
def maxjump(track): return max((math.dist(a, b) for a, b in zip(track, track[1:]) if a and b), default=0)

s = Sim().go(still(0.5, 0.4, 1.0))
b0 = s.e.box()
s.go(still(0.5, 0.4, 3.0))
check("finger still inside the box: box doesn't move", s.e.box() == b0, (b0, s.e.box()))
# quick push out to the right and back (0.3 s)
s.go(path((0.5, 0.4), (0.85, 0.4), 0.3) + still(0.85, 0.4, 0.15) + path((0.85, 0.4), (0.5, 0.4), 0.3))
check("quick push past the edge (0.3 s): box stays", abs(s.e.box()[0] - b0[0]) < 1e-9, (b0, s.e.box()))
# hold it out to the right
s.go(path((0.5, 0.4), (0.9, 0.4), 0.4)); n0 = len(s.track)
s.go(still(0.9, 0.4, 4.0))
seg = s.track[n0:]
check("held outside 4 s: box glides after the finger", s.e.box()[0] > b0[0] + 0.1, (b0, s.e.box()))
check("...finger ends up inside the box", s.e.box()[0] < 0.9 < s.e.box()[2], s.e.box())
check("...while the cursor stays still at the screen edge", min(p[0] for p in seg) >= seg[0][0] - 1 and seg[-1][0] >= 1915 and max(abs(p[1] - seg[0][1]) for p in seg) < 1, (seg[0], seg[-1]))
check("...and box follow is over", not s.e.boxcam.following)
# moving left again moves the cursor left normally
s.go(path((0.9, 0.4), (0.75, 0.4), 0.6))
check("moving the finger left moves the cursor left", s.m.pos[0] < 1700, s.m.pos)
# size fit: move around in a small area for a long time -> box shrinks, cursor still when finger still
s = Sim()
rnd = random.Random(1)
pts = [(0.5, 0.4)]
for i in range(400):
    pts.append((0.5 + rnd.uniform(-0.07, 0.07), 0.4 + rnd.uniform(-0.05, 0.05)))
poses = []
for a, b in zip(pts, pts[1:]): poses += path(a, b, 0.25)
s.go(poses)
sx1 = s.e.boxcam.sx
n0 = len(s.track); s.go(still(*poses[-1], 40.0))
check("small movements for 100 s -> box shrinks", s.e.boxcam.sx < 0.9 and s.e.boxcam.sy < 0.95, (round(s.e.boxcam.sx, 2), round(s.e.boxcam.sy, 2)))
check("...stays within limits", s.e.boxcam.sx >= hm.BOX_SIZE_LIMITS[0] - 1e-6)
check("...and the cursor doesn't move while the box resizes under a still finger", maxjump(s.track[n0 + FPS:]) < 1.0, maxjump(s.track[n0 + FPS:]))   # after the movement settles
# big movements -> expands (but not over the limit)
s = Sim()
pts = [(0.5, 0.4)] + [(0.5 + rnd.uniform(-0.3, 0.3), 0.4 + rnd.uniform(-0.25, 0.25)) for i in range(300)]
poses = []
for a, b in zip(pts, pts[1:]): poses += path(a, b, 0.25)
s.go(poses + still(*poses[-1], 30))
check("big movements -> box grows (max limit)", 1.05 < s.e.boxcam.sx <= hm.BOX_SIZE_LIMITS[1] + 1e-6, round(s.e.boxcam.sx, 2))
# saving / loading
st = s.e.boxcam.state(); e2 = hm.Engine(V.FakeMouse(), 0, 0, 1920, 1080, box_state=st)
check("box state is remembered", e2.boxcam.state() == st, st)
check("bad saved state is ignored", hm.Engine(V.FakeMouse(), 0, 0, 1920, 1080, box_state={"cx": "x"}).boxcam.sx == 1.0)
# fist (scrolling) and clicks don't drag the box
s = Sim().go(still(0.5, 0.4, 1.0)); b0 = s.e.box()
for i in range(60): s.e.update([V.make(px=0.95, py=0.8, fist=True)], s.t); s.t += 1 / FPS
check("fist held far right for 3 s: box doesn't follow", s.e.box() == b0, (b0, s.e.box()))
s.e.recalibrate()
check("re-learn resets the box", s.e.boxcam.state() == hm.CursorBox().state())
print("ALL BOX OK")
