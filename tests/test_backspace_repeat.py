"""Backspace repeats after a delay, Enter never does, release/uncertainty stop output."""
import contextlib
import io
import os
import sys
import unittest

sys.path[:0] = [os.path.dirname(__file__), os.path.dirname(os.path.dirname(__file__))]
with contextlib.redirect_stdout(io.StringIO()):
    from test_l_pose_settings import hm, T, l_hand


class BackspaceRepeat(unittest.TestCase):
    def test_left_repeats_after_initial_delay_without_catchup_bursts(self):
        pose = hm.LKeyPose()
        h = l_hand()
        h.hand_side = "left"
        times = [k / 30 for k in range(75) if pose.update(h, k / 30)]
        self.assertGreater(len(times), 3)
        self.assertGreaterEqual(times[1] - times[0], .49)
        self.assertTrue(all(b - a >= .079 for a, b in zip(times[1:], times[2:])))
        self.assertTrue(pose.update(h, 10))
        self.assertFalse(pose.update(h, 10.001))  # delayed frames never replay a backlog

    def test_right_enter_stays_one_press(self):
        pose = hm.LKeyPose()
        h = l_hand("right")
        h.hand_side = "right"
        self.assertEqual(sum(pose.update(h, k / 30) for k in range(120)), 1)

    def test_release_stops_even_inside_release_grace(self):
        pose = hm.LKeyPose()
        h = l_hand()
        h.hand_side = "left"
        for k in range(60):
            pose.update(h, k / 30)
        opened = T.left()
        opened.hand_side = "left"
        self.assertFalse(pose.update(opened, 2.0))
        self.assertFalse(pose.update(opened, 2.03))
        self.assertFalse(pose.update(opened, 2.3))
        self.assertFalse(pose.busy)

    def test_unreadable_hand_never_deletes(self):
        pose = hm.LKeyPose()
        h = l_hand()
        h.hand_side = "left"
        for k in range(45):
            pose.update(h, k / 30)
        h.unsure = True
        self.assertFalse(any(pose.update(h, 2 + k / 30) for k in range(60)))

    def test_engine_hand_lost_and_gestures_off_stop_deletion(self):
        mouse = T.V.FakeMouse()
        engine = hm.Engine(mouse, 0, 0, 1920, 1080)
        for k in range(90):
            engine.update([l_hand(), T.right()], k / 30)
        self.assertGreater(len(T.keys(mouse)), 3)
        count = len(T.keys(mouse))
        for k in range(30):
            engine.update([], 3 + k / 30)
        self.assertEqual(len(T.keys(mouse)), count)
        engine.set_gestures(False)
        for k in range(90):
            engine.update([l_hand(), T.right()], 4 + k / 30)
        self.assertEqual(len(T.keys(mouse)), count)


if __name__ == "__main__":
    unittest.main()
