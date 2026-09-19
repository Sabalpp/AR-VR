from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select

from app.models import Checkin, Chunk, Device, Metrics, Repetition, Report, now
from app.providers.gemini import summarize
from app.services.attempts import observe_attempt
from app.services.movement import advance, measurement, trunk_lean


def source_mode(device, session):
    if device.source == "simulator":
        return session.mode
    return device.source.removeprefix("simulator_")


def phone_ready(state, config):
    stamp = state.get("phone_capture_server_ms")
    return bool(
        state.get("phone_setup_ready")
        and stamp is not None
        and 0 <= now().timestamp() * 1000 - stamp <= config["gap_ms"] + 500
    )


def live_state(session):
    state = dict(session.state)
    stamp = state.get("phone_capture_server_ms")
    if (
        session.mode == "combined"
        and stamp is not None
        and (not 0 <= now().timestamp() * 1000 - stamp <= session.config_snapshot["gap_ms"] + 500)
    ):
        state.update(
            phone_tracking_valid=False,
            phone_setup_ready=False,
            phone_valid_since_ms=None,
            phone_trunk_lean_deg=None,
            phone_trunk_review=False,
        )
    return state


def ingest(db, session, device, batch):
    if session.completed_at:
        raise HTTPException(409, "Session already complete")
    # Session row is locked by caller; serializes device sequence and counter updates.
    db.refresh(device)
    frames = []
    duplicates = 0
    gaps = 0
    state = live_state(session)
    stream_mode = source_mode(device, session)
    expected = "image_normalized" if stream_mode == "phone" else "quest_local"
    authoritative = device.id == state.get("authoritative_device_id")
    trunk_stream = session.mode == "combined" and stream_mode == "phone"
    for frame in batch.frames:
        if frame.seq <= device.last_seq:
            duplicates += 1
            continue
        if frame.coordinate_system != expected:
            raise HTTPException(
                422,
                "Coordinate system must match session mode; streams are never fused",
            )
        if device.source.startswith("simulator") and not session.is_synthetic:
            raise HTTPException(403, "Simulator requires a synthetic session")
        previous_state = dict(state)
        sequence_gap = device.last_seq >= 0 and frame.seq > device.last_seq + 1
        if sequence_gap:
            gaps += 1
            if authoritative:
                state.update(phase="waiting_return", candidate_since=None)
        if authoritative:
            state, rep, gap = advance(state, frame, session.config_snapshot, session.mode)
            state, attempt_event = observe_attempt(
                previous_state,
                state,
                frame,
                session.config_snapshot,
                session.mode,
                rep,
                sequence_gap,
            )
            value = state["last_measurement"]
            valid = state["tracking_valid"]
        else:
            value = (
                trunk_lean(frame, session.config_snapshot)
                if trunk_stream
                else measurement(frame, session.config_snapshot, stream_mode)
            )
            valid = value is not None
            rep = False
            gap = not valid
        if trunk_stream and device.id == state.get("phone_device_id"):
            ts = frame.captured_at.timestamp() * 1000
            previous = state.get("phone_last_capture_ms")
            contiguous = (
                previous is not None
                and 0 < ts - previous <= session.config_snapshot["gap_ms"]
                and frame.seq == device.last_seq + 1
            )
            timely = (
                0
                <= now().timestamp() * 1000 - (ts - (device.clock_offset_ms or 0))
                <= session.config_snapshot["gap_ms"] + 500
            )
            ready_sample = valid and timely and (previous is None or ts > previous)
            since = state.get("phone_valid_since_ms") if contiguous and ready_sample else None
            since = (since if since is not None else ts) if ready_sample else None
            state.update(
                phone_last_capture_ms=max(ts, previous or ts),
                phone_capture_server_ms=ts - (device.clock_offset_ms or 0),
                phone_valid_since_ms=since,
                phone_setup_ready=bool(
                    since is not None
                    and ts - since >= session.config_snapshot.get("setup_hold_ms", 1000)
                ),
                phone_tracking_valid=ready_sample,
                phone_trunk_lean_deg=value,
                phone_trunk_review=bool(
                    valid and value >= session.config_snapshot.get("trunk_lean_review_deg", 15)
                ),
            )
        if trunk_stream:
            state["trunk_observed_frames"] = state.get("trunk_observed_frames", 0) + int(valid)
            state["trunk_review_frames"] = state.get("trunk_review_frames", 0) + int(
                valid and value >= session.config_snapshot.get("trunk_lean_review_deg", 15)
            )
        gaps += int(gap)
        saved = frame.model_dump(mode="json")
        saved["measurement"] = value
        saved["observed_valid"] = valid
        saved["status"] = state["status"]
        saved["authoritative"] = authoritative
        if authoritative and attempt_event:
            attempt_event.update(
                id=f"{device.id}:{attempt_event['start_seq']}", device_id=device.id
            )
            saved["attempt_event"] = attempt_event
            state["last_attempt"] = attempt_event
            name = "attempts_" + attempt_event["outcome"]
            state[name] = state.get(name, 0) + 1
        saved["measurement_kind"] = (
            "projected_2d_trunk_lean_degrees"
            if trunk_stream
            else (
                "projected_2d_elbow_degrees"
                if stream_mode == "phone"
                else "quest_hand_target_distance_m"
            )
        )
        if trunk_stream:
            saved["trunk_review"] = bool(
                valid and value >= session.config_snapshot.get("trunk_lean_review_deg", 15)
            )
        frames.append(saved)
        if rep:
            db.add(
                Repetition(
                    session_id=session.id,
                    device_id=device.id,
                    seq=frame.seq,
                    captured_at=frame.captured_at,
                    source="backend:" + device.source,
                )
            )
        device.last_seq = frame.seq
    if frames:
        db.add(
            Chunk(
                session_id=session.id,
                device_id=device.id,
                source=device.source,
                seq_start=frames[0]["seq"],
                seq_end=frames[-1]["seq"],
                capture_start=datetime.fromisoformat(frames[0]["captured_at"]),
                capture_end=datetime.fromisoformat(frames[-1]["captured_at"]),
                coordinate_system=expected,
                units=batch.frames[0].units,
                validity={
                    "gaps": gaps,
                    "clock_offset_ms": device.clock_offset_ms,
                    "invalid_frames": sum(not f["observed_valid"] for f in frames),
                },
                frames=frames,
            )
        )
    state["accepted_frames"] = state.get("accepted_frames", 0) + len(frames)
    state["invalid_frames"] = state.get("invalid_frames", 0) + sum(
        not f["observed_valid"] for f in frames
    )
    state["tracking_gaps"] = state.get("tracking_gaps", 0) + gaps
    session.state = state
    db.commit()
    return {"accepted": len(frames), "duplicates": duplicates, "state": state}


def transition(db, session, action, caller=None):
    if session.completed_at:
        if action == "complete":
            return session.state
        raise HTTPException(409, "Session already complete")
    state = dict(session.state)
    if action == "resume":
        if session.mode in ("quest", "combined"):
            if isinstance(caller, Device) and source_mode(caller, session) != "quest":
                raise HTTPException(403, "Resume from the headset; phone is an observation stream")
            if not state.get("authoritative_device_id"):
                raise HTTPException(409, "Pair the headset before starting")
        if session.mode == "combined" and not phone_ready(state, session.config_snapshot):
            raise HTTPException(
                409,
                "Finish phone setup first: keep right shoulder and hip visible with fresh tracking",
            )
        device = (
            db.get(Device, state.get("authoritative_device_id"))
            if state.get("authoritative_device_id")
            else None
        )
        state["resume_after_ms"] = now().timestamp() * 1000 + (
            (device.clock_offset_ms or 0) if device else 0
        )
    state.update(
        status={"pause": "paused", "resume": "active", "complete": "complete"}[action],
        phase="waiting_return",
        candidate_since=None,
    )
    # A pause/resume invalidates a partial attempt; it cannot become a success.
    if state.get("attempt"):
        state["attempt"] = None
    if action == "complete":
        session.completed_at = now()
        metrics = {
            "repetitions": state["repetitions"],
            "accepted_frames": state.get("accepted_frames", 0),
            "invalid_frames": state.get("invalid_frames", 0),
            "tracking_gaps": state.get("tracking_gaps", 0),
            "measurement_kind": "projected_2d_elbow_degrees"
            if session.mode == "phone"
            else "quest_hand_target_distance_m",
            "counter_source": "backend",
            "is_synthetic": session.is_synthetic,
            "attempts_completed": state.get("attempts_completed", 0),
            "attempts_target_not_held": state.get("attempts_target_not_held", 0),
            "attempts_interrupted": state.get("attempts_interrupted", 0),
        }
        if session.mode == "combined":
            metrics.update(
                secondary_measurement_kind="projected_2d_trunk_lean_degrees",
                trunk_observed_frames=state.get("trunk_observed_frames", 0),
                trunk_review_frames=state.get("trunk_review_frames", 0),
                trunk_review_threshold_deg=session.config_snapshot.get("trunk_lean_review_deg", 15),
            )
        db.add(Metrics(session_id=session.id, values=metrics))
    session.state = state
    db.commit()
    return state


async def get_report(db, session):
    existing = db.scalar(select(Report).where(Report.session_id == session.id))
    if existing:
        return existing
    metrics = db.scalar(select(Metrics).where(Metrics.session_id == session.id))
    if not metrics:
        raise HTTPException(409, "Complete the session first")
    checkin = db.scalar(select(Checkin).where(Checkin.session_id == session.id))
    model, content = await summarize(metrics.values, checkin.notes if checkin else "")
    content["attempt_evidence"] = [
        {**frame["attempt_event"], "session_id": session.id}
        for chunk in db.scalars(
            select(Chunk).where(Chunk.session_id == session.id).order_by(Chunk.capture_start)
        )
        for frame in chunk.frames
        if frame.get("attempt_event")
    ]
    report = Report(
        session_id=session.id, model=model, metrics_used=metrics.values, content=content
    )
    db.add(report)
    db.commit()
    return report
