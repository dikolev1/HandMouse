"""Profile persistence, validation, remapped output and release safety."""
import contextlib
from copy import deepcopy
import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path[:0]=[os.path.dirname(__file__),os.path.dirname(os.path.dirname(__file__))]
with contextlib.redirect_stdout(io.StringIO()):
    import test_core as V
from gesture_profiles import BASIC,ProfileStore,ProfileMouse,configure_engine,validate_action,apply_profile_to_engine
hm=V.hm

def action(kind,value="",mode="tap"): return dict(kind=kind,value=value,mode=mode)

class Spy:
    def __init__(self): self.events=[]
    def button(self,name,down): self.events.append(("button",name,down))
    def key(self,vk,down): self.events.append(("key",vk,down))
    def keys(self,keys): self.events.append(("keys",tuple(keys)))
    def toggle_keyboard(self): self.events.append(("keyboard",))

class ProfileTests(unittest.TestCase):
    def test_persistence_copy_rename_delete_and_active_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            path=os.path.join(folder,"profiles.json")
            store=ProfileStore(path,hm.parse_keys)
            bindings={"second:middle":action("keys","ctrl+shift+c")}
            store.save("Work",bindings,activate=True)
            bindings["second:middle"]["value"]="x"
            loaded=ProfileStore(path,hm.parse_keys)
            self.assertEqual(loaded.snapshot()["active"],"Work")
            self.assertEqual(loaded.snapshot()["profiles"]["Work"]["second:middle"]["value"],"ctrl+shift+c")
            loaded.save("Copy",loaded.snapshot()["profiles"]["Work"])
            loaded.rename("Work","Writing")
            self.assertEqual(loaded.snapshot()["active"],"Writing")
            loaded.delete("Writing")
            self.assertEqual(loaded.snapshot()["active"],BASIC)
            self.assertIn("Copy",loaded.snapshot()["profiles"])

    def test_basic_and_reserved_gestures_are_protected(self):
        with tempfile.TemporaryDirectory() as folder:
            store=ProfileStore(os.path.join(folder,"profiles.json"),hm.parse_keys)
            for call in (lambda:store.save(BASIC,{}),lambda:store.delete(BASIC),lambda:store.rename(BASIC,"New"),
                         lambda:store.save("Bad",{"pause":action("keys","a")})):
                with self.assertRaises(ValueError): call()
            self.assertEqual(store.snapshot()["profiles"],{BASIC:{}})

    def test_validation_and_no_partial_save_on_bad_key(self):
        with tempfile.TemporaryDirectory() as folder:
            path=os.path.join(folder,"profiles.json")
            store=ProfileStore(path,hm.parse_keys)
            store.save("Good",{})
            before=store.snapshot()
            with self.assertRaises(ValueError): store.save("Bad",{"second:middle":action("keys","unknown-key")})
            self.assertEqual(store.snapshot(),before)
            with open(path,encoding="utf-8") as f: self.assertEqual(json.load(f),before)
            for source,a in [("second:index",action("keys","a","hold")),("l:right",action("keys","a","repeat")),
                             ("l:left",action("open",os.path.abspath("app.exe"),"repeat")),
                             ("second:middle",action("open","relative.exe"))]:
                with self.assertRaises(ValueError): validate_action(source,a,hm.parse_keys)

    def test_corrupt_file_falls_back_and_is_preserved_on_explicit_save(self):
        with tempfile.TemporaryDirectory() as folder:
            path=os.path.join(folder,"profiles.json")
            with open(path,"w") as f: f.write("broken")
            with self.assertLogs(hm.log,level="WARNING"):
                store=ProfileStore(path,hm.parse_keys)
            self.assertEqual(store.snapshot()["active"],BASIC)
            self.assertTrue(store.load_error)
            store.save("New",{})
            recovery=[n for n in os.listdir(folder) if ".invalid-" in n]
            self.assertEqual(len(recovery),1)
            with open(os.path.join(folder,recovery[0])) as f: self.assertEqual(f.read(),"broken")

    def test_atomic_failure_keeps_old_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            path=os.path.join(folder,"profiles.json")
            store=ProfileStore(path,hm.parse_keys)
            store.save("Old",{})
            before=store.snapshot()
            with patch("gesture_profiles.os.replace",side_effect=OSError("locked")):
                with self.assertRaises(OSError): store.save("New",{},activate=True)
            self.assertEqual(store.snapshot(),before)
            self.assertEqual(ProfileStore(path,hm.parse_keys).snapshot(),before)
            self.assertFalse(any(n.endswith(".tmp") for n in os.listdir(folder)))

    def test_default_buttons_and_remapped_hold_release(self):
        spy=Spy(); mouse=ProfileMouse(spy,hm.parse_keys)
        mouse.button("left",True);mouse.button("left",False)
        self.assertEqual(spy.events,[("button","left",True),("button","left",False)])
        spy.events.clear()
        mouse.bindings={"mouse:left":action("keys","ctrl+a","hold")}
        mouse.button("left",True)
        mouse.release_profile_inputs()
        self.assertEqual(spy.events,[("key",17,True),("key",65,True),("key",65,False),("key",17,False)])
        self.assertEqual(mouse.counts,{})

    def test_overlapping_held_outputs_are_not_released_early(self):
        spy=Spy(); mouse=ProfileMouse(spy,hm.parse_keys)
        mouse.bindings={"mouse:left":action("keys","ctrl","hold"),"mouse:right":action("keys","ctrl","hold")}
        mouse.button("left",True);mouse.button("right",True);mouse.button("left",False)
        self.assertEqual(spy.events,[("key",17,True)])
        mouse.button("right",False)
        self.assertEqual(spy.events[-1],("key",17,False))

    def test_shortcut_does_not_release_another_gestures_modifier(self):
        spy=Spy();mouse=ProfileMouse(spy,hm.parse_keys)
        mouse.bindings={"mouse:left":action("keys","ctrl","hold")}
        mouse.button("left",True)
        mouse.keys([17,67])
        self.assertEqual(spy.events,[("key",17,True),("key",67,True),("key",67,False)])
        mouse.button("left",False)
        self.assertEqual(spy.events[-1],("key",17,False))
        self.assertEqual(mouse.counts,{})

    def test_once_disabled_mouse_keyboard_and_open_actions(self):
        spy=Spy(); mouse=ProfileMouse(spy,hm.parse_keys)
        mouse.bindings={"mouse:left":action("keys","space")}
        mouse.button("left",True);mouse.button("left",True);mouse.button("left",False)
        self.assertEqual(spy.events,[("keys",(32,))])
        mouse.bindings={"mouse:left":action("disabled")}
        mouse.button("left",True);mouse.button("left",False)
        self.assertEqual(len(spy.events),1)
        mouse.perform_action(action("mouse","right"))
        self.assertEqual(spy.events[-2:],[("button","right",True),("button","right",False)])
        mouse.perform_action(action("keyboard"))
        self.assertEqual(spy.events[-1],("keyboard",))
        with patch("gesture_profiles.os.startfile",create=True) as launch:
            mouse.perform_action(action("open",os.path.abspath("app.exe")))
            launch.assert_called_once()
        with patch("gesture_profiles.os.startfile",side_effect=OSError("missing"),create=True),self.assertLogs(hm.log,level="WARNING"):
            self.assertFalse(mouse.perform_action(action("open",os.path.abspath("missing.exe"))))

    def test_disabling_single_keeps_the_double_gesture_working(self):
        with contextlib.redirect_stdout(io.StringIO()):
            import test_second_keys as T
        base=V.FakeMouse();mouse=ProfileMouse(base,hm.parse_keys)
        engine=hm.Engine(mouse,0,0,1920,1080)
        configure_engine(engine,mouse,{"second:index+middle":action("disabled")},hm.SECOND_KEYS,hm.parse_keys,hm.key_label)
        now=0
        for pose,frames in ((None,20),("index+middle",6),(None,6),("index+middle",6),(None,40)):
            for _ in range(frames):
                engine.update([T.left(pose),T.right()],now)
                now+=1/30
        self.assertEqual(T.keys(base),[("osk",)])

    def test_basic_profile_preserves_native_alt_tab_hold_and_navigation(self):
        with contextlib.redirect_stdout(io.StringIO()):
            import test_second_keys as T
        frames=T.START+T.N(10,T.both("index"))+[T.both("index",.3+.012*k) for k in range(1,11)]+T.REST
        expected,_=T.run(frames)
        base=V.FakeMouse();mouse=ProfileMouse(base,hm.parse_keys)
        engine=hm.Engine(mouse,0,0,1920,1080)
        configure_engine(engine,mouse,{},hm.SECOND_KEYS,hm.parse_keys,hm.key_label)
        for k,frame in enumerate(frames): engine.update(frame(k/16),k/16)
        self.assertEqual(T.keys(base),T.keys(expected))
        self.assertEqual(mouse.counts,{})

    def test_custom_left_l_once_and_optional_repeat(self):
        with contextlib.redirect_stdout(io.StringIO()):
            from test_l_pose_settings import T,l_hand
        counts=[]
        for mode in ("tap","repeat"):
            base=V.FakeMouse();mouse=ProfileMouse(base,hm.parse_keys)
            engine=hm.Engine(mouse,0,0,1920,1080)
            configure_engine(engine,mouse,{"l:left":action("keys","a",mode)},hm.SECOND_KEYS,hm.parse_keys,hm.key_label)
            for k in range(20): engine.update([T.left(),T.right()],k/30)
            for k in range(20,90): engine.update([l_hand(),T.right()],k/30)
            counts.append(T.keys(base).count(("keys",(65,))))
        self.assertEqual(counts[0],1)
        self.assertGreater(counts[1],3)

    def test_explicit_pause_does_not_fire_pending_profile_action(self):
        base=V.FakeMouse();mouse=ProfileMouse(base,hm.parse_keys)
        engine=hm.Engine(mouse,0,0,1920,1080)
        configure_engine(engine,mouse,{"second:middle":action("keys","f5")},hm.SECOND_KEYS,hm.parse_keys,hm.key_label)
        engine.keys.pending=("middle",0,.45)
        engine._set_gestures_off(True,1,"tray")
        self.assertEqual(base.events,[])
        self.assertIsNone(engine.keys.pending)

    def test_profile_switch_releases_holds_discards_old_tap_and_turns_off(self):
        base=V.FakeMouse()
        base.key=lambda vk,down:base.events.append(("key",vk,down))
        mouse=ProfileMouse(base,hm.parse_keys)
        engine=hm.Engine(mouse,0,0,1920,1080)
        mouse.bindings={"mouse:left":action("keys","ctrl","hold")}
        mouse.button("left",True)
        engine.keys.pending=("middle",0,.45)
        engine.gestures_request=True
        data={"active":"Demo","profiles":{"Demo":{"second:middle":action("keys","f5")}}}
        apply_profile_to_engine(engine,mouse,data,hm.SECOND_KEYS,hm.parse_keys,hm.key_label,1)
        self.assertEqual(base.events,[("key",17,True),("key",17,False)])
        self.assertIsNone(engine.keys.pending)
        self.assertIsNone(engine.gestures_request)
        self.assertTrue(engine.gestures_off)
        self.assertEqual(mouse.held,{})
        self.assertEqual(engine.profile_name,"Demo")
        self.assertEqual(engine.keys.actions["middle"][0],[116])

    def test_engine_defaults_and_second_hand_custom_actions(self):
        base=V.FakeMouse();mouse=ProfileMouse(base,hm.parse_keys)
        engine=hm.Engine(mouse,0,0,1920,1080)
        original=deepcopy(engine.keys.actions)
        configure_engine(engine,mouse,{},hm.SECOND_KEYS,hm.parse_keys,hm.key_label)
        self.assertEqual(engine.keys.actions,original)
        bindings={"second:middle":action("keys","f5"),"second:ring":action("disabled"),
                  "second:index":action("keys","alt+tab"),"second:middle+ring":action("mouse","right"),
                  "l:left":action("keys","ctrl+z")}
        configure_engine(engine,mouse,bindings,hm.SECOND_KEYS,hm.parse_keys,hm.key_label)
        self.assertNotIn("ring",engine.keys.actions)
        self.assertEqual(engine.keys.actions["index"][1],"Alt+Tab")
        engine.keys._do("middle")
        self.assertIn(("keys",(116,)),base.events)
        self.assertFalse(engine.l_profile_repeat)
        configure_engine(engine,mouse,{"l:left":action("keys","ctrl+z","repeat")},hm.SECOND_KEYS,hm.parse_keys,hm.key_label)
        self.assertTrue(engine.l_profile_repeat)

if __name__=="__main__": unittest.main()
