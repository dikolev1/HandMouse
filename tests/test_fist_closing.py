import os as _os, sys as _sys, tempfile as _tempfile
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import sys, io, contextlib
pass
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
hm = V.hm
def blend(a, b, k):
    h = V.make()
    h.world = [tuple(pa + (pb - pa) * k for pa, pb in zip(a.world[i], b.world[i])) for i in range(21)]
    h.img = [tuple(pa + (pb - pa) * k for pa, pb in zip(a.img[i], b.img[i])) for i in range(21)]
    return h
o, f = V.make(), V.make(fist=True)
print("closing a fist, step by step:")
for k in [i / 6 for i in range(7)]:
    h = blend(o, f, k); dm, dr = hm.pinch_ratios(h); e = hm.finger_extension(h)
    print(f"  {k:.2f}: index {e[0]:.2f}  thumb-mid {dm:.2f}  thumb-ring {dr:.2f}  touch={min(dm,dr)<hm.TOUCH_ON}  index-straight={e[0]>hm.INDEX_STRAIGHT}")
worst = []
for frames in (3, 5, 8, 12):     # fist closing at different speeds (16 fps)
    seq = V.N(10, V.open_) + [lambda t, k=k: blend(o, f, k / frames) for k in range(1, frames + 1)] + V.N(10, lambda t: f) \
        + [lambda t, k=k: blend(f, o, k / frames) for k in range(1, frames + 1)] + V.N(10, V.open_)
    m, e = V.run(seq)
    worst.append((frames, V.btn(m)))
V.check("closing and opening a fist at any speed never clicks", all(b == [] for _, b in worst), worst)
