from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)


class User(Identity, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))


class Patient(Identity, Base):
    __tablename__ = "patients"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    is_fictional: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(String(2000), default="")


class Access(Identity, Base):
    __tablename__ = "therapist_patient_access"
    therapist_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    __table_args__ = (UniqueConstraint("therapist_id", "patient_id"),)


class Exercise(Identity, Base):
    __tablename__ = "exercise_definitions"
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(2000))
    config: Mapped[dict] = mapped_column(JSON)


class Assignment(Identity, Base):
    __tablename__ = "exercise_assignments"
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    therapist_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    exercise_definition_id: Mapped[str] = mapped_column(ForeignKey("exercise_definitions.id"))
    repetitions: Mapped[int] = mapped_column(Integer)
    config: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Session(Identity, Base):
    __tablename__ = "sessions"
    assignment_id: Mapped[str] = mapped_column(ForeignKey("exercise_assignments.id"))
    mode: Mapped[str] = mapped_column(String(20))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    config_snapshot: Mapped[dict] = mapped_column(JSON)
    state: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Device(Identity, Base):
    __tablename__ = "session_devices"
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    source: Mapped[str] = mapped_column(String(20))
    label: Mapped[str] = mapped_column(String(100), default="")
    pairing_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    pairing_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paired: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seq: Mapped[int] = mapped_column(Integer, default=-1)
    clock_offset_ms: Mapped[float | None] = mapped_column(Float, nullable=True)


class Chunk(Identity, Base):
    __tablename__ = "movement_chunks"
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("session_devices.id"))
    source: Mapped[str] = mapped_column(String(20))
    seq_start: Mapped[int] = mapped_column(Integer)
    seq_end: Mapped[int] = mapped_column(Integer)
    capture_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    capture_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    coordinate_system: Mapped[str] = mapped_column(String(40))
    units: Mapped[str] = mapped_column(String(20))
    validity: Mapped[dict] = mapped_column(JSON)
    frames: Mapped[list] = mapped_column(JSON)
    __table_args__ = (
        UniqueConstraint("device_id", "seq_start"),
        Index("movement_session_capture", "session_id", "capture_start"),
    )


class Repetition(Identity, Base):
    __tablename__ = "repetition_events"
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("session_devices.id"))
    seq: Mapped[int] = mapped_column(Integer)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(100), default="repetition")
    authoritative: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("device_id", "seq", "name"),)


class Metrics(Identity, Base):
    __tablename__ = "session_metrics"
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), unique=True)
    values: Mapped[dict] = mapped_column(JSON)


class Checkin(Identity, Base):
    __tablename__ = "patient_checkins"
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), unique=True)
    pain: Mapped[int] = mapped_column(Integer)
    effort: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str] = mapped_column(String(4000))


class Report(Identity, Base):
    __tablename__ = "session_reports"
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), unique=True)
    model: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(20), default="1")
    metrics_used: Mapped[dict] = mapped_column(JSON)
    content: Mapped[dict] = mapped_column(JSON)
