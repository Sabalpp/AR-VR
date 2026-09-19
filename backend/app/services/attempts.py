"""Observed reach attempts, distinct from authoritative completed repetitions."""


def observe_attempt(previous, state, frame, config, mode, repeated, sequence_gap=False):
    state = dict(state)
    attempt = dict(previous["attempt"]) if previous.get("attempt") else None
    event = None
    value = state.get("last_measurement")
    ts = frame.captured_at.timestamp() * 1000
    interrupted = (
        state["status"] != "active"
        or not state["tracking_valid"]
        or sequence_gap
        or (
            previous.get("last_capture_ms") is not None
            and ts - previous["last_capture_ms"] > config["gap_ms"]
        )
        or (attempt is not None and state["phase"] == "waiting_return")
    )
    returned = value is not None and (
        value <= config["phone_return_deg"]
        if mode == "phone"
        else value >= config["quest_return_m"]
    )
    if attempt and interrupted:
        event = {**attempt, "outcome": "interrupted"}
        attempt = None
    elif not interrupted:
        if attempt is None and previous["phase"] == "ready" and not returned:
            attempt = {
                "start_seq": frame.seq,
                "started_at": frame.captured_at.isoformat(),
                "best_measurement": value,
                "return_since": None,
                "target_threshold": config["phone_reach_deg"]
                if mode == "phone"
                else config["quest_reach_m"],
                "measurement_kind": "projected_2d_elbow_degrees"
                if mode == "phone"
                else "quest_hand_target_distance_m",
            }
        if attempt:
            attempt["best_measurement"] = (max if mode == "phone" else min)(
                attempt["best_measurement"], value
            )
            if repeated:
                event = {**attempt, "outcome": "completed"}
                attempt = None
            elif returned and state["phase"] == "ready":
                if attempt["return_since"] is None:
                    attempt["return_since"] = ts
                if ts - attempt["return_since"] >= config["hold_ms"]:
                    event = {**attempt, "outcome": "target_not_held"}
                    attempt = None
            else:
                attempt["return_since"] = None
    state["attempt"] = attempt
    if event:
        event.pop("return_since", None)
        event.update(end_seq=frame.seq, ended_at=frame.captured_at.isoformat())
    return state, event
