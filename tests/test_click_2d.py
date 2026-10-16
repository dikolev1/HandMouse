import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import io, contextlib, random
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
    import test_buttons_4_5 as B
hm, N, check = V.hm, V.N, V.check

# 2026-10-16 screenshot: thumb clearly on the bent middle fingertip, but the depth guess reads t-mid 0.39 (a click
# starts below 0.34). In the picture the two tips are ~0.14 apart.


def on_tip(tip, d3, d2_off=0.0, px=0.7):
    """Right hand, thumb on a fingertip in the picture (or d2_off metres beside it), d3 palm lengths away in 3D."""
    h = V.make(px=px); w = h.world; t = w[tip]; L = hm.palm_length(h)
    x, y = t[0] - d2_off, t[1]
    z = t[2] - max((d3 * L) ** 2 - d2_off ** 2, 0.0) ** 0.5
    return B.with_thumb(h, (x, y, z))


open_ = lambda t: V.make(px=0.7)
btn = lambda m: [x for x in m.events if x[0] in ("left", "right", "middle")]
for name, h, want in (("thumb on middle tip, depth reads 0.39 (screenshot)", on_tip(12, 0.39), "left"),
                      ("thumb on middle tip, depth reads 0.44", on_tip(12, 0.44), "left"),
                      ("thumb on ring tip, depth reads 0.40", on_tip(16, 0.40), "right"),
                      ("thumb behind the middle tip, depth 0.55 (hand turned)", on_tip(12, 0.55), None),
                      ("depth 0.39 but 2 cm beside the tip in the picture", on_tip(12, 0.39, 0.02), None)):
    m, e = B.run(N(12, open_) + N(6, lambda t, h=h: h) + N(10, open_))
    exp = [(want, "down"), (want, "up")] if want else []
    check(f"{name} (3D {h.pinch[0]:.2f}/{h.pinch[1]:.2f}, 2D {hm.thumb_tip_2d(h, 12):.2f}/{hm.thumb_tip_2d(h, 16):.2f})"
          f" -> {want or 'no click'}", btn(m) == exp, btn(m))
rnd = random.Random(21)
m, e = B.run([lambda t: V.make(px=0.7, jitter=0.004, rnd=rnd)] * 300)
check("noisy relaxed hand for 19 s -> no clicks", btn(m) == [], btn(m)[:4])
print("ALL CLICK 2D OK")
