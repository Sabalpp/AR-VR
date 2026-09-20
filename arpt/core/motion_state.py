"""
Motion-state engine: red / yellow / green limb coloring, green-path form
guidance, and the redo-loop form gate.

State model per frame, per tracked angle:
    RED    — not in motion (below velocity threshold, not at goal)
    YELLOW — in motion (angle changing toward the phase goal)
    GREEN  — target reached (within tolerance of the current phase goal)

The green-path guide produces, for any progress value in [0, 1], the target
angle the patient *should* be at — the renderer draws a translucent green
"ghost" pose from these targets so the patient can match it.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from ..medical.tests import MovementTest, Phase, FormGate


class MotionState(str, Enum):
    RED = "red"        # not moving
    YELLOW = "yellow"  # in motion
    GREEN = "green"    # completed / at target


STATE_COLOR = {
    MotionState.RED: (0.90, 0.20, 0.18),
    MotionState.YELLOW: (1.00, 0.80, 0.10),
    MotionState.GREEN: (0.20, 0.85, 0.35),
}

# Angle change (deg/frame) above which a joint counts as "in motion".
MOTION_VELOCITY_DEG = 1.2


@dataclass
class FrameState:
    frame: int
    phase: str
    state: MotionState
    angle: float
    target: float
    progress: float          # 0..1 through the whole test
    gate_violation: str | None = None


@dataclass
class RepResult:
    accepted: bool
    frames: list[FrameState]
    peak_angle: float
    reached_goal: bool
    violations: list[str]


def _phase_targets(test: MovementTest) -> list[Phase]:
    return list(test.phases)


def green_path_target(test: MovementTest, angle_key: str, progress: float) -> float:
    """
    Target angle for `angle_key` at overall `progress` in [0,1].
    Phases are distributed evenly across the progress axis; within a phase the
    target linearly interpolates start->goal (holds stay at goal).
    """
    phases = [p for p in test.phases if p.joint_angle == angle_key] or list(test.phases)
    n = len(phases)
    if n == 0:
        return 180.0
    pos = min(max(progress, 0.0), 1.0) * n
    idx = min(int(pos), n - 1)
    frac = pos - idx
    ph = phases[idx]
    return float(ph.start_deg + (ph.goal_deg - ph.start_deg) * frac)


def classify_frame(prev_angle: float, angle: float, target: float,
                   tolerance: float) -> MotionState:
    if abs(angle - target) <= tolerance:
        return MotionState.GREEN
    if abs(angle - prev_angle) >= MOTION_VELOCITY_DEG:
        return MotionState.YELLOW
    return MotionState.RED


def evaluate_rep(angles: dict[str, np.ndarray], test: MovementTest,
                 primary_angle: str | None = None) -> RepResult:
    """
    Evaluate a single recorded repetition against a test's phases + gates.

    `angles` is the per-frame angle dict from kinematics.compute_angles.
    Returns per-frame motion states, whether the movement reached its goal, and
    any form-gate violations (which drive the redo loop).
    """
    primary = primary_angle or test.phases[0].joint_angle
    series = np.asarray(angles[primary], dtype=float)
    n_frames = len(series)
    if n_frames == 0:
        return RepResult(False, [], 0.0, False, ["empty recording"])

    # Deepest phase goal defines "reached goal".
    goals = [p.goal_deg for p in test.phases if p.joint_angle == primary]
    deepest_goal = min(goals) if goals else series.min()
    tol = test.phases[0].tolerance_deg

    frames: list[FrameState] = []
    violations: list[str] = []
    prev = series[0]
    for i, a in enumerate(series):
        progress = i / max(n_frames - 1, 1)
        target = green_path_target(test, primary, progress)
        state = classify_frame(prev, a, target, tol)

        gate_msg = _check_gates(angles, i, test.form_gates)
        if gate_msg and gate_msg not in violations:
            violations.append(gate_msg)

        frames.append(FrameState(
            frame=i, phase=_phase_at(test, progress), state=state,
            angle=round(float(a), 1), target=round(target, 1),
            progress=round(progress, 3), gate_violation=gate_msg,
        ))
        prev = a

    reached = bool(series.min() <= deepest_goal + tol)
    accepted = reached and not violations
    return RepResult(
        accepted=accepted,
        frames=frames,
        peak_angle=round(float(series.min()), 1),
        reached_goal=reached,
        violations=violations,
    )


def _phase_at(test: MovementTest, progress: float) -> str:
    n = len(test.phases)
    if n == 0:
        return ""
    idx = min(int(progress * n), n - 1)
    return test.phases[idx].name


def _check_gates(angles: dict[str, np.ndarray], i: int,
                 gates: tuple[FormGate, ...]) -> str | None:
    for g in gates:
        if g.metric not in angles:
            continue
        val = float(np.asarray(angles[g.metric])[i])
        # trunk_lean gate: value should stay *below* max_abs from vertical-ish;
        # pelvic_tilt & similar: absolute magnitude must stay under max_abs.
        if g.metric == "trunk_lean":
            if val > g.max_abs:
                return g.message
        else:
            if abs(val) > g.max_abs:
                return g.message
    return None


def summarize_states(frames: list[FrameState]) -> dict:
    counts = {s.value: 0 for s in MotionState}
    for f in frames:
        counts[f.state.value] += 1
    total = max(len(frames), 1)
    return {
        "counts": counts,
        "pct": {k: round(v / total * 100, 1) for k, v in counts.items()},
        "reached_green": counts[MotionState.GREEN.value] > 0,
    }
