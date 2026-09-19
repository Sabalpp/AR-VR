// Browser-only PT equipment detector.
// Confirms the assigned exercise's equipment is actually in frame.
// NOTE: the stock model is COCO-trained. Resistance bands, foam rollers and
// dumbbells have no COCO class, so coverage is limited to the mappings below.
// Swap NEXT_PUBLIC_EQUIPMENT_MODEL_URL for custom-trained weights to extend it.

export type EquipmentKind =
  | "therapy_ball"
  | "chair"
  | "hand_weight"
  | "weighted_bag";

export type EquipmentHit = {
  kind: EquipmentKind;
  label: string;
  score: number;
  /** Normalized to 0..1 against the video's intrinsic dimensions. */
  box: { x: number; y: number; width: number; height: number };
};

/** COCO category -> PT equipment. Extend when custom weights land. */
const COCO_TO_EQUIPMENT: Record<string, { kind: EquipmentKind; label: string }> =
  {
    "sports ball": { kind: "therapy_ball", label: "Therapy ball" },
    chair: { kind: "chair", label: "Chair" },
    bottle: { kind: "hand_weight", label: "Hand weight (proxy)" },
    backpack: { kind: "weighted_bag", label: "Weighted bag (proxy)" },
  };

const WASM_URL =
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/wasm";

const DEFAULT_MODEL =
  "https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float16/1/efficientdet_lite0.tflite";

const SCORE_MIN = 0.4;

export async function createEquipmentDetector() {
  const { FilesetResolver, ObjectDetector } = await import(
    "@mediapipe/tasks-vision"
  );
  const files = await FilesetResolver.forVisionTasks(WASM_URL);
  return ObjectDetector.createFromOptions(files, {
    baseOptions: {
      modelAssetPath:
        process.env.NEXT_PUBLIC_EQUIPMENT_MODEL_URL || DEFAULT_MODEL,
    },
    runningMode: "VIDEO",
    scoreThreshold: SCORE_MIN,
    maxResults: 6,
  });
}

type RawDetection = {
  categories: Array<{ categoryName?: string; score: number }>;
  boundingBox?: {
    originX: number;
    originY: number;
    width: number;
    height: number;
  };
};

export function equipmentFromDetections(
  detections: RawDetection[] | undefined,
  video: HTMLVideoElement,
): EquipmentHit[] {
  if (!detections?.length) return [];
  const width = video.videoWidth || 1;
  const height = video.videoHeight || 1;
  const best = new Map<EquipmentKind, EquipmentHit>();

  for (const detection of detections) {
    const top = detection.categories?.[0];
    if (!top?.categoryName) continue;
    const mapped = COCO_TO_EQUIPMENT[top.categoryName];
    if (!mapped || top.score < SCORE_MIN) continue;

    const box = detection.boundingBox;
    const hit: EquipmentHit = {
      kind: mapped.kind,
      label: mapped.label,
      score: top.score,
      box: box
        ? {
            x: box.originX / width,
            y: box.originY / height,
            width: box.width / width,
            height: box.height / height,
          }
        : { x: 0, y: 0, width: 0, height: 0 },
    };

    // Keep only the highest-confidence instance per kind.
    const prior = best.get(mapped.kind);
    if (!prior || hit.score > prior.score) best.set(mapped.kind, hit);
  }

  return [...best.values()].sort((a, b) => b.score - a.score);
}

/** Draw equipment boxes. Call AFTER drawPose so boxes sit above the skeleton. */
export function drawEquipment(
  canvas: HTMLCanvasElement,
  hits: readonly EquipmentHit[],
) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.save();
  ctx.lineWidth = 3;
  ctx.strokeStyle = "#246f60";
  ctx.font = "600 16px Arial, Helvetica, sans-serif";

  for (const hit of hits) {
    const x = hit.box.x * canvas.width;
    const y = hit.box.y * canvas.height;
    const width = hit.box.width * canvas.width;
    const height = hit.box.height * canvas.height;
    ctx.strokeRect(x, y, width, height);

    const text = `${hit.label} ${Math.round(hit.score * 100)}%`;
    const pad = 6;
    const textWidth = ctx.measureText(text).width;
    ctx.fillStyle = "#246f60";
    ctx.fillRect(x, Math.max(0, y - 24), textWidth + pad * 2, 24);
    ctx.fillStyle = "#f6f7f2";
    ctx.fillText(text, x + pad, Math.max(16, y - 6));
  }
  ctx.restore();
}
