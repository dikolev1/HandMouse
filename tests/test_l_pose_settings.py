"""Physical-hand L keys, disabled startup, and persisted live cursor sensitivity."""
import contextlib
import io
import os
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path[:0] = [os.path.dirname(__file__), os.path.dirname(os.path.dirname(__file__))]
with contextlib.redirect_stdout(io.StringIO()):
    import test_second_keys as T
hm = T.hm


def l_hand(side="left", px=None):
    px = (.35 if side == "left" else .75) if px is None else px
    h = T.with_thumb(T.V.make(px=px, fold=(1, 2, 3), label=side.title()), (-.10, 0, 0))
    if side == "left":
        h = hm.Hand("Left", [(2 * px - x, y) for x, y in h.img], [(-x, y, z) for x, y, z in h.world])
    return h


class LPoseTests(unittest.TestCase):
    def setUp(self):
        self.mouse = T.V.FakeMouse()
        self.engine = hm.Engine(self.mouse, 0, 0, 1920, 1080)
        self.now = 0.0

    def feed(self, factory, frames=16):
        for _ in range(frames):
            self.engine.update(factory(), self.now)
            self.now += 1 / 30

    def test_shapes_and_rejections(self):
        self.assertTrue(hm.is_l_pose(l_hand("left")))
        self.assertTrue(hm.is_l_pose(l_hand("right")))
        for name in (None, "index", "middle", "ring", "middle+ring", "index+middle", "fist", "thumbs"):
            with self.subTest(pose=name):
                self.assertFalse(hm.is_l_pose(T.left(name)))
        self.assertFalse(hm.is_l_pose(T.V.make(fold=(1, 2, 3))))  # index pointing, thumb tucked/up

    def test_short_left_l_backspace_once_without_other_gestures(self):
        self.feed(lambda: [T.left(), T.right()])
        self.mouse.events.clear()
        self.feed(lambda: [l_hand(), T.right()], 22)  # initial key, before repeat delay
        self.feed(lambda: [T.left(), T.right()])
        self.assertEqual(self.mouse.events, [("keys", (hm._VK_NAMES["backspace"],))])

    def test_right_l_enter_once_and_cursor_frozen(self):
        self.feed(lambda: [T.left(), T.right()])
        self.feed(lambda: [T.left(), l_hand("right")], 8)
        before = self.mouse.pos
        self.mouse.events.clear()
        self.feed(lambda: [T.left(), l_hand("right")], 70)
        self.assertEqual(self.mouse.events, [("keys", (hm._VK_NAMES["enter"],))])
        self.assertEqual(self.mouse.pos, before)

    def test_open_then_repeat_and_short_pose_no_key(self):
        self.feed(lambda: [T.left(), T.right()])
        self.feed(lambda: [l_hand(), T.right()], 4)
        self.feed(lambda: [T.left(), T.right()])
        self.assertEqual(T.keys(self.mouse), [])
        for _ in range(2):
            self.feed(lambda: [l_hand(), T.right()], 20)
            self.feed(lambda: [T.left(), T.right()])
        self.assertEqual(T.keys(self.mouse), [("keys", (hm._VK_NAMES["backspace"],))] * 2)

    def test_physical_hand_mapping_with_left_as_main(self):
        self.engine = hm.Engine(self.mouse, 0, 0, 1920, 1080, main_side="left")
        self.feed(lambda: [T.left(), T.right()])
        self.feed(lambda: [l_hand(), l_hand("right")], 25)
        self.assertEqual(sorted(T.keys(self.mouse)), sorted([
            ("keys", (hm._VK_NAMES["backspace"],)), ("keys", (hm._VK_NAMES["enter"],))]))

    def test_unreadable_frames_pause_held_backspace(self):
        self.feed(lambda: [T.left(), T.right()])
        self.feed(lambda: [l_hand(), T.right()], 25)
        def blurred():
            h = l_hand()
            h.unsure = True
            return [h, T.right()]
        self.feed(blurred, 25)
        self.assertEqual(T.keys(self.mouse), [("keys", (hm._VK_NAMES["backspace"],))])
        self.feed(lambda: [l_hand(), T.right()], 1)
        self.assertEqual(T.keys(self.mouse), [("keys", (hm._VK_NAMES["backspace"],))])
        self.feed(lambda: [l_hand(), T.right()], 24)
        self.assertGreater(len(T.keys(self.mouse)), 1)
        self.assertTrue(all(event == ("keys", (hm._VK_NAMES["backspace"],)) for event in T.keys(self.mouse)))

    def test_held_alt_released_before_backspace(self):
        self.feed(lambda: [T.left(), T.right()])
        self.feed(lambda: [T.left("index"), T.right()], 25)
        self.assertTrue(self.engine.keys.switcher)
        self.mouse.events.clear()
        self.feed(lambda: [l_hand(), T.right()], 25)
        self.assertLess(self.mouse.events.index(("key", T.ALT, False)),
                        self.mouse.events.index(("keys", (hm._VK_NAMES["backspace"],))))
        self.assertNotIn(("keys", (T.K["playpause"],)), self.mouse.events)

    def test_off_startup_blocks_keys_and_two_fists_still_enables(self):
        self.engine = hm.Engine(self.mouse, 0, 0, 1920, 1080, gestures_on=False)
        self.feed(lambda: [l_hand(), l_hand("right")], 25)
        self.assertTrue(self.engine.gestures_off)
        self.assertEqual(self.mouse.events, [])
        self.feed(lambda: [T.left(), T.right()], 20)
        self.feed(lambda: [T.left("fist"), T.V.make(px=.75, fist=True)], 75)
        self.assertTrue(self.engine.gestures_off)
        self.feed(lambda: [T.left(), T.right()], 20)
        self.assertFalse(self.engine.gestures_off)
        self.assertEqual(T.keys(self.mouse), [])
        self.feed(lambda: [T.left(), T.right()], 20)
        self.feed(lambda: [T.left(), l_hand("right")], 25)
        self.assertIn(("keys", (hm._VK_NAMES["enter"],)), self.mouse.events)


class SensitivityTests(unittest.TestCase):
    def test_gain_changes_movement_without_moving_at_setting_time(self):
        distances = []
        for gain in (.25, 1.0, 2.5):
            f = hm.CursorFilter((0, 0, 1920, 1080), gain)
            f(500, 500, 0)
            start = tuple(f.cur)
            for k in range(1, 201):
                f(500 + k * .3, 500, k / 30)
            distances.append(f.cur[0] - start[0])
        self.assertLess(distances[0], distances[1])
        self.assertLess(distances[1], distances[2])
        e = hm.Engine(T.V.FakeMouse(), 0, 0, 1920, 1080)
        e.cursor(500, 500, 0)
        before = tuple(e.cursor.cur)
        e.set_sensitivity(2)
        self.assertEqual(tuple(e.cursor.cur), before)
        e.recalibrate()
        self.assertEqual(e.sensitivity, 2)

    def test_saved_gain_survives_new_engine_and_other_state_writes(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(hm, "STATE_PATH", os.path.join(folder, "state.json")):
            hm.save_state(main_side="right", cursor_sensitivity=.65)
            hm.save_state(box={"cx": .5})
            state = hm.load_state()
            e = hm.Engine(T.V.FakeMouse(), 0, 0, 1920, 1080, cursor_sensitivity=state["cursor_sensitivity"])
            self.assertEqual(e.sensitivity, .65)
            self.assertEqual(state["main_side"], "right")
            threads = [threading.Thread(target=lambda i=i: hm.save_state(**{f"setting{i}": i})) for i in range(12)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            state = hm.load_state()
            self.assertEqual(state["cursor_sensitivity"], .65)
            self.assertTrue(all(state[f"setting{i}"] == i for i in range(12)))

    def test_invalid_settings_and_clamping(self):
        for value in (None, "bad", float("nan"), float("inf"), True):
            self.assertEqual(hm.normalize_sensitivity(value), 1.0)
        self.assertEqual(hm.normalize_sensitivity(-1), .25)
        self.assertEqual(hm.normalize_sensitivity(99), 2.5)


if __name__ == "__main__":
    unittest.main()
