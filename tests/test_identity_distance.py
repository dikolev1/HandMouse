import os as _os, sys as _sys, tempfile as _tempfile
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import sys, io, contextlib, random, math
pass
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
hm = V.hm; check = V.check
def far(h, f):
    """the same hand seen f times as big (f<1 = further away)"""
    cx, cy = h.center
    return hm.Hand(h.label, [(cx + (x - cx) * f, cy + (y - cy) * f) for x, y in h.img], h.world, aspect=h.aspect)
def run(frames, fps=16, ref=None):
    m = V.FakeMouse(); learned = []
    e = hm.Engine(m, 0, 0, 1920, 1080, ref_palm=ref, on_ref_learned=learned.append); t = 0.0; path = []
    for f in frames:
        hs = f(t); hs = hs if isinstance(hs, list) else [hs]
        e.update(hs, t); t += 1 / fps; path.append(m.pos)
    return m, e, path, learned
N = V.N
# the tracker's left/right guess: wrong 5% of the time with one hand (real videos: 0-4%), random with two
R1 = lambda px=0.7, **k: V.make(px=px, label="Right" if random.random() < 0.95 else "Left", **k)
R = lambda px=0.7, **k: V.make(px=px, label=random.choice(["Left", "Right"]), **k)
L = lambda px=0.3, **k: V.make(px=px, label=random.choice(["Left", "Right"]), **k)
random.seed(4)

# 1. hand identity ignores the tracker's (random) left/right labels
m, e, path, _ = run(N(40, lambda t: [L(), R()]))
roles = {h.key: h.role for h in []}
check("random labels: right hand stays main", e.main_key is not None and e.tracks[e.main_key].center[0] > 0.5, e.main_key)
check("random labels: only two hand ids used", len(e.tracks) == 2 and e.next_id == 2, list(e.tracks))

# 2. main hand drops out for 0.5 s while the left hand stays: left hand must not take over
pinchL = lambda t: [L(pinch='m')]
m, e, path, _ = run(N(20, lambda t: [L(), R()]) + N(8, pinchL) + N(10, lambda t: [L(), R()]))
b = [x for x in m.events if x[0] in ('left', 'right', 'middle')]
check("main hand gone 0.5 s: other hand doesn't click", b == [], b)
check("...and the cursor holds still meanwhile", max(abs(p[0] - path[19][0]) for p in path[19:28]) < 1, (path[19], path[27]))
check("...and the right hand is main again after", e.tracks[e.main_key].center[0] > 0.5)
# 3. main hand gone for good -> other hand takes over after the grace time, without a cursor jump
m, e, path, _ = run(N(20, lambda t: [L(px=0.42), R1(px=0.62)]) + N(30, lambda t: [L(px=0.42)]))
check("main hand gone for good: the left hand does NOT take over (right hand stays main)", e.main_side == "right" and all(h is None or h.center[0] > 0.5 for h in [e.tracks.get(e.main_key)]))
jump = max(math.dist(path[i], path[i - 1]) for i in range(21, 50))
check("...without the cursor jumping", jump < 60, round(jump))

# 4. normal hand size is learned and saved
m, e, path, learned = run(N(60, lambda t: R1()))
check("normal hand size learned from an open hand", e.ref_palm is not None and learned == [e.ref_palm], learned)
ref = e.ref_palm

# 5. further away: the same real movement gives the same result
def cursor_travel(f):
    """quick real movement of the same size; returns (target travel, final cursor - final target)"""
    frames = N(80, lambda t: far(R1(px=0.5), f)) + [lambda t, k=k: far(R1(px=0.5 + 0.02 * k * f), f) for k in range(1, 6)] \
             + N(30, lambda t: far(R1(px=0.6 * f + 0.5 * (1 - f)), f))
    m = V.FakeMouse(); e = hm.Engine(m, 0, 0, 1920, 1080, ref_palm=ref); t = 0.0; tg = []
    for fr in frames:
        h = fr(t); e.update([h], t); t += 1 / 16
        l, tp, r, b = e.box(); tg.append((h.img[8][0] - l) / (r - l) * 1919)
    return tg[-1] - tg[79], m.pos[0] - tg[-1], e
near_travel, near_off, _ = cursor_travel(1.0)
far_travel, far_off, e_far = cursor_travel(0.5)
check("hand at half size (2x further): cursor box shrinks", abs(e_far.k_cursor - 0.5) < 0.08, round(e_far.k_cursor, 2))
check("...so the same real movement aims the cursor just as far", 0.9 < far_travel / near_travel < 1.1, (round(near_travel), round(far_travel)))
check("...and a quick move lands on target at both distances", abs(near_off) < 80 and abs(far_off) < 80, (round(near_off), round(far_off)))
def scrolled(f):
    frames = N(20, lambda t: far(R1(), f)) + N(4, lambda t: far(R1(fist=True), f)) + N(32, lambda t: far(R1(fist=True, py=0.6 + 0.08 * f), f))
    m, e, path, _ = run(frames, ref=ref)
    return -sum(V.wheel(m))
sn, sf = scrolled(1.0), scrolled(0.5)
check("fist scroll: same real movement scrolls about the same when further away", sn > 0 and 0.7 < sf / sn < 1.4, (sn, sf))
def swiped(f):
    pair = lambda lx: [far(L(px=lx), f), far(R1(px=0.75), f)]
    frames = N(16, lambda t: pair(0.3)) + [lambda t, k=k: pair(0.3 + 0.2 * f * k / 5) for k in range(1, 6)] + N(10, lambda t: pair(0.3 + 0.2 * f))
    m, e, path, _ = run(frames, ref=ref)
    return V.swipes(m)
hm.SECOND_HAND_GESTURES = True
check("(option on) swipe works at 2x distance with the same real movement", swiped(0.5) == ['right'] and swiped(1.0) == ['right'], (swiped(1.0), swiped(0.5)))
hm.SECOND_HAND_GESTURES = False

# 6. a fist seen at an angle (one finger reads a bit open) doesn't flicker
def angled_fist(open_amount):
    h = R1(fist=True)
    w = list(h.world); wr = w[0]
    tip, mcp = 20, 17                             # pinky reads partly open
    w[tip] = tuple(wr[i] + (w[tip][i] - wr[i]) * open_amount for i in range(3))
    h.world = w
    return h
flicker = [lambda t, k=k: angled_fist(1.9 if k % 2 else 1.0) for k in range(30)]
print("   (pinky ratio in the flicker frames:", round(max(angled_fist(1.9).ext), 2), ")")
m, e, path, _ = run(N(10, lambda t: R1()) + N(6, lambda t: R1(fist=True)) + flicker)
check("fist with one finger reading slightly open keeps scrolling state", e.fists[e.main_key].state == "active", e.fists[e.main_key].state)

# 7. monitors change while running
m, e, path, _ = run(N(10, lambda t: R1()))
e.set_screen(-1920, 0, 3840, 1080)
check("screen area updated", e.cursor.x0 == -1920 and e.cursor.x1 == 1919 and e.sw == 3840)
print("ALL V12 OK")
