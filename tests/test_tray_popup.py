"""Tray palette, native-event routing, dismissal and hidden Settings-host tests."""
import gc
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
from app_theme import THEME,PALETTES
from tray_popup import TrayPopup,popup_position,themed_icon_type

class NativeHookTests(unittest.TestCase):
    def test_hook_snapshots_states_and_keeps_native_fallback(self):
        import pystray
        events=[];requests=[]
        class Base:
            def __init__(self):
                self.menu=pystray.Menu(pystray.MenuItem("Status",None,enabled=False),pystray.Menu.SEPARATOR,
                    pystray.MenuItem("Camera && log window",lambda icon,it:events.append("camera"),checked=lambda it:True),
                    pystray.MenuItem("Stop tracking",lambda icon,it:events.append("tracking"),default=True))
            def _on_notify(self,w,l): events.append((w,l))
            def _handler(self,item):
                def invoke(): item(self);events.append("refreshed")
                return invoke
        cls=themed_icon_type(Base,lambda *args:requests.append(args) or True)
        icon=cls()
        with patch("tray_popup.cursor_context",return_value=((100,200),(0,0,800,600))): icon._on_notify(0,0x205)
        self.assertEqual(events,[])
        items,point,work=requests[0]
        self.assertFalse(items[0]["enabled"])
        self.assertTrue(items[1]["separator"])
        self.assertEqual(items[2]["text"],"Camera & log window")
        self.assertTrue(items[2]["checked"])
        self.assertTrue(items[3]["default"])
        items[2]["action"]()
        self.assertEqual(events,["camera","refreshed"])
        icon._on_notify(2,0x202)
        self.assertEqual(events[-1],(2,0x202))
        cls=themed_icon_type(Base,lambda *args:False)
        with patch("tray_popup.cursor_context",return_value=((100,200),(0,0,800,600))): cls()._on_notify(1,0x205)
        self.assertEqual(events[-1],(1,0x205))

    def test_positions_include_negative_monitors(self):
        self.assertEqual(popup_position((1910,1070),(420,280),(0,0,1920,1040)),(1494,760))
        self.assertEqual(popup_position((10,10),(420,280),(0,0,1920,1040)),(0,0))
        self.assertEqual(popup_position((-1850,1000),(400,240),(-1920,0,0,1040)),(-1920,756))

class PopupUITests(unittest.TestCase):
    def tearDown(self): gc.collect()
    def test_colors_checks_disabled_actions_navigation_and_dismissal(self):
        import tkinter as tk
        before=THEME.mode;root=None;calls=[]
        items=[{"text":"Status","enabled":False},{"separator":True},
               {"text":"Settings...","action":lambda:calls.append("settings")},
               {"text":"Gestures on","checked":True,"action":lambda:calls.append("gestures")},
               {"text":"Stop tracking","default":True,"action":lambda:calls.append("tracking")}]
        try:
            root=tk.Tk();root.withdraw();popup=TrayPopup(root)
            for mode in ("light","dark","device"):
                with patch.object(THEME,"detect",return_value="dark"):
                    THEME.configure(mode);popup.show(items,(750,550),(0,0,800,600))
                    p=PALETTES["dark" if mode=="device" else mode]
                    self.assertEqual(popup.rows[0][2].cget("foreground"),p["disabled"])
                    self.assertEqual(popup.rows[2][2].cget("background"),p["bg"])
                    self.assertEqual(popup.rows[3][1].cget("text"),chr(0x2713))
                    popup.select(2)
                    self.assertEqual(popup.rows[2][2].cget("background"),p["hover"])
                    popup.activate(0);self.assertTrue(popup.visible)
                    popup.move(1);self.assertEqual(popup.active,3)
                    popup.activate(popup.active)
                    self.assertFalse(popup.visible);self.assertFalse(root.winfo_ismapped())
            self.assertEqual(calls,["gestures"]*3)
            popup.show(items,(750,550),(0,0,800,600));popup.activate()
            self.assertEqual(calls[-1],"tracking")
            popup.show(items,(750,550),(0,0,800,600))
            with patch.object(popup.window,"focus_displayof",new=lambda:None): popup._focus_check()
            self.assertFalse(popup.visible)
            popup.show(items,(750,550),(0,0,800,600))
            popup.window.event_generate("<Escape>");root.update()
            self.assertFalse(popup.visible)
        finally:
            if root is not None: root.destroy()
            THEME.configure(before)

    def test_opening_menu_keeps_settings_hidden_until_selected(self):
        import tkinter as tk
        import hand_mouse as hm
        from gesture_profiles import ProfileStore
        from gesture_profiles_ui import ProfilesWindow
        errors=[]
        with tempfile.TemporaryDirectory() as folder:
            store=ProfileStore(os.path.join(folder,"profiles.json"),hm.parse_keys)
            host=ProfilesWindow(store,lambda data:None);real_tk=tk.Tk
            def make_root():
                root=real_tk();root.report_callback_exception=lambda *exc:errors.append(str(exc))
                def check():
                    try:
                        self.assertFalse(root.winfo_ismapped())
                        popup=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel) and w.winfo_ismapped())
                        def walk(w):
                            out=[]
                            for child in w.winfo_children(): out+=[child]+walk(child)
                            return out
                        label=next(w for w in walk(popup) if isinstance(w,tk.Label) and w.cget("text")=="Settings...")
                        label.event_generate("<ButtonRelease-1>");root.after(250,lambda:finish(popup))
                    except Exception as exc: errors.append(repr(exc));host.stop_evt.set()
                def finish(popup):
                    try:
                        self.assertTrue(root.winfo_ismapped());self.assertFalse(popup.winfo_ismapped())
                    except Exception as exc: errors.append(repr(exc))
                    finally: host.stop_evt.set()
                root.after(500,check);return root
            with patch("tkinter.Tk",new=make_root):
                self.assertTrue(host.show_tray_popup([{"text":"Settings...","action":host.show}],(750,550),(0,0,800,600)))
                host.thread.join(timeout=10);self.assertFalse(host.thread.is_alive())
            self.assertEqual(errors,[])

if __name__=="__main__": unittest.main()
