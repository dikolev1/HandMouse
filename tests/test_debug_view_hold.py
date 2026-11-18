"""Debug-only, continuous two-second camera shortcut."""
import contextlib
import io
import math
import os
import sys
import unittest
sys.path[:0]=[os.path.dirname(__file__),os.path.dirname(os.path.dirname(__file__))]
with contextlib.redirect_stdout(io.StringIO()):
    import test_second_keys as T
hm=T.hm

def pose(side="Left",angle=0,scale=1):
    h=T.with_thumb(T.V.make(fold=(2,3),label=side),(-.10,0,0))
    a=math.radians(angle); points=[]
    for x,y in h.flat:
        x,y=(x-.5)*scale,(y-.3)*scale
        if side=="Left": x=-x
        points.append((.5+x*math.cos(a)-y*math.sin(a),(.3+x*math.sin(a)+y*math.cos(a))/h.aspect))
    result=hm.Hand(side,points,h.world,aspect=h.aspect)
    result.hand_side=side.lower()
    return result

class DebugViewTests(unittest.TestCase):
    def test_pose_and_other_gestures(self):
        for side in ("Left","Right"):
            for angle in (-40,0,40):
                for scale in (.4,.6):
                    self.assertTrue(hm.is_debug_view_pose(pose(side,angle,scale)))
        for name in (None,"fist","thumbs","index","index+middle","middle+ring"):
            self.assertFalse(hm.is_debug_view_pose(T.left(name)))

    def test_two_seconds_once_and_release_rearms(self):
        d=hm.DebugViewHold(); h=pose()
        fires=[i for i in range(151) if d.update([h],i/30,True)]
        self.assertEqual(fires,[60])
        d.update([],5.1,True)
        self.assertFalse(d.update([h],5.2,True))
        self.assertEqual(sum(d.update([h],5.2+i/30,True) for i in range(1,65)),1)

    def test_debug_off_and_tracking_gap_reset(self):
        d=hm.DebugViewHold(); h=pose()
        self.assertFalse(any(d.update([h],i/30,False) for i in range(100)))
        for i in range(45): self.assertFalse(d.update([h],4+i/30,True))
        self.assertFalse(d.update([h],7,True))
        self.assertFalse(d.update([h],7.1,True))

    def test_main_hand_rejected_and_swapping_main_changes_eligible_hand(self):
        for main,side,wanted in (("right","Right",0),("right","Left",1),
                                 ("left","Left",0),("left","Right",1)):
            d=hm.DebugViewHold(); h=pose(side)
            self.assertEqual(sum(d.update([h],i/30,True,main) for i in range(70)),wanted)
        h=pose(); h.hand_side=None; d=hm.DebugViewHold()
        self.assertFalse(any(d.update([h],i/30,True) for i in range(70)))

    def test_gestures_off_does_not_block_shortcut(self):
        m=T.V.FakeMouse(); e=hm.Engine(m,0,0,1920,1080,gestures_on=False)
        d=hm.DebugViewHold(); fired=0
        for i in range(70):
            hands=[pose()]; e.update(hands,i/30); fired+=d.update(hands,i/30,True)
        self.assertEqual(fired,1)
        self.assertTrue(e.gestures_off)
        self.assertEqual(T.keys(m),[])

if __name__=="__main__": unittest.main()
