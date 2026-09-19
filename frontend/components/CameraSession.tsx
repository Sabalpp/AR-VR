"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Camera, Pause, Play, Square, Volume2, VolumeX } from "lucide-react";
import { api, Frame, Session, errorText } from "@/lib/api";
import { createTracker, frameFromLandmarks, drawPose } from "@/lib/camera";
import { ErrorBox } from "./Shell";
import { useSession } from "@/lib/store";
type State = {
  status: string;
  repetitions: number;
  phase: string;
  last_measurement: number | null;
  tracking_valid: boolean;
  phone_setup_ready?: boolean;
  phone_trunk_lean_deg?: number | null;
  phone_trunk_review?: boolean;
};
type Device = { device_token: string; device_id: string; session_id: string };
export default function CameraSession({ id }: { id: string }) {
  const router = useRouter();
  const video = useRef<HTMLVideoElement>(null),
    canvas = useRef<HTMLCanvasElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const tracker = useRef<Awaited<ReturnType<typeof createTracker>> | null>(
    null,
  );
  const queue = useRef<Frame[]>([]);
  const sequence = useRef(0);
  const running = useRef(false);
  const paused = useRef(false);
  const uploading = useRef(false);
  const draining = useRef(false);
  const device = useRef<Device | null>(null);
  const animation = useRef(0);
  const lastTime = useRef(-1);
  const lastCapture = useRef(0);
  const audio = useRef<AudioContext | null>(null);
  const audioSource = useRef<AudioBufferSourceNode | null>(null);
  const lastCue = useRef(0);
  const mutedRef = useRef(true);
  const previousReps = useRef(0);
  const previousTracking = useRef(false);
  const speechCache = useRef(new Map<string, AudioBuffer>());
  const [started, setStarted] = useState(false);
  const [isPaused, setPaused] = useState(false);
  const [muted, setMuted] = useState(true);
  const [error, setError] = useState("");
  const [connection, setConnection] = useState("Not connected");
  const [tracking, setTracking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [state, setState] = useState<State>();
  const [finished, setFinished] = useState(false);
  const [pain, setPain] = useState(0),
    [effort, setEffort] = useState(0),
    [notes, setNotes] = useState("");
  const [saved, setSaved] = useState(false);
  const [pairCode, setPairCode] = useState("");
  const [target, setTarget] = useState<number>();
  const [mode, setMode] = useState<string>("phone");
  const modeRef = useRef("phone");
  const wakeLock = useRef<WakeLockSentinel | null>(null);
  const [wakeNote, setWakeNote] = useState("");
  async function keepAwake() {
    if (wakeLock.current && !wakeLock.current.released) return;
    try {
      if (!("wakeLock" in navigator)) throw new Error("unsupported");
      wakeLock.current = await navigator.wakeLock.request("screen");
      setWakeNote("Screen wake lock active while this page stays visible.");
    } catch {
      setWakeNote("Keep this page open and disable auto-lock during the session; this browser could not keep the screen awake.");
    }
  }
  function acceptState(next: State) {
    setState(next);
    if (modeRef.current !== "phone") {
      paused.current = next.status !== "active";
      setPaused(paused.current);
    }
    if (next.status === "complete") {
      running.current = false;
      stream.current?.getTracks().forEach((track) => { track.onended = null; track.onmute = null; track.stop(); });
      void wakeLock.current?.release();
      if (queue.current.length) {
        setError(`${queue.current.length} phone samples were not acknowledged on this phone before headset completion. Review the saved replay to confirm coverage.`);
        queue.current = [];
      }
      setFinished(true);
    }
  }
  async function headsetCode() {
    try {
      const p = await api<{ code: string }>(`/sessions/${id}/pairing`, { source: "quest" });
      setPairCode(p.code);
    } catch (e) { setError(errorText(e)); }
  }
  useEffect(() => {
    api<Session>(`/sessions/${id}`)
      .then((session) => {
        setState(session.state);
        setMode(session.mode);
        modeRef.current = session.mode;
        setTarget(Number(session.config_snapshot.target_repetitions));
        if (session.state.status === "complete") setFinished(true);
        if (session.state.status === "paused") {
          paused.current = true;
          setPaused(true);
        }
      })
      .catch((e) => setError(errorText(e)));
  }, [id]);
  useEffect(() => {
    if (mode === "phone" || finished) return;
    let pending = false;
    const timer = setInterval(async () => {
      if (pending) return;
      pending = true;
      try {
        const session = await api<Session>(`/sessions/${id}`, undefined, device.current?.device_token);
        acceptState(session.state);
      } catch (e) { setError(errorText(e)); }
      finally { pending = false; }
    }, 500);
    return () => clearInterval(timer);
  }, [id, mode, finished]);
  async function flush() {
    if (uploading.current || !queue.current.length || !device.current) return;
    uploading.current = true;
    const batch = queue.current.slice(0, 30);
    try {
      const result = await api<{ state: State }>(
        `/sessions/${id}/movement`,
        { frames: batch },
        device.current.device_token,
      );
      queue.current.splice(0, batch.length);
      acceptState(result.state);
      if (result.state.repetitions > previousReps.current)
        void playCue("reach");
      previousReps.current = result.state.repetitions;
      setConnection("Connected · saved to workspace");
    } catch (e) {
      setConnection("Reconnecting · buffered on this phone");
      setError(errorText(e));
    } finally {
      uploading.current = false;
    }
  }
  async function pauseSession(reason?: string) {
    paused.current = true;
    setPaused(true);
    setTracking(false);
    if (reason) setError(reason);
    try {
      await api(`/sessions/${id}/pause`, {}, device.current?.device_token);
    } catch (e) {
      setError(errorText(e));
    }
  }
  useEffect(() => {
    const timer = setInterval(() => void flush(), 250);
    const visibility = () => {
      if (document.hidden && running.current)
        void pauseSession(
          "Session paused because this page moved to the background. Return and resume when ready.",
        );
      else if (running.current) void keepAwake();
    };
    document.addEventListener("visibilitychange", visibility);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", visibility);
      running.current = false;
      cancelAnimationFrame(animation.current);
      stream.current?.getTracks().forEach((t) => t.stop());
      tracker.current?.close();
      void audio.current?.close();
      void wakeLock.current?.release();
    };
  }, [id]);
  async function start() {
    let stage = "Connecting session";
    setBusy(true);
    setError("");
    try {
      if (!window.isSecureContext)
        throw new Error(
          "Camera access needs the public HTTPS address. Open the secure link from setup.",
        );
      if (!navigator.mediaDevices?.getUserMedia)
        throw new Error(
          "This browser cannot access a camera. Try Safari or Chrome over HTTPS.",
        );
      const stored = sessionStorage.getItem(`device-${id}`);
      if (stored) device.current = JSON.parse(stored);
      else {
        const pairing = await api<{ code: string }>(`/sessions/${id}/pairing`, {
          source: "phone",
        });
        device.current = await api<Device>("/devices/pair", {
          code: pairing.code,
          label: "Phone camera",
          expected_source: "phone",
        });
        sessionStorage.setItem(`device-${id}`, JSON.stringify(device.current));
      }
      const before = Date.now();
      const server = await api<{ server_time: string }>("/time");
      const clockOffset =
        (before + Date.now()) / 2 - Date.parse(server.server_time);
      await api(
        `/sessions/${id}/device-status`,
        { clock_offset_ms: clockOffset },
        device.current!.device_token,
      );
      sequence.current = Number(
        sessionStorage.getItem(`seq-${device.current?.device_id}`) || 0,
      );
      stage = "Opening camera";
      stream.current = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "user",
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });
      for (const track of stream.current.getVideoTracks()) {
        track.onended = () =>
          void pauseSession(
            "Camera interrupted. Reload the session to reconnect your camera.",
          );
        track.onmute = () =>
          void pauseSession(
            "Camera unavailable. Bring the camera back before resuming.",
          );
      }
      if (!video.current) throw new Error("Camera preview unavailable");
      video.current.srcObject = stream.current;
      stage = "Starting camera preview";
      await video.current.play();
      stage = "Loading camera movement tracker";
      tracker.current = await createTracker();
      running.current = true;
      await keepAwake();
      setStarted(true);
      setConnection("Connected · waiting for movement");
      const tick = (now: number) => {
        if (!running.current) return;
        const v = video.current;
        if (
          v &&
          tracker.current &&
          !draining.current &&
          (!paused.current || modeRef.current === "combined") &&
          v.readyState >= 2 &&
          now - lastCapture.current >= 100 &&
          v.currentTime !== lastTime.current
        ) {
          lastCapture.current = now;
          lastTime.current = v.currentTime;
          try {
            const result = tracker.current.detectForVideo(v, now);
            const frame = frameFromLandmarks(
              result.landmarks[0],
              v,
              sequence.current++,
              modeRef.current === "combined",
            );
            sessionStorage.setItem(
              `seq-${device.current?.device_id}`,
              String(sequence.current),
            );
            if (canvas.current) drawPose(canvas.current, frame);
            setTracking(frame.tracking_valid);
            if (previousTracking.current && !frame.tracking_valid)
              void playCue("tracking_lost");
            previousTracking.current = frame.tracking_valid;
            if (queue.current.length >= 300) {
              void pauseSession(
                "Connection buffer is full. Recording paused; reconnect before continuing.",
              );
            } else queue.current.push(frame);
          } catch (e) {
            void pauseSession(`Tracking stopped: ${errorText(e)}`);
          }
        }
        animation.current = requestAnimationFrame(tick);
      };
      animation.current = requestAnimationFrame(tick);
    } catch (e) {
      const name = e instanceof Error ? e.name : "";
      const cameraErrors: Record<string, string> = {
        NotAllowedError:
          "Camera permission is blocked. Allow camera access in this site’s browser settings, then tap Allow camera & begin again.",
        PermissionDeniedError:
          "Camera permission was denied. Allow camera access in your browser’s site settings, then try again.",
        NotFoundError:
          "No camera was found. Open this page on a phone or a device with a connected camera.",
        DevicesNotFoundError:
          "No camera was found. Use a device with a connected camera.",
        NotReadableError:
          "The camera could not start. Close other apps using the camera, then try again.",
        TrackStartError:
          "The camera is in use or unavailable. Close other camera apps and try again.",
        NotSupportedError:
          "This browser does not support the camera or video features needed here. Open the HTTPS link in a current Safari or Chrome browser.",
        OverconstrainedError:
          "This camera cannot use the requested capture settings. Try another camera or phone browser.",
        SecurityError:
          "Camera access is restricted by this browser. Open the public HTTPS link directly and allow camera access.",
      };
      setError(
        stage === "Connecting session"
          ? errorText(e)
          : cameraErrors[name] ||
              `${stage} failed: ${errorText(e)}. Try a current phone browser with camera access.`,
      );
      stream.current?.getTracks().forEach((t) => { t.onended = null; t.onmute = null; t.stop(); });
    } finally {
      setBusy(false);
    }
  }
  async function resume() {
    try {
      await flush();
      if (queue.current.length >= 300)
        throw new Error(
          "Still offline. Wait for the saved connection before resuming.",
        );
      await api(`/sessions/${id}/resume`, {}, device.current?.device_token);
      setError("");
      paused.current = false;
      setPaused(false);
    } catch (e) {
      setError(errorText(e));
    }
  }
  async function finish() {
    setBusy(true);
    draining.current = true;
    paused.current = true;
    setPaused(true);
    try {
      if (uploading.current)
        throw new Error(
          "A batch is still saving. Wait a moment and finish again.",
        );
      while (queue.current.length) {
        const before = queue.current.length;
        await flush();
        if (queue.current.length === before)
          throw new Error(
            "Movement is not saved yet. Reconnect and try finishing again.",
          );
      }
      await api(`/sessions/${id}/complete`, {}, device.current?.device_token);
      running.current = false;
      stream.current?.getTracks().forEach((t) => { t.onended = null; t.onmute = null; t.stop(); });
      void wakeLock.current?.release();
      setFinished(true);
      void playCue("complete");
    } catch (e) {
      setError(errorText(e));
    } finally {
      draining.current = false;
      setBusy(false);
    }
  }
  async function playCue(cue: string) {
    if (
      modeRef.current !== "phone" ||
      mutedRef.current ||
      !audio.current ||
      Date.now() - lastCue.current < 8000
    )
      return;
    lastCue.current = Date.now();
    try {
      let buffer = speechCache.current.get(cue);
      if (!buffer) {
        const response = await fetch(`/api/v1/speech/${cue}`, {
          headers: { Authorization: `Bearer ${useSession.getState().token}` },
          signal: AbortSignal.timeout(12000),
        });
        if (!response.ok) throw new Error("Voice unavailable");
        buffer = await audio.current.decodeAudioData(
          await response.arrayBuffer(),
        );
        speechCache.current.set(cue, buffer);
      }
      if (mutedRef.current || audio.current.state === "closed") return;
      const source = audio.current.createBufferSource();
      source.buffer = buffer;
      source.connect(audio.current.destination);
      audioSource.current = source;
      source.start();
    } catch {
      setError(
        "Voice is unavailable. Follow the written instructions; tracking continues normally.",
      );
    }
  }
  async function sound() {
    if (modeRef.current !== "phone") return;
    if (!mutedRef.current) {
      mutedRef.current = true;
      audioSource.current?.stop();
      setMuted(true);
      return;
    }
    try {
      if (!audio.current || audio.current.state === "closed")
        audio.current = new AudioContext();
      await audio.current.resume();
      mutedRef.current = false;
      setMuted(false);
      void playCue("setup");
    } catch {
      setError("Tap voice again to allow browser audio.");
    }
  }
  async function checkin(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api(`/sessions/${id}/checkin`, { pain, effort, notes });
      setSaved(true);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  if (saved)
    return (
      <div className="stack">
        <div className="hero">
          <span className="eyebrow">SESSION SAVED</span>
          <h1 style={{ marginTop: 18 }}>A step worth taking.</h1>
          <p className="muted" style={{ marginTop: 16 }}>
            Your movement and check-in are ready for your therapist to review.
          </p>
        </div>
        <button className="btn" onClick={() => router.push("/patient")}>
          Back to my plan
        </button>
      </div>
    );
  if (finished)
    return (
      <div className="stack">
        <div>
          <div className="step">LAST STEP · CHECK IN</div>
          <h1>How did that feel?</h1>
          <p className="muted" style={{ marginTop: 12 }}>
            Your experience matters alongside the movement.
          </p>
        </div>
        <form className="card form" onSubmit={checkin}>
          <label>
            Pain reported by you · {pain}/10
            <input
              type="range"
              min={0}
              max={10}
              value={pain}
              onChange={(e) => setPain(+e.target.value)}
            />
          </label>
          <label>
            Effort reported by you · {effort}/10
            <input
              type="range"
              min={0}
              max={10}
              value={effort}
              onChange={(e) => setEffort(+e.target.value)}
            />
          </label>
          <label>
            Anything you’d like your therapist to know?
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={2000}
            />
          </label>
          <ErrorBox message={error} />
          <button className="btn" disabled={busy}>
            Save my check-in
          </button>
        </form>
      </div>
    );
  if (mode === "quest") return (
    <div className="stack">
      <h1>Connect your headset</h1>
      <p>Stay seated, clear the area around your chair and turn passthrough on. Use the headset for pause, resume, finish and mute. This phone will stay silent.</p>
      <p className="note">Open this website’s /quest page in Meta Quest Browser and enter the code there. A compatible Unity client can use the same code. Physical headset acceptance is still pending.</p>
      <ErrorBox message={error} />
      <button className="btn" onClick={headsetCode}>Get a headset pairing code</button>
      {pairCode && <div className="card"><p className="code">{pairCode}</p><p className="note">Enter this single-use code at this website’s /quest page in Meta Quest Browser within five minutes.</p></div>}
      <p role="status">{state?.status} · {state?.repetitions ?? 0} saved repetitions</p>
      <button className="btn secondary" onClick={() => pauseSession()}>Emergency pause</button>
      <button className="btn secondary" onClick={finish} disabled={busy}>Finish from browser</button>
    </div>
  );
  return (
    <div className="stack">
      <div>
        <div className="step">
          {started ? "MOVEMENT SESSION" : "STEP 1 · CAMERA SETUP"}
        </div>
        <h1>{started ? "One reach at a time." : "Find your good side."}</h1>
        <p className="muted" style={{ marginTop: 12 }}>
          {mode === "combined"
            ? "Before putting on the headset, sit sideways to a level, stationary phone. Keep your right shoulder and hip visible for at least one second. Stay seated with Quest passthrough on."
            : "Sit sideways to the camera so your right shoulder, elbow and wrist are visible. Bend your elbow, then extend and return; hold each position briefly."}
        </p>
      </div>
      <div className="camera">
        <video ref={video} muted playsInline autoPlay />
        <canvas ref={canvas} />
        <div className="camera-badge" role="status">
          {!started
            ? "Camera off"
            : isPaused && mode !== "combined"
              ? "Paused"
              : tracking
                ? mode === "combined" ? "Shoulder and hip visible" : "Right arm visible"
                : mode === "combined" ? "Bring your right shoulder and hip into view" : "Tracking lost · bring your right arm into view"}
        </div>
      </div>
      <ErrorBox message={error} />
      {!started ? (
        <button className="btn" disabled={busy} onClick={start}>
          <Camera size={18} />
          {busy ? "Opening camera & loading tracker…" : "Allow camera & begin"}
        </button>
      ) : (
        <>
          <div className="row between card">
            <div>
              <p className="eyebrow">SAVED REPETITIONS</p>
              <div className="stat-number">
                {state?.repetitions ?? "—"}
                {target ? (
                  <span style={{ fontSize: 16, color: "var(--muted)" }}>
                    {" "}
                    / {target}
                  </span>
                ) : null}
              </div>
            </div>
            <div>
              <p className="eyebrow">{mode === "combined" ? "PROJECTED TRUNK TILT" : "PROJECTED ELBOW ANGLE"}</p>
              <div className="stat-number">
                {tracking && (mode === "combined" ? state?.phone_trunk_lean_deg : state?.last_measurement) != null
                  ? `${Math.round((mode === "combined" ? state?.phone_trunk_lean_deg : state?.last_measurement)!)}°`
                  : "—"}
              </div>
            </div>
          </div>
          <p role="status" className="note">
            {connection} · {state?.phase || "Waiting for a valid movement"}
          </p>
          <div className="row">
            <button
              className="btn secondary"
              style={{ flex: 1 }}
              onClick={() => (isPaused && mode === "phone" ? resume() : pauseSession())}
            >
              {isPaused ? <Play size={18} /> : <Pause size={18} />}{" "}
              {mode === "combined" ? "Emergency pause" : isPaused ? "Resume" : "Pause"}
            </button>
            <button
              className="btn"
              style={{ flex: 1 }}
              onClick={finish}
              disabled={busy}
            >
              <Square size={16} />
              Finish
            </button>
            {mode === "phone" && <button
              className="btn secondary"
              aria-label={
                muted ? "Enable voice guidance" : "Mute voice guidance"
              }
              onClick={sound}
            >
              {muted ? <VolumeX size={18} /> : <Volume2 size={18} />}
            </button>}
          </div>
        </>
      )}
      <p className="note">{wakeNote}</p>
      <p className="note">No video leaves this phone; only timestamped landmarks are sent.</p>
      <p className="note">{mode === "combined"
        ? "Phone trunk tilt is measured relative to image vertical, not calibrated 3D flexion. Review flags are observations, not a diagnosis. Quest hand positions drive the backend repetition counter. Phone voice is disabled; headset audio and controls are required."
        : "Phone measurements are projected 2D elbow angles, not physical reach distance. Missing or hidden joints do not count as repetitions."}</p>
      {mode === "combined" && <p role="status">{started && tracking && state?.phone_setup_ready ? "Phone setup ready. Leave the phone visible and recording, pair the headset, then start from Quest." : "Waiting for stable shoulder and hip tracking before headset setup."}</p>}
      {mode === "combined" && tracking && state?.phone_trunk_review && <p className="note">Trunk tilt review flag: the projected angle crossed the session’s demonstration threshold. Camera position affects this reading.</p>}
      {mode === "combined" && <button
        className="btn secondary"
        disabled={!started || !tracking || !state?.phone_setup_ready}
        onClick={headsetCode}
      >
        Get a headset pairing code
      </button>}
      {pairCode && (
        <div className="card">
          <p className="eyebrow">TEMPORARY QUEST CODE</p>
          <p className="code">{pairCode}</p>
          <p className="note">
            Enter this code at /quest in Meta Quest Browser within five minutes. Leave the phone open and visible. Start, pause, resume and finish from the headset; the browser controls are an emergency fallback.
          </p>
        </div>
      )}
    </div>
  );
}
