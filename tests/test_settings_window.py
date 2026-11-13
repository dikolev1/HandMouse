"""Unified settings pages and embedded recording/testing use one Tk window."""
import contextlib
import io
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path[:0]=[os.path.dirname(__file__),os.path.dirname(os.path.dirname(__file__))]
with contextlib.redirect_stdout(io.StringIO()):
    from test_custom_gestures import hand,Spy
import tkinter as tk
from tkinter import ttk
import hand_mouse as hm
from gesture_profiles import ProfileStore,ProfileMouse
from gesture_profiles_ui import ProfilesWindow
from gesture_custom import CustomRuntime
from app_theme import THEME
from app_settings import plain_help

class SettingsTest(unittest.TestCase):
    def test_help_text_has_no_css_or_html(self):
        text=plain_help('<style>body{color:red}</style><h1>Guide</h1><p>Open &amp; close</p><li>One</li>')
        self.assertIn('Guide',text)
        self.assertIn('Open & close',text)
        self.assertNotIn('body{',text)
        self.assertNotIn('<',text)

    def test_live_controls_and_embedded_recorder(self):
        before=THEME.mode
        THEME.configure("light")
        with tempfile.TemporaryDirectory() as folder:
            store=ProfileStore(os.path.join(folder,"profiles.json"),hm.parse_keys)
            store.save("QA",{})
            spy=Spy();runtime=CustomRuntime(ProfileMouse(spy,hm.parse_keys),lambda:None)
            values=dict(gain=1,camera=0,auto=False,debug=False,screenshot=True)
            calls=[];saved=[];applied=[];errors=[]
            def set_value(key,value): values[key]=value;calls.append((key,value))
            context={"get_camera":lambda:values["camera"],"on_camera":lambda v:set_value("camera",v),
                     "get_sensitivity":lambda:values["gain"],"on_sensitivity":lambda v:set_value("gain",v),
                     "save_sensitivity":saved.append,"get_screenshot":lambda:values["screenshot"],
                     "on_screenshot":lambda v:set_value("screenshot",v),"get_autostart":lambda:values["auto"],
                     "on_autostart":lambda v:set_value("auto",v),"get_debug":lambda:values["debug"],
                     "on_debug":lambda v:set_value("debug",v),"on_relearn":lambda:calls.append("relearn"),
                     "check_updates":lambda:calls.append("updates"),"download":lambda:calls.append("download"),
                     "version":"test","help_html":"<h1>Guide</h1><p>Gesture help</p>"}
            window=ProfilesWindow(store,applied.append,runtime,context)
            real_tk=tk.Tk
            def make_root():
                root=real_tk()
                root.report_callback_exception=lambda *exc:errors.append(str(exc))
                def walk(widget):
                    out=[]
                    for child in widget.winfo_children(): out+=[child]+walk(child)
                    return out
                def buttons(widget): return {w.cget("text"):w for w in walk(widget) if isinstance(w,ttk.Button)}
                def failed(exc): errors.append(repr(exc));window.stop_evt.set()
                def begin():
                    try:
                        self.assertEqual(root.title(),"Hand Mouse - Settings")
                        nb=next(w for w in walk(root) if isinstance(w,ttk.Notebook))
                        names={nb.tab(t,"text"):root.nametowidget(t) for t in nb.tabs()}
                        self.assertEqual(set(names),{"General","Cursor & appearance","Gesture profiles","Help & updates"})
                        camera=next(w for w in walk(names["General"]) if isinstance(w,ttk.Combobox))
                        camera.set("Camera 3");camera.event_generate("<<ComboboxSelected>>")
                        checks={w.cget("text"):w for w in walk(names["General"]) if isinstance(w,ttk.Checkbutton)}
                        checks["Start with Windows"].invoke()
                        buttons(root)["Re-learn my hand size"].invoke()
                        buttons(root)["Check for updates"].invoke()
                        self.assertEqual(values["camera"],2);self.assertTrue(values["auto"])
                        cursor=names["Cursor & appearance"]
                        theme=next(w for w in walk(cursor) if isinstance(w,ttk.Combobox))
                        theme.set("Dark");theme.event_generate("<<ComboboxSelected>>")
                        self.assertEqual(THEME.mode,"dark")
                        slider=next(w for w in walk(cursor) if isinstance(w,ttk.Scale))
                        slider.set(83)
                        self.assertAlmostEqual(values["gain"],.83)
                        nb.select(names["Gesture profiles"])
                        root.update_idletasks()
                        for label in ("Save & apply","Close settings"):
                            button=buttons(root)[label]
                            self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),root.winfo_rooty()+root.winfo_height())
                        profile=next(w for w in walk(names["Gesture profiles"]) if isinstance(w,ttk.Combobox))
                        profile.set("QA");profile.event_generate("<<ComboboxSelected>>")
                        buttons(root)["Record custom..."].invoke()
                        self.assertFalse(any(isinstance(w,tk.Toplevel) for w in walk(root)))
                        self.assertEqual(nb.tab(nb.select(),"text"),"Record gesture")
                        root.update_idletasks()
                        button=buttons(root)["Save recorded gesture"]
                        self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),root.winfo_rooty()+root.winfo_height())
                        buttons(root)["Record next pose"].invoke()
                        for k in range(55): runtime.feed([hand()],k/10)
                        root.after(250,lambda:finish(nb,names))
                    except Exception as exc: failed(exc)
                def finish(nb,names):
                    try:
                        self.assertIn(.83,saved)
                        buttons(root)["Test recognition (no input)"].invoke()
                        for k in range(30): runtime.feed([hand()],10+k/30)
                        self.assertEqual(runtime.poll()[2],1)
                        buttons(root)["Save recorded gesture"].invoke()
                        self.assertEqual(nb.tab(nb.select(),"text"),"Gesture profiles")
                        self.assertEqual(len(nb.tabs()),4)
                        self.assertTrue(all(nb.tab(t,"state")=="normal" for t in nb.tabs()))
                        buttons(root)["Save & apply"].invoke()
                        self.assertEqual(len(store.snapshot()["profiles"]["QA"]["__custom__"]),1)
                        tree=next(w for w in walk(names["Gesture profiles"]) if isinstance(w,ttk.Treeview))
                        d=store.snapshot()["profiles"]["QA"]["__custom__"][0]
                        tree.selection_set("custom:"+d["id"])
                        buttons(root)["Test recorded"].invoke()
                        self.assertEqual(nb.tab(nb.select(),"text"),"Test gesture")
                        self.assertFalse(any(isinstance(w,tk.Toplevel) for w in walk(root)))
                        buttons(root)["Close test"].invoke()
                        self.assertEqual(len(nb.tabs()),4)
                        self.assertEqual(spy.events,[])
                        root.after(250,window.stop_evt.set)
                    except Exception as exc: failed(exc)
                root.after(400,begin)
                return root
            try:
                with patch("tkinter.Tk",new=make_root),patch("tkinter.messagebox.askyesno",new=lambda *a,**k:True),patch("tkinter.messagebox.showerror",new=lambda *a,**k:errors.append(str(a))):
                    window.show();window.thread.join(timeout=12)
                    self.assertFalse(window.thread.is_alive())
                self.assertEqual(errors,[])
            finally: window.stop();THEME.configure(before)

if __name__=="__main__": unittest.main()
