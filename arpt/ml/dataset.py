"""
Dataset builder: .skel recordings -> normalized, augmented tensors for training.

Two feature representations are supported:
  - "pose"   : (T, J*3) hip-centered, scale-normalized joint positions
  - "angles" : (T, A) biomechanical angle series (knee/hip/ankle/trunk/pelvis)

Because a real deployment starts with very few labeled recordings, this module
provides aggressive, physiologically-plausible augmentation (jitter, temporal
warp, scaling, left/right mirroring) plus a synthetic generator so the training
pipeline is exercisable end-to-end before real labeled data arrives.

Labels come from a manifest JSON: {"filename.skel": ["condition_id", ...], ...}
Multi-label (a recording can show several conditions).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..core.skel import parse_skel, Recording, JOINTS
from ..core.kinematics import compute_angles, ANGLE_DEFS
from ..medical.conditions import all_ids

SEQ_LEN = 96                      # frames every clip is resampled to
ANGLE_KEYS = list(ANGLE_DEFS.keys()) + ["trunk_lean", "pelvic_tilt"]

# Left/right joint index pairs for mirror augmentation.
_MIRROR_PAIRS = [
    ("l_shoulder", "r_shoulder"), ("l_scapula", "r_scapula"),
    ("l_upper_arm", "r_upper_arm"), ("l_lower_arm", "r_lower_arm"),
    ("l_wrist_twist", "r_wrist_twist"), ("l_hand", "r_hand"),
    ("l_upper_leg", "r_upper_leg"), ("l_lower_leg", "r_lower_leg"),
    ("l_ankle", "r_ankle"), ("l_ankle_twist", "r_ankle_twist"),
    ("l_subtalar", "r_subtalar"), ("l_foot_transverse", "r_foot_transverse"),
    ("l_foot_ball", "r_foot_ball"),
]


@dataclass
class LabelSpace:
    ids: list[str]

    def encode(self, condition_ids: list[str]) -> np.ndarray:
        v = np.zeros(len(self.ids), dtype=np.float32)
        for cid in condition_ids:
            if cid in self.ids:
                v[self.ids.index(cid)] = 1.0
        return v

    def decode(self, probs: np.ndarray, threshold: float = 0.5) -> list[tuple[str, float]]:
        out = [(self.ids[i], float(p)) for i, p in enumerate(probs) if p >= threshold]
        return sorted(out, key=lambda x: -x[1])

    def to_json(self) -> dict:
        return {"ids": self.ids}

    @classmethod
    def default(cls) -> "LabelSpace":
        return cls(ids=all_ids())


# ── Normalization ───────────────────────────────────────────────────────────

def _resample(seq: np.ndarray, length: int) -> np.ndarray:
    """Linear-resample a (T, ...) sequence to `length` frames along axis 0."""
    t = seq.shape[0]
    if t == length:
        return seq
    src = np.linspace(0, 1, t)
    dst = np.linspace(0, 1, length)
    flat = seq.reshape(t, -1)
    out = np.empty((length, flat.shape[1]), dtype=np.float32)
    for c in range(flat.shape[1]):
        out[:, c] = np.interp(dst, src, flat[:, c])
    return out.reshape((length,) + seq.shape[1:])


def pose_features(rec: Recording) -> np.ndarray:
    """(T, J*3) hip-centered, height-normalized positions."""
    pos = rec.positions.astype(np.float32).copy()
    hips = pos[:, JOINTS["hips"], :][:, None, :]
    pos -= hips                                    # center on hips each frame
    # scale by standing height (head above foot) for size invariance
    head_y = rec.positions[:, JOINTS["head"], 1]
    foot_y = rec.positions[:, JOINTS["l_foot_ball"], 1]
    height = np.median(np.abs(head_y - foot_y)) + 1e-6
    pos /= height
    return pos.reshape(pos.shape[0], -1)


def angle_features(rec: Recording) -> np.ndarray:
    """(T, A) biomechanical angle series, scaled to roughly [-1, 1]."""
    angles = compute_angles(rec)
    cols = []
    for k in ANGLE_KEYS:
        s = np.asarray(angles[k], dtype=np.float32)
        if k == "pelvic_tilt":
            s = s * 10.0                            # meters -> comparable scale
        else:
            s = (s - 90.0) / 90.0                   # deg -> ~[-1,1]
        cols.append(s)
    return np.stack(cols, axis=1)


def featurize(rec: Recording, kind: str = "angles") -> np.ndarray:
    feat = angle_features(rec) if kind == "angles" else pose_features(rec)
    return _resample(feat, SEQ_LEN)


# ── Augmentation ──────────────────────────────────────────────────────────—

def _augment(feat: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    x = feat.copy()
    # gaussian jitter
    x += rng.normal(0, 0.02, x.shape).astype(np.float32)
    # amplitude scaling
    x *= rng.uniform(0.9, 1.1)
    # temporal warp: resample from a randomly cropped window
    t = x.shape[0]
    crop = rng.integers(int(t * 0.8), t + 1)
    start = rng.integers(0, t - crop + 1)
    x = _resample(x[start:start + crop], t)
    return x.astype(np.float32)


def _mirror_pose(rec: Recording) -> Recording:
    """Left/right mirrored copy (flip X, swap L/R joints) for pose features."""
    pos = rec.positions.copy()
    pos[..., 0] *= -1.0
    for l, r in _MIRROR_PAIRS:
        li, ri = JOINTS[l], JOINTS[r]
        pos[:, [li, ri], :] = pos[:, [ri, li], :]
    return Recording(path=rec.path + "#mirror", joint_count=rec.joint_count,
                     timestamps=rec.timestamps, positions=pos)


# ── Manifest / build ─────────────────────────────────────────────────────—

def load_manifest(path: str | Path) -> dict[str, list[str]]:
    with open(path) as f:
        return json.load(f)


def build_dataset(recordings_dir: str | Path, manifest: dict[str, list[str]],
                  kind: str = "angles", augment_factor: int = 40,
                  seed: int = 0) -> tuple[np.ndarray, np.ndarray, LabelSpace]:
    """
    Returns (X, Y, label_space).
      X: (N, SEQ_LEN, F)   Y: (N, C multi-hot)
    """
    rng = np.random.default_rng(seed)
    labels = LabelSpace.default()
    recordings_dir = Path(recordings_dir)

    X: list[np.ndarray] = []
    Y: list[np.ndarray] = []
    for fname, cond_ids in manifest.items():
        rec = parse_skel(recordings_dir / fname)
        y = labels.encode(cond_ids)

        base = featurize(rec, kind)
        X.append(base); Y.append(y)

        # mirror (pose only — angles are already side-labeled)
        if kind == "pose":
            X.append(featurize(_mirror_pose(rec), kind)); Y.append(y)

        for _ in range(augment_factor):
            X.append(_augment(base, rng)); Y.append(y)

    return np.asarray(X, np.float32), np.asarray(Y, np.float32), labels


def make_synthetic(label_space: LabelSpace, kind: str = "angles",
                   per_class: int = 60, seed: int = 1
                   ) -> tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic labeled clips so training can be demonstrated without a
    labeled corpus. Each condition maps to a characteristic angle-signal template
    (reduced ROM, asymmetry, sway, etc.). Purely for pipeline validation.
    """
    rng = np.random.default_rng(seed)
    F = len(ANGLE_KEYS) if kind == "angles" else len(JOINTS) * 3
    t = np.linspace(0, np.pi, SEQ_LEN)
    X, Y = [], []
    for ci, cid in enumerate(label_space.ids):
        for _ in range(per_class):
            x = rng.normal(0, 0.05, (SEQ_LEN, F)).astype(np.float32)
            depth = 0.8 + 0.2 * (ci % 3)               # class-specific squat depth
            x[:, 0] += -np.sin(t) * depth              # left knee-ish flexion
            x[:, 1] += -np.sin(t) * depth * (0.6 if "asym" in cid or ci % 2 else 1.0)
            x += ci * 0.01                             # class bias
            X.append(x)
            y = np.zeros(len(label_space.ids), np.float32); y[ci] = 1.0
            Y.append(y)
    return np.asarray(X, np.float32), np.asarray(Y, np.float32)
