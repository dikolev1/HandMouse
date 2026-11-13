"""Exercise the real Tk editor with temporary profiles, without emitting OS input."""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
import tkinter as tk
from tkinter import ttk
import hand_mouse as hm
from gesture_profiles import ProfileStore,GESTURES
from gesture_profiles_ui import ProfilesWindow

class EditorTest(unittest.TestCase):
    def test_edit_apply_duplicate_rename_delete_and_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            store=ProfileStore(os.path.join(folder,"profiles.json"),hm.parse_keys)
            store.save("QA",{"second:middle":{"kind":"keys","value":"f5","mode":"tap"}})
            applied=[]
            errors=[]
            real_tk=tk.Tk
            window=ProfilesWindow(store,applied.append)
            def make_root():
                root=real_tk()
                root.report_callback_exception=lambda *exc: errors.append(str(exc))
                def exercise():
                    try:
                        def walk(widget):
                            out=[]
                            for child in widget.winfo_children(): out+=[child]+walk(child)
                            return out
                        widgets=walk(root)
                        tree=next(w for w in widgets if isinstance(w,ttk.Treeview))
                        self.assertEqual(len(tree.get_children()),len(GESTURES))
                        combos=[w for w in widgets if isinstance(w,ttk.Combobox)]
                        profile,kind=combos
                        buttons={w.cget("text"):w for w in widgets if isinstance(w,ttk.Button)}
                        profile.set("QA");profile.event_generate("<<ComboboxSelected>>")
                        tree.selection_set("second:middle");tree.event_generate("<<TreeviewSelect>>")
                        root.update_idletasks()
                        entry=next(w for w in widgets if isinstance(w,ttk.Entry) and not isinstance(w,ttk.Combobox))
                        kind.set("Key / shortcut / media key")
                        entry.delete(0,"end");entry.insert(0,"f6")
                        buttons["Save binding"].invoke()
                        buttons["Save & apply"].invoke()
                        self.assertEqual(store.snapshot()["active"],"QA")
                        self.assertEqual(store.snapshot()["profiles"]["QA"]["second:middle"]["value"],"f6")
                        buttons["Rename"].invoke()
                        self.assertEqual(store.snapshot()["active"],"QA renamed")
                        buttons["Duplicate"].invoke()
                        self.assertEqual(store.snapshot()["profiles"]["QA copy"],store.snapshot()["profiles"]["QA renamed"])
                        buttons["Save & apply"].invoke()
                        buttons["Delete"].invoke()
                        self.assertEqual(store.snapshot()["active"],"Basic")
                        self.assertEqual(applied[-1]["active"],"Basic")
                        self.assertEqual(store.snapshot()["profiles"]["Basic"],{})
                        self.assertGreaterEqual(root.winfo_height(),root.winfo_reqheight())
                    except Exception as exc: errors.append(repr(exc))
                    finally: window.stop_evt.set()
                root.after(500,exercise)
                return root
            names=iter(["QA renamed","QA copy"])
            # Plain replacements do not retain parent=root in Mock call history across threads.
            with patch("tkinter.Tk",new=make_root),patch("tkinter.simpledialog.askstring",new=lambda *a,**k:next(names)),patch("tkinter.messagebox.askyesno",new=lambda *a,**k:True),patch("tkinter.messagebox.showerror",new=lambda *a,**k:errors.append(str(a))):
                window.show()
                window.thread.join(timeout=12)
                self.assertFalse(window.thread.is_alive())
            self.assertEqual(errors,[])
            self.assertEqual(ProfileStore(store.path,hm.parse_keys).snapshot()["active"],"Basic")

if __name__=="__main__": unittest.main()
