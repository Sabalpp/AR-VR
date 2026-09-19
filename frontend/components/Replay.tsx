"use client";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { Play, Pause } from "lucide-react";
import { Frame } from "@/lib/api";
import { bones } from "@/lib/camera";
export type ReplayFrame = Frame & {
  measurement: number | null;
  observed_valid: boolean;
  status: string;
  device_id: string;
  source: string;
  measurement_kind?: string;
  trunk_review?: boolean;
  attempt_event?: { id: string; device_id: string; outcome: string; started_at: string; ended_at: string; start_seq: number; end_seq: number; best_measurement: number; target_threshold: number; measurement_kind: string };
};
export default function Replay({
  frames,
  repetitions,
  gapMs = 750,
}: {
  frames: ReplayFrame[];
  repetitions: {
    seq: number;
    captured_at: string;
    source: string;
    device_id: string;
    authoritative: boolean;
  }[];
  gapMs?: number;
}) {
  const mount = useRef<HTMLDivElement>(null);
  const [source, setSource] = useState(frames[0]?.device_id || "");
  const selected = frames.filter((f) => f.device_id === source);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const sceneRef = useRef<{
    renderer: THREE.WebGLRenderer;
    scene: THREE.Scene;
    camera: THREE.OrthographicCamera;
    group: THREE.Group;
  } | null>(null);
  const first = selected.length ? Date.parse(selected[0].captured_at) : 0;
  const duration = selected.length
    ? (Date.parse(selected[selected.length - 1].captured_at) - first) / 1000
    : 0;
  let index = selected.findLastIndex(
    (f) => (Date.parse(f.captured_at) - first) / 1000 <= time,
  );
  if (index < 0) index = 0;
  const frame = selected[index];
  const age = frame
    ? time - (Date.parse(frame.captured_at) - first) / 1000
    : Infinity;
  const observed = !!frame && frame.observed_valid && age < gapMs / 1000;
  useEffect(() => {
    if (!mount.current) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      return;
    }
    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(-1.5, 1.5, 1.2, -1.2, 0.1, 100);
    camera.position.z = 5;
    const group = new THREE.Group();
    scene.add(group);
    mount.current.appendChild(renderer.domElement);
    sceneRef.current = { renderer, scene, camera, group };
    const resize = () => {
      renderer.setSize(mount.current?.clientWidth || 500, 340);
      renderer.render(scene, camera);
    };
    resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      renderer.dispose();
      renderer.domElement.remove();
      group.children.forEach((obj) => {
        if (obj instanceof THREE.Line || obj instanceof THREE.Mesh) {
          obj.geometry.dispose();
          (obj.material as THREE.Material).dispose();
        }
      });
    };
  }, []);
  useEffect(() => {
    const s = sceneRef.current;
    if (!s) return;
    for (const obj of [...s.group.children]) {
      s.group.remove(obj);
      if (obj instanceof THREE.Line || obj instanceof THREE.Mesh) {
        obj.geometry.dispose();
        (obj.material as THREE.Material).dispose();
      }
    }
    if (observed && frame) {
      const aspect = frame.image_width / frame.image_height;
      const pos = (name: string) => {
        const j = frame.joints[name];
        return frame.coordinate_system === "image_normalized"
          ? new THREE.Vector3((j.x - 0.5) * 2 * aspect, (0.5 - j.y) * 2, 0)
          : new THREE.Vector3(j.x, j.y - 1, -(j.z || 0));
      };
      for (const [a, b] of bones) {
        const ja = frame.joints[a],
          jb = frame.joints[b];
        if (!ja || !jb || ja.visibility < 0.65 || jb.visibility < 0.65)
          continue;
        const line = new THREE.Line(
          new THREE.BufferGeometry().setFromPoints([pos(a), pos(b)]),
          new THREE.LineBasicMaterial({
            color: ja.inferred || jb.inferred ? "#c78c39" : "#347563",
          }),
        );
        s.group.add(line);
      }
      for (const [name, j] of Object.entries(frame.joints)) {
        if (j.visibility < 0.65) continue;
        const dot = new THREE.Mesh(
          new THREE.SphereGeometry(0.025, 10, 8),
          new THREE.MeshBasicMaterial({
            color: j.inferred ? "#c78c39" : "#347563",
          }),
        );
        dot.position.copy(pos(name));
        s.group.add(dot);
      }
    }
    s.renderer.render(s.scene, s.camera);
  }, [frame, observed]);
  useEffect(() => {
    if (!playing) return;
    let last = performance.now();
    const timer = setInterval(() => {
      const now = performance.now();
      setTime((t) => {
        const n = t + (now - last) / 1000;
        if (n >= duration) {
          setPlaying(false);
          return duration;
        }
        return n;
      });
      last = now;
    }, 50);
    return () => clearInterval(timer);
  }, [playing, duration]);
  const width = 800,
    height = 160;
  const x = (date: string) =>
    duration ? ((Date.parse(date) - first) / 1000 / duration) * width : 0;
  const values = selected
    .filter((f) => f.measurement != null)
    .map((f) => f.measurement!);
  const max = Math.max(...values, 1);
  const y = (n: number) => height - 15 - (n / max) * (height - 30);
  const paths: string[] = [];
  let path = "";
  for (let i = 0; i < selected.length; i++) {
    const f = selected[i];
    const gap =
      i > 0 &&
      Date.parse(f.captured_at) - Date.parse(selected[i - 1].captured_at) >
        gapMs;
    if (!f.observed_valid || f.measurement == null || gap) {
      if (path) paths.push(path);
      path = "";
    }
    if (f.observed_valid && f.measurement != null)
      path += `${path ? "L" : "M"}${x(f.captured_at)},${y(f.measurement)} `;
  }
  if (path) paths.push(path);
  return (
    <div className="stack">
      <section id="attempt-review" className="stack">
        <h3>Which attempts need a closer look?</h3>
        {frames.filter(f => f.attempt_event).map(f => {
          const a = f.attempt_event!;
          const unit = a.measurement_kind === "quest_hand_target_distance_m" ? "m" : "°";
          return <button key={a.id} id={`attempt-${a.id}`} className="btn secondary" style={{display:"block",textAlign:"left"}} onClick={() => {
            const deviceFrames = frames.filter(item => item.device_id === a.device_id);
            const origin = Math.min(...deviceFrames.map(item => Date.parse(item.captured_at)));
            setSource(a.device_id); setTime(Math.max(0, (Date.parse(a.started_at) - origin) / 1000)); setPlaying(false);
          }}>
            {a.outcome === "completed" ? "Completed reach and return" : a.outcome === "target_not_held" ? "Review: target was not held" : "Interrupted tracking"}
            <span className="note" style={{display:"block"}}>Best observed {a.best_measurement.toFixed(2)}{unit} · target {a.target_threshold.toFixed(2)}{unit} · frames {a.start_seq}–{a.end_seq}. Select to inspect the attempt.</span>
          </button>;
        })}
        {!frames.some(f => f.attempt_event) && <p className="note">No complete attempt segments were recorded. Older sessions may not include attempt indexing.</p>}
      </section>
      <label>
        Tracking source
        <select
          value={source}
          onChange={(e) => {
            setSource(e.target.value);
            setTime(0);
            setPlaying(false);
          }}
        >
          {Array.from(new Set(frames.map((f) => f.device_id))).map((id) => (
            <option key={id} value={id}>
              {frames.find((f) => f.device_id === id)?.source} ·{" "}
              {id.slice(0, 8)}
            </option>
          ))}
        </select>
      </label>
      <div className="replay" style={{ position: "relative" }}>
        <div ref={mount} />
        <span className="camera-badge">
          {observed ? "Observed pose" : "No observed tracking at this time"}
        </span>
      </div>
      <div className="row">
        <button
          className="btn secondary"
          aria-label={playing ? "Pause playback" : "Play playback"}
          onClick={() => {
            if (time >= duration) setTime(0);
            setPlaying(!playing);
          }}
        >
          {playing ? <Pause size={16} /> : <Play size={16} />}
        </button>
        <input
          aria-label="Replay time"
          type="range"
          min={0}
          max={duration || 1}
          step={0.05}
          value={time}
          onChange={(e) => setTime(+e.target.value)}
        />
        <span className="note">
          {time.toFixed(1)} / {duration.toFixed(1)}s
        </span>
      </div>
      <div>
        <h3>
          {frame?.measurement_kind === "projected_2d_trunk_lean_degrees"
            ? "Projected trunk tilt from image vertical (°)"
            : frame?.coordinate_system === "quest_local"
            ? "Hand-to-target distance (m)"
            : "Projected elbow angle (°)"}
        </h3>
        {frame?.measurement_kind === "projected_2d_trunk_lean_degrees" && (
          <p className="note">Separate phone observation. A level side-on camera is required; this is not calibrated 3D trunk flexion or a diagnosis of compensation. {observed && frame.trunk_review ? "Review flag at this sample." : ""}</p>
        )}
        <svg
          className="chart"
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label="Observed movement over time; breaks indicate missing tracking"
        >
          <rect width={width} height={height} fill="#f7f8f3" />
          {selected.map((f, i) => {
            if (i === 0) return null;
            const prev = selected[i - 1];
            return !f.observed_valid ||
              Date.parse(f.captured_at) - Date.parse(prev.captured_at) >
                gapMs ? (
              <rect
                key={i}
                x={x(prev.captured_at)}
                y={0}
                width={Math.max(x(f.captured_at) - x(prev.captured_at), 2)}
                height={height}
                fill="#f5dfc6"
              />
            ) : null;
          })}
          {paths.map((p, i) => (
            <path key={i} d={p} fill="none" stroke="#347563" strokeWidth={2} />
          ))}
          {repetitions
            .filter((r) => r.device_id === source && r.authoritative)
            .map((r, i) => (
              <line
                key={i}
                x1={x(r.captured_at)}
                x2={x(r.captured_at)}
                y1={0}
                y2={height}
                stroke="#85a65c"
                strokeDasharray="4 4"
              />
            ))}
          <line
            x1={duration ? (time / duration) * width : 0}
            x2={duration ? (time / duration) * width : 0}
            y1={0}
            y2={height}
            stroke="#203e37"
          />
        </svg>
        <p className="note">
          Green dashed lines: repetition events · Amber: missing or invalid
          tracking / inferred joints. No poses are interpolated across gaps.
          Phone depth is not rendered as physical distance.
        </p>
      </div>
    </div>
  );
}
