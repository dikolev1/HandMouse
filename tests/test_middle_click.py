import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
    import test_buttons_4_5 as B
hm, N, check = V.hm, V.N, V.check

# Middle click (thumb on middle AND ring tips) read as left clicks, 2026-10-15 debug pictures: the thumb reaches
# the middle tip one frame before the ring tip (first frame: middle 0.19, ring 0.61), and at 27 fps two frames
# are only 37 ms. After that one wrong left click, every retry within the double-click time repeated "left".


def thumb_on_middle_ring_far():
    """Thumb on the middle tip, ring tip still 0.6 away (the first frame of a real middle click)."""
    h = V.make(px=0.7); w = h.world; t = w[12]
    return B.with_thumb(h, (t[0] - 0.012, t[1] + 0.004, t[2] - 0.006))


h = thumb_on_middle_ring_far()
print("   first frame: middle %.2f ring %.2f" % h.pinch)
open_ = lambda t: V.make(px=0.7)
mid_first = lambda t: thumb_on_middle_ring_far()
both_ = lambda t: V.make(px=0.7, pinch="mr")
btn = lambda m: [x for x in m.events if x[0] in ("left", "right", "middle")]

for fps in (16, 27, 30):
    m, e = B.run(N(12, open_) + N(1, mid_first) + N(8, both_) + N(8, open_), fps=fps)
    check(f"{fps} fps: thumb on middle tip one frame before the ring -> middle click only (no left)",
          btn(m) == [("middle", "down"), ("middle", "up")], btn(m))

m, e = B.run(N(12, open_) + N(6, lambda t: V.make(px=0.7, pinch="m")) + N(6, open_) + N(1, mid_first)
             + N(10, both_) + N(8, open_), fps=27)
check("left click, then a middle click within the double-click time -> the middle click still comes",
      ("middle", "down") in btn(m) and btn(m)[-1] == ("middle", "up"), btn(m))

for fps in (16, 27):
    m, e = B.run(N(12, open_) + N(5, lambda t: V.make(px=0.7, pinch="m")) + N(8, open_), fps=fps)
    check(f"{fps} fps: plain left click still a left click", btn(m) == [("left", "down"), ("left", "up")], btn(m))
    m, e = B.run(N(12, open_) + N(5, lambda t: V.make(px=0.7, pinch="m")) + N(4, open_)
                 + N(5, lambda t: V.make(px=0.7, pinch="m")) + N(8, open_), fps=fps)
    check(f"{fps} fps: double-click still only left clicks (a slow second pinch gets a helper click)",
          {x[0] for x in btn(m)} == {"left"} and btn(m).count(("left", "down")) >= 2, btn(m))
m, e = B.run(N(12, open_) + N(3, lambda t: V.make(px=0.7, pinch="m")) + N(8, open_), fps=27)
check("27 fps: quick tap of 3 frames (0.11 s) -> still a click", btn(m) == [("left", "down"), ("left", "up")], btn(m))
for n in (2, 3):
    m, e = B.run(N(12, open_) + N(n, lambda t: V.make(px=0.7, pinch="m")) + N(8, open_), fps=30)
    check(f"30 fps: very quick tap of {n} frames ({n / 30:.2f} s) -> still one click",
          btn(m) == [("left", "down"), ("left", "up")], btn(m))
m, e = B.run(N(12, open_) + N(1, lambda t: V.make(px=0.7, pinch="m")) + N(8, open_), fps=30)
check("30 fps: one frame brush -> no click", btn(m) == [], btn(m))
print("ALL MIDDLE CLICK OK")
