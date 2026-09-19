// Synthesises the elbow-angle signal a seated-reach session actually produces.
// Shape and thresholds mirror backend/app/services/movement.py: the counter is
// deterministic, a repetition needs a held reach and a held return, and frames
// the tracker is not confident in are dropped rather than interpolated.

export const SAMPLE_HZ = 12;
export const REST_DEG = 62;
export const PEAK_DEG = 154;
export const REACH_THRESHOLD_DEG = 150;
export const RETURN_THRESHOLD_DEG = 70;
export const HOLD_MS = 400;

export type Sample = {
  /** Seconds from session start. */
  t: number;
  angle: number;
  /** False where tracking confidence fell below the visibility floor. */
  valid: boolean;
};

export type RepEvent = { t: number; index: number };

export type Trace = {
  samples: Sample[];
  reps: RepEvent[];
  duration: number;
  /** Seconds [from, to] where tracking was lost. */
  dropout: [number, number];
};

const easeInOut = (p: number) =>
  p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;

type Phase = { seconds: number; from: number; to: number; hold?: boolean };

function cycle(): Phase[] {
  return [
    { seconds: 0.9, from: REST_DEG, to: PEAK_DEG },
    { seconds: 0.7, from: PEAK_DEG, to: PEAK_DEG, hold: true },
    { seconds: 0.9, from: PEAK_DEG, to: REST_DEG },
    { seconds: 1.0, from: REST_DEG, to: REST_DEG },
  ];
}

/** Deterministic: same trace every render, no Math.random hydration drift. */
function jitter(index: number, amplitude: number) {
  return Math.sin(index * 12.9898) * amplitude;
}

export function buildTrace(repCount = 4): Trace {
  const samples: Sample[] = [];
  const reps: RepEvent[] = [];
  const step = 1 / SAMPLE_HZ;

  // Tracking drops mid-way through the third cycle, so the page can show a gap
  // that costs a repetition instead of pretending the signal was continuous.
  const dropoutCycle = 2;
  let t = 0.8;

  // Lead-in at rest.
  for (let i = 0; i < Math.round(0.8 / step); i++) {
    samples.push({
      t: i * step,
      angle: REST_DEG + jitter(i, 1.1),
      valid: true,
    });
  }

  let dropoutFrom = 0;
  let dropoutTo = 0;

  for (let c = 0; c < repCount; c++) {
    const isDropout = c === dropoutCycle;
    for (const phase of cycle()) {
      const count = Math.round(phase.seconds / step);
      for (let i = 0; i < count; i++) {
        const p = count <= 1 ? 1 : i / (count - 1);
        const base = phase.from + (phase.to - phase.from) * easeInOut(p);
        const noise = jitter(samples.length, phase.hold ? 0.7 : 1.4);

        // Lose tracking across the rising edge of the dropout cycle only.
        const rising = phase.to > phase.from;
        const valid = !(isDropout && rising && p > 0.25 && p < 0.95);
        if (isDropout && rising) {
          if (p > 0.25 && dropoutFrom === 0) dropoutFrom = t;
          if (p < 0.95) dropoutTo = t;
        }

        samples.push({ t, angle: base + noise, valid });
        t += step;
      }
    }
    // The dropout cycle never produces a countable repetition.
    if (!isDropout) reps.push({ t: t - 1.0, index: reps.length + 1 });
  }

  return {
    samples,
    reps,
    duration: t,
    dropout: [dropoutFrom, dropoutTo],
  };
}

export type Projector = {
  x: (t: number) => number;
  y: (angle: number) => number;
};

export function projector(
  trace: Trace,
  width: number,
  height: number,
  pad: number,
  /** Reserved right-hand gutter so threshold labels never sit over the signal. */
  padRight = pad,
): Projector {
  const minDeg = 40;
  const maxDeg = 170;
  return {
    x: (t) => pad + (t / trace.duration) * (width - pad - padRight),
    y: (angle) =>
      height -
      pad -
      ((angle - minDeg) / (maxDeg - minDeg)) * (height - pad * 2),
  };
}

/** Splits into contiguous runs so invalid stretches can be drawn differently. */
export function runs(samples: Sample[]): { valid: boolean; points: Sample[] }[] {
  const out: { valid: boolean; points: Sample[] }[] = [];
  for (const sample of samples) {
    const last = out[out.length - 1];
    if (!last || last.valid !== sample.valid) {
      // Repeat the boundary sample so the runs visually join.
      const started = last ? [last.points[last.points.length - 1], sample] : [sample];
      out.push({ valid: sample.valid, points: started });
    } else {
      last.points.push(sample);
    }
  }
  return out;
}

export function toPath(points: Sample[], p: Projector): string {
  return points
    .map((s, i) => `${i === 0 ? "M" : "L"}${p.x(s.t).toFixed(2)},${p.y(s.angle).toFixed(2)}`)
    .join(" ");
}
