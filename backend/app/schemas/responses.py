"""Public REST response contracts; database-only fields never cross the API."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class UserOut(BaseModel):
    id: str
    email: str
    role: Literal["therapist", "patient"]
    name: str


class LoginOut(BaseModel):
    access_token: str
    token_type: str
    user: UserOut


class PatientOut(BaseModel):
    id: str
    user_id: str
    name: str
    is_fictional: bool
    notes: str


class ExerciseOut(BaseModel):
    id: str
    name: str
    description: str
    config: dict[str, Any]


class AssignmentOut(BaseModel):
    id: str
    patient_id: str
    therapist_id: str
    exercise_definition_id: str
    repetitions: int
    config: dict[str, Any]
    created_at: datetime
    exercise_name: str


class SessionState(BaseModel):
    # Additional persisted quality/control fields remain forward-compatible.
    model_config = {"extra": "allow"}
    status: Literal["active", "paused", "complete"]
    repetitions: int
    phase: str
    last_measurement: float | None
    tracking_valid: bool


class SessionOut(BaseModel):
    id: str
    assignment_id: str
    mode: Literal["phone", "quest", "combined"]
    is_synthetic: bool
    config_snapshot: dict[str, Any]
    state: SessionState
    created_at: datetime
    completed_at: datetime | None


class PairingOut(BaseModel):
    code: str
    expires_at: datetime


class PairOut(BaseModel):
    source: Literal["phone", "quest", "simulator", "simulator_phone", "simulator_quest"]
    device_token: str
    device_id: str
    session_id: str


class IngestOut(BaseModel):
    accepted: int
    duplicates: int
    state: SessionState


class CheckinOut(BaseModel):
    id: str
    session_id: str
    pain: int
    effort: int
    notes: str


class ChunkOut(BaseModel):
    id: str
    session_id: str
    device_id: str
    source: str
    seq_start: int
    seq_end: int
    capture_start: datetime
    capture_end: datetime
    coordinate_system: str
    units: str
    validity: dict[str, Any]
    frames: list[dict[str, Any]]


class RepetitionOut(BaseModel):
    id: str
    session_id: str
    device_id: str
    seq: int
    captured_at: datetime
    source: str
    name: str
    authoritative: bool


class ReplayOut(BaseModel):
    session: SessionOut
    chunks: list[ChunkOut]
    frames: list[dict[str, Any]]
    repetitions: list[RepetitionOut]
    checkin: CheckinOut | None


class ReportOut(BaseModel):
    id: str
    session_id: str
    model: str
    version: str
    metrics_used: dict[str, Any]
    content: dict[str, Any]


class DeviceStatusOut(BaseModel):
    clock_offset_ms: float | None
    state: SessionState
