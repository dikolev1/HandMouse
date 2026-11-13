"""Guided record/test dialog, on the profile editor's existing Tk thread."""
from copy import deepcopy


def poll_window(win,callback):
    from tkinter import TclError
    state={"job":None}
    def tick():
        try:
            if not win.winfo_exists(): return
            callback()
            if win.winfo_exists(): state["job"]=win.after(100,tick)
        except TclError: pass
    def cleanup(event):
        if event.widget is win and state["job"] is not None:
            try: win.after_cancel(state["job"])
            except TclError: pass
            state["job"]=None
    win.bind("<Destroy>",cleanup,add="+")
    state["job"]=win.after(100,tick)


def record_dialog(parent,runtime,existing,parse_keys,on_save,embedded=False,on_close=None):
    import tkinter as tk
    from tkinter import ttk,messagebox,filedialog
    from gesture_custom import new_definition,validate_custom
    from gesture_profiles_ui import TYPE_LABELS
    if embedded:
        win=ttk.Frame(parent);win.pack(fill="both",expand=True)
    else:
        win=tk.Toplevel(parent)
        from app_theme import attach_theme
        attach_theme(win)
        win.title("Hand Mouse - Record custom gesture")
        win.geometry("740x650")
        win.minsize(700,610)
    frame=ttk.Frame(win,padding=16)
    frame.pack(fill="both",expand=True)
    frame.columnconfigure(1,weight=1)
    frame.rowconfigure(4,weight=1)
    ttk.Label(frame,text="Record a pose or combination",font=("Segoe UI",13,"bold")).grid(row=0,column=0,columnspan=3,sticky="w")
    name=tk.StringVar(value="My gesture")
    side=tk.StringVar(value="left")
    mode=tk.StringVar(value="Single pose")
    kind=tk.StringVar(value="Key / shortcut / media key")
    value=tk.StringVar(value="space")
    behavior=tk.StringVar(value="Once")
    ttk.Label(frame,text="Name").grid(row=1,column=0,sticky="w",pady=8)
    ttk.Entry(frame,textvariable=name).grid(row=1,column=1,columnspan=2,sticky="ew")
    ttk.Label(frame,text="Hand").grid(row=2,column=0,sticky="w")
    ttk.Combobox(frame,textvariable=side,values=("left","right","main","second","either"),state="readonly").grid(row=2,column=1,sticky="ew")
    ttk.Label(frame,text="Type").grid(row=3,column=0,sticky="w",pady=8)
    mode_box=ttk.Combobox(frame,textvariable=mode,values=("Single pose","Pose sequence","Pose + swipe left","Pose + swipe right"),state="readonly")
    mode_box.grid(row=3,column=1,columnspan=2,sticky="ew")
    steps=[];warnings=[];seen_result=None
    listing=ttk.Treeview(frame,columns=("step",),show="headings",height=4)
    listing.heading("step",text="Recorded steps (in order)")
    listing.grid(row=4,column=0,columnspan=3,sticky="nsew")
    controls=ttk.Frame(frame)
    controls.grid(row=5,column=0,columnspan=3,sticky="ew",pady=8)
    status=tk.StringVar(value="Gestures stay off during recording/testing. Keep one chosen hand fully visible.\nChoose a distinct first pose; open palms and closed fists are reserved. Each pose records for 4 seconds.")
    ttk.Label(frame,textvariable=status,wraplength=690).grid(row=6,column=0,columnspan=3,sticky="w",pady=(0,10))
    ttk.Label(frame,text="Action").grid(row=7,column=0,sticky="w")
    kind_box=ttk.Combobox(frame,textvariable=kind,values=[k for k in TYPE_LABELS if k!="Basic action"],state="readonly")
    kind_box.grid(row=7,column=1,sticky="ew")
    def type_changed(event=None):
        if TYPE_LABELS[kind.get()] not in ("keys","mouse"): behavior.set("Once")
    kind_box.bind("<<ComboboxSelected>>",type_changed)
    ttk.Label(frame,text="Key or value").grid(row=8,column=0,sticky="w",pady=8)
    ttk.Entry(frame,textvariable=value).grid(row=8,column=1,sticky="ew")
    def browse():
        path=filedialog.askopenfilename(parent=win,title="Choose application or file")
        if path: kind.set("Open application / file");value.set(path);behavior.set("Once")
    ttk.Button(frame,text="Browse...",command=browse).grid(row=8,column=2,padx=(8,0))
    ttk.Label(frame,text="Behavior").grid(row=9,column=0,sticky="w")
    ttk.Combobox(frame,textvariable=behavior,values=("Once","Hold until release","Repeat while held"),state="readonly").grid(row=9,column=1,sticky="ew")
    ttk.Label(frame,text="Examples: space, ctrl+c, f5, nexttrack. Mouse: left / right / middle / x1 / x2.\n"
              "Sequences: record 2-5 distinct poses, then perform them in that order. For a swipe, record one pose.\n"
              "During capture keep the finger shape steady and gently vary its angle. Test mode sends no input.",
              wraplength=690).grid(row=10,column=0,columnspan=3,sticky="w",pady=10)
    footer=ttk.Frame(frame)
    footer.grid(row=11,column=0,columnspan=3,sticky="ew")
    def redraw():
        listing.delete(*listing.get_children())
        for i,step in enumerate(steps): listing.insert("","end",values=(f"{i+1}. Pose ({len(step['templates'])} angle templates)",))
    def record():
        nonlocal seen_result
        max_steps=5 if mode.get()=="Pose sequence" else 1
        if len(steps)>=max_steps:
            messagebox.showinfo("Recording","Remove the last step to re-record, or choose Pose sequence to add more steps.",parent=win);return
        seen_result=None
        runtime.start_capture(side.get(),first=not steps)
        status.set(runtime.poll()[0])
        record_button.configure(state="disabled")
    def remove():
        nonlocal seen_result
        runtime.stop_training();seen_result=None
        if steps: steps.pop()
        if warnings: warnings.pop()
        redraw();record_button.configure(state="normal")
        status.set("Step removed. Record a replacement pose.")
    def definition():
        chosen=deepcopy(steps)
        if mode.get()=="Single pose" and len(chosen)!=1: raise ValueError("Record exactly one pose for Single pose.")
        if mode.get()=="Pose sequence" and not 2<=len(chosen)<=5: raise ValueError("Record 2-5 different poses for a sequence.")
        if mode.get().startswith("Pose + swipe"):
            if len(chosen)!=1: raise ValueError("Record one pose before adding a swipe.")
            chosen.append({"kind":"swipe","direction":"left" if mode.get().endswith("left") else "right"})
        behavior_code={"Once":"tap","Hold until release":"hold","Repeat while held":"repeat"}[behavior.get()]
        d=new_definition(name.get().strip(),side.get(),chosen,{"kind":TYPE_LABELS[kind.get()],"value":value.get()},behavior_code)
        return validate_custom(list(existing)+[d],parse_keys)[-1]
    def test():
        try:
            d=definition()
            runtime.start_test(d)
            status.set("Test mode: perform the gesture now. No keys or mouse actions will be sent.")
        except Exception as exc: messagebox.showerror("Test gesture",str(exc),parent=win)
    def close():
        runtime.stop_training()
        win.destroy()
        if on_close is not None: on_close()
    def save():
        try:
            d=definition()
            overlap=next((w for w in warnings if w),"")
            if overlap and not messagebox.askyesno("Gesture overlap",overlap+" The recorded gesture will take priority while recognized. Save it anyway?",parent=win): return
            on_save(d)
            close()
        except Exception as exc: messagebox.showerror("Save gesture",str(exc),parent=win)
    record_button=ttk.Button(controls,text="Record next pose",command=record)
    record_button.pack(side="left")
    ttk.Button(controls,text="Remove last step",command=remove).pack(side="left",padx=8)
    ttk.Button(footer,text="Test recognition (no input)",command=test).pack(side="left")
    ttk.Button(footer,text="Save recorded gesture",command=save).pack(side="left",padx=8)
    ttk.Button(footer,text="Cancel",command=close).pack(side="right")
    if not embedded: win.protocol("WM_DELETE_WINDOW",close)
    def poll():
        nonlocal seen_result
        if not win.winfo_exists(): return
        message,result,count=runtime.poll()
        if message: status.set(message)
        if result is not None and result!=seen_result:
            seen_result=deepcopy(result)
            record_button.configure(state="normal")
            if "step" in result:
                steps.append(result["step"]);warnings.append(result.get("warning",""));redraw()
            elif "error" in result: status.set(result["error"])
    poll_window(win,poll)
    if not embedded:
        win.transient(parent)
        win.grab_set()
        win.focus_force()


def test_dialog(parent,runtime,definition,embedded=False,on_close=None):
    import tkinter as tk
    from tkinter import ttk
    if embedded:
        win=ttk.Frame(parent);win.pack(fill="both",expand=True)
    else:
        win=tk.Toplevel(parent)
        from app_theme import attach_theme
        attach_theme(win)
        win.title("Hand Mouse - Test "+definition["name"])
        win.geometry("620x210")
    status=tk.StringVar(value="Perform the gesture. No keys or mouse actions are sent.")
    ttk.Label(win,textvariable=status,wraplength=570,padding=20).pack(fill="both",expand=True)
    runtime.start_test(definition)
    def close():
        runtime.stop_training();win.destroy()
        if on_close is not None: on_close()
    ttk.Button(win,text="Close test",command=close).pack(pady=12)
    if not embedded: win.protocol("WM_DELETE_WINDOW",close)
    def poll():
        if not win.winfo_exists(): return
        message,_,count=runtime.poll()
        status.set(message or "Perform the gesture. No input sent.")
    poll_window(win,poll)
    if not embedded: win.transient(parent);win.grab_set()
