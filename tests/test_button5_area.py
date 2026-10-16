import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
    import test_buttons_4_5 as B
hm, N, check = V.hm, V.N, V.check

# 2026-10-16 debug picture: the thumb held for a second on the palm under the ring / little finger did nothing;
# button 5 came only when the thumb slid up onto the knuckle line.


def thumb_at(frac_down, across=1.0, px=0.7):
    """Thumb tip on the palm: across = 0 under the ring knuckle, 1 under the little-finger knuckle (2 = index side
    is -2); frac_down = 0 on the knuckle line, 1 at the wrist."""
    h = V.make(px=px); w = h.world
    r, k, wr = w[hm.RING_MCP], w[hm.PINKY_MCP], w[hm.WRIST]
    top = [r[i] + (k[i] - r[i]) * across for i in range(3)]
    pos = [top[i] + (wr[i] - top[i]) * frac_down for i in range(3)]
    return B.with_thumb(h, (pos[0], pos[1], pos[2] - 0.012))


open_ = lambda t: V.make(px=0.7)
ev = lambda m: [x for x in m.events if x[0] in ("x1", "x2", "left", "right", "middle")]
for name, h, want in (("on the knuckle line under the little finger", thumb_at(0.0), True),
                      ("palm under the little finger, 30% down to the wrist", thumb_at(0.3), True),
                      ("palm under the little finger, 50% down", thumb_at(0.5), True),
                      ("palm between ring and little finger, 40% down", thumb_at(0.4, 0.5), True),
                      ("palm under the index finger (other side)", thumb_at(0.3, -2.0), False),
                      ("near the wrist (85% down)", thumb_at(0.85), False)):
    m, e = B.run(N(12, open_) + N(8, lambda t, h=h: h) + N(8, open_))
    exp = [("x2", "down"), ("x2", "up")] if want else []
    check(f"thumb {name} (x2 {h.side['x2']:.2f}) -> {'button 5' if want else 'nothing'}", ev(m) == exp, ev(m))

# the thumb's way to the ring fingertip (right click) passes over the palm: still only a right click
ring = V.make(px=0.7, pinch="r").world[4]
rest = V.make(px=0.7).world[4]
path = [lambda t, a=a: B.with_thumb(V.make(px=0.7), tuple(rest[i] + (ring[i] - rest[i]) * a for i in range(3)))
        for a in (0.2, 0.4, 0.6, 0.8)]
m, e = B.run(N(12, open_) + path + N(6, lambda t: V.make(px=0.7, pinch="r")) + N(8, open_))
check("thumb moving across the palm to the ring fingertip -> a click, no button 5 on the way",
      not any(x[0] == "x2" for x in ev(m)) and len(ev(m)) == 2, ev(m))
print("ALL BUTTON 5 AREA OK")
