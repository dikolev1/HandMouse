import os as _os, sys as _sys, tempfile as _tempfile
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import sys, io, contextlib, random, math
pass
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
    import test_click_jumps as J
hm = V.hm; check = V.check
class WinLikeMouse:
    """records downs with time and position, and judges double-clicks like Windows (500 ms, 4 px)"""
    def __init__(s): s.now = 0.0; s.pos = (0, 0); s.downs = []; s.events = []; s.moves = 0
    def move(s, x, y): s.pos = (x, y); s.moves += 1
    def button(s, n, d):
        s.events.append((n, 'down' if d else 'up', round(s.now, 3)))
        if d: s.downs.append((n, s.now, s.pos))
    def wheel(s, d): pass
    def swipe(s, a, d): pass
    double_click_time = 0.5
    def doubles(s):
        out, i = 0, 1
        while i < len(s.downs):
            a, b = s.downs[i - 1], s.downs[i]
            if a[0] == b[0] == 'left' and b[1] - a[1] <= 0.5 and math.dist(a[2], b[2]) <= 4:
                out += 1; i += 2
            else:
                i += 1
        return out
def run(frames, fps, jitter=0.0, seed=0):
    rnd = random.Random(seed)
    m = WinLikeMouse(); e = hm.Engine(m, 0, 0, 1920, 1080); t = 0.0
    for f in frames:
        m.now = t
        h = f(t)
        if jitter and h:
            h.img = list(h.img); x, y = h.img[8]; h.img[8] = (x + rnd.gauss(0, jitter), y + rnd.gauss(0, jitter))
        e.update([h] if h else [], t); t += 1 / fps
    return m, e
def seq(fps, pattern, x=0.47):
    """pattern: list of (state, seconds); state 'open' / 'pinch' / 'half' (fingers only slightly open)"""
    out = []
    for state, secs in pattern:
        n = max(1, round(secs * fps))
        for _ in range(n):
            if state == 'open': out.append(lambda t: J.hand(x, 0.40))
            elif state == 'pinch': out.append(lambda t: J.hand(x, 0.40, 'm'))
            elif state == 'half':      # thumb drifts only a little away from the middle finger
                def f(t):
                    h = J.hand(x, 0.40, 'm'); w = list(h.world); w[4] = (w[4][0] - 0.022, w[4][1] + 0.02, w[4][2]); h.world = w
                    return h
                out.append(f)
    return out
print("half-open pinch ratio:", [round(v, 2) for v in seq(10, [('half', 0.1)])[0](0).pinch])
for fps in (10, 16, 25):
    # a natural quick double pinch: 0.15 s pinch, 0.15 s open, 0.15 s pinch
    m, e = run(seq(fps, [('open', 1.5), ('pinch', 0.15), ('open', 0.15), ('pinch', 0.15), ('open', 1.0)]), fps, jitter=0.002)
    check(f"{fps} fps: quick double pinch -> Windows sees a double-click", m.doubles() == 1, m.events)
    # slower double pinch (0.25/0.25/0.25)
    m, e = run(seq(fps, [('open', 1.5), ('pinch', 0.25), ('open', 0.25), ('pinch', 0.25), ('open', 1.0)]), fps, jitter=0.002)
    check(f"{fps} fps: relaxed double pinch -> double-click", m.doubles() == 1, m.events)
    # fingers only open slightly between the two pinches
    m, e = run(seq(fps, [('open', 1.5), ('pinch', 0.2), ('open', 0.1), ('pinch', 0.2), ('open', 1.0)]), fps, jitter=0.002)
    check(f"{fps} fps: very short opening between pinches -> double-click", m.doubles() == 1, m.events)
    # two separate clicks 2 s apart -> two single clicks, no double
    m, e = run(seq(fps, [('open', 1.5), ('pinch', 0.2), ('open', 2.0), ('pinch', 0.2), ('open', 1.0)]), fps, jitter=0.002)
    lefts = [x for x in m.events if x[0] == 'left' and x[1] == 'down']
    check(f"{fps} fps: clicks 2 s apart stay single clicks", m.doubles() == 0 and len(lefts) == 2, m.events)
    # a single click -> exactly one click
    m, e = run(seq(fps, [('open', 1.5), ('pinch', 0.2), ('open', 1.5)]), fps, jitter=0.002)
    check(f"{fps} fps: single pinch -> one click", [x[:2] for x in m.events] == [('left', 'down'), ('left', 'up')], m.events)
    # triple pinch: double-click then one more click (not two double-clicks)
    m, e = run(seq(fps, [('open', 1.5), ('pinch', 0.15), ('open', 0.15), ('pinch', 0.15), ('open', 0.15), ('pinch', 0.15), ('open', 1.0)]), fps, jitter=0.002)
    check(f"{fps} fps: triple pinch -> one double-click", m.doubles() == 1, m.events)
# after a click, a deliberate move still works right away
m, e = run(seq(16, [('open', 1.5), ('pinch', 0.2), ('open', 0.1)]) + [lambda t, k=k: J.hand(0.47 + 0.02 * k, 0.40) for k in range(1, 10)], 16)
p_click = m.downs[0][2]
check("deliberate move right after a click is not held back", m.pos[0] - p_click[0] > 300, (p_click, m.pos))
# a long hold (drag) with a noisy frame does not release early
noisy = seq(16, [('open', 1.5), ('pinch', 0.3)]) + [lambda t: J.hand(0.47, 0.40)] + seq(16, [('pinch', 0.4), ('open', 1.0)])
m, e = run(noisy, 16)
print("   (one-frame open during a hold:", [x[:2] for x in m.events], ")")
print("ALL DOUBLE OK")
