"""Photo-shaped L poses survive scale/rotation without loosening other gestures."""
import contextlib
import io
import math
import os
import sys
import unittest
sys.path[:0] = [os.path.dirname(__file__), os.path.dirname(os.path.dirname(__file__))]
with contextlib.redirect_stdout(io.StringIO()):
    from test_l_pose_settings import hm, l_hand

# Approximate image landmarks read from the user's 2026-11-06 screenshot.
POINTS = [(144,314),(184,284),(222,263),(269,248),(310,234),
          (215,222),(232,181),(245,146),(254,119),
          (188,218),(195,199),(185,245),(181,273),
          (164,219),(166,208),(164,252),(161,277),
          (127,222),(136,207),(141,236),(141,256)]

def photo_pose(scale=1, degrees=0, mirror=False):
    a = math.radians(degrees)
    f = []
    for x, y in POINTS:
        x, y = (x-215)/820*scale, (y-220)/820*scale
        if mirror:
            x = -x
        f.append((.5+x*math.cos(a)-y*math.sin(a), .375+x*math.sin(a)+y*math.cos(a)))
    base = l_hand()
    h = hm.Hand("Right" if mirror else "Left", [(x,y/.75) for x,y in f], base.world)
    h.aspect = .75
    h.hand_side = "right" if mirror else "left"
    return h

class RotationTests(unittest.TestCase):
    def test_photo_pose_at_sizes_angles_and_both_sides(self):
        for scale in (.45, .7, 1, 1.5):
            for angle in (-65, -35, 0, 35, 65, 120):
                for mirror in (False, True):
                    with self.subTest(scale=scale, angle=angle, mirror=mirror):
                        h = photo_pose(scale, angle, mirror)
                        self.assertTrue(hm.is_l_pose(h))
                        pose = hm.LKeyPose()
                        fired = sum(pose.update(h, k/30) for k in range(22))
                        self.assertEqual(fired, 1)

    def test_thumb_tucked_or_parallel_is_rejected(self):
        for tip in ((223,200), (252,123)):
            h = photo_pose()
            h.img[4] = (tip[0]/820 + .5-215/820,
                        (tip[1]/820 + .375-220/820)/.75)
            self.assertFalse(hm.is_l_pose(h))

if __name__ == "__main__":
    unittest.main()
