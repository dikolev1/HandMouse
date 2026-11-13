"""Recorded pose templates, ordered pose/swipe combinations, and guided capture without images."""
from copy import deepcopy
import math
import logging
import threading
import uuid

LANDMARKS=(0,4,5,8,9,12,13,16,17,20)
FEATURE_SIZE=45
log=logging.getLogger("hand_mouse")


def pose_feature(hand):
    scale=max(math.dist(hand.world[0],hand.world[9]),1e-5)
    return [round(min(math.dist(hand.world[a],hand.world[b])/scale,4),4)
            for i,a in enumerate(LANDMARKS) for b in LANDMARKS[i+1:]]


def distance(a,b):
    return math.sqrt(sum((x-y)**2 for x,y in zip(a,b))/FEATURE_SIZE)


def in_view(hand):
    return not hand.unsure and all(0<x<1 and 0<y<1 for x,y in hand.img)


def targets(hand,side):
    return side=="either" or hand.hand_side==side or hand.role==side


def pose_score(feature,step):
    return min(distance(feature,t) for t in step["templates"])


def make_pose(samples):
    if len(samples)<12: raise ValueError("Not enough clear samples. Keep the whole hand visible and try again.")
    mean=[sum(row[i] for row in samples)/len(samples) for i in range(FEATURE_SIZE)]
    ranked=sorted(samples,key=lambda row:distance(row,mean))
    if distance(ranked[int(len(ranked)*.9)],mean)>.35:
        raise ValueError("The pose changed too much. Keep the finger shape steady while gently changing its angle.")
    templates=[ranked[0]]
    for _ in range(min(4,len(samples)-1)):
        candidate=max(ranked[:max(1,int(len(ranked)*.95))],key=lambda row:min(distance(row,t) for t in templates))
        if min(distance(candidate,t) for t in templates)<.025: break
        templates.append(candidate)
    errors=sorted(min(distance(row,t) for t in templates) for row in ranked)
    threshold=min(.20,max(.09,errors[int(len(errors)*.9)]*1.6+.035))
    return {"kind":"pose","templates":deepcopy(templates),"threshold":round(threshold,4)}


def validate_custom(definitions,parse_keys):
    from gesture_profiles import validate_action
    if not isinstance(definitions,list) or len(definitions)>30: raise ValueError("Use at most 30 recorded gestures per profile.")
    checked=[]; ids=set()
    for original in definitions:
        d=deepcopy(original)
        if not isinstance(d,dict) or not isinstance(d.get("id"),str) or not d["id"] or len(d["id"])>60 or d["id"] in ids:
            raise ValueError("Invalid or duplicate recorded gesture ID")
        ids.add(d["id"])
        if not isinstance(d.get("name"),str) or not d["name"].strip() or len(d["name"])>60 or any(ord(c)<32 for c in d["name"]): raise ValueError("Name the recorded gesture (1-60 characters).")
        if d.get("hand") not in ("left","right","main","second","either"): raise ValueError("Choose which hand performs the gesture.")
        steps=d.get("steps")
        if not isinstance(steps,list) or not 1<=len(steps)<=6 or not isinstance(steps[0],dict) or steps[0].get("kind")!="pose": raise ValueError("Start with a recorded pose and use at most six steps.")
        for i,step in enumerate(steps):
            if not isinstance(step,dict): raise ValueError("Invalid recorded step")
            if step.get("kind")=="pose":
                ts=step.get("templates")
                if not isinstance(ts,list) or not 1<=len(ts)<=5: raise ValueError("A pose needs 1-5 templates.")
                for row in ts:
                    if not isinstance(row,list) or len(row)!=FEATURE_SIZE or any(type(x) not in (float,int) or not math.isfinite(x) or not 0<=x<=4 for x in row):
                        raise ValueError("Invalid recorded landmark template")
                limit=step.get("threshold")
                if type(limit) not in (int,float) or not .06<=limit<=.25: raise ValueError("Invalid pose tolerance")
            elif step.get("kind")=="swipe":
                if i!=len(steps)-1 or step.get("direction") not in ("left","right") or i==0:
                    raise ValueError("A left/right swipe must be the last step after a pose.")
            else: raise ValueError("Unknown recorded step")
        behavior=d.get("behavior","tap")
        if behavior not in ("tap","hold","repeat"): raise ValueError("Invalid gesture behavior")
        if steps[-1]["kind"]=="swipe" and behavior!="tap": raise ValueError("Swipe combinations act once; choose Once.")
        source="mouse:left" if behavior=="hold" else "l:left"
        action=deepcopy(d.get("action",{}));action["mode"]=behavior
        d["action"]=validate_action(source,action,parse_keys)
        if action.get("kind")=="default": raise ValueError("Choose an action for a new gesture.")
        if behavior in ("hold","repeat") and action.get("kind") not in ("keys","mouse"):
            raise ValueError("Hold/repeat requires a key shortcut or mouse button.")
        d["behavior"]=behavior
        for a,b in zip(steps,steps[1:]):
            if a["kind"]==b["kind"]=="pose" and min(distance(x,y) for x in a["templates"] for y in b["templates"])<max(a["threshold"],b["threshold"])+.02:
                raise ValueError("Consecutive steps must be distinct poses.")
        # Ambiguous first steps (including prefixes) cannot coexist for overlapping hands.
        for old in checked:
            if d["hand"]==old["hand"] or d["hand"] in ("either","main","second") or old["hand"] in ("either","main","second"):
                a,b=d["steps"][0],old["steps"][0]
                if min(distance(x,y) for x in a["templates"] for y in b["templates"])<max(a["threshold"],b["threshold"])+.035:
                    raise ValueError("The first pose overlaps recorded gesture '"+old["name"]+"'. Use a different first pose or a separate profile.")
        checked.append(d)
    return checked


class PoseMachine:
    """Consumes a stable unique first pose, then ordered steps, with release latching."""
    def __init__(self,definitions=()):
        self.definitions=deepcopy(list(definitions))
        self.reset()

    def reset(self):
        self.current=None;self.hand_key=None;self.step=0;self.since=None
        self.last_seen=None;self.deadline=None;self.complete=False;self.last_match=None
        self.origin=None;self.swipe_distance=None;self.status="";self.ambiguous=False

    def update(self,hands,now):
        self.ambiguous=False
        # Both folded hands always belong to pause/reactivation, never to a custom combination.
        if len(hands)>=2 and all(max(h.ext)<1.55 for h in hands):
            self.reset();return None,False
        if self.last_seen is not None and now-self.last_seen>.4:
            self.reset()
        valid=[h for h in hands if in_view(h)]
        if self.current is None:
            choices=[]
            for h in valid:
                feature=pose_feature(h)
                for d in self.definitions:
                    if targets(h,d["hand"]):
                        score=pose_score(feature,d["steps"][0])
                        if score<=d["steps"][0]["threshold"]: choices.append((score,d,h))
            choices.sort(key=lambda row:row[0])
            if not choices: return None,False
            if len(choices)>1 and choices[1][0]-choices[0][0]<.035:
                self.ambiguous=True;self.status="Ambiguous pose: adjust or re-record";return None,False
            _,self.current,h=choices[0]
            self.hand_key=h.key;self.since=now;self.step=0;self.deadline=now+5
        h=next((h for h in valid if h.key==self.hand_key),None)
        if h is None:
            self.reset();return None,False
        self.last_seen=now
        d=self.current
        feature=pose_feature(h)
        if self.complete:
            last=d["steps"][-1]
            if last["kind"]=="swipe": last=d["steps"][-2]
            matched=pose_score(feature,last)<=last["threshold"]*1.2
            if not matched:
                # Stop held/repeated outputs immediately, latch until a short clear release.
                if self.last_match is None: self.last_match=now
                if now-self.last_match>=.25:
                    self.reset()
                    return None,False
                return None,True
            self.last_match=None
            self.status=d["name"]+" - release to repeat"
            return d,True
        if now>self.deadline:
            self.reset();return None,False
        step=d["steps"][self.step]
        if step["kind"]=="swipe":
            previous=d["steps"][self.step-1]
            if pose_score(feature,previous)>previous["threshold"]*1.2:
                self.reset();return None,False
            dx=h.center[0]-self.origin
            reached=dx<=-self.swipe_distance if step["direction"]=="left" else dx>=self.swipe_distance
            if reached:
                self.complete=True;self.last_match=now
                self.status=d["name"]+" - release to repeat"
                return d,True
        else:
            match=pose_score(feature,step)<=step["threshold"]
            if match:
                if self.since is None: self.since=now
                if now-self.since>=.25:
                    if self.step==len(d["steps"])-1:
                        self.complete=True;self.last_match=None
                        self.status=d["name"]+" - release to repeat"
                        return d,True
                    self.step+=1;self.since=None;self.deadline=now+5
                    self.origin=h.center[0];self.swipe_distance=min(.18,max(.06,h.palm*.8))
            else:
                self.since=None
                if self.step==0:
                    self.reset();return None,False
        self.status=d["name"]+f" - step {self.step+1}/{len(d['steps'])}"
        return None,True


class CustomRuntime:
    def __init__(self,mouse,pause,show_camera=None,conflict=None):
        self.mouse,self.pause=mouse,pause
        self.show_camera=show_camera or (lambda:None)
        self.conflict=conflict or (lambda h:"")
        self.lock=threading.RLock()
        self.machine=PoseMachine()
        self.capture=None;self.result=None;self.tester=None;self.test_count=0
        self.message="";self.busy=False;self.output=None;self.fired=False;self.repeat_at=None
        self.held=[];self.status="";self.testing=False

    def configure(self,definitions):
        self.cancel()
        self.machine=PoseMachine(definitions)

    def _release(self):
        for kind,value in reversed(self.held): self.mouse._hold(kind,value,False)
        self.held=[]

    def cancel(self):
        self._release()
        self.machine.reset()
        self.output=None;self.fired=False;self.repeat_at=None;self.busy=False

    def observe(self,hands,now,enabled):
        if not enabled:
            self.cancel();return False
        output,busy=self.machine.update(hands,now)
        if output is None: self._release()
        if not busy:
            self.fired=False;self.repeat_at=None
        self.output,self.busy=output,busy
        self.status=self.machine.status
        return busy

    def dispatch(self,now):
        d=self.output
        if d is None: return
        a=d["action"];behavior=d["behavior"]
        if behavior=="hold":
            if not self.held:
                outputs=[("keys",vk) for vk in self.mouse.parse_keys(a["value"])] if a["kind"]=="keys" else [("mouse",a["value"])]
                for kind,value in outputs:
                    self.mouse._hold(kind,value,True)
                    self.held.append((kind,value))
                log.info("recorded gesture %s -> hold %s",d["name"],a.get("value",""))
        elif not self.fired:
            self.mouse.perform_action(a);self.fired=True;self.repeat_at=now+.5
            log.info("recorded gesture %s -> %s",d["name"],a.get("value",a["kind"]))
        elif behavior=="repeat" and now>=self.repeat_at:
            self.mouse.perform_action(a);self.repeat_at=now+.12

    def start_capture(self,side,first=True):
        self.pause();self.show_camera()
        with self.lock:
            self.capture={"hand":side,"first":first,"start":None,"samples":[],"key":None,"warning":""}
            self.result=None;self.tester=None;self.testing=False
            self.message="Prepare the pose. Recording starts after 1 second; hold it for 4 seconds and gently vary its angle."

    def start_test(self,definition):
        self.pause();self.show_camera()
        with self.lock:
            self.capture=None;self.result=None;self.tester=PoseMachine([definition]);self.test_count=0
            self.testing=False;self.message="Perform the gesture. Test mode sends no keys or mouse actions."

    def stop_training(self):
        with self.lock:
            self.capture=None;self.tester=None;self.result=None
            self.message="";self.testing=False

    def poll(self):
        with self.lock: return self.message,deepcopy(self.result),self.test_count

    def feed(self,hands,now):
        with self.lock:
            if self.tester is not None:
                output,busy=self.tester.update(hands,now)
                if output is not None and not self.testing:
                    self.test_count+=1
                    self.message=f"Recognized {self.test_count} time(s). No input sent. Release, then try another angle."
                if output is None and self.tester.status:
                    self.message=self.tester.status+" (test only; no input sent)"
                if output is not None: self.testing=True
                elif not busy: self.testing=False
                return
            job=self.capture
            if job is None: return
            if job["start"] is None: job["start"]=now
            elapsed=now-job["start"]
            if elapsed<1: return
            hs=[h for h in hands if in_view(h) and targets(h,job["hand"])]
            if len(hs)==1 and (job["key"] is None or job["key"]==hs[0].key):
                h=hs[0];job["key"]=h.key
                if job["first"] and (min(h.ext)>1.5 or max(h.ext)<1.35):
                    self.capture=None
                    self.result={"error":"Open palms and closed fists are reserved as the first pose. Use an existing binding or choose a distinct starting pose."}
                    self.message=self.result["error"];return
                warning=self.conflict(h) if job["first"] else ""
                if warning: job["warning"]=warning
                if len(job["samples"])<100: job["samples"].append(pose_feature(h))
            self.message=f"Recording: {max(0,5-elapsed):.1f}s left, {len(job['samples'])} clear samples. Keep the same finger shape."
            if elapsed>=5:
                try:
                    step=make_pose(job["samples"])
                    self.result={"step":step,"warning":job["warning"]}
                    self.message="Pose recorded. Test it before saving."
                except ValueError as exc:
                    self.result={"error":str(exc)};self.message=str(exc)
                self.capture=None


def new_definition(name,side,steps,action,behavior):
    return {"id":uuid.uuid4().hex,"name":name,"hand":side,"steps":deepcopy(steps),
            "action":deepcopy(action),"behavior":behavior}
