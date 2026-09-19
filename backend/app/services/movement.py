"""Deterministic backend counter; camera output is projected 2D, never metric depth."""

import math

from app.schemas.api import Frame


def measurement(frame: Frame, config, mode):
    if not frame.tracking_valid:
        return None
    required = (
        ["right_wrist"] if mode == "quest" else ["right_shoulder", "right_elbow", "right_wrist"]
    )
    if any(
        name not in frame.joints
        or frame.joints[name].visibility < config["visibility_min"]
        or frame.joints[name].inferred
        for name in required
    ):
        return None
    if mode == "quest":
        if frame.coordinate_system != "quest_local":
            return None
        wrist = frame.joints["right_wrist"]
        if wrist.z is None:
            return None
        return math.sqrt(
            sum((getattr(wrist, k) - config["quest_target_m"][k]) ** 2 for k in ("x", "y", "z"))
        )
    if frame.coordinate_system != "image_normalized":
        return None
    if any(not (0 <= frame.joints[k].x <= 1 and 0 <= frame.joints[k].y <= 1) for k in required):
        return None
    a, b, c = [frame.joints[k] for k in required]
    aspect = frame.image_width / frame.image_height
    u = ((a.x - b.x) * aspect, a.y - b.y)
    v = ((c.x - b.x) * aspect, c.y - b.y)
    norm = math.hypot(*u) * math.hypot(*v)
    if norm < 1e-8:
        return None
    return math.degrees(math.acos(max(-1, min(1, (u[0] * v[0] + u[1] * v[1]) / norm))))


def advance(state, frame, config, mode):
    state = dict(state)
    ts = frame.captured_at.timestamp() * 1000
    previous = state.get("last_capture_ms")
    value = measurement(frame, config, mode)
    cutoff = state.get("resume_after_ms")
    invalid = (
        value is None
        or (previous is not None and ts <= previous)
        or (cutoff is not None and ts < cutoff)
    )
    gap = previous is not None and ts - previous > config["gap_ms"]
    state["last_capture_ms"] = max(ts, previous or ts)
    state["last_measurement"] = value
    state["tracking_valid"] = not invalid
    if state["status"] != "active" or invalid or gap:
        state.update(phase="waiting_return", candidate_since=None)
        return state, False, gap or invalid
    reach = (
        value >= config["phone_reach_deg"] if mode == "phone" else value <= config["quest_reach_m"]
    )
    returned = (
        value <= config["phone_return_deg"]
        if mode == "phone"
        else value >= config["quest_return_m"]
    )
    phase = state.get("phase", "waiting_return")
    condition = reach if phase == "ready" else returned
    if not condition:
        state["candidate_since"] = None
        return state, False, False
    if state.get("candidate_since") is None:
        state["candidate_since"] = ts
    if ts - state["candidate_since"] < config["hold_ms"]:
        return state, False, False
    state["candidate_since"] = None
    if phase == "waiting_return":
        state["phase"] = "ready"
        return state, False, False
    if phase == "ready":
        state["phase"] = "reached"
        return state, False, False
    state["phase"] = "ready"
    state["repetitions"] += 1
    return state, True, False
