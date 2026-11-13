"""Profile editor. All Tk objects live and are collected on the editor thread."""
from copy import deepcopy
import logging
import threading
from gesture_profiles import BASIC, GESTURES, MOUSE_GESTURES, action_label, validate_action

log=logging.getLogger("hand_mouse")
TYPE_LABELS={"Basic action":"default","Disabled":"disabled","Key / shortcut / media key":"keys",
             "Mouse button":"mouse","On-screen keyboard":"keyboard","Open application / file":"open"}

class ProfilesWindow:
    def __init__(self,store,on_apply):
        self.store,self.on_apply=store,on_apply
        self.show_evt,self.stop_evt=threading.Event(),threading.Event()
        self.lock=threading.Lock()
        self.thread=None

    def show(self):
        with self.lock:
            self.show_evt.set()
            if self.thread is None or not self.thread.is_alive():
                self.stop_evt.clear()
                self.thread=threading.Thread(target=self._run,daemon=True,name="gesture-profiles")
                self.thread.start()

    def stop(self):
        self.stop_evt.set()
        if self.thread and self.thread is not threading.current_thread(): self.thread.join(timeout=2)

    def _run(self):
        try: self._ui()
        except Exception: log.exception("Could not open gesture profiles")
        finally:
            import gc
            gc.collect()

    def _ui(self):
        import tkinter as tk
        from tkinter import ttk, messagebox, simpledialog, filedialog
        root=tk.Tk()
        root.withdraw()
        root.title("Hand Mouse - Gesture profiles")
        root.minsize(780,640)
        root.geometry("860x680")
        root.columnconfigure(0,weight=1)
        root.rowconfigure(0,weight=1)
        frame=ttk.Frame(root,padding=16)
        frame.grid(sticky="nsew")
        frame.columnconfigure(0,weight=1)
        frame.rowconfigure(3,weight=1)
        title=ttk.Label(frame,text="Gesture profiles",font=("Segoe UI",14,"bold"))
        title.grid(row=0,column=0,sticky="w")
        active=tk.StringVar()
        ttk.Label(frame,textvariable=active).grid(row=1,column=0,sticky="w",pady=(4,8))
        header=ttk.Frame(frame)
        header.grid(row=2,column=0,sticky="ew",pady=(0,10))
        choice=tk.StringVar(value=self.store.snapshot()["active"])
        profiles=ttk.Combobox(header,textvariable=choice,state="readonly",width=25)
        profiles.pack(side="left",padx=(0,8))
        tree_frame=ttk.Frame(frame)
        tree_frame.grid(row=3,column=0,sticky="nsew")
        tree_frame.columnconfigure(0,weight=1)
        tree_frame.rowconfigure(0,weight=1)
        tree=ttk.Treeview(tree_frame,columns=("gesture","action"),show="headings",selectmode="browse")
        tree.heading("gesture",text="Gesture")
        tree.heading("action",text="Assigned action")
        tree.column("gesture",width=390,minwidth=240)
        tree.column("action",width=330,minwidth=160)
        tree.grid(row=0,column=0,sticky="nsew")
        scroll=ttk.Scrollbar(tree_frame,orient="vertical",command=tree.yview)
        scroll.grid(row=0,column=1,sticky="ns")
        tree.configure(yscrollcommand=scroll.set)
        edit=ttk.LabelFrame(frame,text="Selected gesture",padding=10)
        edit.grid(row=4,column=0,sticky="ew",pady=10)
        edit.columnconfigure(1,weight=1)
        selected=tk.StringVar(value="Choose a gesture above")
        ttk.Label(edit,textvariable=selected).grid(row=0,column=0,columnspan=3,sticky="w",pady=(0,8))
        kind=tk.StringVar(value="Basic action")
        value=tk.StringVar()
        held=tk.BooleanVar(value=False)
        repeated=tk.BooleanVar(value=False)
        ttk.Label(edit,text="Action").grid(row=1,column=0,sticky="w",padx=(0,8))
        type_box=ttk.Combobox(edit,textvariable=kind,values=list(TYPE_LABELS),state="readonly")
        type_box.grid(row=1,column=1,sticky="ew")
        ttk.Label(edit,text="Key or value").grid(row=2,column=0,sticky="w",pady=8)
        entry=ttk.Entry(edit,textvariable=value)
        entry.grid(row=2,column=1,sticky="ew")
        def browse():
            path=filedialog.askopenfilename(parent=root,title="Choose application or file")
            if path:
                kind.set("Open application / file")
                value.set(path)
        ttk.Button(edit,text="Browse...",command=browse).grid(row=2,column=2,padx=(8,0))
        hold=ttk.Checkbutton(edit,text="Hold keys / button until pinch is released",variable=held)
        hold.grid(row=3,column=0,columnspan=3,sticky="w")
        repeat=ttk.Checkbutton(edit,text="Repeat while the left L pose is held",variable=repeated)
        repeat.grid(row=4,column=0,columnspan=3,sticky="w")
        ttk.Label(edit,text="Examples: ctrl+c, win+shift+s, space, f5, playpause. Mouse: left / right / middle / x1 / x2.",
                  wraplength=760).grid(row=5,column=0,columnspan=3,sticky="w",pady=(8,0))
        note=tk.StringVar()
        ttk.Label(frame,textvariable=note,wraplength=800).grid(row=5,column=0,sticky="w",pady=(0,8))
        ttk.Label(frame,text="Pause, reactivation and hand swapping are reserved. Existing gesture timing stays the same.\n"
                  "Save & apply releases held inputs and turns gestures off; enable them again when ready.",
                  wraplength=800).grid(row=6,column=0,sticky="w",pady=(0,12))
        footer=ttk.Frame(frame)
        footer.grid(row=7,column=0,sticky="ew")
        draft={}
        dirty=False
        loaded=None

        def error(exc): messagebox.showerror("Gesture profiles",str(exc),parent=root)
        def redraw():
            tree.delete(*tree.get_children())
            for source,label in GESTURES.items():
                tree.insert("","end",iid=source,values=(label,action_label(draft.get(source))))
            basic=choice.get()==BASIC
            type_box.configure(state="disabled" if basic else "readonly")
            entry.configure(state="disabled" if basic else "normal")
            note.set("Basic is read-only. Duplicate it to create your own profile." if basic else
                     "Select a gesture, edit its action, then click Save binding. Finish with Save & apply.")
            active.set("Active: "+self.store.snapshot()["active"])

        def load(event=None):
            nonlocal draft,dirty,loaded
            if dirty and not messagebox.askyesno("Unsaved bindings","Discard the unsaved bindings?",parent=root):
                choice.set(loaded)
                return
            data=self.store.snapshot()
            profiles.configure(values=list(data["profiles"]))
            if choice.get() not in data["profiles"]: choice.set(BASIC)
            draft=deepcopy(data["profiles"][choice.get()])
            loaded=choice.get()
            dirty=False
            redraw()

        def selected_changed(event=None):
            rows=tree.selection()
            if not rows: return
            source=rows[0]
            selected.set(GESTURES[source])
            action=draft.get(source,{"kind":"default","value":"","mode":"tap"})
            kind.set(next(label for label,k in TYPE_LABELS.items() if k==action["kind"]))
            value.set(action.get("value",""))
            held.set(action.get("mode")=="hold")
            repeated.set(action.get("mode")=="repeat")
            repeat.configure(state="normal" if source=="l:left" and choice.get()!=BASIC else "disabled")
            hold.configure(state="normal" if source in MOUSE_GESTURES and choice.get()!=BASIC else "disabled")

        def save_binding():
            nonlocal dirty
            if choice.get()==BASIC:
                error(ValueError("Duplicate Basic before editing.")); return
            rows=tree.selection()
            if not rows: error(ValueError("Select a gesture first.")); return
            source=rows[0]
            try:
                action=validate_action(source,{"kind":TYPE_LABELS[kind.get()],"value":value.get(),
                    "mode":"repeat" if repeated.get() else ("hold" if held.get() else "tap")},self.store.parse_keys)
                if action["kind"]=="default": draft.pop(source,None)
                else: draft[source]=action
                tree.item(source,values=(GESTURES[source],action_label(action)))
                dirty=True
                note.set("Binding saved in this draft. Click Save & apply to store and activate the profile.")
            except Exception as exc: error(exc)
        ttk.Button(edit,text="Save binding",command=save_binding).grid(row=1,column=2,padx=(8,0))

        def create(copy):
            nonlocal dirty
            name=simpledialog.askstring("New profile","Profile name:",parent=root)
            if name is None: return
            try:
                name=self.store.name(name)
                if name in self.store.snapshot()["profiles"]: raise ValueError("That name already exists")
                self.store.save(name,draft if copy else {})
                dirty=False
                choice.set(name)
                load()
            except Exception as exc: error(exc)
        def rename():
            nonlocal dirty
            if choice.get()==BASIC: error(ValueError("Basic is read-only")); return
            name=simpledialog.askstring("Rename profile","New name:",initialvalue=choice.get(),parent=root)
            if name is None: return
            try:
                if dirty: self.store.save(choice.get(),draft)
                self.store.rename(choice.get(),name)
                dirty=False
                choice.set(name.strip())
                load()
                self.on_apply(self.store.snapshot())
            except Exception as exc: error(exc)
        def delete():
            nonlocal dirty
            if choice.get()==BASIC: error(ValueError("Basic cannot be deleted")); return
            if not messagebox.askyesno("Delete profile","Delete "+choice.get()+"?",parent=root): return
            try:
                was_active=self.store.snapshot()["active"]==choice.get()
                self.store.delete(choice.get())
                dirty=False
                choice.set(BASIC)
                load()
                if was_active: self.on_apply(self.store.snapshot())
            except Exception as exc: error(exc)
        def apply():
            nonlocal dirty
            try:
                if choice.get()==BASIC: self.store.activate(BASIC)
                else: self.store.save(choice.get(),draft,activate=True)
                dirty=False
                self.on_apply(self.store.snapshot())
                active.set("Active: "+choice.get())
                note.set("Saved and applied. Gestures are off; enable them when ready.")
            except Exception as exc: error(exc)
        def hide():
            nonlocal dirty
            if dirty and not messagebox.askyesno("Unsaved bindings","Discard unsaved bindings and close?",parent=root): return
            dirty=False
            load()
            root.withdraw()
        ttk.Button(header,text="New",command=lambda:create(False)).pack(side="left",padx=3)
        ttk.Button(header,text="Duplicate",command=lambda:create(True)).pack(side="left",padx=3)
        ttk.Button(header,text="Rename",command=rename).pack(side="left",padx=3)
        ttk.Button(header,text="Delete",command=delete).pack(side="left",padx=3)
        ttk.Button(footer,text="Save & apply",command=apply).pack(side="left")
        ttk.Button(footer,text="Close",command=hide).pack(side="right")
        tree.bind("<<TreeviewSelect>>",selected_changed)
        profiles.bind("<<ComboboxSelected>>",load)
        root.protocol("WM_DELETE_WINDOW",hide)
        load()
        if self.store.load_error: note.set("Could not load saved profiles: "+self.store.load_error+". Basic is active.")
        def poll():
            if self.stop_evt.is_set(): root.destroy(); return
            if self.show_evt.is_set():
                self.show_evt.clear()
                active.set("Active: "+self.store.snapshot()["active"])
                root.deiconify()
                root.lift()
                root.focus_force()
            root.after(100,poll)
        root.after(0,poll)
        try: root.mainloop()
        finally:
            try: root.destroy()
            except tk.TclError: pass
