"""Saved bindings for existing Hand Mouse gestures; recognition and emergency controls stay in the app."""
from copy import deepcopy
import json
import logging
import os
import tempfile
import threading

log = logging.getLogger("hand_mouse")
BASIC = "Basic"
MOUSE_GESTURES = {
    "mouse:left": "Main hand: thumb + middle (left click / drag)",
    "mouse:right": "Main hand: thumb + ring (right click)",
    "mouse:middle": "Main hand: thumb + middle + ring (middle click)",
    "mouse:x1": "Main hand: thumb + index (Back)",
    "mouse:x2": "Main hand: thumb across palm (Forward)",
}
SECOND_LABELS = {
    "index": "Other hand: thumb + index (Alt+Tab)",
    "middle": "Other hand: thumb + middle (Copy)",
    "ring": "Other hand: thumb + ring (Paste)",
    "little base": "Other hand: thumb across palm (Undo)",
    "little base twice": "Other hand: thumb across palm twice (Redo)",
    "middle+ring": "Other hand: thumb + middle + ring (Screenshot)",
    "index+middle": "Other hand: thumb + index + middle (Voice typing)",
    "index+middle twice": "Other hand: thumb + index + middle twice (Keyboard)",
    "fist": "Other hand: single fist (Esc)",
    "thumbs-up, hand open": "Other hand: music pose then open (Play/pause)",
    "thumbs-up right": "Other hand: music swipe right (Next track)",
    "thumbs-up left": "Other hand: music swipe left (Previous track)",
}
GESTURES = dict(MOUSE_GESTURES, **{"second:"+k:v for k,v in SECOND_LABELS.items()},
                **{"l:left":"Physical left L pose (Backspace; repeats)", "l:right":"Physical right L pose (Enter)"})
KINDS = ("default", "disabled", "keys", "mouse", "keyboard", "open")


def validate_action(source, action, parse_keys):
    if source not in GESTURES:
        raise ValueError("This gesture is not configurable. Pause and reactivation are reserved.")
    if not isinstance(action, dict) or action.get("kind") not in KINDS:
        raise ValueError("Choose a valid action type.")
    kind = action["kind"]
    value = action.get("value", "")
    mode = action.get("mode", "tap")
    if not isinstance(value, str) or len(value)>4096 or mode not in ("tap", "hold", "repeat"):
        raise ValueError("Invalid action value or behavior.")
    if mode=="hold" and (source not in MOUSE_GESTURES or kind not in ("keys","mouse")):
        raise ValueError("Hold until release is available for main-hand pinch bindings only.")
    if mode=="repeat" and (source!="l:left" or kind not in ("keys","mouse")):
        raise ValueError("Repeat is available for left L-pose key or mouse bindings only.")
    if kind=="keys" and (not value.strip() or not isinstance(parse_keys(value), list)):
        raise ValueError("Enter a key or shortcut, for example space, ctrl+c, or win+shift+s.")
    if kind=="mouse" and value not in ("left","right","middle","x1","x2"):
        raise ValueError("Choose left, right, middle, x1 or x2.")
    if kind=="open" and (not value or not os.path.isabs(value)):
        raise ValueError("Choose an application or file using an absolute path.")
    return {"kind":kind,"value":value.strip() if kind!="open" else value,"mode":mode}


def action_label(action):
    if not action or action["kind"]=="default": return "Basic action"
    kind,value,mode=action["kind"],action.get("value",""),action.get("mode","tap")
    text={"disabled":"Disabled", "keys":value, "mouse":"Mouse "+value,
          "keyboard":"On-screen keyboard", "open":"Open "+value}.get(kind,kind)
    return text+({"hold":" (hold until release)","repeat":" (repeat while held)"}.get(mode,""))


def checked_bindings(bindings,parse_keys):
    if not isinstance(bindings,dict): raise ValueError("Invalid bindings")
    checked={source:validate_action(source,action,parse_keys) for source,action in bindings.items() if source!="__custom__"}
    if "__custom__" in bindings:
        from gesture_custom import validate_custom
        checked["__custom__"]=validate_custom(bindings["__custom__"],parse_keys)
    return checked


class ProfileStore:
    def __init__(self,path,parse_keys):
        self.path,self.parse_keys=path,parse_keys
        self.lock=threading.RLock()
        self.data={"version":1,"active":BASIC,"profiles":{BASIC:{}}}
        self.load_error=""
        if os.path.isfile(path):
            try:
                if os.path.getsize(path)>8*1024*1024: raise ValueError("Profiles file is too large")
                with open(path,encoding="utf-8") as f: data=json.load(f)
                if data.get("version")!=1 or not isinstance(data.get("profiles"),dict):
                    raise ValueError("Unsupported profiles format")
                profiles={BASIC:{}}
                for name,bindings in data["profiles"].items():
                    self.name(name)
                    if not isinstance(bindings,dict): raise ValueError("Invalid bindings")
                    checked=checked_bindings(bindings,parse_keys)
                    if name==BASIC and checked: raise ValueError("Basic profile must stay unchanged")
                    profiles[name]=checked
                active=data.get("active",BASIC)
                if active not in profiles: raise ValueError("Active profile is missing")
                self.data={"version":1,"active":active,"profiles":profiles}
            except Exception as exc:
                self.load_error=str(exc)
                log.warning("Profiles could not be loaded; Basic is active: %s",exc)

    @staticmethod
    def name(name):
        if not isinstance(name,str) or not name.strip() or len(name)>60 or any(ord(c)<32 for c in name):
            raise ValueError("Use a profile name of 1-60 characters.")
        return name.strip()

    def snapshot(self):
        with self.lock: return deepcopy(self.data)

    def _write(self,data):
        if len(data["profiles"])>64: raise ValueError("Use at most 64 profiles.")
        payload=json.dumps(data,ensure_ascii=False,indent=2)
        if len(payload.encode("utf-8"))>8*1024*1024: raise ValueError("Saved profiles exceed 8 MB. Remove unused recorded gestures first.")
        folder=os.path.dirname(os.path.abspath(self.path))
        os.makedirs(folder,exist_ok=True)
        # Preserve a malformed user file before any subsequent explicit save.
        if self.load_error and os.path.exists(self.path):
            import shutil
            import time
            shutil.copy2(self.path,self.path+".invalid-"+str(time.time_ns()))
        fd,temp=tempfile.mkstemp(prefix=".profiles-",suffix=".tmp",dir=folder)
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp,self.path)
        finally:
            if os.path.exists(temp): os.remove(temp)
        self.data=data
        self.load_error=""

    def save(self,name,bindings,activate=False):
        name=self.name(name)
        if name==BASIC: raise ValueError("Basic is read-only. Duplicate it to customize gestures.")
        if not isinstance(bindings,dict): raise ValueError("Invalid bindings")
        checked=checked_bindings(bindings,self.parse_keys)
        with self.lock:
            data=self.snapshot()
            data["profiles"][name]=checked
            if activate: data["active"]=name
            self._write(data)

    def activate(self,name):
        with self.lock:
            data=self.snapshot()
            if name not in data["profiles"]: raise ValueError("Profile not found")
            data["active"]=name
            self._write(data)

    def rename(self,old,new):
        new=self.name(new)
        with self.lock:
            data=self.snapshot()
            if old==BASIC: raise ValueError("Basic is read-only")
            if new in data["profiles"]: raise ValueError("That name already exists")
            data["profiles"][new]=data["profiles"].pop(old)
            if data["active"]==old: data["active"]=new
            self._write(data)

    def delete(self,name):
        with self.lock:
            if name==BASIC: raise ValueError("Basic cannot be deleted")
            data=self.snapshot()
            data["profiles"].pop(name)
            if data["active"]==name: data["active"]=BASIC
            self._write(data)


class ProfileMouse:
    """Remap existing main-hand button gestures without changing their recognition."""
    def __init__(self,base,parse_keys):
        self.base,self.parse_keys=base,parse_keys
        self.bindings={}
        self.held={}
        self.counts={}

    def __getattr__(self,name): return getattr(self.base,name)

    def perform_action(self,action):
        try:
            kind,value=action["kind"],action.get("value","")
            if kind in ("default","disabled"): return True
            if kind=="keys": self.keys(self.parse_keys(value))
            elif kind=="mouse":
                self._hold("mouse",value,True)
                self._hold("mouse",value,False)
            elif kind=="keyboard": self.base.toggle_keyboard()
            elif kind=="open": os.startfile(value)
            return True
        except Exception as exc:
            log.warning("Profile action %s failed: %s",action_label(action),exc)
            return False

    def _hold(self,kind,value,down):
        identity=(kind,value)
        count=self.counts.get(identity,0)
        new=count+1 if down else max(count-1,0)
        if (down and count==0) or (not down and count==1):
            if kind=="keys": self.base.key(value,down)
            else: self.base.button(value,down)
        if new: self.counts[identity]=new
        else: self.counts.pop(identity,None)

    def profile_label(self,source,default):
        action=self.bindings.get(source)
        return default if not action or action["kind"]=="default" else action_label(action)

    def key(self,vk,down):
        self._hold("keys",vk,down)

    def keys(self,vks):
        if not any(self.counts.get(("keys",vk),0) for vk in vks):
            self.base.keys(vks)
            return
        # A shortcut must not release a modifier held by another gesture.
        import time
        pressed=[]
        try:
            for vk in vks:
                self._hold("keys",vk,True)
                pressed.append(vk)
                time.sleep(.01)
        finally:
            for vk in reversed(pressed):
                self._hold("keys",vk,False)
                time.sleep(.01)

    def button(self,name,down):
        source="mouse:"+name
        if down:
            if source in self.held: return
            action=self.bindings.get(source,{"kind":"default"})
            kind=action["kind"]
            if kind=="default": outputs=[("mouse",name)]
            elif action.get("mode")=="hold" and kind=="keys": outputs=[("keys",vk) for vk in self.parse_keys(action["value"])]
            elif action.get("mode")=="hold" and kind=="mouse": outputs=[("mouse",action["value"])]
            else:
                self.perform_action(action)
                outputs=[]
            self.held[source]=outputs
            for k,v in outputs: self._hold(k,v,True)
        else:
            for k,v in reversed(self.held.pop(source,[])): self._hold(k,v,False)

    def release_profile_inputs(self):
        for source in list(self.held): self.button(source.split(":",1)[1],False)
        for (kind,value),count in list(self.counts.items()):
            for _ in range(count): self._hold(kind,value,False)


def configure_engine(engine,mouse,bindings,second_defaults,parse_keys,key_label):
    # Called on the gesture thread, after pending gestures have been discarded and inputs released.
    mouse.release_profile_inputs()
    mouse.bindings=deepcopy(bindings)
    if hasattr(engine,"custom_runtime"):
        engine.custom_runtime.configure(bindings.get("__custom__",[]))
    actions={}
    for name,text in second_defaults.items():
        source="second:"+name
        action=bindings.get(source,{"kind":"default"})
        kind=action["kind"]
        if kind=="disabled": continue
        if kind=="default":
            keys=parse_keys(text)
            if keys is not None: actions[name]=(keys,key_label(text))
        elif kind=="keys": actions[name]=(parse_keys(action["value"]),key_label(action["value"]))
        elif kind=="keyboard": actions[name]=("keyboard","on-screen keyboard")
        else: actions[name]=(deepcopy(action),action_label(action))
    # A disabled single must still be recognized to reach its configured double gesture.
    for name in list(actions):
        if name.endswith(" twice") and name[:-6] not in actions:
            actions[name[:-6]]=({"kind":"disabled"},"Disabled")
    engine.keys.actions=actions
    engine.l_profile_actions={side:deepcopy(bindings.get("l:"+side,{"kind":"default"})) for side in ("left","right")}
    left=engine.l_profile_actions["left"]
    engine.l_profile_repeat=left["kind"]=="default" or left.get("mode")=="repeat"



def apply_profile_to_engine(engine,mouse,data,second_defaults,parse_keys,key_label,now):
    """Swap on the gesture thread, never firing an old pending shortcut or leaving inputs held."""
    engine.gestures_request=None
    engine.keys.pending=None
    engine.release_all(now)
    mouse.release_profile_inputs()
    name=data["active"]
    configure_engine(engine,mouse,data["profiles"][name],second_defaults,parse_keys,key_label)
    engine.profile_name=name
    engine._set_gestures_off(True,now,"profile changed")
    return name
