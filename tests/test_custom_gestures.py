"""Recorded features, pose/sequence/swipe recognition, capture, and reserved controls."""
import contextlib
import io
import os
import sys
import tempfile
import unittest
sys.path[:0]=[os.path.dirname(__file__),os.path.dirname(os.path.dirname(__file__))]
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
from gesture_custom import pose_feature,distance,make_pose,validate_custom,new_definition,PoseMachine,CustomRuntime
from gesture_profiles import ProfileMouse,ProfileStore,configure_engine
hm=V.hm

class Spy:
    def __init__(self): self.events=[]
    def key(self,k,down): self.events.append(("key",k,down))
    def keys(self,keys): self.events.append(("keys",tuple(keys)))
    def button(self,b,down): self.events.append(("button",b,down))


def hand(shape="a",px=.3,side="left"):
    folds={"a":(2,3),"b":(1,2),"c":(0,1),"open":(),"fist":(0,1,2,3)}[shape]
    h=V.make(px=px,fold=folds,fist=shape=="fist",label=side.title())
    h.key=side;h.hand_side=side;h.role="second" if side=="left" else "main"
    return h


def step(shape):
    return make_pose([pose_feature(hand(shape)) for _ in range(12)])


def definition(shapes=("a",),behavior="tap",value="space",side="left"):
    d=new_definition("Recorded",side,[step(s) for s in shapes],{"kind":"keys","value":value},behavior)
    return validate_custom([d],hm.parse_keys)[0]

class CustomTests(unittest.TestCase):
    def test_feature_is_invariant_to_scale_translation_and_rotation(self):
        h=hand();original=pose_feature(h)
        transformed=[(-y*2+.1,x*2-.2,z*2+.05) for x,y,z in h.world]
        altered=hm.Hand(h.label,h.img,transformed)
        self.assertLess(distance(original,pose_feature(altered)),.0001)
        self.assertGreater(distance(original,pose_feature(hand("b"))),.09)

    def test_recording_requires_samples_and_rejects_ambiguous_prefixes(self):
        with self.assertRaises(ValueError): make_pose([pose_feature(hand())])
        a=definition();b=definition()
        with self.assertRaisesRegex(ValueError,"overlaps"): validate_custom([a,b],hm.parse_keys)
        b["hand"]="right"
        self.assertEqual(len(validate_custom([a,b],hm.parse_keys)),2)
        invalid=definition()
        invalid["steps"]=[step("a"),step("a")]
        with self.assertRaisesRegex(ValueError,"distinct"): validate_custom([invalid],hm.parse_keys)
        invalid["steps"]=[{"kind":"swipe","direction":"left"}]
        with self.assertRaises(ValueError): validate_custom([invalid],hm.parse_keys)

    def test_single_pose_is_stable_and_latched_until_release(self):
        d=definition();machine=PoseMachine([d]);outputs=[]
        for k in range(30): outputs.append(machine.update([hand()],k/30)[0])
        self.assertIsNone(outputs[2]);self.assertIsNotNone(outputs[12])
        for k in range(30,42): machine.update([hand("open")],k/30)
        self.assertIsNone(machine.current)
        for k in range(42,60): result,busy=machine.update([hand()],k/30)
        self.assertIsNotNone(result)
        self.assertTrue(busy)

    def test_ordered_combination_needs_every_step(self):
        d=definition(("a","b","c"));machine=PoseMachine([d]);now=0
        for shape,count in (("a",15),("c",15)):
            for _ in range(count):
                result,_=machine.update([hand(shape)],now);now+=1/30
                self.assertIsNone(result)
        for shape in ("b","c"):
            for _ in range(15): result,_=machine.update([hand(shape)],now);now+=1/30
        self.assertIsNotNone(result)

    def test_swipe_requires_pose_and_stays_latched_while_pose_is_held(self):
        d=definition();d["steps"].append({"kind":"swipe","direction":"right"})
        d=validate_custom([d],hm.parse_keys)[0]
        machine=PoseMachine([d])
        for k in range(15): result,_=machine.update([hand()],k/30)
        self.assertIsNone(result)
        for k in range(15,35): result,_=machine.update([hand(px=.3+(k-14)*.012)],k/30)
        self.assertIsNotNone(result)
        for k in range(35,100): result,_=machine.update([hand(px=.55)],k/30)
        self.assertTrue(machine.complete)
        self.assertIsNotNone(result)
        for k in range(100,112): machine.update([hand("open",px=.55)],k/30)
        self.assertIsNone(machine.current)

    def test_wrong_hand_uncertainty_and_loss_do_not_fire(self):
        machine=PoseMachine([definition()])
        for k in range(15): self.assertEqual(machine.update([hand(side="right")],k/30),(None,False))
        h=hand();h.unsure=True
        self.assertEqual(machine.update([h],1),(None,False))
        machine.update([hand()],1.1)
        self.assertEqual(machine.update([],1.2),(None,False))

    def test_hold_releases_immediately_on_loss_pause_and_profile_change(self):
        spy=Spy();mouse=ProfileMouse(spy,hm.parse_keys);runtime=CustomRuntime(mouse,lambda:None)
        runtime.configure([definition(behavior="hold",value="ctrl")])
        for k in range(15): runtime.observe([hand()],k/30,True);runtime.dispatch(k/30)
        self.assertEqual(spy.events,[("key",17,True)])
        runtime.observe([],1,True)
        self.assertEqual(spy.events[-1],("key",17,False))
        for k in range(31,46): runtime.observe([hand()],k/30,True);runtime.dispatch(k/30)
        runtime.observe([hand()],2,False)
        self.assertEqual(spy.events[-1],("key",17,False))
        self.assertEqual(mouse.counts,{})
        runtime.configure([])
        self.assertEqual(runtime.machine.definitions,[])

    def test_repeat_and_tap_output_once_per_activation(self):
        for behavior in ("tap","repeat"):
            spy=Spy();mouse=ProfileMouse(spy,hm.parse_keys);runtime=CustomRuntime(mouse,lambda:None)
            runtime.configure([definition(behavior=behavior)])
            for k in range(60): runtime.observe([hand()],k/30,True);runtime.dispatch(k/30)
            self.assertEqual(len(spy.events),1) if behavior=="tap" else self.assertGreater(len(spy.events),3)

    def test_runtime_can_fire_again_after_a_clear_release(self):
        spy=Spy();runtime=CustomRuntime(ProfileMouse(spy,hm.parse_keys),lambda:None)
        runtime.configure([definition()])
        now=0
        for shape,frames in (("a",30),("open",15),("a",30)):
            for _ in range(frames):
                runtime.observe([hand(shape)],now,True);runtime.dispatch(now);now+=1/30
        self.assertEqual(spy.events,[("keys",(32,)),("keys",(32,))])

    def test_guided_capture_and_test_never_emit_input(self):
        spy=Spy();mouse=ProfileMouse(spy,hm.parse_keys);pauses=[]
        runtime=CustomRuntime(mouse,lambda:pauses.append(True))
        runtime.start_capture("left")
        for k in range(55): runtime.feed([hand()],k/10)
        message,result,count=runtime.poll()
        self.assertIn("step",result)
        self.assertGreaterEqual(len(result["step"]["templates"]),1)
        runtime.start_test(definition())
        for k in range(30): runtime.feed([hand()],k/30)
        self.assertEqual(runtime.poll()[2],1)
        for k in range(30,42): runtime.feed([hand("open")],k/30)
        for k in range(42,60): runtime.feed([hand()],k/30)
        self.assertEqual(runtime.poll()[2],2)
        self.assertEqual(spy.events,[])
        self.assertEqual(len(pauses),2)
        runtime.stop_training()

    def test_recording_reserves_open_palms_and_fists_as_first_step(self):
        for shape in ("open","fist"):
            runtime=CustomRuntime(ProfileMouse(Spy(),hm.parse_keys),lambda:None)
            runtime.start_capture("left")
            for k in range(20): runtime.feed([hand(shape)],k/10)
            self.assertIn("reserved",runtime.poll()[1]["error"])

    def test_definitions_persist_inside_their_profile_and_basic_stays_clean(self):
        with tempfile.TemporaryDirectory() as folder:
            path=os.path.join(folder,"profiles.json")
            store=ProfileStore(path,hm.parse_keys)
            d=definition(("a","b"))
            store.save("Custom",{"__custom__":[d]},activate=True)
            loaded=ProfileStore(path,hm.parse_keys)
            self.assertEqual(loaded.snapshot()["profiles"]["Custom"]["__custom__"][0],d)
            self.assertEqual(loaded.snapshot()["profiles"]["Basic"],{})
            loaded.rename("Custom","Renamed")
            self.assertEqual(loaded.snapshot()["profiles"]["Renamed"]["__custom__"][0],d)

    def test_other_hand_modifier_allows_main_hand_cursor_and_clicks(self):
        base=V.FakeMouse()
        base.key=lambda vk,down:base.events.append(("key",vk,down))
        mouse=ProfileMouse(base,hm.parse_keys);engine=hm.Engine(mouse,0,0,1920,1080)
        engine.custom_runtime=CustomRuntime(mouse,lambda:engine.set_gestures(False))
        configure_engine(engine,mouse,{"__custom__":[definition(behavior="hold",value="ctrl")]},hm.SECOND_KEYS,hm.parse_keys,hm.key_label)
        now=0
        for k in range(20):
            engine.update([hand("open"),hand("open",px=.7,side="right")],now);now+=1/30
        before=base.moves
        for k in range(45):
            right=V.make(px=.7+k*.0015,label="Right",pinch="m" if 30<=k<36 else None)
            engine.update([hand(),right],now);now+=1/30
        self.assertIn(("key",17,True),base.events)
        self.assertNotIn(("key",17,False),base.events)
        self.assertIn(("left","down"),base.events)
        self.assertIn(("left","up"),base.events)
        self.assertGreater(base.moves,before)
        for k in range(15): engine.update([hand("open"),hand("open",px=.76,side="right")],now);now+=1/30
        self.assertIn(("key",17,False),base.events)

    def test_reserved_two_fists_can_still_pause_while_custom_is_active(self):
        base=V.FakeMouse()
        base.key=lambda vk,down:base.events.append(("key",vk,down))
        mouse=ProfileMouse(base,hm.parse_keys);engine=hm.Engine(mouse,0,0,1920,1080)
        engine.custom_runtime=CustomRuntime(mouse,lambda:engine.set_gestures(False))
        configure_engine(engine,mouse,{"__custom__":[definition(behavior="hold",value="ctrl")]},hm.SECOND_KEYS,hm.parse_keys,hm.key_label)
        now=0
        for shape,frames in (("open",20),("a",20),("fist",45)):
            for _ in range(frames):
                engine.update([hand(shape),hand("fist" if shape=="fist" else "open",px=.7,side="right")],now)
                now+=1/30
        self.assertTrue(engine.gestures_off)
        self.assertIn(("key",17,True),base.events)
        self.assertIn(("key",17,False),base.events)
        self.assertEqual(mouse.counts,{})

if __name__=="__main__": unittest.main()
