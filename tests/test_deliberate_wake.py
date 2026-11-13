"""Resting hands cannot wake gestures; only the complete deliberate sequence can."""
import contextlib
import io
import os
import sys
import unittest
sys.path[:0]=[os.path.dirname(__file__),os.path.dirname(os.path.dirname(__file__))]
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
hm=V.hm

class WakeTests(unittest.TestCase):
    def setUp(self):
        self.mouse=V.FakeMouse()
        self.e=hm.Engine(self.mouse,0,0,1920,1080,gestures_on=False)
        self.t=0
        self.feedback=[]

    def feed(self,pose,seconds):
        for _ in range(round(seconds*30)):
            hands=[] if pose=="lost" else [V.make(px=.3,label="Left",fist=pose=="fists"),V.make(px=.7,label="Right",fist=pose=="fists")]
            if pose=="partial":
                for h in hands: h.__dict__["ext"]=[1.4]*4
            if pose=="one": hands=hands[:1]
            if pose=="uncertain": hands[0].unsure=True
            self.e.update(hands,self.t)
            if self.e.wake.feedback: self.feedback.append(self.e.wake.feedback)
            self.t+=1/30

    def test_resting_fists_and_hiding_hands_never_enable(self):
        self.feed("fists",5)
        self.feed("lost",1)
        self.feed("fists",5)
        self.assertTrue(self.e.gestures_off)

    def test_full_sequence_only_activates_after_opening(self):
        # No initial open-palms stage is needed.
        self.feed("fists",2.5)
        self.assertTrue(self.e.gestures_off)
        self.feed("open",1.2)
        self.assertFalse(self.e.gestures_off)
        self.assertEqual(self.mouse.events,[])

    def test_normal_finger_transitions_are_allowed(self):
        self.feed("open",.6)
        self.feed("partial",.2)
        self.feed("fists",2.4)
        self.feed("partial",.2)
        self.feed("open",1.2)
        self.assertFalse(self.e.gestures_off)

    def test_short_hold_and_single_hand_do_not_enable(self):
        self.feed("open",.6)
        self.feed("fists",1.2)
        self.feed("open",.6)
        self.assertTrue(self.e.gestures_off)
        self.feed("fists",1)
        self.feed("one",1)
        self.feed("fists",1)
        self.feed("open",1.2)
        self.assertTrue(self.e.gestures_off)

    def test_tracking_loss_or_uncertainty_cancels_sequence(self):
        for interruption in ("lost","one","uncertain"):
            self.setUp()
            self.feed("open",.6)
            self.feed("fists",2.5)
            self.feed(interruption,.1)
            self.feed("open",1.2)
            self.assertTrue(self.e.gestures_off)

    def test_ready_beeps_once_and_overhold_beeps_once(self):
        self.feed("fists",1.2)
        self.assertEqual(self.feedback,[])
        self.feed("fists",.6)
        self.assertEqual(self.feedback,["ready"])
        self.feed("fists",5)
        self.assertEqual(self.feedback,["ready","overheld"])
        self.assertTrue(self.e.gestures_off)
        self.feed("open",1.2)
        self.feed("fists",2)
        self.assertEqual(self.feedback,["ready","overheld","ready"])

    def test_valid_opening_never_gives_negative_feedback(self):
        self.feed("fists",2)
        self.feed("open",1.2)
        self.assertFalse(self.e.gestures_off)
        self.assertEqual(self.feedback,["ready"])

    def test_short_or_lost_hold_does_not_give_ready_feedback(self):
        self.feed("fists",1)
        self.feed("lost",.1)
        self.feed("fists",1)
        self.feed("open",1.2)
        self.assertEqual(self.feedback,[])

    def test_minimum_and_maximum_hold_are_accepted(self):
        for duration in (1.5,3):
            self.setUp()
            self.feed("fists",duration)
            self.feed("open",1.2)
            self.assertFalse(self.e.gestures_off)

    def test_one_second_open_is_required(self):
        self.feed("fists",2)
        self.feed("open",.8)
        self.assertTrue(self.e.gestures_off)
        self.feed("open",.4)
        self.assertFalse(self.e.gestures_off)

    def test_overlong_hold_does_not_start_a_second_timer(self):
        self.feed("fists",5)
        self.feed("open",1.2)
        self.assertTrue(self.e.gestures_off)
        self.feed("fists",2)
        self.feed("open",1.2)
        self.assertFalse(self.e.gestures_off)

    def test_completion_times_out_and_tray_still_works(self):
        self.feed("open",.6)
        self.feed("fists",8)
        self.feed("open",1.2)
        self.assertTrue(self.e.gestures_off)
        self.e.set_gestures(True)
        self.feed("open",.1)
        self.assertFalse(self.e.gestures_off)

if __name__=="__main__": unittest.main()
