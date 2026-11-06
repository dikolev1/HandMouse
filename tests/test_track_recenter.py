"""One song per excursion, return to the original centre to rearm either direction."""
import contextlib
import io
import os
import sys
import unittest

sys.path[:0] = [os.path.dirname(__file__), os.path.dirname(os.path.dirname(__file__))]
with contextlib.redirect_stdout(io.StringIO()):
    import test_second_keys as T


class TrackRecenter(unittest.TestCase):
    def run_swipes(self, segments, origin=.45):
        m = T.V.FakeMouse()
        e = T.hm.SecondHandKeys(m)
        now = 0.0
        for x, frames, scale in [(origin, 10, 1.0)] + segments:
            for _ in range(frames):
                e.update(T.thumbs(x), now, k=scale)
                now += 1 / 16
        for _ in range(12):
            e.update(T.left(), now)
            now += 1 / 16
        return T.keys(m)

    @staticmethod
    def move(start, end, frames=20, scale=1.0):
        return [(start + (end - start) * i / frames, 1, scale) for i in range(1, frames + 1)]

    def test_long_swipe_only_one_song_in_either_direction(self):
        for end, action in ((.72, "nexttrack"), (.18, "prevtrack")):
            with self.subTest(direction=action):
                events = self.run_swipes(self.move(.45, end, 32) + [(end, 32, 1.0)])
                self.assertEqual(events, [("keys", (T.K[action],))])

    def test_return_then_swipe_same_direction(self):
        events = self.run_swipes(self.move(.45, .64) + self.move(.64, .45) + [(.45, 12, 1.0)]
                                 + self.move(.45, .64))
        self.assertEqual(events, [("keys", (T.K["nexttrack"],))] * 2)

    def test_return_then_swipe_opposite_direction(self):
        events = self.run_swipes(self.move(.45, .64) + self.move(.64, .45) + [(.45, 12, 1.0)]
                                 + self.move(.45, .26))
        self.assertEqual(events, [("keys", (T.K["nexttrack"],)), ("keys", (T.K["prevtrack"],))])

    def test_partial_return_does_not_rearm(self):
        events = self.run_swipes(self.move(.45, .64) + self.move(.64, .55) + [(.55, 8, 1.0)]
                                 + self.move(.55, .72))
        self.assertEqual(events, [("keys", (T.K["nexttrack"],))])

    def test_passing_through_start_does_not_reverse(self):
        events = self.run_swipes(self.move(.45, .64) + self.move(.64, .26, 16) + [(.26, 16, 1.0)])
        self.assertEqual(events, [("keys", (T.K["nexttrack"],))])

    def test_short_return_wait_does_not_rearm(self):
        events = self.run_swipes(self.move(.45, .64) + self.move(.64, .45, 8) + [(.45, 2, 1.0)]
                                 + self.move(.45, .26, 8) + [(.26, 16, 1.0)])
        self.assertEqual(events, [("keys", (T.K["nexttrack"],))])

    def test_leaving_start_resets_the_wait(self):
        events = self.run_swipes(self.move(.45, .64) + self.move(.64, .45, 8)
                                 + [(.45, 4, 1.0), (.55, 4, 1.0), (.45, 4, 1.0)]
                                 + self.move(.45, .26, 8) + [(.26, 12, 1.0)])
        self.assertEqual(events, [("keys", (T.K["nexttrack"],))])

    def test_return_near_start_is_enough(self):
        events = self.run_swipes(self.move(.45, .64) + self.move(.64, .48) + [(.48, 12, 1.0)]
                                 + self.move(.48, .26))
        self.assertEqual(events, [("keys", (T.K["nexttrack"],)), ("keys", (T.K["prevtrack"],))])

    def test_same_threshold_despite_scale_reading_drift(self):
        for end, scale, action in ((.62, 2.0, "nexttrack"), (.28, .8, "prevtrack")):
            with self.subTest(direction=action):
                events = self.run_swipes(self.move(.45, end, scale=scale) + [(end, 8, scale)])
                self.assertEqual(events, [("keys", (T.K[action],))])


if __name__ == "__main__":
    unittest.main()
