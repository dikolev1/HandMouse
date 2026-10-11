import os as _os, sys as _sys, tempfile as _tempfile
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import sys, io, contextlib, math
pass
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
hm, N, check = V.hm, V.N, V.check
class Vol:
    def __init__(s, level=0.4): s.level, s.sets, s.shown = level, [], 0
    def get(s): return s.level
    def set(s, v): s.level = v; s.sets.append(v)
    def show(s): s.shown += 1
def thumbs(angle_deg, px=0.6, py=0.6, label="Right"):
    """thumbs-up hand turned so the thumb points at angle (0 = up, 180 = down) in the picture"""
    h = V.make(px=0.5, py=0.5, fist=True, label=label)
    w = list(h.world); base = w[2]; L = 0.09
    w[3] = (base[0], base[1] - L * 0.55, base[2]); w[4] = (base[0], base[1] - L, base[2])
    a = math.radians(angle_deg); c, s_ = math.cos(a), math.sin(a)
    cx, cy = w[9][0], w[9][1]
    w = [(cx + (x - cx) * c - (y - cy) * s_, cy + (x - cx) * s_ + (y - cy) * c, z) for x, y, z in w]
    img = [(x * 3.2, y * 3.2 * 1.33) for x, y, z in w]
    mx = sum(img[i][0] for i in (0, 5, 9, 13, 17)) / 5; my = sum(img[i][1] for i in (0, 5, 9, 13, 17)) / 5
    img = [(x - mx + px, y - my + py) for x, y in img]
    return hm.Hand(label, img, w)
def run(frames, vol, fps=20):
    m = V.FakeMouse(); m.volume = vol; e = hm.Engine(m, 0, 0, 1920, 1080); t = 0.0
    for f in frames:
        hs = f(t); e.update(hs if isinstance(hs, list) else [hs], t); t += 1 / fps
    return m, e
print("thumb_out: thumbs-up", round(hm.thumb_out(thumbs(0)), 2), "fist", round(hm.thumb_out(V.make(fist=True)), 2), "| is_fist(thumbs-up)", hm.is_fist(thumbs(0)))
op = lambda t: V.make(px=0.6)
v = Vol(0.4); m, e = run(N(10, op) + N(40, lambda t: thumbs(0)) + N(10, op), v)
steps = [abs(b - a) for a, b in zip([0.4] + v.sets, v.sets)]
check("thumbs-up held 2 s -> volume goes to 100%", abs(v.level - 1.0) < 1e-6, round(v.level, 3))
check("...gradually, never jumping", max(steps) <= hm.VOLUME_SPEED / 20 + 1e-6, round(max(steps), 3))
check("...shows the Windows volume indicator once", v.shown == 1, v.shown)
check("...no scroll and no clicks", [x for x in m.events if x[0] in ("wheel", "left", "right", "middle")] == [], m.events[:4])
v = Vol(0.4); run(N(10, op) + N(40, lambda t: thumbs(90)) + N(10, op), v)
check("thumb sideways -> about 50%", abs(v.level - 0.5) < 0.03, round(v.level, 3))
v = Vol(0.4); run(N(10, op) + N(40, lambda t: thumbs(178)) + N(10, op), v)
check("thumb down -> 0%", v.level == 0.0, v.level)
v = Vol(0.4); run(N(10, op) + N(40, lambda t: thumbs(0)) + [lambda t, k=k: thumbs(min(k * 6, 180)) for k in range(31)] + N(30, lambda t: thumbs(180)), v)
check("turning the thumb from up to down -> 100% then down to 0%", v.level == 0.0 and max(v.sets) == 1.0, (max(v.sets), v.level))
v = Vol(0.4); run(N(10, op) + N(5, lambda t: thumbs(0)) + N(20, op), v)
check("thumbs-up for only 0.25 s -> volume untouched", v.sets == [], v.sets[:3])
v = Vol(0.4); m, e = run(N(10, op) + N(10, lambda t: V.make(px=0.6, fist=True)) + [lambda t, k=k: V.make(px=0.6, py=0.6 + 0.02 * k, fist=True) for k in range(15)] + N(5, op), v)
check("plain fist still scrolls, volume untouched", any(x[0] == "wheel" for x in m.events) and v.sets == [], (len([x for x in m.events if x[0] == 'wheel']), v.sets[:2]))
two = lambda t: [thumbs(0, px=0.3, label="Left"), thumbs(0, px=0.75)]
v = Vol(0.4); m, e = run(N(10, lambda t: [V.make(px=0.3, label="Left"), V.make(px=0.75)]) + N(40, two), v)
check("two thumbs-up don't turn gestures off", not e.gestures_off, e.gestures_off)
v = Vol(0.4); m, e = run(N(12, lambda t: [V.make(px=0.3, label="Left"), V.make(px=0.75)]) + N(40, lambda t: [thumbs(90, px=0.3, label="Left"), V.make(px=0.75)]), v)
check("second hand thumbs-up -> volume untouched (main hand only)", v.sets == [], v.sets[:2])
print("ALL VOLUME OK")
