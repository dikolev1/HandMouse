"""Light/Dark/Device appearance. No Tk objects are shared across UI threads."""
import threading
import time

PALETTES={
    "light":dict(bg="#f5f7fa",card="#ffffff",field="#ffffff",fg="#1b2430",muted="#586474",
                 accent="#2458c5",selection="#356bd6",selected_fg="#ffffff",border="#ccd2db",hover="#e5ebf5",
                 disabled="#89929f",green="#23763c",orange="#995700"),
    "dark":dict(bg="#171b22",card="#222833",field="#121820",fg="#e7ecf4",muted="#aab4c4",
                accent="#8bb5ff",selection="#356bd6",selected_fg="#ffffff",border="#3c4655",hover="#303c4e",
                disabled="#8994a5",green="#8cdf94",orange="#ffc46b"),
}


def device_theme():
    try:
        import winreg
        path=r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,path) as key:
            return "light" if winreg.QueryValueEx(key,"AppsUseLightTheme")[0] else "dark"
    except (ImportError,OSError):
        return "light"


class ThemeManager:
    def __init__(self,mode="device",save=None,detect=None):
        self.lock=threading.RLock()
        self.mode=mode if mode in ("light","dark","device") else "device"
        self.save=save
        self.detect=detect or device_theme
        self.cached="light";self.next_check=0.0

    def configure(self,mode,save=None):
        with self.lock:
            self.mode=mode if mode in ("light","dark","device") else "device"
            self.save=save;self.next_check=0

    def set(self,mode):
        if mode not in ("light","dark","device"): raise ValueError("Choose Light, Dark or Device.")
        with self.lock:
            changed=self.mode!=mode
            self.mode=mode;self.next_check=0
            save=self.save
        if changed and save is not None: save(mode)

    def effective(self):
        with self.lock:
            if self.mode!="device": return self.mode
            now=time.monotonic()
            if now>=self.next_check:
                self.next_check=now+1
                try: self.cached=self.detect()
                except OSError: self.cached="light"
                if self.cached not in PALETTES: self.cached="light"
            return self.cached

    def palette(self): return PALETTES[self.effective()]

    def bgr(self,key):
        color=self.palette()[key].lstrip("#")
        r,g,b=(int(color[i:i+2],16) for i in (0,2,4))
        return b,g,r


THEME=ThemeManager()


def attach_theme(root):
    """Apply/update styling on the window's OWN Tk thread; unregister when destroyed."""
    from tkinter import ttk,TclError
    if getattr(root,"_handmouse_theme_attached",False): return
    root._handmouse_theme_attached=True
    style=ttk.Style(root)
    token={"effective":None,"job":None}

    def titlebar(dark):
        try:
            import ctypes as c
            u=c.WinDLL("user32");dwm=c.WinDLL("dwmapi")
            u.GetParent.argtypes=[c.c_void_p];u.GetParent.restype=c.c_void_p
            dwm.DwmSetWindowAttribute.argtypes=[c.c_void_p,c.c_ulong,c.c_void_p,c.c_ulong]
            hwnd=u.GetParent(root.winfo_id()) or root.winfo_id()
            value=c.c_int(bool(dark))
            dwm.DwmSetWindowAttribute(hwnd,20,c.byref(value),c.sizeof(value))
        except (AttributeError,OSError,TclError): pass

    def apply():
        current=THEME.effective()
        if token["effective"]==current: return
        token["effective"]=current
        p=PALETTES[current]
        if style.theme_use()!="clam": style.theme_use("clam")
        style.configure(".",background=p["bg"],foreground=p["fg"],fieldbackground=p["field"],
                        bordercolor=p["border"],lightcolor=p["border"],darkcolor=p["border"],troughcolor=p["card"])
        style.configure("TNotebook",background=p["bg"],bordercolor=p["border"],tabmargins=(0,0,0,0))
        style.configure("TNotebook.Tab",background=p["bg"],foreground=p["fg"],
                        bordercolor=p["border"],lightcolor=p["border"],darkcolor=p["border"],padding=(10,5))
        style.map("TNotebook.Tab",
                  background=[("disabled",p["bg"]),("selected",p["card"]),("active",p["hover"])],
                  foreground=[("disabled",p["disabled"]),("selected",p["accent"])],
                  bordercolor=[("selected",p["accent"]),("active",p["border"])])
        style.configure("TFrame",background=p["bg"])
        style.configure("TLabel",background=p["bg"],foreground=p["fg"])
        style.configure("TLabelframe",background=p["bg"],bordercolor=p["border"])
        style.configure("TLabelframe.Label",background=p["bg"],foreground=p["fg"])
        style.configure("TButton",background=p["card"],foreground=p["fg"],padding=(9,5))
        style.map("TButton",background=[("active",p["hover"]),("pressed",p["hover"])],
                  foreground=[("disabled",p["disabled"])])
        for widget in ("TCheckbutton","TRadiobutton"):
            style.configure(widget,background=p["bg"],foreground=p["fg"],indicatorbackground=p["field"],indicatorforeground=p["accent"])
            style.map(widget,background=[("active",p["bg"])],foreground=[("disabled",p["disabled"])])
        for widget in ("TEntry","TCombobox"):
            style.configure(widget,fieldbackground=p["field"],background=p["card"],foreground=p["fg"],
                            insertcolor=p["fg"],arrowcolor=p["fg"],selectbackground=p["selection"],selectforeground=p["selected_fg"])
            style.map(widget,fieldbackground=[("readonly",p["field"]),("disabled",p["card"])],
                      foreground=[("disabled",p["disabled"]),("readonly",p["fg"])],
                      selectbackground=[("readonly",p["selection"])],selectforeground=[("readonly",p["selected_fg"])])
        style.configure("Treeview",background=p["field"],fieldbackground=p["field"],foreground=p["fg"],bordercolor=p["border"])
        style.configure("Treeview.Heading",background=p["card"],foreground=p["fg"],padding=(6,5))
        style.map("Treeview",background=[("selected",p["selection"])],foreground=[("selected",p["selected_fg"])])
        style.map("Treeview.Heading",background=[("active",p["hover"])])
        style.configure("TScale",background=p["bg"],troughcolor=p["card"])
        style.configure("TScrollbar",background=p["card"],troughcolor=p["bg"],arrowcolor=p["fg"])
        style.configure("TSeparator",background=p["border"])
        root.configure(background=p["bg"])
        # Tk's standard name dialogs use classic widgets rather than ttk.
        for key,value in (("background",p["bg"]),("foreground",p["fg"]),("insertBackground",p["fg"]),
                          ("selectBackground",p["selection"]),("selectForeground",p["selected_fg"]),
                          ("activeBackground",p["hover"]),("activeForeground",p["fg"]),
                          ("disabledForeground",p["disabled"])):
            root.option_add("*"+key,value)
        for cls in ("Entry","Text","Listbox"):
            root.option_add("*"+cls+".background",p["field"])
        def paint(widget):
            cls=widget.winfo_class()
            if cls in ("Frame","Label","Entry","Text","Listbox","Button","Checkbutton","Radiobutton","Canvas","Toplevel"):
                supported=widget.keys()
                options={"background":p["field"] if cls in ("Entry","Text","Listbox") else p["bg"],
                         "foreground":p["fg"],"insertbackground":p["fg"],"selectbackground":p["selection"],
                         "selectforeground":p["selected_fg"],"activebackground":p["hover"],"activeforeground":p["fg"]}
                widget.configure(**{key:value for key,value in options.items() if key in supported})
            if cls=="TCombobox":
                # Tk creates the dropdown in Tcl, without a Python Widget wrapper.
                popup=str(widget)+".popdown.f.l"
                if int(widget.tk.call("winfo","exists",popup)):
                    widget.tk.call(popup,"configure","-background",p["field"],"-foreground",p["fg"],
                                   "-selectbackground",p["selection"],"-selectforeground",p["selected_fg"])
            for child in tuple(widget.children.values()): paint(child)
        paint(root)
        for key,value in (("background",p["field"]),("foreground",p["fg"]),("selectBackground",p["selection"]),("selectForeground",p["selected_fg"])):
            root.option_add("*TCombobox*Listbox."+key,value)
        titlebar(current=="dark")

    def poll():
        try:
            if not root.winfo_exists(): return
            apply()
            token["job"]=root.after(500,poll)
        except TclError: pass

    def destroyed(event):
        if event.widget is root and token["job"] is not None:
            try: root.after_cancel(token["job"])
            except TclError: pass
            token["job"]=None
    root.bind("<Destroy>",destroyed,add="+")
    root.bind("<Map>",lambda event: titlebar(THEME.effective()=="dark") if event.widget is root else None,add="+")
    apply()
    token["job"]=root.after(500,poll)


def help_style():
    if THEME.mode=="device": return ""
    p=THEME.palette()
    return ("<style>:root{--bg:"+p["bg"]+";--card:"+p["card"]+";--ink:"+p["fg"]+
            ";--muted:"+p["muted"]+";--accent:"+p["accent"]+";--line:"+p["border"]+";color-scheme:"+THEME.mode+"}</style>")
