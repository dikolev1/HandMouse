import os as _os, sys as _sys, tempfile as _tempfile
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import sys, io, contextlib, random
pass
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
    import test_fist_closing as B
hm = V.hm; check = V.check
def with_thumb(h, pos):
    w = list(h.world); w[4] = pos; w[3] = (pos[0] - 0.012, pos[1] + 0.018, pos[2] + 0.004)
    img = list(h.img)
    for i in (3, 4):   # same projection as test_v7.make
        img[i] = (img[0][0] + (w[i][0] - w[0][0]) * 3.2, img[0][1] + (w[i][1] - w[0][1]) * 3.2 * 1.33)
    return hm.Hand(h.label, img, w)
def thumb_on(finger, px=0.7, label="Right", jit=0.0, rnd=random):
    h = V.make(px=px, label=label)
    w = h.world
    if finger == "index":            # button 4 now: thumb tip on the index fingertip ("OK" sign)
        t = w[8]
        pos = (t[0] - 0.01, t[1] + 0.006, t[2] - 0.01)
    elif finger == "indexmid":       # old button-4 spot: thumb tip pressed on the middle of the index finger
        a, b = w[5], w[6]
        mid = [a[i] + (b[i] - a[i]) * 0.7 for i in range(3)]
        pos = (mid[0] - 0.003, mid[1], mid[2] - 0.012)
    elif finger == "pinky":          # thumb across the palm onto the base of the little finger
        k = w[17]
        pos = (k[0] - 0.008, k[1] - 0.004, k[2] - 0.012)
    else:                            # middle of the middle finger (the old button-5 spot)
        a, b = w[10], w[11]
        mid = [(a[i] + b[i]) / 2 for i in range(3)]
        pos = (mid[0] - 0.011, mid[1], mid[2] - 0.008)
    pos = (pos[0] + rnd.gauss(0, jit), pos[1] + rnd.gauss(0, jit), pos[2] + rnd.gauss(0, jit))
    return with_thumb(h, pos)
def index_tip_pinch(px=0.7):
    h = V.make(px=px); w = h.world; t = w[8]
    return with_thumb(h, (t[0] - 0.01, t[1] + 0.006, t[2] - 0.01))
def run(frames, fps=16):
    m = V.FakeMouse(); e = hm.Engine(m, 0, 0, 1920, 1080); t = 0.0
    for f in frames:
        hs = f(t); hs = hs if isinstance(hs, list) else [hs]
        e.update(hs, t); t += 1 / fps
    return m, e
N = V.N
def ev(m, names=("x1", "x2")): return [x for x in m.events if x[0] in names]
def clicks(m): return [x for x in m.events if x[0] in ("left", "right", "middle")]
print("distances  thumb on index middle:", {k: round(v, 2) for k, v in thumb_on("index").side.items()}, "tips", round(thumb_on("index").tip_min, 2))
print("           thumb on middle middle:", {k: round(v, 2) for k, v in thumb_on("pinky").side.items()}, "tips", round(thumb_on("pinky").tip_min, 2))
print("           thumb on middle-finger middle:", {k: round(v, 2) for k, v in thumb_on("middlemid").side.items()})
print("           left-click pose:", {k: round(v, 2) for k, v in V.make(pinch='m').side.items()}, "tips", round(V.make(pinch='m').tip_min, 2))
open_ = lambda t: V.make(px=0.7)
m, e = run(N(10, open_) + N(8, lambda t: thumb_on("index")) + N(8, open_))
check("thumb on the middle of the index finger -> button 4 down and up", ev(m) == [('x1', 'down'), ('x1', 'up')] and clicks(m) == [], m.events)
m, e = run(N(10, open_) + N(8, lambda t: thumb_on("pinky")) + N(8, open_))
check("thumb on the base of the little finger -> button 5", ev(m) == [('x2', 'down'), ('x2', 'up')] and clicks(m) == [], m.events)
m, e = run(N(10, open_) + N(24, lambda t: thumb_on("index")) + N(8, open_))
check("held 1.5 s -> button 4 held, released once", ev(m) == [('x1', 'down'), ('x1', 'up')], m.events)
rnd = random.Random(3)
m, e = run(N(10, open_) + N(10, lambda t: thumb_on("pinky", jit=0.003, rnd=rnd)) + N(8, open_))
check("noisy tracking -> still one clean button 5", ev(m) == [('x2', 'down'), ('x2', 'up')], m.events)
m, e = run(N(10, open_) + N(1, lambda t: thumb_on("index")) + N(8, open_))
check("thumb brushes past for one frame -> nothing", ev(m) == [], m.events)
# second hand (left) does it while the right hand points
two = lambda h_left: [h_left, V.make(px=0.75, label="Right")]
m, e = run(N(12, lambda t: two(V.make(px=0.3, label="Left"))) + N(8, lambda t: two(thumb_on("index", px=0.3, label="Left"))) + N(8, lambda t: two(V.make(px=0.3, label="Left"))))
check("second (left) hand -> no button 4 (main hand only)", ev(m) == [] and clicks(m) == [], m.events)
m, e = run(N(12, lambda t: two(V.make(px=0.3, label="Left"))) + N(8, lambda t: two(thumb_on("pinky", px=0.3, label="Left"))) + N(8, lambda t: two(V.make(px=0.3, label="Left"))))
check("second hand -> no button 5", ev(m) == [], m.events)
# both hands at once
m, e = run(N(12, lambda t: two(V.make(px=0.3, label="Left"))) + N(8, lambda t: [thumb_on("index", px=0.3, label="Left"), thumb_on("pinky", px=0.75)]) + N(8, lambda t: two(V.make(px=0.3, label="Left"))))
check("both hands at once -> only the main hand's button 5", ev(m) == [('x2', 'down'), ('x2', 'up')], m.events)
# hand leaves while holding -> button released
m, e = run(N(10, open_) + N(8, lambda t: thumb_on("index")) + N(12, lambda t: []))
check("hand leaves while holding -> button let go", ev(m) == [('x1', 'down'), ('x1', 'up')], m.events)
# --- no false triggers
for name, pose, expect in (("left click (thumb on middle fingertip)", lambda t: V.make(px=0.7, pinch='m'), [('left', 'down'), ('left', 'up')]),
                           ("right click (thumb on ring fingertip)", lambda t: V.make(px=0.7, pinch='r'), [('right', 'down'), ('right', 'up')]),
                           ("middle click", lambda t: V.make(px=0.7, pinch='mr'), [('middle', 'down'), ('middle', 'up')]),
                           ("thumb on the middle of the index finger (old button-4 spot)", lambda t: thumb_on("indexmid"), []),
                           ("fist", lambda t: V.make(px=0.7, fist=True), [])):
    m, e = run(N(10, open_) + N(10, pose) + N(8, open_))
    check(f"{name}: no button 4/5", ev(m) == [] and clicks(m) == expect, m.events)
o, f = B.o, B.f
for frames in (3, 6, 10):
    seq = N(10, V.open_) + [lambda t, k=k: B.blend(o, f, k / frames) for k in range(1, frames + 1)] + N(10, lambda t: f) \
        + [lambda t, k=k: B.blend(f, o, k / frames) for k in range(1, frames + 1)] + N(10, V.open_)
    m, e = run(seq)
    check(f"closing/opening a fist over {frames} frames: no button 4/5", ev(m) == [], m.events)
rnd = random.Random(9)
m, e = run([lambda t: V.make(px=0.7, jitter=0.004, rnd=rnd)] * 200)
check("relaxed noisy hand for 12 s: nothing", m.events == [], m.events[:3])
# side button then a left click right after: both work
m, e = run(N(10, open_) + N(8, lambda t: thumb_on("index")) + N(8, open_) + N(6, lambda t: V.make(px=0.7, pinch='m')) + N(8, open_))
check("button 4 then a left click", [x[:2] for x in m.events if x[0] != 'wheel'] == [('x1', 'down'), ('x1', 'up'), ('left', 'down'), ('left', 'up')], m.events)
m, e = run(N(10, open_) + N(10, lambda t: thumb_on("middlemid")) + N(8, open_))
check("old spot (middle of the middle finger): no button 5 and no left click", ev(m, ("x2",)) == [] and clicks(m) == [], m.events)
# thumb travelling to the middle / ring fingertips for a click, passing over the index finger on the way
def travel(target, k):
    h = V.make(px=0.7); w = h.world
    start = w[4]; mid = [w[5][i] + (w[6][i] - w[5][i]) * 0.7 for i in range(3)]; mid[2] -= 0.012
    end = V.make(pinch=target).world[4]
    a, b, u = (start, mid, k / 0.5) if k < 0.5 else (mid, end, (k - 0.5) / 0.5)
    return with_thumb(h, tuple(a[i] + (b[i] - a[i]) * u for i in range(3)))
for target, btn in (("m", "left"), ("r", "right"), ("mr", "middle")):
    for frames in (3, 6, 12):
        seq = N(10, open_) + [lambda t, k=k: travel(target, k / frames) for k in range(frames + 1)] + N(8, lambda t: V.make(px=0.7, pinch=target)) + N(8, open_)
        m, e = run(seq)
        check(f"{btn} click with the thumb sliding over the index finger ({frames} frames): no button 4", ev(m) == [] and len(clicks(m)) == 2, m.events)   # (a straight-line path may brush the middle tip: any one click is fine)
# cursor stays put while the "OK" pinch is held
m, e = run(N(10, open_) + N(3, lambda t: thumb_on("index")) + N(10, lambda t: thumb_on("index")))
print("ALL SIDE OK")
