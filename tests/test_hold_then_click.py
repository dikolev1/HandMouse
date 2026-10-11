import os as _os, sys as _sys, tempfile as _tempfile
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import sys, io, contextlib
pass
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
hm, check, N = V.hm, V.check, V.N
def run(frames, fps=20):
    m = V.FakeMouse(); e = hm.Engine(m, 0, 0, 1920, 1080); t = 0.0
    for f in frames: e.update([f(t)], t); t += 1 / fps
    return m
o = lambda t: V.make(px=0.7); mp = lambda t: V.make(px=0.7, pinch='m')
b = lambda m: [x for x in m.events if x[0] in ('left', 'right', 'middle')]
m = run(N(10, o) + N(40, mp) + N(4, o) + N(6, mp) + N(10, o))
check("2 s hold, then a quick new pinch: two separate clicks, no extra click", b(m) == [('left', 'down'), ('left', 'up')] * 2, b(m))
m = run(N(10, o) + N(4, mp) + N(4, o) + N(4, mp) + N(10, o))
check("quick double pinch still a double-click", b(m) == [('left', 'down'), ('left', 'up')] * 2, b(m))
m = run(N(10, o) + N(4, mp) + N(12, o) + N(4, mp) + N(10, o))
check("slower double pinch gets the helper click", b(m) == [('left', 'down'), ('left', 'up')] * 3, b(m))
print("ALL HOLD OK")
