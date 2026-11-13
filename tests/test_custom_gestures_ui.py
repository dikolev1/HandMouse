"""Real Tk record -> dry test -> save/apply -> test/remove workflow with synthetic camera input."""
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
from gesture_custom import CustomRuntime
from gesture_profiles import ProfileStore,ProfileMouse,GESTURES
from gesture_profiles_ui import ProfilesWindow

class RecorderUI(unittest.TestCase):
    def test_record_test_save_apply_remove_without_input(self):
        with tempfile.TemporaryDirectory() as folder:
            store=ProfileStore(os.path.join(folder,"profiles.json"),hm.parse_keys)
            store.save("QA",{})
            applied=[];errors=[];pauses=[]
            spy=Spy();runtime=CustomRuntime(ProfileMouse(spy,hm.parse_keys),lambda:pauses.append(True))
            editor=ProfilesWindow(store,applied.append,runtime)
            real_tk=tk.Tk
            def make_root():
                root=real_tk()
                root.report_callback_exception=lambda *exc:errors.append(str(exc))
                def walk(widget):
                    out=[]
                    for child in widget.winfo_children(): out+=[child]+walk(child)
                    return out
                def buttons(widget): return {w.cget("text"):w for w in walk(widget) if isinstance(w,ttk.Button)}
                def fail(exc): errors.append(repr(exc));editor.stop_evt.set()
                def begin():
                    try:
                        combo=next(w for w in walk(root) if isinstance(w,ttk.Combobox))
                        combo.set("QA");combo.event_generate("<<ComboboxSelected>>")
                        buttons(root)["Record custom..."].invoke()
                        dialog=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
                        entry=next(w for w in walk(dialog) if isinstance(w,ttk.Entry) and not isinstance(w,ttk.Combobox))
                        entry.delete(0,"end");entry.insert(0,"V signal")
                        buttons(dialog)["Record next pose"].invoke()
                        for k in range(55): runtime.feed([hand()],k/10)
                        self.assertIn("step",runtime.poll()[1])
                        root.after(250,lambda:recognize(dialog))
                    except Exception as exc: fail(exc)
                def recognize(dialog):
                    try:
                        buttons(dialog)["Test recognition (no input)"].invoke()
                        for k in range(30): runtime.feed([hand()],10+k/30)
                        self.assertEqual(runtime.poll()[2],1)
                        buttons(dialog)["Save recorded gesture"].invoke()
                        widgets=walk(root)
                        tree=next(w for w in widgets if isinstance(w,ttk.Treeview))
                        self.assertEqual(len(tree.get_children()),len(GESTURES)+1)
                        buttons(root)["Save & apply"].invoke()
                        saved=store.snapshot()["profiles"]["QA"]["__custom__"]
                        self.assertEqual(saved[0]["name"],"V signal")
                        self.assertEqual(store.snapshot()["active"],"QA")
                        self.assertEqual(applied[-1]["active"],"QA")
                        reloaded=ProfileStore(store.path,hm.parse_keys).snapshot()
                        self.assertEqual(reloaded["profiles"]["QA"]["__custom__"],saved)
                        tree.selection_set("custom:"+saved[0]["id"])
                        tree.event_generate("<<TreeviewSelect>>")
                        parent_widgets=[w for w in walk(root) if not isinstance(w,tk.Toplevel)]
                        entry=next(w for w in parent_widgets if isinstance(w,ttk.Entry) and not isinstance(w,ttk.Combobox))
                        entry.delete(0,"end");entry.insert(0,"f6")
                        buttons(root)["Save binding"].invoke()
                        buttons(root)["Save & apply"].invoke()
                        self.assertEqual(store.snapshot()["profiles"]["QA"]["__custom__"][0]["action"]["value"],"f6")
                        buttons(root)["Test recorded"].invoke()
                        for k in range(30): runtime.feed([hand()],20+k/30)
                        self.assertEqual(runtime.poll()[2],1)
                        buttons(root)["Close test"].invoke()
                        buttons(root)["Remove recorded"].invoke()
                        buttons(root)["Save & apply"].invoke()
                        self.assertEqual(store.snapshot()["profiles"]["QA"]["__custom__"],[])
                        self.assertEqual(spy.events,[])
                        self.assertGreaterEqual(len(pauses),3)
                    except Exception as exc: errors.append(repr(exc))
                    finally: editor.stop_evt.set()
                root.after(400,begin)
                return root
            with patch("tkinter.Tk",new=make_root),patch("tkinter.messagebox.askyesno",new=lambda *a,**k:True),patch("tkinter.messagebox.showerror",new=lambda *a,**k:errors.append(str(a))):
                editor.show();editor.thread.join(timeout=12)
                self.assertFalse(editor.thread.is_alive())
            self.assertEqual(errors,[])

if __name__=="__main__": unittest.main()
