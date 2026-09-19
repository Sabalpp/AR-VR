"use client";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import Link from "next/link";
import { errorText } from "@/lib/api";
import { webXRWristToQuest } from "@/lib/quest-coordinates";

type Device = { device_token: string; device_id: string; session_id: string };
type Config = { quest_target_m: {x:number;y:number;z:number}; quest_reach_m:number; quest_return_m:number; hold_ms:number; mode?:string };
type State = { status:string; repetitions:number; phase:string; tracking_valid:boolean; last_measurement:number|null; phone_tracking_valid?:boolean; last_attempt?:{id:string;outcome:string} };
type Pending = { resolve:(value:State)=>void; reject:(reason:Error)=>void; timer:ReturnType<typeof setTimeout> };

export default function QuestSession() {
  const [code,setCode] = useState("");
  const [message,setMessage] = useState("Enter the headset pairing code from the patient session.");
  const [supported,setSupported] = useState<boolean|null>(null);
  const [paired,setPaired] = useState(false);
  const [immersive,setImmersive] = useState(false);
  const [busy,setBusy] = useState(false);
  const [viewState,setViewState] = useState<State>();
  const [muted,setMuted] = useState(false);
  const host=useRef<HTMLDivElement>(null);
  const device=useRef<Device|null>(null), config=useRef<Config|null>(null);
  const state=useRef<State|null>(null), socket=useRef<WebSocket|null>(null);
  const pending=useRef(new Map<string,Pending>());
  const renderer=useRef<THREE.WebGLRenderer|null>(null), session=useRef<XRSession|null>(null);
  const seq=useRef(0), sending=useRef(false), commandBusy=useRef(false), entered=useRef(false);
  const stopped=useRef(true), fatal=useRef(false), muteRef=useRef(false);
  const audio=useRef<AudioContext|null>(null), audioNode=useRef<AudioBufferSourceNode|null>(null);
  const cueBusy=useRef(false), lastCue=useRef(0), audioCache=useRef(new Map<string,AudioBuffer>());
  const caption=useRef(message), cleanupXR=useRef<(()=>void)|null>(null);
  function say(text:string) { caption.current=text; setMessage(text); }
  useEffect(()=>{
    let active=true;
    navigator.xr?.isSessionSupported("immersive-ar").then(value=>{if(active)setSupported(value);}).catch(()=>{if(active)setSupported(false);});
    if(!navigator.xr)setSupported(false);
    return ()=>{active=false; stopped.current=true; socket.current?.close(); void session.current?.end(); cleanupXR.current?.(); void audio.current?.close();};
  },[]);
  function failPending() {
    pending.current.forEach(p=>{clearTimeout(p.timer);p.reject(new Error("Connection closed; recording paused."));}); pending.current.clear();
  }
  function send(type:string,payload:object):Promise<State> {
    return new Promise((resolve,reject)=>{
      if(socket.current?.readyState!==WebSocket.OPEN){reject(new Error("Connect the headset first."));return;}
      const id=crypto.randomUUID();
      const timer=setTimeout(()=>{pending.current.delete(id);stopped.current=true;reject(new Error("No save acknowledgement; recording paused. Reconnect before resuming."));},8000);
      pending.current.set(id,{resolve,reject,timer});
      socket.current.send(JSON.stringify({version:1,type,id,payload}));
    });
  }
  async function cue(id:string,attemptId?:string) {
    if(muteRef.current||!audio.current||cueBusy.current||Date.now()-lastCue.current<8000)return;
    cueBusy.current=true;lastCue.current=Date.now();
    try {
      let buffer=audioCache.current.get(id);
      if(!buffer){
        const response=await fetch(`/api/v1/speech/${id}`,{headers:{Authorization:`Bearer ${device.current!.device_token}`},signal:AbortSignal.timeout(12000)});
        if(!response.ok)throw new Error("Voice unavailable");
        buffer=await audio.current.decodeAudioData(await response.arrayBuffer()); audioCache.current.set(id,buffer);
      }
      if(muteRef.current||!session.current||state.current?.status!=="active")return;
      if(attemptId && state.current.last_attempt?.id !== attemptId)return;
      audioNode.current?.stop();const node=audio.current.createBufferSource();node.buffer=buffer;node.connect(audio.current.destination);audioNode.current=node;node.start();
    } catch { /* The same cue remains visible; audio never blocks tracking. */ }
    finally {cueBusy.current=false;}
  }
  async function connectSocket() {
    if(!device.current)throw new Error("Pair first.");
    if(socket.current) {socket.current.onclose=null;socket.current.close();failPending();}
    const ws=new WebSocket(`${location.protocol==="https:"?"wss":"ws"}://${location.host}/api/v1/ws/${device.current.session_id}`);
    socket.current=ws;
    ws.onmessage=(event)=>{
      const msg=JSON.parse(event.data);
      if(msg.type==="session.config"){
        if(!["quest","combined"].includes(msg.payload.mode)){fatal.current=true;ws.close();say("This code belongs to a phone-only session. Create a Quest or combined session.");return;}
        config.current={...msg.payload.config,mode:msg.payload.mode};seq.current=Math.max(seq.current,msg.payload.last_seq+1);
      }
      if(msg.type==="session.state"){
        state.current=msg.payload;setViewState(msg.payload);
        if(msg.payload.status!=="active"){stopped.current=true; audioNode.current?.stop();}
        const p=pending.current.get(msg.payload.ack_id);if(p){clearTimeout(p.timer);pending.current.delete(msg.payload.ack_id);p.resolve(msg.payload);}
      }
      if(msg.type==="exercise.feedback") {say(msg.payload.message);void cue(msg.payload.cue_id,msg.payload.attempt_id);}
      if(msg.type==="error"){
        const p=pending.current.get(msg.payload.ack_id);if(p){clearTimeout(p.timer);pending.current.delete(msg.payload.ack_id);p.reject(new Error(msg.payload.message));}
        say(msg.payload.message);
      }
    };
    ws.onclose=()=>{stopped.current=true;failPending();say("Connection closed. Recording paused; reconnect, then resume deliberately.");};
    await new Promise<void>((resolve,reject)=>{
      const timer=setTimeout(()=>{ws.close();reject(new Error("Connection timed out"));},10000);
      ws.onopen=()=>{clearTimeout(timer);resolve();};ws.onerror=()=>{clearTimeout(timer);reject(new Error("Could not connect to the session"));};
    });
    await send("device.join",{token:device.current.device_token});
    if(!config.current)throw new Error("Session configuration missing.");
    if(state.current?.status!=="complete") await send("session.pause",{});
    const before=Date.now();const response=await fetch("/api/v1/time");if(!response.ok)throw new Error("Could not estimate device clock");
    const time=await response.json();await send("device.status",{clock_offset_ms:(before+Date.now())/2-Date.parse(time.server_time),tracking_valid:false});
  }
  async function pair(event:React.FormEvent) {
    event.preventDefault();setBusy(true);
    try {
      const response=await fetch("/api/v1/devices/pair",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({code:code.trim(),expected_source:"quest",label:"Quest Browser WebXR wrist"})});
      const result=await response.json();if(!response.ok)throw new Error(typeof result.detail==="string"?result.detail:"Pairing failed");
      device.current=result;setPaired(true);await connectSocket();say("Paired. Stay seated, keep the area clear, then enter passthrough. Use your left hand to point and pinch the controls.");
    }catch(error){say(errorText(error));}finally{setBusy(false);}
  }
  async function action(kind:string) {
    if(commandBusy.current)return;
    if(kind==="mute") {muteRef.current=!muteRef.current;setMuted(muteRef.current);if(muteRef.current)audioNode.current?.stop();return;}
    if(kind==="exit"){stopped.current=true;void send("session.pause",{}).catch(()=>{});await session.current?.end();return;}
    commandBusy.current=true;
    try {
      if(kind==="reconnect"){await connectSocket();say("Reconnected. Resume when ready.");return;}
      if(kind==="resume" && (fatal.current||!session.current))throw new Error("Enter a fresh passthrough session before starting.");
      stopped.current=true;
      // Freeze sampling before draining the one in-flight frame.
      const deadline=Date.now()+8500;
      while(sending.current&&Date.now()<deadline)await new Promise(r=>setTimeout(r,30));
      if(sending.current)throw new Error("Wait for the outstanding sample to save.");
      await send(`session.${kind}`,{});
      if(kind==="resume"){stopped.current=false;say("Begin at the return zone. Reach the green target, hold, then return.");}
      if(kind==="pause")say("Paused. Resume only when ready.");
      if(kind==="complete"){say("Session saved. Remove the headset and submit your check-in on the phone.");await session.current?.end();}
    }catch(error){say(errorText(error));}finally{commandBusy.current=false;}
  }
  async function enter() {
    if(!navigator.xr||!config.current||!device.current)return;
    if(entered.current){say("The tracking origin has ended. Finish this session and create a new one before re-entering.");return;}
    setBusy(true);
    let xr:XRSession|null=null;
    try {
      audio.current??=new AudioContext();void audio.current.resume();
      xr=await navigator.xr.requestSession("immersive-ar",{requiredFeatures:["local-floor","hand-tracking"]});
      session.current=xr;entered.current=true;setImmersive(true);
      const r=new THREE.WebGLRenderer({antialias:true,alpha:true});renderer.current=r;
      r.setPixelRatio(Math.min(devicePixelRatio,2));r.setSize(window.innerWidth,window.innerHeight);r.xr.enabled=true;r.xr.setReferenceSpaceType("local-floor");host.current?.appendChild(r.domElement);
      await r.xr.setSession(xr);
      const baseReference=r.xr.getReferenceSpace();if(!baseReference)throw new Error("Floor tracking origin unavailable");
      let reference:XRReferenceSpace=baseReference;
      const scene=new THREE.Scene(), camera=new THREE.PerspectiveCamera(65,innerWidth/innerHeight,0.01,30);
      for(let i=0;i<2;i++){
        const pointer=r.xr.getController(i);
        const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0,0,0),new THREE.Vector3(0,0,-2)]),new THREE.LineBasicMaterial({color:0xf3d17b}));
        pointer.add(line);scene.add(pointer);
      }
      const cfg=config.current;
      // WebXR is right-handed, -Z forward. The wire contract is Unity-style +Z forward.
      const target=new THREE.Mesh(new THREE.SphereGeometry(cfg.quest_reach_m,24,16),new THREE.MeshBasicMaterial({color:0x36c994,transparent:true,opacity:.4,wireframe:true}));
      target.position.set(cfg.quest_target_m.x,cfg.quest_target_m.y,-cfg.quest_target_m.z);scene.add(target);
      const returnZone=new THREE.Mesh(new THREE.SphereGeometry(cfg.quest_return_m,24,16),new THREE.MeshBasicMaterial({color:0xcba954,transparent:true,opacity:.18,wireframe:true}));returnZone.position.copy(target.position);scene.add(returnZone);
      const wrist=new THREE.Mesh(new THREE.SphereGeometry(.018,12,8),new THREE.MeshBasicMaterial({color:0xffffff}));wrist.visible=false;scene.add(wrist);
      const panel=document.createElement("canvas");panel.width=1024;panel.height=512;const ctx=panel.getContext("2d")!;
      const texture=new THREE.CanvasTexture(panel);const board=new THREE.Mesh(new THREE.PlaneGeometry(1.05,.525),new THREE.MeshBasicMaterial({map:texture,transparent:true}));scene.add(board);
      const buttons:{mesh:THREE.Mesh;kind:string;label:string}[]=[];
      const kinds=[["resume","Start / resume"],["pause","Pause"],["complete","Finish"],["mute","Mute / unmute"],["reconnect","Reconnect"],["exit","Exit"]];
      for(let i=0;i<kinds.length;i++){
        const c=document.createElement("canvas");c.width=320;c.height=100;const context=c.getContext("2d")!;context.fillStyle="#174b40";context.fillRect(0,0,320,100);context.fillStyle="white";context.font="24px sans-serif";context.textAlign="center";context.fillText(kinds[i][1],160,60);
        const mesh=new THREE.Mesh(new THREE.PlaneGeometry(.31,.097),new THREE.MeshBasicMaterial({map:new THREE.CanvasTexture(c)}));scene.add(mesh);buttons.push({mesh,kind:kinds[i][0],label:kinds[i][1]});
      }
      let placed=false,lastPaint=0,lastSample=0,lastLabel="";
      const poseMatrix=new THREE.Matrix4(), raycaster=new THREE.Raycaster();
      const select=(event:XRInputSourceEvent)=>{
        const pose=event.frame.getPose(event.inputSource.targetRaySpace,reference);if(!pose)return;
        poseMatrix.fromArray(pose.transform.matrix);raycaster.ray.origin.setFromMatrixPosition(poseMatrix);raycaster.ray.direction.set(0,0,-1).transformDirection(poseMatrix);
        const hit=raycaster.intersectObjects(buttons.map(b=>b.mesh))[0];const button=buttons.find(b=>b.mesh===hit?.object);if(button)void action(button.kind);
      };
      const reset=()=>{fatal.current=true;stopped.current=true;void send("session.pause",{}).catch(()=>{});say("Tracking origin changed. Finish and create a new session; do not continue with the shifted target.");};
      baseReference.addEventListener("reset",reset);xr.addEventListener("select",select);
      const visibility=()=>{if(xr!.visibilityState!=="visible"){stopped.current=true;void send("session.pause",{}).catch(()=>{});}};
      xr.addEventListener("visibilitychange",visibility);
      cleanupXR.current=()=>{
        r.setAnimationLoop(null);baseReference.removeEventListener("reset",reset);xr?.removeEventListener("select",select);xr?.removeEventListener("visibilitychange",visibility);
        scene.traverse(object=>{if(object instanceof THREE.Mesh || object instanceof THREE.Line){object.geometry.dispose();const material=object.material as THREE.MeshBasicMaterial;material.map?.dispose();material.dispose();}});r.dispose();r.domElement.remove();cleanupXR.current=null;
      };
      xr.addEventListener("end",()=>{stopped.current=true;setImmersive(false);session.current=null;audioNode.current?.stop();void send("session.pause",{}).catch(()=>{});cleanupXR.current?.();},{once:true});
      r.setAnimationLoop((time,frame)=>{
        if(!frame)return;
        let viewer=frame.getViewerPose(reference);
        if(!placed&&viewer){
          // Establish one stable floor origin beneath the seated viewer, facing
          // their initial heading. Both measurements and rendered target use it.
          const initial=viewer.transform, q=initial.orientation;
          const forward=new THREE.Vector3(0,0,-1).applyQuaternion(new THREE.Quaternion(q.x,q.y,q.z,q.w));
          const yaw=Math.atan2(-forward.x,-forward.z);
          reference=baseReference.getOffsetReferenceSpace(new XRRigidTransform({x:initial.position.x,y:0,z:initial.position.z},{x:0,y:Math.sin(yaw/2),z:0,w:Math.cos(yaw/2)}));
          r.xr.setReferenceSpace(reference);viewer=frame.getViewerPose(reference);if(!viewer)return;
          // Keep the controls near seated eye height, separate from the reach target.
          const eye=viewer.transform.position;board.position.set(eye.x,eye.y+.18,eye.z-1.05);
          buttons.forEach((b,i)=>b.mesh.position.set(eye.x+(i%3-1)*.34,eye.y-.18-Math.floor(i/3)*.12,eye.z-1.04));placed=true;
        }
        let point:DOMPointReadOnly|null=null;
        for(const source of xr!.inputSources){if(source.handedness!=="right"||!source.hand)continue;const joint=source.hand.get("wrist");if(!joint)continue;const pose=frame.getJointPose?.(joint,reference);if(pose && !pose.emulatedPosition)point=pose.transform.position;}
        wrist.visible=!!point;if(point)wrist.position.set(point.x,point.y,point.z);
        if(time-lastSample>=100&&!stopped.current&&!sending.current&&socket.current?.readyState===WebSocket.OPEN){
          lastSample=time;sending.current=true;
          const joint=point?webXRWristToQuest(point):null;
          const payload={seq:seq.current++,captured_at:new Date().toISOString(),coordinate_system:"quest_local",units:"meters",tracking_valid:!!joint,joints:joint?{right_wrist:joint}:{}};
          void send("tracking.frame",payload).catch(error=>{stopped.current=true;say(errorText(error));}).finally(()=>{sending.current=false;});
        }
        if(time-lastPaint>200){
          lastPaint=time;const s=state.current;
          const label=`${s?.status||"paused"} | ${s?.repetitions||0} saved repetitions | ${muteRef.current?"muted":"voice on"}`;
          ctx.fillStyle="rgba(15,38,32,.95)";ctx.fillRect(0,0,1024,512);ctx.fillStyle="white";ctx.font="bold 34px sans-serif";ctx.fillText("REACH · Seated hand-to-target",30,55);ctx.font="27px sans-serif";ctx.fillText(label,30,110);
          ctx.fillText(point?"Right wrist observed":"Right wrist not observed — no counting",30,160);
          ctx.fillText(`Target radius ${cfg.quest_reach_m.toFixed(2)}m · hold ${cfg.hold_ms}ms`,30,205);
          ctx.fillText(cfg.mode==="combined"?`Phone torso: ${s?.phone_tracking_valid?"observed":"not currently observed"}`:"Return outside amber shell after reaching green target.",30,250);
          const words=caption.current.split(" ");let line="",y=315;for(const word of words){if(ctx.measureText(line+word).width>950){ctx.fillText(line,30,y);line="";y+=40;}line+=word+" ";}ctx.fillText(line,30,y);texture.needsUpdate=true;
          if(label!==lastLabel)lastLabel=label;
        }
        r.render(scene,camera);
      });
      say("Use your left hand to point and pinch Start. Move your right wrist from outside the amber shell into the green target, hold, then return. Stop if uncomfortable.");
    }catch(error){say(`Could not enter passthrough: ${errorText(error)}. Enable hand tracking in Quest settings and allow spatial tracking permissions.`);await xr?.end();cleanupXR.current?.();}
    finally{setBusy(false);}
  }
  return <main style={{maxWidth:760,margin:"40px auto",padding:24}}>
    <Link href="/">Reach home</Link><h1 style={{marginTop:24}}>Quest 3 · seated reach</h1>
    <p className="muted">Open this page in Meta Quest Browser. This client requires passthrough and tracked hands; a controller is never substituted for a measured wrist.</p>
    <p className="note">Prototype awaiting physical Quest 3 acceptance. Stay seated, clear the reach area, and stop if uncomfortable. The fixed target uses the session’s saved floor-relative origin.</p>
    {supported===false&&<p className="error">Immersive passthrough is unavailable in this browser. Use Meta Quest Browser over HTTPS with hand tracking enabled.</p>}
    {!paired?<form className="card form" onSubmit={pair}><label>Headset pairing code<input value={code} onChange={e=>setCode(e.target.value.toUpperCase())} required minLength={6} autoComplete="off"/></label><button className="btn" disabled={busy||supported!==true}>{busy?"Connecting…":"Pair headset"}</button></form>:<div className="stack"><p>Session {device.current?.session_id}</p><button className="btn" disabled={busy||immersive||entered.current||supported!==true} onClick={enter}>Enter passthrough</button><div className="row"><button className="btn secondary" onClick={()=>void action("reconnect")}>Reconnect</button><button className="btn secondary" onClick={()=>void action("pause")}>Pause</button><button className="btn secondary" onClick={()=>void action("complete")}>Finish</button><button className="btn secondary" onClick={()=>void action("mute")}>{muted?"Unmute":"Mute"}</button></div></div>}
    <p role="status" style={{marginTop:24}}>{message}</p><p>{viewState?.status} · {viewState?.repetitions??0} saved repetitions</p><div ref={host}/>
  </main>;
}
