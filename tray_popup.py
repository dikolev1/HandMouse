"""App-themed tray popup, hosted on the Settings Tk thread. No Windows theme changes."""
import logging
from app_theme import THEME,attach_theme

log=logging.getLogger("hand_mouse")


def cursor_context():
    import ctypes as c
    from ctypes import wintypes as w
    u=c.WinDLL("user32")
    class Info(c.Structure):
        _fields_=[("size",w.DWORD),("monitor",w.RECT),("work",w.RECT),("flags",w.DWORD)]
    u.GetCursorPos.argtypes=[c.POINTER(w.POINT)]
    u.MonitorFromPoint.argtypes=[w.POINT,w.DWORD];u.MonitorFromPoint.restype=w.HANDLE
    u.GetMonitorInfoW.argtypes=[w.HANDLE,c.POINTER(Info)]
    point=w.POINT();u.GetCursorPos(c.byref(point))
    info=Info();info.size=c.sizeof(info)
    if u.GetMonitorInfoW(u.MonitorFromPoint(point,2),c.byref(info)):
        r=info.work;bounds=(r.left,r.top,r.right,r.bottom)
    else: bounds=(0,0,1920,1080)
    return (point.x,point.y),bounds


def popup_position(point,size,work):
    x,y=point;width,height=size
    l,t,r,b=work
    return max(l,min(x-width+4,r-width)),max(t,min(y-height-4,b-height))


def themed_icon_type(base,on_popup):
    """Intercept only Windows right-click notifications; native behavior remains the fallback."""
    import pystray
    class ThemedIcon(base):
        def _on_notify(self,wparam,lparam):
            if lparam==0x0205:  # WM_RBUTTONUP, same event used by pystray's Windows backend
                try:
                    items=[]
                    for item in self.menu:
                        if item is pystray.Menu.SEPARATOR: items.append({"separator":True});continue
                        if item.submenu is not None: raise ValueError("Nested tray menu requires native fallback")
                        items.append({"text":item.text.replace("&&","&"),"enabled":bool(item.enabled),
                                      "checked":item.checked,"default":bool(item.default),
                                      "action":self._handler(item)})
                    if getattr(self,"_hwnd",None):
                        import ctypes as c
                        u=c.WinDLL("user32")
                        u.SetForegroundWindow.argtypes=[c.c_void_p]
                        u.SetForegroundWindow(self._hwnd)
                    point,work=cursor_context()
                    if on_popup(items,point,work): return
                except Exception:
                    log.exception("Themed tray popup unavailable; using native menu")
            return super()._on_notify(wparam,lparam)
    return ThemedIcon


class TrayPopup:
    def __init__(self,root):
        import tkinter as tk
        self.tk=tk
        self.window=tk.Toplevel(root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost",True)
        try: self.window.attributes("-toolwindow",True)
        except tk.TclError: pass
        attach_theme(self.window)
        self.items=[];self.rows=[];self.active=None;self.visible=False;self.previous_grab=None
        self.window.bind("<Escape>",lambda event:self.hide())
        self.window.bind("<Up>",lambda event:self.move(-1))
        self.window.bind("<Down>",lambda event:self.move(1))
        self.window.bind("<Return>",lambda event:self.activate(self.active))
        self.window.bind("<KP_Enter>",lambda event:self.activate(self.active))
        self.window.bind("<FocusOut>",lambda event:self.window.after_idle(self._focus_check))

    def _focus_check(self):
        if not self.visible: return
        focus=self.window.focus_displayof()
        if focus is None or focus.winfo_toplevel() is not self.window: self.hide()

    def show(self,items,point,work):
        from tkinter import font
        self.hide()
        for child in self.window.winfo_children(): child.destroy()
        self.items=list(items);self.rows=[];self.active=None
        p=THEME.palette()
        normal=font.Font(self.window,family="Segoe UI",size=9)
        bold=font.Font(self.window,family="Segoe UI",size=9,weight="bold")
        self.fonts=(normal,bold)
        max_width=max(120,min(560,work[2]-work[0]-16))
        width=min(max_width,max(260,max((bold.measure(item.get("text",""))+58 for item in items),default=260)))
        self.window.configure(background=p["border"])
        body=self.tk.Frame(self.window,background=p["bg"],padx=1,pady=5)
        body.pack(fill="both",expand=True,padx=1,pady=1)
        for index,item in enumerate(items):
            if item.get("separator"):
                self.tk.Frame(body,background=p["border"],height=1).pack(fill="x",padx=8,pady=4)
                self.rows.append(None);continue
            enabled=item.get("enabled",True)
            fg=p["fg"] if enabled else p["disabled"]
            row=self.tk.Frame(body,background=p["bg"])
            row.pack(fill="x")
            check=self.tk.Label(row,text=chr(0x2713) if item.get("checked") else "",font=normal,
                                width=2,background=p["bg"],foreground=p["accent"] if enabled else fg)
            check.pack(side="left",padx=(7,0))
            text=self.tk.Label(row,text=item.get("text",""),font=bold if item.get("default") else normal,
                               background=p["bg"],foreground=fg,anchor="w",justify="left",wraplength=width-58)
            text.pack(side="left",fill="x",expand=True,padx=(3,12),pady=6)
            self.rows.append((row,check,text))
            if enabled:
                for widget in (row,check,text):
                    widget.bind("<Enter>",lambda event,i=index:self.select(i))
                    widget.bind("<ButtonRelease-1>",lambda event,i=index:self.activate(i))
        self.window.geometry(f"{width}x{self.window.winfo_reqheight()}")
        self.window.update_idletasks()
        height=min(self.window.winfo_reqheight(),work[3]-work[1])
        self.window.geometry(f"{width}x{height}")
        x,y=popup_position(point,(width,height),work)
        self.window.deiconify();self.window.update_idletasks()
        try:
            import ctypes as c
            u=c.WinDLL("user32")
            u.GetParent.argtypes=[c.c_void_p];u.GetParent.restype=c.c_void_p
            u.SetWindowPos.argtypes=[c.c_void_p,c.c_void_p,c.c_int,c.c_int,c.c_int,c.c_int,c.c_uint]
            hwnd=u.GetParent(self.window.winfo_id()) or self.window.winfo_id()
            u.SetWindowPos(hwnd,c.c_void_p(-1),x,y,width,height,0x0040)
        except (AttributeError,OSError):
            self.window.geometry(f"{width}x{height}+{max(0,x)}+{max(0,y)}")
        self.previous_grab=self.window.grab_current()
        self.window.grab_set()
        self.visible=True
        self.window.lift();self.window.focus_force()

    def select(self,index):
        if index is None or not 0<=index<len(self.items) or self.items[index].get("separator") or not self.items[index].get("enabled",True): return
        self.active=index
        p=THEME.palette()
        for i,row in enumerate(self.rows):
            if row is None: continue
            bg=p["hover"] if i==index else p["bg"]
            for widget in row: widget.configure(background=bg)

    def move(self,direction):
        enabled=[i for i,item in enumerate(self.items) if not item.get("separator") and item.get("enabled",True)]
        if not enabled: return
        offset=enabled.index(self.active) if self.active in enabled else (-1 if direction>0 else 0)
        self.select(enabled[(offset+direction)%len(enabled)])

    def activate(self,index=None):
        if index is None:
            index=next((i for i,item in enumerate(self.items) if item.get("default") and item.get("enabled",True)),None)
        if index is None or not 0<=index<len(self.items): return
        item=self.items[index]
        if item.get("separator") or not item.get("enabled",True): return
        callback=item.get("action")
        self.hide()
        if callback is not None:
            try: callback()
            except Exception: log.exception("Tray menu action failed")

    def hide(self):
        self.visible=False
        try:
            if self.window.grab_current() is self.window: self.window.grab_release()
            if self.previous_grab is not None and self.previous_grab.winfo_exists(): self.previous_grab.grab_set()
            self.window.withdraw()
        except self.tk.TclError: pass
        self.previous_grab=None
        self.items=[];self.rows=[];self.active=None
