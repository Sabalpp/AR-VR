// Browser-only pose adapter. Normalized depth is retained for provenance, never used as meters.
import type { Frame, Joint } from "./api";
export const jointIndices: Record<string, number> = {
  nose: 0,
  left_shoulder: 11,
  right_shoulder: 12,
  left_elbow: 13,
  right_elbow: 14,
  left_wrist: 15,
  right_wrist: 16,
  left_hip: 23,
  right_hip: 24,
  left_knee: 25,
  right_knee: 26,
  left_ankle: 27,
  right_ankle: 28,
};
export const bones = [
  ["left_shoulder", "right_shoulder"],
  ["left_shoulder", "left_elbow"],
  ["left_elbow", "left_wrist"],
  ["right_shoulder", "right_elbow"],
  ["right_elbow", "right_wrist"],
  ["left_shoulder", "left_hip"],
  ["right_shoulder", "right_hip"],
  ["left_hip", "right_hip"],
  ["left_hip", "left_knee"],
  ["right_hip", "right_knee"],
  ["left_knee", "left_ankle"],
  ["right_knee", "right_ankle"],
];
export async function createTracker() {
  const { FilesetResolver, PoseLandmarker } =
    await import("@mediapipe/tasks-vision");
  const files = await FilesetResolver.forVisionTasks(
    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/wasm",
  );
  return PoseLandmarker.createFromOptions(files, {
    baseOptions: {
      modelAssetPath:
        process.env.NEXT_PUBLIC_MEDIAPIPE_MODEL_URL ||
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
    },
    runningMode: "VIDEO",
    numPoses: 1,
    minPoseDetectionConfidence: 0.65,
    minTrackingConfidence: 0.65,
  });
}
export function frameFromLandmarks(
  landmarks:
    Array<{ x: number; y: number; z: number; visibility?: number }> | undefined,
  video: HTMLVideoElement,
  seq: number,
  trunkOnly = false,
): Frame {
  const joints: Record<string, Joint> = {};
  if (landmarks)
    for (const [name, index] of Object.entries(jointIndices)) {
      const p = landmarks[index];
      if (p)
        joints[name] = {
          x: p.x,
          y: p.y,
          z: p.z,
          visibility: p.visibility ?? 0,
          inferred: false,
        };
    }
  return {
    seq,
    captured_at: new Date().toISOString(),
    coordinate_system: "image_normalized",
    units: "normalized",
    image_width: video.videoWidth,
    image_height: video.videoHeight,
    tracking_valid: (trunkOnly ? ["right_shoulder", "right_hip"] : ["right_shoulder", "right_elbow", "right_wrist"]).every(
      (n) => joints[n]?.visibility >= 0.65 && joints[n].x >= 0 && joints[n].x <= 1 && joints[n].y >= 0 && joints[n].y <= 1,
    ),
    joints,
  };
}
export function drawPose(canvas: HTMLCanvasElement, frame: Frame) {
  canvas.width = frame.image_width;
  canvas.height = frame.image_height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.lineWidth = 4;
  ctx.strokeStyle = "#d5edac";
  for (const [a, b] of bones) {
    const p = frame.joints[a],
      q = frame.joints[b];
    if (!p || !q || p.visibility < 0.65 || q.visibility < 0.65) continue;
    ctx.beginPath();
    ctx.moveTo(p.x * canvas.width, p.y * canvas.height);
    ctx.lineTo(q.x * canvas.width, q.y * canvas.height);
    ctx.stroke();
  }
  for (const p of Object.values(frame.joints)) {
    if (p.visibility < 0.65) continue;
    ctx.beginPath();
    ctx.fillStyle = "#f7f5df";
    ctx.arc(p.x * canvas.width, p.y * canvas.height, 5, 0, Math.PI * 2);
    ctx.fill();
  }
}
