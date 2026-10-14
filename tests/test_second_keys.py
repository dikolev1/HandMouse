import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_HERE, _os.path.dirname(_HERE)]   # tests/ and the app folder
import io, contextlib, math, random
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
hm, N, check = V.hm, V.N, V.check
K = hm._VK_NAMES
CTRL, ALT, WIN = K["ctrl"], K["alt"], K["win"]


def with_thumb(h, pos):
    w = list(h.world); w[4] = pos; w[3] = (pos[0] - 0.012, pos[1] + 0.018, pos[2] + 0.004)
    img = list(h.img)
    for i in (3, 4):   # same projection as test_core.make
        img[i] = (img[0][0] + (w[i][0] - w[0][0]) * 3.2, img[0][1] + (w[i][1] - w[0][1]) * 3.2 * 1.33)
    return hm.Hand(h.label, img, w)


def left(pose=None, px=0.3, rnd=random, jit=0.0):
    """The LEFT hand doing a pose (None = open hand)."""
    if pose == "fist":
        return V.make(px=px, fist=True, label="Left")
    if pose == "thumbs":
        return thumbs(px)
    if pose in ("middle", "ring", "middle+ring"):
        return V.make(px=px, pinch={"middle": "m", "ring": "r", "middle+ring": "mr"}[pose], label="Left",
                      jitter=jit, rnd=rnd)
    h = V.make(px=px, label="Left", jitter=jit, rnd=rnd)
    if pose is None:
        return h
    w = h.world
    if pose == "index":
        t = w[8]; pos = (t[0] - 0.01, t[1] + 0.006, t[2] - 0.01)
    elif pose == "index+middle":
        a, b = w[8], w[12]; pos = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 0.008, -0.012)
    elif pose == "little base":
        k = w[17]; pos = (k[0] - 0.008, k[1] - 0.004, k[2] - 0.012)
    else:
        raise ValueError(pose)
    return with_thumb(h, pos)


def thumbs(px=0.3):
    """Thumbs-up (thumb straight up)."""
    h = V.make(px=0.5, py=0.5, fist=True, label="Left")
    w = list(h.world); base = w[2]; L = 0.09
    w[3] = (base[0], base[1] - L * 0.55, base[2]); w[4] = (base[0], base[1] - L, base[2])
    img = [(x * 3.2, y * 3.2 * 1.33) for x, y, z in w]
    mx = sum(img[i][0] for i in (0, 5, 9, 13, 17)) / 5; my = sum(img[i][1] for i in (0, 5, 9, 13, 17)) / 5
    return hm.Hand("Left", [(x - mx + px, y - my + 0.6) for x, y in img], w)


right = lambda pose=None: V.make(px=0.75, label="Right", pinch=pose)
both = lambda lpose=None, lpx=0.3: (lambda t: [left(lpose, lpx), right()])
only_left = lambda pose=None: (lambda t: [left(pose)])


def run(frames, fps=16):
    m = V.FakeMouse(); e = hm.Engine(m, 0, 0, 1920, 1080); t = 0.0
    for f in frames:
        hs = f(t); e.update(hs if isinstance(hs, list) else [hs], t); t += 1 / fps
    return m, e


def keys(m): return [x for x in m.events if x[0] in ("keys", "key", "osk")]
def mouse(m): return [x for x in m.events if x[0] in ("left", "right", "middle", "x1", "x2", "wheel")]
START = N(14, both())                 # both hands in view, settled
REST = N(16, both())                  # open left hand for 1 s (longer than the double-tap wait)

# ---- what the classifier sees
for pose in ("index", "middle", "ring", "middle+ring", "index+middle", "little base"):
    check(f"pose '{pose}' is read as {pose}", hm.second_contact(left(pose)) == pose, hm.second_contact(left(pose)))
check("open hand: no touch", hm.second_contact(left()) is None)
check("fist: no touch", hm.second_contact(left("fist")) is None)

# ---- single pinches
for pose, expect in (("middle", [CTRL, ord("C")]), ("ring", [CTRL, ord("V")]), ("middle+ring", [K["printscreen"]])):
    m, e = run(START + N(5, both(pose)) + REST)
    check(f"left {pose} pinch -> {hm.SECOND_KEYS[pose]} once", keys(m) == [("keys", tuple(expect))], keys(m))
    check("...no mouse buttons", mouse(m) == [], mouse(m))
m, e = run(START + N(1, both("middle")) + REST)
check("thumb brushes the middle fingertip for one frame -> nothing", keys(m) == [], keys(m))

# ---- Alt+Tab: quick tap, and held with moving the hand
m, e = run(START + N(4, both("index")) + REST)
check("index tap -> Alt+Tab", keys(m) == [("keys", (ALT, K["tab"]))], keys(m))
hold = N(10, both("index")) + [both("index", 0.3 + 0.012 * k) for k in range(1, 11)]   # then 0.12 to the right
m, e = run(START + hold + REST)
ks = keys(m)
check("index held -> Alt down, Tab, 2 x Right, Alt up",
      ks == [("key", ALT, True), ("keys", (K["tab"],)), ("keys", (K["right"],)), ("keys", (K["right"],)),
             ("key", ALT, False)], ks)
hold_l = N(10, both("index", 0.35)) + [both("index", 0.35 - 0.012 * k) for k in range(1, 6)]
m, e = run(START + hold_l + REST)
check("...moving left -> Left arrow", ("keys", (K["left"],)) in keys(m) and keys(m)[-1] == ("key", ALT, False), keys(m))
m, e = run(START + N(12, both("index")) + N(20, lambda t: [right()]))
check("left hand leaves while holding Alt+Tab -> Alt let go", keys(m)[-1] == ("key", ALT, False), keys(m))

# ---- undo / redo: single waits for a possible second tap
m, e = run(START + N(4, both("little base")) + REST)
check("little-finger base once -> Ctrl+Z", keys(m) == [("keys", (CTRL, ord("Z")))], keys(m))
m, e = run(START + N(4, both("little base")) + N(3, both()) + N(4, both("little base")) + REST)
check("little-finger base twice quickly -> only Ctrl+Y", keys(m) == [("keys", (CTRL, ord("Y")))], keys(m))
m, e = run(START + N(4, both("little base")) + N(12, both()) + N(4, both("little base")) + REST)
check("twice but slowly -> Ctrl+Z, Ctrl+Z", keys(m) == [("keys", (CTRL, ord("Z")))] * 2, keys(m))
m, e = run(START + N(4, both("little base")) + N(2, both()) + N(30, lambda t: []))
check("tap, then both hands leave -> the undo still happens", keys(m) == [("keys", (CTRL, ord("Z")))], keys(m))

# ---- voice typing / on-screen keyboard
m, e = run(START + N(4, both("index+middle")) + REST)
check("index+middle once -> Win+H", keys(m) == [("keys", (WIN, ord("H")))], keys(m))
m, e = run(START + N(4, both("index+middle")) + N(3, both()) + N(4, both("index+middle")) + REST)
check("index+middle twice -> on-screen keyboard", keys(m) == [("osk",)], keys(m))
m, e = run(START + N(2, both("middle")) + N(4, both("middle+ring")) + REST)
check("thumb slides from middle onto middle+ring -> Print Screen only", keys(m) == [("keys", (K["printscreen"],))], keys(m))

# ---- fist -> Esc
m, e = run(START + N(6, both("fist")) + REST)
check("left fist then open -> Esc", keys(m) == [("keys", (K["esc"],))], keys(m))
check("...and no scrolling", mouse(m) == [], mouse(m))
m, e = run(START + N(40, both("fist")) + REST)
check("left fist held 2.5 s (resting) -> nothing", keys(m) == [], keys(m))
m, e = run(START + N(24, lambda t: [left("fist"), V.make(px=0.75, fist=True, label="Right")]) + REST)
check("two fists (gestures off) -> no Esc", keys(m) == [] and e.gestures_off, (keys(m), e.gestures_off))
m, e = run(N(14, only_left()) + N(3, only_left("fist")) + N(3, only_left()) + N(3, only_left("fist")) + N(10, only_left()))
check("left hand alone, fist twice -> becomes the main hand, no Esc", e.main_side == "left" and keys(m) == [],
      (e.main_side, keys(m)))

# ---- thumbs-up -> play / pause
m, e = run(START + N(16, both("thumbs")) + REST)
check("left thumbs-up held 1 s -> play/pause once", keys(m) == [("keys", (K["playpause"],))], keys(m))
m, e = run(START + N(3, both("thumbs")) + REST)
check("brief thumbs-up -> nothing", keys(m) == [], keys(m))
m, e = run(START + N(16, both("thumbs")) + N(4, both("fist")) + REST)
check("thumbs-up, then fist, then open -> play/pause, no Esc", keys(m) == [("keys", (K["playpause"],))], keys(m))

# ---- the main hand is not affected, and noise does nothing
m, e = run(START + N(6, lambda t: [left(), right("m")]) + REST)
check("right hand click -> left click, no keys", keys(m) == [] and
      [x for x in mouse(m) if x[0] == "left"] == [("left", "down"), ("left", "up")], m.events)
m, e = run(N(10, lambda t: [right()]) + N(6, lambda t: [right("m")]) + N(10, lambda t: [right()]))
check("right hand alone pinching -> no keys", keys(m) == [], keys(m))
rnd = random.Random(5)
m, e = run(START + [lambda t: [left(None, jit=0.004, rnd=rnd), right()]] * 200)
check("noisy relaxed left hand for 12 s -> nothing", keys(m) == [], keys(m))
m, e = run(START + N(24, lambda t: [left("fist"), V.make(px=0.75, fist=True, label="Right")]) + REST
           + N(6, both("middle")) + REST)
check("gestures off -> left pinches do nothing", keys(m) == [], keys(m))

# ---- real-life readings (2026-10-14 test: pinches split, Alt+Tab fired twice, switcher let go early)
def bent(pose, ext):
    """The hand model reads the pinching finger, and often the relaxed ring / little finger, as bent."""
    h = left(pose); h.__dict__["ext"] = list(ext); return h
RELAXED = {"index": (1.35, 1.8, 1.4, 1.35), "middle": (1.8, 1.4, 1.35, 1.3), "ring": (1.7, 1.6, 1.3, 1.3),
           "middle+ring": (1.8, 1.35, 1.3, 1.3), "index+middle": (1.35, 1.35, 1.6, 1.5)}
for pose, ext in RELAXED.items():
    m, e = run(START + N(5, lambda t, p=pose, x=ext: [bent(p, x), right()]) + REST)
    want = e.keys.actions[pose][0]
    check(f"relaxed {pose} pinch (fingers read bent {ext}) -> one {hm.SECOND_KEYS[pose]}",
          keys(m) == [("keys", tuple(want))] or (pose == "index+middle" and keys(m) == []), keys(m))
def loose(pose, dist):
    """The thumb read a little away from the fingertip (between the touch limits and wide open)."""
    h = left(pose); w = h.world; tip = {"index": w[8], "middle": w[12], "ring": w[16]}[pose]
    t = w[4]; L = hm.palm_length(h); d = [t[i] - tip[i] for i in range(3)]; n = sum(c * c for c in d) ** 0.5
    return with_thumb(h, tuple(tip[i] + d[i] / n * dist * L for i in range(3)))
for pose in ("index", "middle"):
    print("   thumb read loose:", pose, {k: round(v, 2) for k, v in hm.tip_distances(loose(pose, 0.5)).items()})
flick = N(3, both("index")) + N(2, lambda t: [loose("index", 0.5), right()]) + N(2, both("index"))
m, e = run(START + flick + REST)
check("one short pinch with a 2-frame dropout -> one Alt+Tab", keys(m) == [("keys", (ALT, K["tab"]))], keys(m))
hold_flick = (N(5, both("index")) + N(2, lambda t: [loose("index", 0.5), right()])) * 4
m, e = run(START + hold_flick + REST)
ks = keys(m)
check("held Alt+Tab with dropouts -> switcher opened once, no extra Alt+Tab",
      ks.count(("key", ALT, True)) == 1 and ("keys", (ALT, K["tab"])) not in ks, ks)
m, e = run(START + N(4, both("middle")) + N(2, lambda t: [loose("middle", 0.5), right()]) + N(4, both("middle")) + REST)
check("Ctrl+C pinch with a dropout -> one Ctrl+C", keys(m) == [("keys", (CTRL, ord("C")))], keys(m))
m, e = run(START + N(2, both("index")) + N(8, both("fist")) + REST)
check("thumb brushes the index while closing a fist -> Esc only, no Alt+Tab", keys(m) == [("keys", (K["esc"],))], keys(m))

# ---- Esc as tested live (2026-10-14): left hand alone in view, relaxed open hand afterwards
ESC = [("keys", (K["esc"],))]
m, e = run(N(14, only_left()) + N(3, only_left("fist")) + N(20, only_left()))
check("left hand alone: quick fist, open -> Esc (after a short wait)", keys(m) == ESC and e.main_side == "right",
      (keys(m), e.main_side))
m, e = run(N(14, only_left()) + N(12, only_left("fist")) + N(2, only_left()))
check("left hand alone: slower fist (0.75 s) -> Esc at once when it opens", keys(m) == ESC, keys(m))
relaxed_open = lambda t: [bent(None, (1.7, 1.4, 1.3, 1.8))]
m, e = run(N(14, relaxed_open) + N(4, only_left("fist")) + N(20, relaxed_open))
check("left alone, opened relaxed (fingers read 1.7 1.4 1.3 1.8) -> Esc", keys(m) == ESC, keys(m))
m, e = run(START + N(4, both("fist")) + N(10, lambda t: [bent(None, (1.7, 1.4, 1.3, 1.8)), right()]))
check("both hands in view, opened relaxed -> Esc", keys(m) == ESC, keys(m))
m, e = run(N(14, only_left()) + N(3, only_left("fist")) + N(2, only_left()) + N(30, lambda t: []))
check("left alone: quick fist, then the hand leaves -> Esc still", keys(m) == ESC, keys(m))

# ---- Alt+Tab stops at the first / last window instead of wrapping around
def run_w(frames, windows, fps=16):
    m = V.FakeMouse(); m.windows = windows; e = hm.Engine(m, 0, 0, 1920, 1080); t = 0.0
    for f in frames:
        hs = f(t); e.update(hs if isinstance(hs, list) else [hs], t); t += 1 / fps
    return m, e
arrows = lambda m: ["R" if x == ("keys", (K["right"],)) else "L" for x in keys(m) if x in (("keys", (K["right"],)), ("keys", (K["left"],)))]
far_right = N(10, both("index")) + [both("index", 0.3 + 0.012 * k) for k in range(1, 31)]     # ~7 steps right
m, e = run_w(START + far_right + REST, 4)
check("4 windows, hand moves 7 steps right -> only 2 Rights (stops on the last window)", arrows(m) == ["R", "R"], arrows(m))
back = far_right + [both("index", 0.66 - 0.012 * k) for k in range(1, 8)]                    # then ~1.5 steps back
m, e = run_w(START + back + REST, 4)
check("...then a small move back left -> Left at once", arrows(m) == ["R", "R", "L"], arrows(m))
far_left = N(10, both("index", 0.5)) + [both("index", 0.5 - 0.012 * k) for k in range(1, 26)]
m, e = run_w(START + far_left + REST, 4)
check("4 windows, hand moves far left -> 1 Left (stops on the first window)", arrows(m) == ["L"], arrows(m))
m, e = run_w(START + far_right + REST, 1)
check("only 1 window -> no arrows", arrows(m) == [] and keys(m)[-1] == ("key", ALT, False), keys(m))
m, e = run_w(START + far_right + REST, None)
check("window count unknown -> arrows as before (no stop)", len(arrows(m)) >= 6, arrows(m))
hm.ALT_TAB_STOP_AT_ENDS = False
m, e = run_w(START + far_right + REST, 4)
check("ALT_TAB_STOP_AT_ENDS = False -> wraps like Windows", len(arrows(m)) >= 6, arrows(m))
hm.ALT_TAB_STOP_AT_ENDS = True

# ---- Alt+Tab held while the hand moves: the depth guess reads the thumb 0.5-0.65 away (debug pictures
# 2026-10-14) although the "OK" sign is held. The picture (2D) keeps it held.
def ok_depth_off(px=0.3, dz=0.055):
    """Thumb on the index fingertip in the picture, but read 5.5 cm away in depth."""
    h = left("index", px); w = h.world; t = w[8]
    return with_thumb(h, (t[0] - 0.003, t[1] + 0.003, t[2] - dz))
h = ok_depth_off()
print("   depth misread: 3D", round(h.side["x1"], 2), "2D", round(hm.thumb_index_2d(h), 2))
moving = N(10, both("index")) + [lambda t, k=k: [ok_depth_off(0.3 + 0.012 * k), right()] for k in range(1, 21)]
m, e = run_w(START + moving + N(10, lambda t: [ok_depth_off(0.54), right()]), 8)
ks = keys(m)
check("switcher open, hand moving with depth misread for 1.9 s -> still open, Alt still down",
      ks.count(("key", ALT, True)) == 1 and ("key", ALT, False) not in ks and arrows(m) == ["R"] * 4, (arrows(m), ks[-2:]))
m, e = run_w(START + moving + REST, 8)
check("...then the hand really opens -> let go once", keys(m).count(("key", ALT, False)) == 1, keys(m)[-2:])
m, e = run(START + N(12, lambda t: [ok_depth_off(), right()]) + REST)
check("depth misread alone (no pinch seen before) -> no Alt+Tab", keys(m) == [], keys(m))

# ---- settings
hm.SECOND_HAND_KEYS = False
m, e = run(START + N(5, both("middle")) + REST)
check("SECOND_HAND_KEYS = False -> nothing", keys(m) == [], keys(m))
hm.SECOND_HAND_KEYS = True
check("key names parse", hm.parse_keys("Ctrl+Shift+F5") == [CTRL, K["shift"], 0x74] and hm.parse_keys("") is None
      and hm.parse_keys("keyboard") == "keyboard", hm.parse_keys("Ctrl+Shift+F5"))
try:
    hm.parse_keys("ctrl+nope"); bad = False
except ValueError:
    bad = True
check("unknown key name is refused", bad)
print("ALL SECOND-HAND KEYS OK")
