"""Second-hand close-window pose; no real input or windows."""
import contextlib
import io
import os
import sys
import unittest
sys.path[:0]=[os.path.dirname(__file__),os.path.dirname(os.path.dirname(__file__))]
with contextlib.redirect_stdout(io.StringIO()):
    from test_debug_view_hold import hm, T, pose

class CloseWindowTests(unittest.TestCase):
    def run_pose(self, side="Left", enabled=True, main="right", frames=180):
        m=T.V.FakeMouse();e=hm.Engine(m,0,0,1920,1080,gestures_on=enabled,main_side=main)
        for i in range(frames): e.update([pose(side)],i/30)
        return m,e

    def test_once_per_hold_with_debug_off(self):
        m,e=self.run_pose()
        expected=[("keys",tuple(hm.parse_keys("alt+f4")))]
        self.assertEqual(T.keys(m),expected)
        for i in range(180,200):e.update([T.left()],i/30)
        for i in range(200,270):e.update([pose("Left")],i/30)
        self.assertEqual(T.keys(m),expected*2)

    def test_only_second_hand_and_gestures_on(self):
        for side,enabled,main,wanted in (("Right",True,"right",0),("Left",False,"right",0),
                                         ("Left",True,"right",1),("Right",True,"left",1)):
            m,e=self.run_pose(side,enabled,main)
            self.assertEqual(len(T.keys(m)),wanted)

    def test_short_hold_and_loss_cancel(self):
        m,e=self.run_pose(frames=25)
        self.assertEqual(T.keys(m),[])
        for i in range(25,60):e.update([],i/30)
        for i in range(60,85):e.update([pose("Left")],i/30)
        self.assertEqual(T.keys(m),[])

if __name__=="__main__":unittest.main()
