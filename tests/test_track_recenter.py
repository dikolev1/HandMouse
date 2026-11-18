"""Relative music rotations with cooldown and no neutral return requirement."""
import contextlib
import io
import os
import sys
import unittest
sys.path[:0]=[os.path.dirname(__file__),os.path.dirname(os.path.dirname(__file__))]
with contextlib.redirect_stdout(io.StringIO()):
    import test_second_keys as T

class TrackRotation(unittest.TestCase):
    def run_angles(self, segments):
        m=T.V.FakeMouse(); e=T.hm.SecondHandKeys(m); now=0
        for angle,frames in [(0,16)]+segments:
            for _ in range(frames):
                e.update(T.rotated_thumb(angle),now); now+=1/60
        e.update(T.left(),now)
        return [event[1][0] for event in T.keys(m)]

    def test_stationary_after_skip_never_repeats_or_pauses(self):
        for angle,key in ((10,"nexttrack"),(-10,"prevtrack")):
            self.assertEqual(self.run_angles([(0,20),(angle,120)]),[T.K[key]])

    def test_no_return_required_for_another_rotation(self):
        self.assertEqual(self.run_angles([(0,20),(10,40),(20,40)]),[T.K["nexttrack"]]*2)

    def test_reverse_without_returning_to_original_angle(self):
        self.assertEqual(self.run_angles([(0,20),(20,40),(10,40)]),[T.K["nexttrack"],T.K["prevtrack"]])

    def test_subthreshold_rotation_only_playpauses(self):
        self.assertEqual(self.run_angles([(0,20),(7,120)]),[T.K["playpause"]])

    def test_cooldown_discards_extra_rotation(self):
        self.assertEqual(self.run_angles([(0,20),(10,5),(20,25),(30,120)]),[T.K["nexttrack"]])

if __name__=="__main__": unittest.main()
