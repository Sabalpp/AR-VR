from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Login(Strict):
    email: str
    password: str


class ExerciseConfig(Strict):
    phone_return_deg: float = Field(default=95, ge=20, le=150)
    phone_reach_deg: float = Field(default=145, ge=40, le=180)
    hold_ms: int = Field(default=300, ge=200, le=5000)
    visibility_min: float = Field(default=0.65, ge=0.5, le=1)
    gap_ms: int = Field(default=750, ge=200, le=2000)
    quest_target_m: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 1, "z": 0.5})
    quest_reach_m: float = Field(default=0.12, gt=0, le=1)
    quest_return_m: float = Field(default=0.3, gt=0, le=2)
    trunk_lean_review_deg: float = Field(default=15, ge=5, le=60)
    setup_hold_ms: int = Field(default=1000, ge=500, le=5000)

    @model_validator(mode="after")
    def ordered(self):
        if (
            self.phone_return_deg >= self.phone_reach_deg
            or self.quest_reach_m >= self.quest_return_m
        ):
            raise ValueError("Reach and return thresholds must have hysteresis")
        if set(self.quest_target_m) != {"x", "y", "z"}:
            raise ValueError("Target requires x,y,z")
        return self


class AssignmentIn(Strict):
    patient_id: str
    exercise_definition_id: str
    repetitions: int = Field(default=5, ge=1, le=100)
    config: ExerciseConfig = Field(default_factory=ExerciseConfig)


class SessionIn(Strict):
    assignment_id: str
    mode: Literal["phone", "quest", "combined"] = "phone"
    is_synthetic: bool = False


class PairingIn(Strict):
    source: Literal["phone", "quest", "simulator", "simulator_phone", "simulator_quest"]


class PairIn(Strict):
    expected_source: (
        Literal["phone", "quest", "simulator", "simulator_phone", "simulator_quest"] | None
    ) = None
    code: str = Field(min_length=6, max_length=20)
    label: str = Field(default="Device", max_length=100)


class Joint(Strict):
    x: float
    y: float
    z: float | None = None
    visibility: float = Field(ge=0, le=1)
    inferred: bool = False


class Frame(Strict):
    seq: int = Field(ge=0)
    captured_at: datetime
    coordinate_system: Literal["image_normalized", "quest_local"]
    units: Literal["normalized", "meters"]
    image_width: int | None = Field(default=None, ge=1, le=10000)
    image_height: int | None = Field(default=None, ge=1, le=10000)
    tracking_valid: bool
    joints: dict[str, Joint] = Field(max_length=64)

    @field_validator("captured_at")
    @classmethod
    def timezone_required(cls, v):
        if v.tzinfo is None:
            raise ValueError("Timestamp must include timezone")
        return v

    @model_validator(mode="after")
    def coordinates(self):
        if self.coordinate_system == "image_normalized":
            if self.units != "normalized" or not self.image_width or not self.image_height:
                raise ValueError("Image frames require dimensions and normalized units")
        elif self.units != "meters":
            raise ValueError("Quest frames require meters")
        return self


class Batch(Strict):
    frames: list[Frame] = Field(min_length=1, max_length=60)


class CheckinIn(Strict):
    pain: int = Field(ge=0, le=10)
    effort: int = Field(ge=0, le=10)
    notes: str = Field(default="", max_length=4000)


class Envelope(Strict):
    version: Literal[1]
    type: Literal[
        "device.join",
        "device.status",
        "tracking.frame",
        "exercise.event",
        "session.pause",
        "session.resume",
        "session.complete",
    ]
    id: str = Field(min_length=1, max_length=100)
    payload: dict


class DeviceStatusIn(Strict):
    clock_offset_ms: float | None = Field(default=None, gt=-86400000, lt=86400000)
    tracking_valid: bool | None = None
