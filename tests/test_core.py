import os as _os, sys as _sys, tempfile as _tempfile
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import sys, math, random
pass
import hand_mouse as hm
hm.RIGHT_HAND_LABEL = "Right"   # the synthetic hands here are labelled with your own hand side

def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name, info); assert cond

class FakeMouse:
    def __init__(s): s.events = []; s.pos = None; s.moves = 0
    def move(s, x, y): s.pos = (x, y); s.moves += 1
    def button(s, n, d): s.events.append((n, 'down' if d else 'up'))
    def wheel(s, d): s.events.append(('wheel', d))
    def swipe(s, a, d): s.events.append(('swipe', d))
    def keys(s, vks): s.events.append(('keys', tuple(vks)))
    def key(s, vk, down): s.events.append(('key', vk, down))
    def toggle_keyboard(s): s.events.append(('osk',))

# open hand, palm to camera, fingers up (world metres, y down)
OPEN = {0:(0,0.04,0),1:(-0.03,0.02,0),2:(-0.045,0,0),3:(-0.055,-0.02,0),4:(-0.06,-0.035,0),
 5:(-0.025,-0.05,0),6:(-0.027,-0.08,0),7:(-0.028,-0.10,0),8:(-0.029,-0.12,0),
 9:(0,-0.052,0),10:(0,-0.085,0),11:(0,-0.105,0),12:(0,-0.125,0),
 13:(0.02,-0.05,0),14:(0.022,-0.08,0),15:(0.023,-0.10,0),16:(0.024,-0.115,0),
 17:(0.04,-0.045,0),18:(0.043,-0.07,0),19:(0.045,-0.085,0),20:(0.046,-0.1,0)}

def make(px=0.5, py=0.6, pinch=None, fist=False, fold=(), label="Right", jitter=0.0, rnd=random):
    w = dict(OPEN)
    folded = {0, 1, 2, 3} if fist else set(fold)
    for f, (tip, mcp) in enumerate(hm.FINGERS):
        if f in folded:     # fold: fingertip tucked into the palm, in front of the knuckle
            mx, my, mz = w[mcp]
            w[tip] = (mx, my + 0.035, -0.03); w[tip - 1] = (mx, my + 0.01, -0.035); w[tip - 2] = (mx, my - 0.02, -0.025)
    if fist:                # thumb wraps over the index/middle middle segments
        w[4] = (-0.005, -0.03, -0.045); w[3] = (-0.03, -0.02, -0.035)
    if pinch == 'm': w[4] = (w[12][0] - 0.01, w[12][1] + 0.005, -0.01)
    if pinch == 'r': w[4] = (w[16][0] - 0.01, w[16][1] + 0.005, -0.01)
    if pinch == 'mr': w[4] = ((w[12][0] + w[16][0]) / 2, (w[12][1] + w[16][1]) / 2 + 0.008, -0.012)
    world = [w[i] for i in range(21)]
    # image: 1 m of hand ~ 3.2 picture widths; y down; place palm centre at (px, py)
    img = [(x * 3.2, y * 3.2 * 1.33) for x, y, z in world]
    cx = sum(img[i][0] for i in (0, 5, 9, 13, 17)) / 5; cy = sum(img[i][1] for i in (0, 5, 9, 13, 17)) / 5
    img = [(x - cx + px + rnd.gauss(0, jitter), y - cy + py + rnd.gauss(0, jitter)) for x, y in img]
    return hm.Hand(label, img, world)

def run(frames, fps=16):
    m = FakeMouse(); e = hm.Engine(m, 0, 0, 1920, 1080); t = 0.0
    for f in frames:
        hs = f(t) if callable(f) else f
        hs = hs if isinstance(hs, list) else [hs]
        e.update(hs, t); t += 1 / fps
    return m, e
def btn(m): return [x for x in m.events if x[0] in ('left', 'right', 'middle')]
def wheel(m): return [x[1] for x in m.events if x[0] == 'wheel']
def swipes(m): return [x[1] for x in m.events if x[0] == 'swipe']
open_ = lambda t: make()
N = lambda n, f: [f] * n

# ---- sanity of the hand model
check("open hand fingers straight", min(hm.finger_extension(make())) > 1.5, [round(v, 2) for v in hm.finger_extension(make())])
check("fist fingers folded", max(hm.finger_extension(make(fist=True))) < hm.FIST_CURL, [round(v, 2) for v in hm.finger_extension(make(fist=True))])
check("left-click pose is not a fist", not hm.is_fist(make(pinch='m')))
check("left-click pose keeps index straight", hm.finger_extension(make(pinch='m'))[0] > hm.INDEX_STRAIGHT)

# ---- clicks still work
m, e = run(N(10, open_) + N(6, lambda t: make(pinch='m')) + N(6, open_)); check("left click", btn(m) == [('left', 'down'), ('left', 'up')], btn(m))
m, e = run(N(10, open_) + N(6, lambda t: make(pinch='r')) + N(6, open_)); check("right click", btn(m) == [('right', 'down'), ('right', 'up')], btn(m))
m, e = run(N(10, open_) + N(6, lambda t: make(pinch='mr')) + N(6, open_)); check("middle click", btn(m) == [('middle', 'down'), ('middle', 'up')], btn(m))
m, e = run(N(10, open_) + N(1, lambda t: make(pinch='m')) + N(6, open_)); check("brief brush ignored", btn(m) == [], btn(m))

# ---- fist scroll
m, e = run(N(10, open_) + N(16, lambda t: make(fist=True)) + N(8, open_))
check("fist held still: no scroll, no click", wheel(m) == [] and btn(m) == [], (wheel(m)[:3], btn(m)))
down = [lambda t, k=k: make(fist=True, py=0.6 + min(k, 8) * 0.02) for k in range(40)]
m, e = run(N(10, open_) + N(4, lambda t: make(fist=True)) + down + N(8, open_))
w = wheel(m); check("fist moved down -> scrolls down", len(w) > 10 and all(v < 0 for v in w), (len(w), sum(w)))
check("...and no clicks while forming/holding the fist", btn(m) == [], btn(m))
up = [lambda t, k=k: make(fist=True, py=0.6 - min(k, 8) * 0.02) for k in range(40)]
m, e = run(N(10, open_) + N(4, lambda t: make(fist=True)) + up); w = wheel(m)
check("fist moved up -> scrolls up", len(w) > 10 and all(v > 0 for v in w), sum(w))
m, e = run(N(10, open_) + N(4, lambda t: make(fist=True)) + down + N(16, open_))
n_before = len(wheel(m))
m2, e2 = run(N(10, open_) + N(4, lambda t: make(fist=True)) + down + N(16, open_) + N(32, open_))
check("opening the hand stops scrolling", len(wheel(m2)) == n_before, (n_before, len(wheel(m2))))
# speed grows with distance
def total(dist):
    mm, _ = run(N(10, open_) + N(4, lambda t: make(fist=True)) + N(32, lambda t: make(fist=True, py=0.6 + dist)))
    return -sum(wheel(mm))
a, b = total(0.06), total(0.20); check("further = faster", b > 2 * a > 0, (a, b))
# cursor frozen during fist
m, e = run(N(10, open_) + N(4, lambda t: make(fist=True)) + down)
moves_before = m.moves; m, e = run(N(10, open_))
m3, _ = run(N(10, open_) + N(4, lambda t: make(fist=True)) + down)
check("cursor doesn't move while scrolling", m3.moves - 0 <= m.moves + 2, (m.moves, m3.moves))
# jittery fist in dim light: noisy landmarks don't break it
rnd = random.Random(1)
m, e = run(N(10, open_) + [lambda t, k=k: make(fist=True, py=0.6 + min(k, 8) * 0.02, jitter=0.004, rnd=rnd) for k in range(48)])
check("noisy fist still scrolls smoothly", len(wheel(m)) > 20 and all(v < 0 for v in wheel(m)), len(wheel(m)))
# second hand fist scrolls too, main keeps cursor
two = lambda y: [make(px=0.3, py=y, fist=True, label="Left"), make(px=0.7, label="Right")]
m, e = run(N(10, lambda t: two(0.6)) + [lambda t, k=k: two(0.6 + min(k, 8) * 0.02) for k in range(40)])
check("second hand only does on/off: its fist does not scroll", wheel(m) == [], len(wheel(m)))
hm.SECOND_HAND_GESTURES = True        # the older second-hand features, still available as an option
m, e = run(N(10, lambda t: two(0.6)) + [lambda t, k=k: two(0.6 + min(k, 8) * 0.02) for k in range(40)])
check("(option on) left-hand fist scrolls while right hand points", len(wheel(m)) > 10, len(wheel(m)))

# ---- swipe with the second hand only
def pair(lx): return [make(px=lx, label="Left"), make(px=0.75, label="Right")]
flick_r = [lambda t, k=k: pair(0.25 + 0.05 * k) for k in range(1, 6)]
m, e = run(N(16, lambda t: pair(0.25)) + flick_r + N(16, lambda t: pair(0.50)))
check("second hand fast right -> swipe right", swipes(m) == ['right'], swipes(m))
back = [lambda t, k=k: pair(0.5 - 0.05 * k) for k in range(1, 6)]
m, e = run(N(16, lambda t: pair(0.25)) + flick_r + back + N(16, lambda t: pair(0.25)))
check("coming back doesn't swipe the other way", swipes(m) == ['right'], swipes(m))
m, e = run(N(16, lambda t: pair(0.25)) + flick_r + N(20, lambda t: pair(0.50)) + [lambda t, k=k: pair(0.5 - 0.05 * k) for k in range(1, 6)] + N(8, lambda t: pair(0.25)))
check("a deliberate swipe back later works", swipes(m) == ['right', 'left'], swipes(m))
slow = [lambda t, k=k: pair(0.25 + 0.3 * k / 48) for k in range(48)]
m, e = run(N(16, lambda t: pair(0.25)) + slow); check("slow second-hand movement: no swipe", swipes(m) == [], swipes(m))
single = [lambda t, k=k: make(px=0.25 + 0.05 * min(k, 6)) for k in range(30)]
m, e = run(N(16, open_) + single); check("main hand alone moving fast: no swipe", swipes(m) == [], swipes(m))
m, e = run(N(16, lambda t: [make(px=0.75, label="Right")]) + [lambda t: pair(0.1)] + [lambda t, k=k: pair(0.1 + 0.06 * k) for k in range(1, 3)] + N(10, lambda t: pair(0.22)))
check("second hand entering the view doesn't swipe", swipes(m) == [], swipes(m))
two_moving = [lambda t, k=k: [make(px=0.2 + 0.05 * min(k, 5), label="Left"), make(px=0.6 + 0.05 * min(k, 5), label="Right")] for k in range(16)]
m, e = run(N(16, lambda t: [make(px=0.2, label="Left"), make(px=0.6, label="Right")]) + two_moving)
check("both hands moving right together (body moves): no swipe", swipes(m) == [], swipes(m))

# ---- no scrolling or swiping from a normal relaxed hand with noise
rnd = random.Random(7)
m, e = run([lambda t: make(jitter=0.004, rnd=rnd)] * 200)
check("noisy relaxed hand: nothing fires", wheel(m) == [] and swipes(m) == [] and btn(m) == [], m.events[:4])
hm.SECOND_HAND_GESTURES = False
m, e = run(N(16, lambda t: pair(0.25)) + flick_r + N(16, lambda t: pair(0.50)))
check("second hand fast right with the option off (default) -> no swipe", swipes(m) == [], swipes(m))
print("ALL V7 OK")
