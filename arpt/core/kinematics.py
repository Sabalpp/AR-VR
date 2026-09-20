"""
Kinematic analysis of a skeletal recording.

Computes joint angles, range of motion, left/right symmetry, pelvic tilt,
trunk lean and joint velocities — the biomechanical features that feed both
the diagnosis prompt and the ML model.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

from .skel import Recording, LOWER_BODY


def _angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Angle (deg) at vertex b between b->a and b->c, vectorized over frames."""
    v1 = a - b
    v2 = c - b
    dot = np.sum(v1 * v2, axis=-1)
    norm = np.linalg.norm(v1, axis=-1) * np.linalg.norm(v2, axis=-1) + 1e-9
    return np.degrees(np.arccos(np.clip(dot / norm, -1.0, 1.0)))


# Named angle definitions: (proximal, vertex, distal) joint names.
ANGLE_DEFS = {
    "left_knee":  ("l_upper_leg", "l_lower_leg", "l_ankle"),
    "right_knee": ("r_upper_leg", "r_lower_leg", "r_ankle"),
    "left_hip":   ("spine_lower", "hips", "l_upper_leg"),
    "right_hip":  ("spine_lower", "hips", "r_upper_leg"),
    "left_ankle": ("l_lower_leg", "l_ankle", "l_foot"),
    "right_ankle":("r_lower_leg", "r_ankle", "r_foot"),
}

# Symmetry pairs keyed by region.
SYMMETRY_PAIRS = {
    "knee":  ("left_knee", "right_knee"),
    "hip":   ("left_hip", "right_hip"),
    "ankle": ("left_ankle", "right_ankle"),
}


@dataclass
class RomStat:
    min: float
    max: float
    range: float
    mean: float
    std: float


def compute_angles(rec: Recording) -> dict[str, np.ndarray]:
    """Per-frame angle series (deg) for each named angle, plus trunk/pelvis."""
    def jp(name: str) -> np.ndarray:
        # LOWER_BODY 'l_foot' maps to foot_ball index
        idx = rec.joint_names.get(name) or LOWER_BODY.get(name)
        if name == "l_foot":
            idx = rec.joint_names["l_foot_ball"]
        if name == "r_foot":
            idx = rec.joint_names["r_foot_ball"]
        return rec.positions[:, idx, :]

    angles: dict[str, np.ndarray] = {}
    for name, (a, b, c) in ANGLE_DEFS.items():
        angles[name] = _angle(jp(a), jp(b), jp(c))

    hips = jp("hips")
    spine = jp("spine_lower")
    spine_vec = spine - hips
    vertical = np.array([0.0, 1.0, 0.0])
    dot = spine_vec @ vertical
    norm = np.linalg.norm(spine_vec, axis=-1) + 1e-9
    angles["trunk_lean"] = np.degrees(np.arccos(np.clip(dot / norm, -1, 1)))

    # Pelvic tilt: height difference between left/right hip origins (meters).
    angles["pelvic_tilt"] = jp("l_upper_leg")[:, 1] - jp("r_upper_leg")[:, 1]
    return angles


def _rom(series: np.ndarray) -> RomStat:
    return RomStat(
        min=float(series.min()), max=float(series.max()),
        range=float(series.max() - series.min()),
        mean=float(series.mean()), std=float(series.std()),
    )


@dataclass
class Analysis:
    file: str
    frame_count: int
    duration_s: float
    rom: dict[str, dict]
    symmetry: dict[str, dict]
    velocities: dict[str, dict]
    pelvic_tilt_mean_mm: float
    angles: dict[str, list] = None      # per-frame, for the ML model / plots

    def summary(self) -> dict:
        """Compact dict for LLM prompts (no per-frame arrays)."""
        d = asdict(self)
        d.pop("angles", None)
        return d


def analyze(rec: Recording, include_frames: bool = True) -> Analysis:
    angles = compute_angles(rec)
    rom = {name: asdict(_rom(series)) for name, series in angles.items()}

    symmetry = {}
    for region, (l, r) in SYMMETRY_PAIRS.items():
        lr, rr = rom[l]["range"], rom[r]["range"]
        diff = abs(lr - rr)
        avg = (lr + rr) / 2 + 1e-9
        symmetry[region] = {
            "left_rom": round(lr, 2),
            "right_rom": round(rr, 2),
            "asymmetry_pct": round(diff / avg * 100, 1),
        }

    velocities = {}
    for name, idx in LOWER_BODY.items():
        traj = rec.positions[:, idx, :]
        speed = np.linalg.norm(np.diff(traj, axis=0), axis=1) if len(traj) > 1 else np.array([0.0])
        velocities[name] = {
            "mean_speed": round(float(speed.mean()), 4),
            "max_speed": round(float(speed.max()), 4),
        }

    return Analysis(
        file=rec.path,
        frame_count=rec.frame_count,
        duration_s=round(rec.duration_s, 2),
        rom=rom,
        symmetry=symmetry,
        velocities=velocities,
        pelvic_tilt_mean_mm=round(float(np.mean(np.abs(angles["pelvic_tilt"]))) * 1000, 1),
        angles={k: [round(float(v), 2) for v in series] for k, series in angles.items()}
        if include_frames else None,
    )
