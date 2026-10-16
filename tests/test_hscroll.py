import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import io, contextlib, random
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
hm, N, check, run = V.hm, V.N, V.check, V.run
open_ = lambda t: V.make()
wheel = lambda m: [x[1] for x in m.events if x[0] == "wheel"]
hwheel = lambda m: [x[1] for x in m.events if x[0] == "hwheel"]
ASPECT = 0.5625


def fist_path(dx, dy, frames=40):
    """Fist closes at the middle, then moves dx (fraction of the picture width) and dy (of the height)."""
    return [lambda t, k=k: V.make(fist=True, px=0.5 + dx * min(k, 8) / 8, py=0.6 + dy * min(k, 8) / 8)
            for k in range(frames)]


START = N(10, open_) + N(4, lambda t: V.make(fist=True))
m, e = run(START + fist_path(0.12, 0.0))
check("fist moved right -> scrolls right", len(hwheel(m)) > 10 and all(v > 0 for v in hwheel(m)) and wheel(m) == [],
      (sum(hwheel(m)), wheel(m)[:3]))
m, e = run(START + fist_path(-0.12, 0.0))
check("fist moved left -> scrolls left", len(hwheel(m)) > 10 and all(v < 0 for v in hwheel(m)) and wheel(m) == [],
      sum(hwheel(m)))
m, e = run(START + fist_path(0.03, 0.2))
check("fist moved down with a little sideways drift -> only vertical", len(wheel(m)) > 10 and hwheel(m) == [],
      (sum(wheel(m)), hwheel(m)[:3]))
m, e = run(START + fist_path(0.15, 0.08))
check("fist moved mostly right (diagonal) -> only sideways", len(hwheel(m)) > 10 and wheel(m) == [],
      (sum(hwheel(m)), wheel(m)[:3]))
# the same real distance scrolls the same amount sideways as up / down (the picture is wider than tall)
dz = hm.HSCROLL_DEADZONE
hm.HSCROLL_DEADZONE = hm.SCROLL_DEADZONE        # (sideways has a slightly bigger dead zone on purpose)
mh, _ = run(START + fist_path(0.1 * ASPECT, 0.0))
mv, _ = run(START + fist_path(0.0, 0.1))
hm.HSCROLL_DEADZONE = dz
a, b = sum(hwheel(mh)), -sum(wheel(mv))
check("same real distance (and dead zone) -> the same speed sideways and down", b > 0 and abs(a - b) / b < 0.05, (a, b))
m, e = run(START + fist_path(0.12, 0.0) + N(16, open_))
n = len(hwheel(m))
m2, _ = run(START + fist_path(0.12, 0.0) + N(16, open_) + N(30, open_))
check("opening the hand stops sideways scrolling", len(hwheel(m2)) == n, (n, len(hwheel(m2))))
m, e = run(START + fist_path(0.02, 0.0))
check("tiny sideways movement (dead zone) -> nothing", hwheel(m) == [] and wheel(m) == [], (hwheel(m), wheel(m)))
# switching direction while scrolling: down first, then clearly sideways
path = fist_path(0.0, 0.1, 20) + [lambda t, k=k: V.make(fist=True, px=0.5 + 0.03 * min(k, 8), py=0.7) for k in range(30)]
m, e = run(START + path)
check("down, then clearly sideways in the same fist -> vertical first, then sideways",
      len(wheel(m)) > 5 and len(hwheel(m)) > 5 and m.events.index(("wheel", wheel(m)[0])) < m.events.index(("hwheel", hwheel(m)[0])),
      (len(wheel(m)), len(hwheel(m))))
hm.HSCROLL_INVERT = True
m, e = run(START + fist_path(0.12, 0.0))
check("HSCROLL_INVERT -> right movement scrolls left", hwheel(m) and all(v < 0 for v in hwheel(m)), sum(hwheel(m)))
hm.HSCROLL_INVERT = False
hm.HSCROLL = False
m, e = run(START + fist_path(0.12, 0.0))
check("HSCROLL = False -> no sideways scrolling", hwheel(m) == [] and wheel(m) == [], (hwheel(m)[:3], wheel(m)[:3]))
hm.HSCROLL = True
# the second hand's fist does not scroll; a noisy relaxed hand does nothing
two = lambda x: [V.make(px=x, fist=True, label="Left"), V.make(px=0.75, label="Right")]
m, e = run(N(10, lambda t: two(0.3)) + [lambda t, k=k: two(0.3 + 0.02 * min(k, 8)) for k in range(40)])
check("left-hand fist moved sideways -> no scrolling (main hand only)", hwheel(m) == [] and wheel(m) == [], hwheel(m)[:3])
rnd = random.Random(11)
m, e = run([lambda t: V.make(jitter=0.004, rnd=rnd)] * 200)
check("noisy relaxed hand -> no sideways scrolling", hwheel(m) == [], hwheel(m)[:3])
print("ALL HSCROLL OK")
