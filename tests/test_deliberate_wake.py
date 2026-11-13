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
        self.feed("fists",.7)
        self.feed("open",.6)
        self.assertTrue(self.e.gestures_off)
        self.feed("fists",.7)
        self.feed("one",1)
        self.feed("fists",.7)
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
        self.feed("fists",.7)
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
        self.feed("fists",.7)
        self.feed("lost",.1)
        self.feed("fists",.7)
        self.feed("open",1.2)
        self.assertEqual(self.feedback,[])

    def test_minimum_and_maximum_hold_are_accepted(self):
        for duration in (1,3):
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

    def test_retry_after_overhold_only_needs_brief_release(self):
        self.feed("fists",4)
        self.feed("open",.35)
        self.feed("fists",2)
        self.feed("open",1.2)
        self.assertFalse(self.e.gestures_off)
        self.assertEqual(self.feedback,["ready","overheld","ready"])

    def test_retry_after_incomplete_final_open(self):
        self.feed("fists",2)
        self.feed("open",.5)
        self.feed("fists",2)
        self.feed("open",1.2)
        self.assertFalse(self.e.gestures_off)
        self.assertEqual(self.feedback,["ready","ready"])

    def test_partial_final_open_restarts_only_open_timer(self):
        self.feed("fists",2)
        self.feed("open",.5)
        self.feed("partial",.1)
        self.feed("open",.8)
        self.assertTrue(self.e.gestures_off)
        self.feed("open",.4)
        self.assertFalse(self.e.gestures_off)

    def test_multiple_pause_and_wake_cycles(self):
        for _ in range(3):
            self.e.set_gestures(False)
            self.feed("open",.2)
            self.feed("fists",2)
            self.feed("open",1.2)
            self.assertFalse(self.e.gestures_off)
        self.assertEqual(self.feedback,["ready"]*3)

    def test_fist_tracking_hysteresis_survives_looser_folded_frames(self):
        self.feed("fists",.4)
        # FIST_KEEP tolerates a rotated fist whose fingers read 1.4 after recognition.
        for _ in range(27):
            hands=[V.make(px=.3,label="Left",fist=True),V.make(px=.7,label="Right",fist=True)]
            for h in hands: h.__dict__["ext"]=[1.4]*4
            self.e.update(hands,self.t)
            if self.e.wake.feedback: self.feedback.append(self.e.wake.feedback)
            self.t+=1/30
        self.assertIn("ready",self.feedback)
        self.feed("open",1.2)
        self.assertFalse(self.e.gestures_off)

    def test_fully_visible_hand_inside_old_edge_margin_can_activate(self):
        wake=hm.GestureWake()
        for k in range(75):
            hands=[V.make(px=.3,label="Left",fist=k<36),V.make(px=.7,label="Right",fist=k<36)]
            for i,h in enumerate(hands):
                h.key=str(i)
                h.img[0]=(.01,h.img[0][1])
            result=wake.update(hands,k/30)
            if result: break
        self.assertTrue(result)

    def test_completion_times_out_and_tray_still_works(self):
        self.feed("open",.6)
        self.feed("fists",8)
        self.feed("open",1.2)
        self.assertTrue(self.e.gestures_off)
        self.e.set_gestures(True)
        self.feed("open",.1)
        self.assertFalse(self.e.gestures_off)

if __name__=="__main__": unittest.main()
