import numpy as np
from skel_parser import parse_skel, get_joint_trajectory, LOWER_BODY


def angle_between(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Angle at point b formed by vectors b->a and b->c, in degrees."""
    v1 = a - b
    v2 = c - b
    cos_a = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9)
    return float(np.degrees(np.arccos(np.clip(cos_a, -1, 1))))


def compute_joint_angles(skel: dict) -> dict:
    """
    Compute key lower-body joint angles per frame.
    Returns dict of joint_name -> list of angles (one per frame).
    """
    frames = skel['frames']
    angles = {
        'left_knee': [],
        'right_knee': [],
        'left_hip': [],
        'right_hip': [],
        'left_ankle': [],
        'right_ankle': [],
        'trunk_lean': [],       # forward lean of spine
        'pelvic_tilt': [],      # hip asymmetry (L vs R hip height)
    }

    for f in frames:
        j = f['joints']
        hips    = j[LOWER_BODY['hips']]
        l_up    = j[LOWER_BODY['l_upper_leg']]
        l_lo    = j[LOWER_BODY['l_lower_leg']]
        l_ank   = j[LOWER_BODY['l_ankle']]
        l_foot  = j[LOWER_BODY['l_foot']]
        r_up    = j[LOWER_BODY['r_upper_leg']]
        r_lo    = j[LOWER_BODY['r_lower_leg']]
        r_ank   = j[LOWER_BODY['r_ankle']]
        r_foot  = j[LOWER_BODY['r_foot']]
        spine   = j[LOWER_BODY['spine_lower']]

        angles['left_knee'].append(angle_between(l_up, l_lo, l_ank))
        angles['right_knee'].append(angle_between(r_up, r_lo, r_ank))
        angles['left_hip'].append(angle_between(spine, hips, l_up))
        angles['right_hip'].append(angle_between(spine, hips, r_up))
        angles['left_ankle'].append(angle_between(l_lo, l_ank, l_foot))
        angles['right_ankle'].append(angle_between(r_lo, r_ank, r_foot))

        # Trunk lean: angle of spine from vertical (y-axis)
        spine_vec = spine - hips
        vertical = np.array([0, 1, 0])
        lean = float(np.degrees(np.arccos(np.clip(
            np.dot(spine_vec, vertical) / (np.linalg.norm(spine_vec) + 1e-9), -1, 1
        ))))
        angles['trunk_lean'].append(lean)

        # Pelvic tilt: difference in y between L and R upper leg origins
        angles['pelvic_tilt'].append(float(l_up[1] - r_up[1]))

    return angles


def compute_rom(angles: dict) -> dict:
    """Range of motion stats per angle."""
    rom = {}
    for name, vals in angles.items():
        arr = np.array(vals)
        rom[name] = {
            'min': float(arr.min()),
            'max': float(arr.max()),
            'range': float(arr.max() - arr.min()),
            'mean': float(arr.mean()),
            'std': float(arr.std()),
        }
    return rom


def compute_symmetry(rom: dict) -> dict:
    """Left-right symmetry scores (0=perfect, higher=more asymmetric)."""
    pairs = [
        ('left_knee', 'right_knee'),
        ('left_hip', 'right_hip'),
        ('left_ankle', 'right_ankle'),
    ]
    symmetry = {}
    for l, r in pairs:
        joint = l.replace('left_', '')
        l_range = rom[l]['range']
        r_range = rom[r]['range']
        diff = abs(l_range - r_range)
        avg = (l_range + r_range) / 2 + 1e-9
        symmetry[joint] = {
            'left_rom': round(l_range, 2),
            'right_rom': round(r_range, 2),
            'asymmetry_pct': round(diff / avg * 100, 1),
        }
    return symmetry


def compute_velocity(skel: dict, joint_idx: int) -> np.ndarray:
    """Frame-to-frame speed of a joint (m/frame)."""
    traj = get_joint_trajectory(skel, joint_idx)
    deltas = np.diff(traj, axis=0)
    return np.linalg.norm(deltas, axis=1)


def analyze(skel_path: str) -> dict:
    skel = parse_skel(skel_path)
    angles = compute_joint_angles(skel)
    rom = compute_rom(angles)
    symmetry = compute_symmetry(rom)

    # Velocity for key lower-body joints
    from skel_parser import LOWER_BODY
    velocities = {}
    for name, idx in LOWER_BODY.items():
        v = compute_velocity(skel, idx)
        velocities[name] = {
            'mean_speed': round(float(v.mean()), 4),
            'max_speed': round(float(v.max()), 4),
        }

    return {
        'file': skel_path,
        'frame_count': skel['frame_count'],
        'rom': rom,
        'symmetry': symmetry,
        'velocities': velocities,
        'angles_per_frame': {k: [round(v, 2) for v in vals] for k, vals in angles.items()},
        'pelvic_tilt_mean_mm': round(float(np.mean(np.abs(angles['pelvic_tilt']))) * 1000, 1),
    }


if __name__ == '__main__':
    import json, sys
    path = sys.argv[1] if len(sys.argv) > 1 else 'rec_20260919_164205.skel'
    result = analyze(path)
    # Print summary without the per-frame data
    summary = {k: v for k, v in result.items() if k != 'angles_per_frame'}
    print(json.dumps(summary, indent=2))
