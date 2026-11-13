"""General, cursor/appearance and help pages for the shared Settings notebook."""
import time
from html.parser import HTMLParser
from app_theme import THEME


def plain_help(html):
    class Reader(HTMLParser):
        def __init__(self): super().__init__();self.parts=[];self.skip=0
        def handle_starttag(self,tag,attrs):
            if tag in ("style","script"): self.skip+=1
            elif not self.skip and tag in ("h1","h2","h3","p","li","br"): self.parts.append("\n"+("• " if tag=="li" else ""))
        def handle_endtag(self,tag):
            if tag in ("style","script"): self.skip=max(self.skip-1,0)
            elif not self.skip and tag in ("h1","h2","h3","p","li"): self.parts.append("\n")
        def handle_data(self,data):
            if not self.skip: self.parts.append(data)
    reader=Reader();reader.feed(html)
    return "\n".join(line.strip() for line in "".join(reader.parts).splitlines() if line.strip())


def build_pages(root,notebook,context):
    import tkinter as tk
    from tkinter import ttk,messagebox
    pages={}
    def page(name):
        frame=ttk.Frame(notebook,padding=20)
        notebook.add(frame,text=name);pages[name]=frame
        return frame
    def report(callback,*args):
        try: callback(*args)
        except Exception as exc: messagebox.showerror("Settings",str(exc),parent=root)
    general=page("General")
    ttk.Label(general,text="General",font=("Segoe UI",14,"bold")).pack(anchor="w",pady=(0,18))
    camera_group=ttk.LabelFrame(general,text="Camera",padding=14)
    camera_group.pack(fill="x",pady=(0,16))
    camera=tk.StringVar(value=f"Camera {context['get_camera']()+1}")
    camera_box=ttk.Combobox(camera_group,textvariable=camera,values=tuple(f"Camera {i+1}" for i in range(10)),state="readonly",width=24)
    camera_box.pack(anchor="w")
    camera_box.bind("<<ComboboxSelected>>",lambda event:report(context["on_camera"],int(camera.get().split()[-1])-1))
    ttk.Label(camera_group,text="Changing camera restarts the app. Save profile edits first.\nThe Camera & log window stays available directly from the tray.",wraplength=780).pack(anchor="w",pady=(8,0))
    options=ttk.LabelFrame(general,text="Startup and diagnostics",padding=14)
    options.pack(fill="x",pady=(0,16))
    autostart=tk.BooleanVar(value=context["get_autostart"]())
    debug=tk.BooleanVar(value=context["get_debug"]())
    ttk.Checkbutton(options,text="Start with Windows",variable=autostart,command=lambda:report(context["on_autostart"],autostart.get())).pack(anchor="w",pady=4)
    ttk.Checkbutton(options,text="Debug: save pictures of recognized gestures",variable=debug,command=lambda:report(context["on_debug"],debug.get())).pack(anchor="w",pady=4)
    ttk.Label(options,text="Debug pictures stay in the app's debug folder. Turn this off when finished troubleshooting.",wraplength=780).pack(anchor="w",pady=6)
    ttk.Button(general,text="Re-learn my hand size",command=lambda:report(context["on_relearn"])).pack(anchor="w",pady=6)

    cursor=page("Cursor & appearance")
    ttk.Label(cursor,text="Cursor & appearance",font=("Segoe UI",14,"bold")).pack(anchor="w",pady=(0,18))
    appearance=ttk.LabelFrame(cursor,text="Appearance",padding=14)
    appearance.pack(fill="x",pady=(0,16))
    theme=tk.StringVar(value=THEME.mode.title())
    theme_box=ttk.Combobox(appearance,textvariable=theme,values=("Light","Dark","Device"),state="readonly",width=24)
    theme_box.pack(anchor="w")
    theme_box.bind("<<ComboboxSelected>>",lambda event:report(THEME.set,theme.get().lower()))
    ttk.Label(appearance,text="Device follows Windows app colors. Changes apply live and are remembered.").pack(anchor="w",pady=(8,0))
    sensitivity=ttk.LabelFrame(cursor,text="Cursor sensitivity",padding=14)
    sensitivity.pack(fill="x",pady=(0,16))
    value=tk.DoubleVar(value=context["get_sensitivity"]()*100)
    label=tk.StringVar(value=f"{value.get():.0f}%")
    ttk.Label(sensitivity,textvariable=label,font=("Segoe UI",12)).pack()
    pending={"job":None,"gain":None}
    def flush():
        if pending["job"] is not None:
            root.after_cancel(pending["job"]);pending["job"]=None
        if pending["gain"] is not None:
            context["save_sensitivity"](pending["gain"]);pending["gain"]=None
    def changed(raw):
        gain=min(2.5,max(.25,round(float(raw))/100))
        context["on_sensitivity"](gain)
        label.set(f"{gain*100:.0f}%")
        pending["gain"]=gain
        if pending["job"] is not None: root.after_cancel(pending["job"])
        pending["job"]=root.after(250,flush)
    ttk.Scale(sensitivity,from_=25,to=250,variable=value,command=changed,length=500).pack(fill="x",pady=10)
    ttk.Label(sensitivity,text="25%: slower cursor / more hand movement. 250%: faster cursor.").pack(anchor="w")
    def reset(): value.set(100);changed(100)
    ttk.Button(sensitivity,text="Reset to 100%",command=reset).pack(anchor="w",pady=(10,0))
    screenshot=tk.BooleanVar(value=context["get_screenshot"]())
    ttk.Checkbutton(cursor,text="Reduce sensitivity by 25% while selecting a screenshot",variable=screenshot,
                    command=lambda:report(context["on_screenshot"],screenshot.get())).pack(anchor="w",pady=6)

    help_page=page("Help & updates")
    ttk.Label(help_page,text="Hand Mouse "+context["version"],font=("Segoe UI",14,"bold")).pack(anchor="w",pady=(0,10))
    buttons=ttk.Frame(help_page);buttons.pack(fill="x",pady=(0,14))
    ttk.Button(buttons,text="Check for updates",command=lambda:report(context["check_updates"])).pack(side="left")
    ttk.Button(buttons,text="Download latest version",command=lambda:report(context["download"])).pack(side="left",padx=8)
    ttk.Label(help_page,text="Gesture guide",font=("Segoe UI",12,"bold")).pack(anchor="w",pady=(0,8))
    text_area=ttk.Frame(help_page);text_area.pack(fill="both",expand=True)
    text=tk.Text(text_area,wrap="word",padx=12,pady=12,height=15,borderwidth=0)
    scroll=ttk.Scrollbar(text_area,command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right",fill="y");text.pack(side="left",fill="both",expand=True)
    text.insert("1.0",plain_help(context["help_html"]));text.configure(state="disabled")
    next_poll=0
    def poll():
        nonlocal next_poll
        now=time.monotonic()
        if now<next_poll: return
        next_poll=now+1
        theme.set(THEME.mode.title())
        camera.set(f"Camera {context['get_camera']()+1}")
        autostart.set(context["get_autostart"]())
        debug.set(context["get_debug"]())
        screenshot.set(context["get_screenshot"]())
        if pending["gain"] is None:
            value.set(context["get_sensitivity"]()*100)
            label.set(f"{value.get():.0f}%")
    return pages,flush,poll
