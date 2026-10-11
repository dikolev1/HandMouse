import os as _os, sys as _sys, tempfile as _tempfile
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import sys, io, contextlib, random
pass
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
hm, N, check = V.hm, V.N, V.check
L = lambda px=0.35, **k: V.make(px=px, label="Left", **k)
R = lambda px=0.65, **k: V.make(px=px, label="Right", **k)
def run(frames, side="right", fps=20):
    m = V.FakeMouse(); saved = []
    e = hm.Engine(m, 0, 0, 1920, 1080, main_side=side, on_main_side=saved.append); t = 0.0; moves = []
    for f in frames:
        hs = f(t); e.update(hs if isinstance(hs, list) else [hs], t); t += 1 / fps; moves.append(m.moves)
    return m, e, saved, moves
clicks = lambda m: [x for x in m.events if x[0] in ("left", "right", "middle")]
def dfist(hand):
    return N(4, lambda t: hand(fist=True)) + N(4, lambda t: hand()) + N(4, lambda t: hand(fist=True)) + N(8, lambda t: hand())
m, e, saved, mv = run(N(30, lambda t: L()) + N(8, lambda t: L(pinch='m')) + N(10, lambda t: L()))
check("left hand alone: no cursor, no clicks", m.moves == 0 and clicks(m) == [], (m.moves, clicks(m)))
m, e, saved, mv = run(N(10, lambda t: L()) + dfist(L) + [lambda t, k=k: L(px=0.35 + 0.01 * (k % 8)) for k in range(30)] + N(8, lambda t: L(pinch='m')) + N(10, lambda t: L()))
check("left hand alone, fist twice -> it becomes the main hand (saved)", e.main_side == "left" and saved == ["left"], (e.main_side, saved))
check("...and moves the cursor and clicks", m.moves > 5 and clicks(m) == [("left", "down"), ("left", "up")], (m.moves, clicks(m)))
m, e, saved, mv = run(N(30, lambda t: R()) + N(8, lambda t: R(pinch='m')) + N(5, lambda t: R()), side="left")
check("left is main (remembered after a restart): right hand alone does nothing", m.moves == 0 and clicks(m) == [], (m.moves, clicks(m)))
m, e, saved, mv = run(N(10, lambda t: R()) + dfist(R) + N(20, lambda t: R()), side="left")
check("right hand alone, fist twice -> right is main again", e.main_side == "right" and saved == ["right"], saved)
m, e, saved, mv = run(N(20, lambda t: [L(), R()]) + N(8, lambda t: [L(pinch='m'), R()]) + N(10, lambda t: [L(), R()]), side="left")
check("left main, both hands in view: the left hand clicks", clicks(m) == [("left", "down"), ("left", "up")], clicks(m))
m, e, saved, mv = run(N(20, lambda t: [L(), R()]) + N(8, lambda t: [L(), R(pinch='m')]) + N(10, lambda t: [L(), R()]), side="left")
check("...and the right hand doesn't", clicks(m) == [], clicks(m))
m, e, saved, mv = run(N(10, lambda t: R()) + dfist(R) + N(10, lambda t: R()))
check("the main hand making a fist twice changes nothing", saved == [] and e.main_side == "right", saved)
rnd = random.Random(2)
def flicky(t):
    h = R(); h.label = "Left" if rnd.random() < 0.08 else "Right"; return h
m, e, saved, mv = run(N(10, lambda t: R()) + N(200, flicky) + N(8, lambda t: R(pinch='m')) + N(10, lambda t: R()))
check("right hand whose left/right guess is wrong 8% of the time stays main", clicks(m) == [("left", "down"), ("left", "up")] and e.main_side == "right", clicks(m))
both = lambda **k: [L(**k), R()]
m, e, saved, mv = run(N(10, lambda t: [L(), R()]) + N(4, lambda t: both(fist=True)) + N(4, lambda t: both()) + N(4, lambda t: both(fist=True)) + N(8, lambda t: both()))
check("fist twice with the left hand while both hands are in view -> no switch", saved == [], saved)
print("ALL MAINSIDE OK")
