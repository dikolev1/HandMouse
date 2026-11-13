"""Appearance persistence, device-mode refresh, real widgets and camera-panel colors."""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
from app_theme import ThemeManager,THEME,PALETTES,attach_theme,help_style,device_theme

class ThemeTests(unittest.TestCase):
    def tearDown(self):
        # Collect destroyed main-thread Tk roots before another UI-thread test starts.
        import gc
        gc.collect()

    def test_saved_choices_and_invalid_mode(self):
        saved=[];manager=ThemeManager(save=saved.append)
        manager.set("dark");manager.set("dark");manager.set("light");manager.set("device")
        self.assertEqual(saved,["dark","light","device"])
        manager.configure("dark",saved.append)
        self.assertEqual(manager.effective(),"dark")
        self.assertEqual(saved,["dark","light","device"])
        manager.configure("invalid")
        self.assertEqual(manager.mode,"device")
        with self.assertRaises(ValueError): manager.set("invalid")

    def test_device_changes_refresh_without_saving_again(self):
        saved=[]
        with patch("app_theme.time.monotonic",side_effect=[1,1.1,3]):
            with patch("app_theme.device_theme",side_effect=["light","dark"]) as detect:
                manager=ThemeManager(save=saved.append)
                self.assertEqual(manager.effective(),"light")
                self.assertEqual(manager.effective(),"light")
                self.assertEqual(manager.effective(),"dark")
                self.assertEqual(detect.call_count,2)
        self.assertEqual(saved,[])
        self.assertIn(device_theme(),("light","dark"))

    def test_help_and_bgr_use_explicit_choice(self):
        before=THEME.mode
        try:
            THEME.configure("dark")
            self.assertIn("color-scheme:dark",help_style())
            self.assertEqual(THEME.bgr("bg"),(34,27,23))
            THEME.configure("light")
            self.assertIn(PALETTES["light"]["bg"],help_style())
            THEME.configure("device")
            self.assertEqual(help_style(),"")
        finally: THEME.configure(before)

    def test_theme_persists_without_overwriting_other_settings(self):
        import hand_mouse as hm
        before=THEME.mode
        try:
            with tempfile.TemporaryDirectory() as folder,patch.object(hm,"STATE_PATH",os.path.join(folder,"state.json")):
                THEME.configure("device",lambda mode:hm.save_state(theme=mode))
                THEME.set("dark")
                hm.save_state(cursor_sensitivity=.7)
                data=hm.load_state()
                self.assertEqual(data["theme"],"dark")
                self.assertEqual(data["cursor_sensitivity"],.7)
                manager=ThemeManager(data["theme"])
                self.assertEqual(manager.effective(),"dark")
        finally: THEME.configure(before)

    def test_sensitivity_theme_dropdown_changes_and_saves(self):
        import tkinter as tk
        from tkinter import ttk
        import hand_mouse as hm
        before=THEME.mode
        saved=[];errors=[]
        THEME.configure("light",saved.append)
        real_tk=tk.Tk
        window=hm.SensitivityWindow(lambda:1,lambda value:None,lambda value:None)
        def make_root():
            root=real_tk()
            root.report_callback_exception=lambda *exc:errors.append(str(exc))
            def walk(widget):
                out=[]
                for child in widget.winfo_children(): out+=[child]+walk(child)
                return out
            def choose():
                try:
                    combo=next(w for w in walk(root) if isinstance(w,ttk.Combobox))
                    self.assertEqual(tuple(combo.cget("values")),("Light","Dark","Device"))
                    combo.set("Dark");combo.event_generate("<<ComboboxSelected>>")
                    root.after(650,verify)
                except Exception as exc: errors.append(repr(exc));window.stop_evt.set()
            def verify():
                try:
                    self.assertEqual(THEME.mode,"dark")
                    self.assertEqual(root.cget("background"),PALETTES["dark"]["bg"])
                    self.assertEqual(saved,["dark"])
                except Exception as exc: errors.append(repr(exc))
                finally: window.stop_evt.set()
            root.after(250,choose)
            return root
        try:
            with patch("tkinter.Tk",new=make_root):
                window.show();window.thread.join(timeout=8)
                self.assertFalse(window.thread.is_alive())
            self.assertEqual(errors,[])
        finally:
            window.stop();THEME.configure(before)

    def test_tray_has_one_settings_entry_and_separate_camera(self):
        import hand_mouse as hm
        import pystray
        calls=[]
        class Icon:
            def __init__(self,name,image,title,menu): self.menu=menu
            def run(self): pass
            def update_menu(self): pass
        with patch.object(pystray,"Icon",Icon),patch.object(hm.TrayIcon,"_make_images",return_value={"on":None,"sleep":None,"paused":None}):
            tray=hm.TrayIcon(lambda:False,lambda:None,lambda:None,
                            on_settings=lambda:calls.append("settings"),on_view=lambda:calls.append("camera"))
            self.assertIsNotNone(tray.icon)
            labels=[it.text for it in tray.icon.menu.items]
            self.assertIn("Settings...",labels)
            self.assertIn("Camera && log window",labels)
            for old in ("Theme","Camera","Gesture profiles...","Cursor sensitivity...","Gestures help","Check for updates"):
                self.assertNotIn(old,labels)
            next(it for it in tray.icon.menu.items if it.text=="Settings...")(tray.icon)
            next(it for it in tray.icon.menu.items if it.text=="Camera && log window")(tray.icon)
            self.assertEqual(calls,["settings","camera"])

    def test_real_tk_windows_and_readonly_fields_switch_live(self):
        import tkinter as tk
        from tkinter import ttk
        before=THEME.mode
        root=None
        try:
            THEME.configure("light")
            root=tk.Tk();root.withdraw();attach_theme(root)
            ttk.Label(root,text="Settings").pack()
            ttk.Entry(root).pack()
            combo=ttk.Combobox(root,values=["Light","Dark","Device"],state="readonly")
            combo.pack()
            tree=ttk.Treeview(root,columns=("value",),show="headings")
            tree.insert("","end",values=("Example",));tree.pack()
            child=tk.Toplevel(root);child.withdraw();attach_theme(child)
            ttk.Label(child,text="Record gesture").pack()
            classic=tk.Entry(child);classic.pack()
            self.assertEqual(classic.cget("background"),PALETTES["light"]["field"])
            self.assertEqual(root.cget("background"),PALETTES["light"]["bg"])
            root.deiconify();root.update_idletasks()
            root.tk.call("ttk::combobox::Post",str(combo))
            THEME.set("dark")
            root.after(650,root.quit);root.mainloop()
            popup=str(combo)+".popdown.f.l"
            self.assertEqual(root.tk.call(popup,"cget","-background"),PALETTES["dark"]["field"])
            root.tk.call("ttk::combobox::Unpost",str(combo))
            self.assertEqual(root.cget("background"),PALETTES["dark"]["bg"])
            self.assertEqual(child.cget("background"),PALETTES["dark"]["bg"])
            self.assertEqual(classic.cget("background"),PALETTES["dark"]["field"])
            self.assertEqual(classic.cget("foreground"),PALETTES["dark"]["fg"])
            style=ttk.Style(root)
            self.assertEqual(style.lookup("TEntry","fieldbackground"),PALETTES["dark"]["field"])
            self.assertEqual(style.lookup("TCombobox","foreground",("readonly",)),PALETTES["dark"]["fg"])
            self.assertEqual(style.lookup("Treeview","background"),PALETTES["dark"]["field"])
            child.destroy()
            THEME.set("light")
            root.after(650,root.quit);root.mainloop()
            self.assertEqual(root.cget("background"),PALETTES["light"]["bg"])
        finally:
            if root is not None: root.destroy()
            THEME.configure(before)

    def test_camera_log_panel_tracks_palette(self):
        import numpy as np
        import cv2
        import hand_mouse as hm
        class Engine:
            gesture="";status=[]
        before=THEME.mode
        try:
            for mode in ("light","dark"):
                THEME.configure(mode)
                panel=hm.draw_panel(cv2,np,540,Engine(),False)
                self.assertEqual(tuple(panel[0,0]),THEME.bgr("bg"))
                self.assertEqual(panel.shape,(540,hm.PANEL_W,3))
        finally: THEME.configure(before)

if __name__=="__main__": unittest.main()
