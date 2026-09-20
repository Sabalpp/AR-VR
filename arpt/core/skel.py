"""
Meta Quest 3 skeletal recording (.skel) parser.

Binary format (little-endian):
    header:  int32 frame_count, int32 joint_count
    per frame: float32 timestamp, then joint_count * (float32 x, y, z)

World space is meters. Y is up, X is left/right, Z is depth.
Joint layout is Meta OVRBody2 (84 joints for full body + hands).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# ── OVRBody2 joint index map ────────────────────────────────────────────────
JOINTS: dict[str, int] = {
    "root": 0, "hips": 1,
    "spine_lower": 2, "spine_middle": 3, "spine_upper": 4, "chest": 5,
    "neck": 6, "head": 7,
    "l_shoulder": 8, "l_scapula": 9, "l_upper_arm": 10, "l_lower_arm": 11,
    "l_wrist_twist": 12, "l_hand": 18,
    "r_shoulder": 13, "r_scapula": 14, "r_upper_arm": 15, "r_lower_arm": 16,
    "r_wrist_twist": 17, "r_hand": 44,
    "l_upper_leg": 70, "l_lower_leg": 71, "l_ankle_twist": 72, "l_ankle": 73,
    "l_subtalar": 74, "l_foot_transverse": 75, "l_foot_ball": 76,
    "r_upper_leg": 77, "r_lower_leg": 78, "r_ankle_twist": 79, "r_ankle": 80,
    "r_subtalar": 81, "r_foot_transverse": 82, "r_foot_ball": 83,
}

# Bone connectivity for rendering / graph models.
SKELETON_EDGES: list[tuple[int, int]] = [
    (0, 1),
    (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7),
    (5, 8), (8, 10), (10, 11), (11, 12), (12, 18),
    (5, 13), (13, 15), (15, 16), (16, 17), (17, 44),
    (1, 70), (70, 71), (71, 73), (73, 76),
    (1, 77), (77, 78), (78, 80), (80, 83),
]

# Lower-body joints — the diagnostic focus of the device.
LOWER_BODY: dict[str, int] = {
    "hips": 1, "spine_lower": 2,
    "l_upper_leg": 70, "l_lower_leg": 71, "l_ankle": 73, "l_foot": 76,
    "r_upper_leg": 77, "r_lower_leg": 78, "r_ankle": 80, "r_foot": 83,
}

_HEADER = struct.Struct("<II")


@dataclass
class Recording:
    """Parsed skeletal recording."""
    path: str
    joint_count: int
    timestamps: np.ndarray          # (F,)
    positions: np.ndarray           # (F, J, 3) float32 world-space meters
    joint_names: dict[str, int] = field(default_factory=lambda: dict(JOINTS))

    @property
    def frame_count(self) -> int:
        return self.positions.shape[0]

    @property
    def duration_s(self) -> float:
        if self.timestamps.size < 2:
            return 0.0
        return float(self.timestamps[-1] - self.timestamps[0])

    @property
    def fps(self) -> float:
        d = self.duration_s
        return (self.frame_count - 1) / d if d > 0 else 0.0

    def joint(self, name: str) -> np.ndarray:
        """Trajectory (F, 3) for a named joint."""
        return self.positions[:, self.joint_names[name], :]

    def frame(self, i: int) -> np.ndarray:
        """All joint positions (J, 3) at frame i."""
        return self.positions[i]


def parse_skel(path: str | Path) -> Recording:
    path = str(path)
    with open(path, "rb") as f:
        data = f.read()

    frame_count, joint_count = _HEADER.unpack_from(data, 0)
    frame_stride = 4 + joint_count * 12          # timestamp + xyz per joint
    expected = _HEADER.size + frame_count * frame_stride
    if len(data) != expected:
        raise ValueError(
            f"{path}: size mismatch (expected {expected}, got {len(data)}); "
            f"file may be corrupt or a different format."
        )

    timestamps = np.empty(frame_count, dtype=np.float32)
    positions = np.empty((frame_count, joint_count, 3), dtype=np.float32)

    for i in range(frame_count):
        off = _HEADER.size + i * frame_stride
        timestamps[i] = struct.unpack_from("<f", data, off)[0]
        flat = np.frombuffer(data, dtype="<f4", count=joint_count * 3, offset=off + 4)
        positions[i] = flat.reshape(joint_count, 3)

    return Recording(path=path, joint_count=joint_count,
                     timestamps=timestamps, positions=positions)
