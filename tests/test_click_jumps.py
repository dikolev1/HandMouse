import os as _os, sys as _sys, tempfile as _tempfile
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import sys, io, contextlib, random, math
pass
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
hm = V.hm
FPS = 16
def hand(ix, iy, pinch=None, label="Right", jit=0.0, rnd=random):
    h = V.make(px=ix, py=iy + 0.25, pinch=pinch, label=label)
    h.img = list(h.img); h.img[8] = (ix + rnd.gauss(0, jit), iy + rnd.gauss(0, jit))
    return h
def scenario(name, frames):
    m = V.FakeMouse(); e = hm.Engine(m, 0, 0, 3840, 1080); t = 0.0; path = []; clicks = []
    for f in frames:
        hs = f(t); hs = hs if isinstance(hs, list) else [hs]
        e.update(hs, t); t += 1 / FPS
        path.append(m.pos); clicks.append(e.clicks.pressed)
    # position when the button went down vs max distance from it afterwards (until 1 s after release)
    down = next(i for i, c in enumerate(clicks) if c)
    p0 = path[down]
    after = [p for p in path[down:down + int(2.0 * FPS)] if p]
    far = max(math.dist(p, p0) for p in after)
    print(("PASS " if far < 30 else "FAIL ") + f"{name:55s} cursor moved up to {far:5.0f} px away from where it clicked")
    assert far < 30
rnd = random.Random(3)
# build a precision offset: slow drift right for 3 s, then click
drift = [lambda t, k=k: hand(0.40 + 0.0015 * k, 0.40) for k in range(48)]
still = lambda n, x=0.472: [lambda t: hand(x, 0.40)] * n
pinch = lambda n, x=0.472, jit=0.0: [lambda t: hand(x, 0.40, 'm', jit=jit, rnd=rnd)] * n
glitch = lambda x=0.472: [lambda t: hand(x + 0.12, 0.33, 'm')]      # one bad frame: index tip misread during the pinch
scenario("clean click", still(20) + drift + still(8) + pinch(5) + still(24))
scenario("click held a bit longer (0.5 s)", still(20) + drift + still(8) + pinch(8) + still(24))
scenario("click with a 1-frame index-tip glitch", still(20) + drift + still(8) + pinch(2) + glitch() + pinch(5) + still(24))
scenario("click with a glitch right after release", still(20) + drift + still(8) + pinch(5) + [lambda t: hand(0.59, 0.33)] + still(24))
scenario("click, hand lost 0.5 s, back", still(20) + drift + still(8) + pinch(3) + [lambda t: []] * 8 + pinch(2) + still(24))
ghost = lambda t: [hand(0.472, 0.40, 'm'), hand(0.80, 0.30, label="Left")]
scenario("click while a false 2nd hand appears on the right", still(20) + drift + still(8) + pinch(3) + [ghost] * 3 + pinch(2) + still(24))
