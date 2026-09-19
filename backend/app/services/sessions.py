from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select

from app.models import Checkin, Chunk, Device, Metrics, Repetition, Report, now
from app.providers.gemini import summarize
from app.services.movement import advance, measurement


def ingest(db, session, device, batch):
    if session.completed_at:
        raise HTTPException(409, "Session already complete")
    # Session row is locked by caller; serializes device sequence and counter updates.
    db.refresh(device)
    frames = []
    duplicates = 0
    gaps = 0
    state = dict(session.state)
    source_mode = session.mode if device.source == "simulator" else device.source
    expected = "image_normalized" if source_mode == "phone" else "quest_local"
    authoritative = device.id == state.get("authoritative_device_id")
    for frame in batch.frames:
        if frame.seq <= device.last_seq:
            duplicates += 1
            continue
        if frame.coordinate_system != expected:
            raise HTTPException(
                422,
                "Coordinate system must match session mode; streams are never fused",
            )
        if device.source == "simulator" and not session.is_synthetic:
            raise HTTPException(403, "Simulator requires a synthetic session")
        if device.last_seq >= 0 and frame.seq > device.last_seq + 1:
            gaps += 1
            if authoritative:
                state.update(phase="waiting_return", candidate_since=None)
        if authoritative:
            state, rep, gap = advance(state, frame, session.config_snapshot, session.mode)
            value = state["last_measurement"]
            valid = state["tracking_valid"]
        else:
            value = measurement(frame, session.config_snapshot, source_mode)
            valid = value is not None
            rep = False
            gap = not valid
        gaps += int(gap)
        saved = frame.model_dump(mode="json")
        saved["measurement"] = value
        saved["observed_valid"] = valid
        saved["status"] = state["status"]
        saved["authoritative"] = authoritative
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


def transition(db, session, action):
    if session.completed_at:
        if action == "complete":
            return session.state
        raise HTTPException(409, "Session already complete")
    state = dict(session.state)
    if action == "resume":
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
        }
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
    report = Report(
        session_id=session.id, model=model, metrics_used=metrics.values, content=content
    )
    db.add(report)
    db.commit()
    return report
