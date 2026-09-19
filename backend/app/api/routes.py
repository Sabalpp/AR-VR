import asyncio
import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.db import get_db
from app.models import (
    Access,
    Assignment,
    Checkin,
    Chunk,
    Device,
    Exercise,
    Patient,
    Repetition,
    Report,
    Session,
    User,
    now,
)
from app.providers.speech import speech
from app.repositories.access import patient_access, session_access
from app.schemas.api import (
    AssignmentIn,
    Batch,
    CheckinIn,
    DeviceStatusIn,
    ExerciseConfig,
    Login,
    PairIn,
    PairingIn,
    SessionIn,
)
from app.schemas.responses import (
    AssignmentOut,
    CheckinOut,
    DeviceStatusOut,
    ExerciseOut,
    IngestOut,
    LoginOut,
    PairingOut,
    PairOut,
    PatientOut,
    ReplayOut,
    ReportOut,
    SessionOut,
    SessionState,
    UserOut,
)
from app.services.security import password_verify, principal, token, user
from app.services.sessions import get_report, ingest, live_state, transition

router = APIRouter(prefix="/api/v1")
_attempts = defaultdict(deque)


def rate_limit(key, limit=10):
    current = time.monotonic()
    values = _attempts[key]
    while values and current - values[0] > 60:
        values.popleft()
    if len(values) >= limit:
        raise HTTPException(429, "Rate limit exceeded; retry in one minute")
    values.append(current)
    if len(_attempts) > 10000:
        for k in list(_attempts):
            if not _attempts[k] or current - _attempts[k][-1] > 60:
                del _attempts[k]


def row(value):
    return {
        c.name: getattr(value, c.name)
        for c in value.__table__.columns
        if c.name not in {"password_hash", "pairing_hash"}
    }


def assignment_row(db, a):
    result = row(a)
    result["exercise_name"] = db.get(Exercise, a.exercise_definition_id).name
    return result


@router.post("/auth/login", response_model=LoginOut)
def login(data: Login, request: Request, db: DBSession = Depends(get_db)):
    rate_limit(("login", request.client.host))
    u = db.scalar(select(User).where(User.email == data.email.lower()))
    if not u or not password_verify(data.password, u.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return {"access_token": token(u.id, "user"), "token_type": "bearer", "user": row(u)}


@router.get("/auth/me", response_model=UserOut)
def me(u=Depends(user)):
    return row(u)


@router.get("/patients", response_model=list[PatientOut])
def patients(u=Depends(user), db: DBSession = Depends(get_db)):
    q = (
        select(Patient).where(Patient.user_id == u.id)
        if u.role == "patient"
        else select(Patient)
        .join(Access, Access.patient_id == Patient.id)
        .where(Access.therapist_id == u.id)
    )
    return [row(p) for p in db.scalars(q)]


@router.get("/patients/{patient_id}", response_model=PatientOut)
def patient(patient_id: str, u=Depends(user), db: DBSession = Depends(get_db)):
    return row(patient_access(db, u, patient_id))


@router.get("/exercises", response_model=list[ExerciseOut])
def exercises(u=Depends(user), db: DBSession = Depends(get_db)):
    return [row(e) for e in db.scalars(select(Exercise))]


@router.get("/patients/{patient_id}/assignments", response_model=list[AssignmentOut])
@router.get("/assignments", response_model=list[AssignmentOut])
def assignments(patient_id: str | None = None, u=Depends(user), db: DBSession = Depends(get_db)):
    if patient_id is None:
        patient = db.scalar(select(Patient).where(Patient.user_id == u.id))
        if not patient:
            raise HTTPException(422, "patient_id required for therapist")
        patient_id = patient.id
    patient_access(db, u, patient_id)
    return [
        assignment_row(db, a)
        for a in db.scalars(
            select(Assignment)
            .where(Assignment.patient_id == patient_id)
            .order_by(Assignment.created_at.desc())
        )
    ]


@router.post("/assignments", status_code=201, response_model=AssignmentOut)
def assign(data: AssignmentIn, u=Depends(user), db: DBSession = Depends(get_db)):
    if u.role != "therapist":
        raise HTTPException(403, "Therapist required")
    patient_access(db, u, data.patient_id)
    if not db.get(Exercise, data.exercise_definition_id):
        raise HTTPException(404, "Exercise not found")
    a = Assignment(
        patient_id=data.patient_id,
        therapist_id=u.id,
        exercise_definition_id=data.exercise_definition_id,
        repetitions=data.repetitions,
        config=data.config.model_dump(),
    )
    db.add(a)
    db.commit()
    return assignment_row(db, a)


@router.post("/sessions", status_code=201, response_model=SessionOut)
def create_session(data: SessionIn, u=Depends(user), db: DBSession = Depends(get_db)):
    a = db.get(Assignment, data.assignment_id)
    if not a:
        raise HTTPException(404, "Assignment not found")
    patient_access(db, u, a.patient_id)
    s = Session(
        assignment_id=a.id,
        mode=data.mode,
        is_synthetic=data.is_synthetic,
        config_snapshot={
            **ExerciseConfig.model_validate(a.config).model_dump(),
            "target_repetitions": a.repetitions,
            "authoritative_counter": "backend",
            "counter_stream": "phone" if data.mode == "phone" else "quest",
            "audio_owner": "phone" if data.mode == "phone" else "quest",
            "control_owner": "phone" if data.mode == "phone" else "quest",
            "capture_hz": 10,
            "batch_interval_ms": 250,
            "seated_only": True,
            "passthrough_required": data.mode != "phone",
        },
        state={
            "status": "paused" if data.mode == "combined" else "active",
            "repetitions": 0,
            "phase": "waiting_return",
            "last_measurement": None,
            "tracking_valid": False,
        },
    )
    db.add(s)
    db.commit()
    return row(s)


@router.get("/patients/{patient_id}/sessions", response_model=list[SessionOut])
def patient_sessions(patient_id: str, u=Depends(user), db: DBSession = Depends(get_db)):
    patient_access(db, u, patient_id)
    return [
        row(s)
        for s in db.scalars(
            select(Session)
            .join(Assignment, Session.assignment_id == Assignment.id)
            .where(Assignment.patient_id == patient_id)
            .order_by(Session.created_at.desc())
        )
    ]


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: str, p=Depends(principal), db: DBSession = Depends(get_db)):
    session = session_access(db, p, session_id)
    return {**row(session), "state": live_state(session)}


@router.post("/sessions/{session_id}/pairing", response_model=PairingOut)
def pairing(session_id: str, data: PairingIn, p=Depends(user), db: DBSession = Depends(get_db)):
    s = session_access(db, p, session_id, True)
    rate_limit(("issue", p.id))
    if s.completed_at:
        raise HTTPException(409, "Session complete")
    if s.is_synthetic and not data.source.startswith("simulator"):
        raise HTTPException(422, "Synthetic sessions accept simulator sources only")
    if data.source.startswith("simulator") and not s.is_synthetic:
        raise HTTPException(422, "Simulator requires synthetic session")
    if data.source in ("simulator_phone", "simulator_quest") and s.mode != "combined":
        raise HTTPException(422, "Explicit simulator streams require combined mode")
    if data.source == "simulator" and s.mode == "combined":
        raise HTTPException(422, "Choose simulator_phone or simulator_quest for combined mode")
    code = secrets.token_hex(4).upper()
    expiry = now() + timedelta(minutes=5)
    db.add(
        Device(
            session_id=s.id,
            source=data.source,
            pairing_hash=hashlib.sha256(code.encode()).hexdigest(),
            pairing_expires_at=expiry,
        )
    )
    db.commit()
    return {"code": code, "expires_at": expiry}


@router.post("/devices/pair", response_model=PairOut)
def pair(data: PairIn, request: Request, db: DBSession = Depends(get_db)):
    rate_limit(("pair", request.client.host), 6)
    d = db.scalar(
        select(Device)
        .where(Device.pairing_hash == hashlib.sha256(data.code.upper().encode()).hexdigest())
        .with_for_update()
    )
    if not d or d.paired or d.pairing_expires_at.replace(tzinfo=timezone.utc) < now():
        raise HTTPException(401, "Invalid or expired pairing code")
    if data.expected_source is not None and data.expected_source != d.source:
        raise HTTPException(422, "Pairing code belongs to a different device source")
    s = db.scalar(select(Session).where(Session.id == d.session_id).with_for_update())
    if s.completed_at:
        raise HTTPException(409, "Session unavailable")
    d.paired = True
    d.pairing_hash = None
    d.label = data.label
    counter_stream = "phone" if s.mode == "phone" else "quest"
    if not s.state.get("authoritative_device_id") and (
        d.source in (counter_stream, "simulator_" + counter_stream, "simulator")
    ):
        s.state = {**s.state, "authoritative_device_id": d.id}
    if (
        s.mode == "combined"
        and d.source in ("phone", "simulator_phone")
        and not s.state.get("phone_device_id")
    ):
        s.state = {**s.state, "phone_device_id": d.id}
    db.commit()
    return {
        "source": d.source,
        "device_token": token(d.id, "device", d.session_id),
        "device_id": d.id,
        "session_id": d.session_id,
    }


@router.post("/sessions/{session_id}/movement", response_model=IngestOut)
def movement(session_id: str, data: Batch, p=Depends(principal), db: DBSession = Depends(get_db)):
    if not isinstance(p, Device):
        raise HTTPException(403, "Device token required")
    return ingest(db, session_access(db, p, session_id, True), p, data)


@router.post("/sessions/{session_id}/pause", response_model=SessionState)
def pause(session_id: str, p=Depends(principal), db: DBSession = Depends(get_db)):
    return transition(db, session_access(db, p, session_id, True), "pause")


@router.post("/sessions/{session_id}/resume", response_model=SessionState)
def resume(session_id: str, p=Depends(principal), db: DBSession = Depends(get_db)):
    return transition(db, session_access(db, p, session_id, True), "resume", p)


@router.post("/sessions/{session_id}/complete", response_model=SessionState)
def complete(session_id: str, p=Depends(principal), db: DBSession = Depends(get_db)):
    return transition(db, session_access(db, p, session_id, True), "complete")


@router.post("/sessions/{session_id}/checkin", response_model=CheckinOut)
def checkin(session_id: str, data: CheckinIn, u=Depends(user), db: DBSession = Depends(get_db)):
    s = session_access(db, u, session_id, True)
    patient = db.get(Patient, db.get(Assignment, s.assignment_id).patient_id)
    if patient.user_id != u.id:
        raise HTTPException(403, "Only the patient can submit feedback")
    c = db.scalar(select(Checkin).where(Checkin.session_id == s.id))
    if c:
        for k, v in data.model_dump().items():
            setattr(c, k, v)
    else:
        c = Checkin(session_id=s.id, **data.model_dump())
        db.add(c)
    old = db.scalar(select(Report).where(Report.session_id == s.id))
    if old:
        db.delete(old)
    db.commit()
    return row(c)


@router.get("/sessions/{session_id}/replay", response_model=ReplayOut)
def replay(session_id: str, u=Depends(user), db: DBSession = Depends(get_db)):
    s = session_access(db, u, session_id)
    chunks = list(
        db.scalars(select(Chunk).where(Chunk.session_id == s.id).order_by(Chunk.capture_start))
    )
    return {
        "session": row(s),
        "chunks": [row(c) for c in chunks],
        "frames": [
            dict(f, device_id=c.device_id, source=c.source) for c in chunks for f in c.frames
        ],
        "repetitions": [
            row(r) for r in db.scalars(select(Repetition).where(Repetition.session_id == s.id))
        ],
        "checkin": row(c)
        if (c := db.scalar(select(Checkin).where(Checkin.session_id == s.id)))
        else None,
    }


@router.get("/sessions/{session_id}/report", response_model=ReportOut)
def report(session_id: str, u=Depends(user), db: DBSession = Depends(get_db)):
    s = session_access(db, u, session_id, True)
    return row(asyncio.run(get_report(db, s)))


@router.get("/speech/{cue}")
async def get_speech(cue: str, p=Depends(principal)):
    rate_limit(("speech", p.id), 12)
    return Response(
        await speech(cue),
        media_type="audio/mpeg",
        headers={"Cache-Control": "private, max-age=86400"},
    )


@router.post("/sessions/{session_id}/device-status", response_model=DeviceStatusOut)
def device_status(
    session_id: str,
    data: DeviceStatusIn,
    p=Depends(principal),
    db: DBSession = Depends(get_db),
):
    if not isinstance(p, Device):
        raise HTTPException(403, "Device token required")
    s = session_access(db, p, session_id, True)
    if data.clock_offset_ms is not None:
        p.clock_offset_ms = data.clock_offset_ms
    if data.tracking_valid is False and s.state.get("authoritative_device_id") == p.id:
        s.state = {
            **s.state,
            "tracking_valid": False,
            "phase": "waiting_return",
            "candidate_since": None,
        }
    db.commit()
    return {"clock_offset_ms": p.clock_offset_ms, "state": s.state}
