import os as _os, sys as _sys, tempfile as _tempfile
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import sys, io, contextlib
pass
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
    import test_buttons_4_5 as S
hm, N, check = V.hm, V.N, V.check
def fists(ly=0.6, ry=0.6): return [V.make(px=0.3, py=ly, fist=True, label="Left"), V.make(px=0.7, py=ry, fist=True, label="Right")]
opn = lambda t: [V.make(px=0.3, label="Left"), V.make(px=0.7, label="Right")]
one = lambda **k: (lambda t: [V.make(px=0.7, **k)])
class Sim:
    def __init__(s): s.m = V.FakeMouse(); s.e = hm.Engine(s.m, 0, 0, 1920, 1080); s.t = 0.0
    def go(s, frames):
        n0, m0 = len(s.m.events), s.m.moves
        for f in frames:
            s.e.update(f(s.t), s.t); s.t += 1 / 16
        return s.m.events[n0:] + [('move',)] * (s.m.moves - m0)
def acts(ev): return [x for x in ev if x[0] != 'move']
sim = Sim()
sim.go(N(10, opn) + N(24, lambda t: fists()))
check("two fists 1.5 s -> gestures off (camera keeps going)", sim.e.gestures_off and sim.e.gestures_changed == "off")
sim.e.gestures_changed = None
ev = sim.go(N(30, lambda t: fists()))
check("fists still held after turning off -> stays off, no scroll", sim.e.gestures_off and acts(ev) == [], acts(ev))
ev = sim.go(N(10, opn) + [lambda t, k=k: [V.make(px=0.5 + 0.03 * k)] for k in range(10)] + N(10, one()) + N(6, one(pinch='m')) + N(8, one()) + N(6, one(pinch='r')) + N(8, one())
            + N(8, lambda t: [S.thumb_on("index")]) + N(8, one()) + N(8, lambda t: [S.thumb_on("pinky")]) + N(8, one())
            + N(20, one(fist=True)) + [lambda t, k=k: [V.make(px=0.7, py=0.6 + 0.02 * k, fist=True)] for k in range(15)] + N(8, one()))
check("while off: moving, clicks, buttons 4/5, fist scroll -> nothing at all", ev == [], ev[:5])
check("...and it says so", sim.e.gesture == "gestures off")
ev = sim.go(N(8, opn) + N(10, lambda t: fists()) + N(8, opn))
check("two fists only 0.6 s while off -> still off", sim.e.gestures_off and acts(ev) == [])
ev = sim.go(N(24, lambda t: fists()))
check("two fists 1.5 s again -> gestures on", not sim.e.gestures_off and sim.e.gestures_changed == "on")
sim.e.gestures_changed = None
ev = sim.go(N(30, lambda t: fists()) + N(10, one()))
check("fists still held after turning on -> no instant off, no scroll", not sim.e.gestures_off and [x for x in ev if x[0] == 'wheel'] == [])
ev = sim.go(N(6, one(pinch='m')) + N(8, one()))
check("gestures work again: left click", [x for x in ev if x[0] == 'left'] == [('left', 'down'), ('left', 'up')], acts(ev))
ev = sim.go(N(6, one(pinch='m')) + N(4, one()))
ev = sim.go([lambda t: [V.make(px=0.7 + 0.01 * (k % 5))] for k in range(10)])
check("cursor moves again", any(x[0] == 'move' for x in ev))
# tray switch
sim.e.set_gestures(False); sim.go(N(2, one()))
check("tray: gestures off", sim.e.gestures_off)
sim.e.set_gestures(True); sim.go(N(2, one()))
check("tray: gestures on", not sim.e.gestures_off)
# a held click is let go when gestures turn off
sim2 = Sim(); sim2.go(N(10, one()) + N(10, one(pinch='m')))
sim2.e.set_gestures(False); ev = sim2.go(N(2, one(pinch='m')))
check("button held when gestures go off -> let go", ('left', 'up') in ev, ev)
print("ALL V20 OK")
