import struct
import numpy as np

# OVRBody2 joint indices (Meta Quest 3, 84 joints)
JOINTS = {
    0: 'Root',
    1: 'Hips',
    2: 'SpineLower',
    3: 'SpineMiddle',
    4: 'SpineUpper',
    5: 'Chest',
    6: 'Neck',
    7: 'Head',
    8: 'L_Shoulder',
    9: 'L_Scapula',
    10: 'L_ArmUpper',
    11: 'L_ArmLower',
    12: 'L_WristTwist',
    13: 'R_Shoulder',
    14: 'R_Scapula',
    15: 'R_ArmUpper',
    16: 'R_ArmLower',
    17: 'R_WristTwist',
    18: 'L_HandPalm',
    44: 'R_HandPalm',
    70: 'L_UpperLeg',
    71: 'L_LowerLeg',
    72: 'L_AnkleTwist',
    73: 'L_Ankle',
    74: 'L_Subtalar',
    75: 'L_FootTransverse',
    76: 'L_FootBall',
    77: 'R_UpperLeg',
    78: 'R_LowerLeg',
    79: 'R_AnkleTwist',
    80: 'R_Ankle',
    81: 'R_Subtalar',
    82: 'R_FootTransverse',
    83: 'R_FootBall',
}

# Skeleton connectivity for visualization
SKELETON_EDGES = [
    (0, 1),   # Root -> Hips
    (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7),  # spine -> head
    (5, 8), (8, 10), (10, 11), (11, 12), (12, 18),    # left arm
    (5, 13), (13, 15), (15, 16), (16, 17), (17, 44),  # right arm
    (1, 70), (70, 71), (71, 73), (73, 76),             # left leg
    (1, 77), (77, 78), (78, 80), (80, 83),             # right leg
]

# Key joints for lower-body injury analysis
LOWER_BODY = {
    'hips': 1,
    'l_upper_leg': 70, 'l_lower_leg': 71, 'l_ankle': 73, 'l_foot': 76,
    'r_upper_leg': 77, 'r_lower_leg': 78, 'r_ankle': 80, 'r_foot': 83,
    'spine_lower': 2,
}


def parse_skel(path: str) -> dict:
    with open(path, 'rb') as f:
        data = f.read()
    frame_count, joint_count = struct.unpack('<II', data[:8])
    frames = []
    for i in range(frame_count):
        off = 8 + i * (4 + joint_count * 12)
        ts = struct.unpack('<f', data[off:off + 4])[0]
        joints = np.array([
            struct.unpack('<fff', data[off + 4 + j * 12: off + 4 + j * 12 + 12])
            for j in range(joint_count)
        ], dtype=np.float32)
        frames.append({'timestamp': float(ts), 'joints': joints})
    return {
        'path': path,
        'frame_count': frame_count,
        'joint_count': joint_count,
        'frames': frames,
        'duration_frames': frame_count,
    }


def get_joint_trajectory(skel: dict, joint_idx: int) -> np.ndarray:
    """Returns (N, 3) array of joint positions across all frames."""
    return np.array([f['joints'][joint_idx] for f in skel['frames']])
