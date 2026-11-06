"""Either hand can toggle the main side, alone or with both visible, only once per gesture."""
import contextlib
import io
import os
import sys
import unittest

sys.path[:0] = [os.path.dirname(__file__), os.path.dirname(os.path.dirname(__file__))]
with contextlib.redirect_stdout(io.StringIO()):
    import test_second_keys as T


class AnyHandSwap(unittest.TestCase):
    def run_case(self, performer="left", both=True, side="right", simultaneous=False):
        m = T.V.FakeMouse()
        saved = []
        e = T.hm.Engine(m, 0, 0, 1920, 1080, main_side=side, on_main_side=saved.append)
        def hands(fist=False):
            hs = [T.V.make(px=.30, label="Left", fist=fist and (performer == "left" or simultaneous)),
                  T.V.make(px=.75, label="Right", fist=fist and (performer == "right" or simultaneous))]
            return hs if both else [hs[0 if performer == "left" else 1]]
        t = 0.0
        for fist, frames in ((False, 20), (True, 7), (False, 5), (True, 7), (False, 25)):
            for _ in range(frames):
                e.update(hands(fist), t)
                t += 1 / 30
        return m, e, saved

    def test_any_hand_alone_or_both_visible_toggles_both_ways(self):
        for side in ("left", "right"):
            for performer in ("left", "right"):
                for both in (False, True):
                    with self.subTest(main=side, hand=performer, both=both):
                        m, e, saved = self.run_case(performer, both, side)
                        other = "left" if side == "right" else "right"
                        self.assertEqual((e.main_side, saved), (other, [other]))
                        self.assertEqual(T.keys(m), [])  # no Esc from the double fist

    def test_simultaneous_double_fists_swap_once_without_gestures_off(self):
        _, e, saved = self.run_case(simultaneous=True)
        self.assertEqual(saved, ["left"])
        self.assertFalse(e.gestures_off)

    def test_staggered_completions_swap_once(self):
        saved = []
        e = T.hm.Engine(T.V.FakeMouse(), 0, 0, 1920, 1080, on_main_side=saved.append)
        for k in range(80):
            left_fist = 20 <= k < 27 or 32 <= k < 39
            right_fist = 23 <= k < 30 or 35 <= k < 42
            e.update([T.V.make(px=.3, label="Left", fist=left_fist),
                      T.V.make(px=.75, label="Right", fist=right_fist)], k / 30)
        self.assertEqual(saved, ["left"])

    def test_one_fist_per_hand_does_not_combine(self):
        saved = []
        e = T.hm.Engine(T.V.FakeMouse(), 0, 0, 1920, 1080, on_main_side=saved.append)
        for k in range(80):
            e.update([T.V.make(px=.3, label="Left", fist=20 <= k < 27),
                      T.V.make(px=.75, label="Right", fist=32 <= k < 39)], k / 30)
        self.assertEqual(saved, [])

    def test_music_pose_does_not_swap_main(self):
        m = T.V.FakeMouse()
        saved = []
        e = T.hm.Engine(m, 0, 0, 1920, 1080, on_main_side=saved.append)
        t = 0.0
        for pose, frames in ((None, 20), ("thumbs", 10), (None, 5), ("thumbs", 10), (None, 20)):
            for _ in range(frames):
                e.update([T.left(pose), T.right()], t)
                t += 1 / 30
        self.assertEqual(saved, [])
        self.assertEqual(e.main_side, "right")

    def test_held_two_fists_still_turn_gestures_off(self):
        m = T.V.FakeMouse()
        saved = []
        e = T.hm.Engine(m, 0, 0, 1920, 1080, on_main_side=saved.append)
        for k in range(70):
            fist = k >= 20
            e.update([T.V.make(px=.3, fist=fist, label="Left"),
                      T.V.make(px=.75, fist=fist, label="Right")], k / 30)
        self.assertTrue(e.gestures_off)
        self.assertEqual(saved, [])


if __name__ == "__main__":
    unittest.main()
