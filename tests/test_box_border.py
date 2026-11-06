"""Safety inset holds under following, scale changes and stale saved positions."""
import contextlib
import io
import os
import sys
import unittest
sys.path[:0] = [os.path.dirname(__file__), os.path.dirname(os.path.dirname(__file__))]
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
hm = V.hm

class BorderTests(unittest.TestCase):
    def inside(self, box, k):
        l, t, r, b = box.rect(k)
        self.assertGreaterEqual(l, hm.BOX_EDGE_MARGIN_X - 1e-9)
        self.assertGreaterEqual(t, hm.BOX_EDGE_MARGIN_Y - 1e-9)
        self.assertLessEqual(r, 1 - hm.BOX_EDGE_MARGIN_X + 1e-9)
        self.assertLessEqual(b, 1 - hm.BOX_EDGE_MARGIN_Y + 1e-9)
        self.assertGreater(r, l)
        self.assertGreater(b, t)

    def test_saved_edge_positions_and_large_sizes(self):
        for cx in (0, .5, 1):
            for cy in (0, .5, 1):
                box = hm.CursorBox(dict(cx=cx, cy=cy, sx=1.3, sy=1.3))
                for k in (.35, 1, 2, 4):
                    self.inside(box, k)

    def test_follow_stops_at_each_edge_and_can_return(self):
        for target in ((0, .4), (1, .4), (.5, 0), (.5, 1), (1, 1), (0, 0)):
            box = hm.CursorBox()
            for frame in range(300):
                box.update(target, 1, frame / 30, 1 / 30, True)
                self.inside(box, 1)
            before = box.rect()
            self.assertFalse(box.following)
            for frame in range(300, 360):
                box.update(target, 1, frame / 30, 1 / 30, True)
            self.assertEqual(before, box.rect())
            for frame in range(360, 600):
                box.update((.5, .4), 1, frame / 30, 1 / 30, True)
            self.inside(box, 1)
            l, t, r, b = box.rect()
            self.assertTrue(l <= .5 <= r and t <= .4 <= b)

if __name__ == "__main__":
    unittest.main()
