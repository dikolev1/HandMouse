import os as _os, sys as _sys, tempfile as _tempfile
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import sys, io, contextlib, random, math
pass
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
    import test_click_jumps as J
hm = V.hm; check = V.check
def run(frames, sw=3840):
    m = V.FakeMouse(); e = hm.Engine(m, 0, 0, sw, 1080); t = 0.0; path = []
    for f in frames:
        hs = f(t); hs = hs if isinstance(hs, list) else [hs]
        e.update(hs, t); t += 1 / 16; path.append(m.pos)
    return m, e, path
H = J.hand
# drag: press, then move the finger clearly -> cursor follows while the button is held
drag = [lambda t, k=k: H(0.45 + 0.01 * k, 0.40, 'm') for k in range(1, 20)]
m, e, path = run([lambda t: H(0.45, 0.40)] * 20 + [lambda t: H(0.45, 0.40, 'm')] * 4 + drag + [lambda t: H(0.64, 0.40)] * 8)
b = [x for x in m.events if x[0] == 'left']
pressed_at = path[23]; released_at = path[23 + 19]
check("drag moves the cursor while held", b == [('left', 'down'), ('left', 'up')] and released_at[0] - pressed_at[0] > 300, (pressed_at, released_at))
# small finger wobble while held (under the drag threshold) -> no movement
rnd = random.Random(2)
m, e, path = run([lambda t: H(0.45, 0.40)] * 20 + [lambda t: H(0.45 + rnd.uniform(-0.004, 0.004), 0.40 + rnd.uniform(-0.004, 0.004), 'm')] * 12 + [lambda t: H(0.45, 0.40)] * 8)
check("wobble while holding the click doesn't move the cursor", max(math.dist(p, path[23]) for p in path[23:34]) < 1, path[23])
# fast real movement is not blocked by the glitch filter (only 1 frame of delay)
fast = [lambda t, k=k: H(0.30 + 0.05 * k, 0.40) for k in range(1, 9)]
m, e, path = run([lambda t: H(0.30, 0.40)] * 20 + fast + [lambda t: H(0.70, 0.40)] * 10)
l, tp, r, bt = hm.cursor_box(); target = (0.70 - l) / (r - l) * 3839
check("fast sweep across still reaches its target", abs(path[-1][0] - target) < 60, (round(path[-1][0]), round(target)))
# reaching the screen edges still works
m, e, path = run([lambda t: H(0.5, 0.40)] * 20 + [lambda t, k=k: H(0.5 + 0.03 * k, 0.40) for k in range(1, 12)] + [lambda t: H(0.85, 0.40)] * 20)
check("pushing past the box edge reaches the screen edge", path[-1][0] > 3830, path[-1])
# the right hand still takes over the cursor when raised (after MAIN_SWITCH_TIME)
two = lambda t: [H(0.30, 0.40, label="Left"), H(0.70, 0.40)]
m, e, path = run([lambda t: H(0.30, 0.40, label="Left")] * 20 + [two] * 20)
check("raising the right hand gives it the cursor", path[-1][0] > 2800, path[-1])
m, e, path = run([lambda t: H(0.50, 0.40)] * 20 + [lambda t: [H(0.50, 0.40), H(0.80, 0.40)]] * 3 + [lambda t: H(0.50, 0.40)] * 10)
check("a 0.2 s phantom 'hand' to the right doesn't take the cursor", max(abs(p[0] - path[19][0]) for p in path[19:]) < 5, path[19])
# hand away for 5 s -> cursor starts where the finger points again
m, e, path = run([lambda t: H(0.5, 0.40)] * 20 + [lambda t: []] * 80 + [lambda t: H(0.30, 0.40)] * 10)
expect = (0.30 - l) / (r - l) * 3839
check("after a long absence the cursor starts at the finger", abs(path[-1][0] - expect) < 60, (round(path[-1][0]), round(expect)))
print("ALL V10 OK")
