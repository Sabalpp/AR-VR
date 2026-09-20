"""
Renders a proper 3D character video from a .skel file.
- All-white 3D humanoid character (cylinders + spheres)
- 3rd-person camera with subtle orbit
- Risk joints highlighted with colored glow rings
- MP4 output via OpenCV
"""
import os
import math
import argparse
import tempfile
import struct
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

# Load the renderer only once rendering starts, so CLI help is immediate.
pv = None

from skel_parser import parse_skel

# ── Joint index map (OVRBody2, 84 joints) ────────────────────────────────────
J = {
    'hips':         1,
    'spine_lo':     2,
    'spine_mid':    3,
    'spine_up':     4,
    'chest':        5,
    'neck':         6,
    'head':         7,
    'l_shoulder':   8,
    'l_upper_arm':  10,
    'l_lower_arm':  11,
    'l_hand':       18,
    'r_shoulder':   13,
    'r_upper_arm':  15,
    'r_lower_arm':  16,
    'r_hand':       44,
    'l_thigh':      70,
    'l_shin':       71,
    'l_ankle':      73,
    'l_foot':       76,
    'r_thigh':      77,
    'r_shin':       78,
    'r_ankle':      80,
    'r_foot':       83,
}

# Limb connections: (joint_a, joint_b, radius)
LIMBS = [
    # spine
    ('hips',        'spine_lo',    0.055),
    ('spine_lo',    'spine_mid',   0.055),
    ('spine_mid',   'spine_up',    0.052),
    ('spine_up',    'chest',       0.052),
    ('chest',       'neck',        0.035),
    ('neck',        'head',        0.030),
    # left arm
    ('chest',       'l_shoulder',  0.030),
    ('l_shoulder',  'l_upper_arm', 0.028),
    ('l_upper_arm', 'l_lower_arm', 0.025),
    ('l_lower_arm', 'l_hand',      0.020),
    # right arm
    ('chest',       'r_shoulder',  0.030),
    ('r_shoulder',  'r_upper_arm', 0.028),
    ('r_upper_arm', 'r_lower_arm', 0.025),
    ('r_lower_arm', 'r_hand',      0.020),
    # left leg
    ('hips',        'l_thigh',     0.052),
    ('l_thigh',     'l_shin',      0.045),
    ('l_shin',      'l_ankle',     0.032),
    ('l_ankle',     'l_foot',      0.022),
    # right leg
    ('hips',        'r_thigh',     0.052),
    ('r_thigh',     'r_shin',      0.045),
    ('r_shin',      'r_ankle',     0.032),
    ('r_ankle',     'r_foot',      0.022),
]

# Joint sphere radii
JOINT_RADII = {
    'head':        0.095,
    'hips':        0.065,
    'chest':       0.058,
    'neck':        0.030,
    'l_shoulder':  0.038, 'r_shoulder':  0.038,
    'l_upper_arm': 0.030, 'r_upper_arm': 0.030,
    'l_lower_arm': 0.025, 'r_lower_arm': 0.025,
    'l_hand':      0.028, 'r_hand':      0.028,
    'l_thigh':     0.048, 'r_thigh':     0.048,
    'l_shin':      0.038, 'r_shin':      0.038,
    'l_ankle':     0.030, 'r_ankle':     0.030,
    'l_foot':      0.022, 'r_foot':      0.022,
}

# Risk joints and which symmetry key drives their color
RISK_CONFIG = {
    'l_thigh': 'hip',  'l_shin': 'knee',
    'r_thigh': 'hip',  'r_shin': 'knee',
    'l_ankle': 'ankle', 'r_ankle': 'ankle',
    'hips':    'hip',
}

WHITE      = (1.00, 1.00, 1.00)
RISK_COLORS = {
    'normal': (0.00, 0.90, 1.00),   # cyan  — kept for glow rings only
    'low':    (1.00, 0.92, 0.27),
    'med':    (1.00, 0.60, 0.00),
    'high':   (0.96, 0.26, 0.21),
}
BG_COLOR   = (0.05, 0.07, 0.09)


def _risk_level(pct: float) -> str:
    if not math.isfinite(pct) or pct < 0:
        raise ValueError('asymmetry percentage must be finite and nonnegative')
    if pct < 15:  return 'normal'
    if pct < 35:  return 'low'
    if pct < 60:  return 'med'
    return 'high'


def _pos(joints, name):
    p = joints[J[name]]
    return (float(p[0]), float(p[2]), float(p[1]))   # swap y↔z for pyvista (z=up)


def _load_renderer():
    global pv
    if pv is None:
        import pyvista
        pv = pyvista
    return pv


@lru_cache(maxsize=32)
def _sphere(radius):
    return _load_renderer().Sphere(radius=radius, theta_resolution=24, phi_resolution=24)


@lru_cache(maxsize=16)
def _ring(radius):
    # A real ring, rather than a translucent ball obscuring the joint.
    angles = np.linspace(0, 2 * np.pi, 49)
    points = np.column_stack((radius * np.cos(angles),
                              np.zeros_like(angles), radius * np.sin(angles)))
    return _load_renderer().lines_from_points(points).tube(radius=0.006, n_sides=8)


def _cylinder(p1, p2, radius):
    """Return a pyvista cylinder mesh between two 3D points."""
    _load_renderer()
    cx = (p1[0] + p2[0]) / 2
    cy = (p1[1] + p2[1]) / 2
    cz = (p1[2] + p2[2]) / 2
    dx, dy, dz = p2[0]-p1[0], p2[1]-p1[1], p2[2]-p1[2]
    length = math.sqrt(dx*dx + dy*dy + dz*dz)
    if length < 1e-4:
        return None
    direction = (dx/length, dy/length, dz/length)
    cyl = pv.Cylinder(center=(cx, cy, cz), direction=direction,
                      radius=radius, height=length, resolution=16, capping=True)
    return cyl


def build_character_mesh(joints, risk_map: dict):
    """Build white body meshes and colored joint overlays."""
    meshes_white = []
    meshes_risk  = []   # list of (mesh, color_rgb)

    # ── Limb cylinders ──
    for (a, b, r) in LIMBS:
        pa = _pos(joints, a)
        pb = _pos(joints, b)
        cyl = _cylinder(pa, pb, r)
        if cyl is not None:
            meshes_white.append(cyl)

    # ── Joint spheres ──
    for name, radius in JOINT_RADII.items():
        p = _pos(joints, name)
        sphere = _sphere(radius).translate(p, inplace=False)
        meshes_white.append(sphere)

    # Colored rings around flagged joints
    for joint_name, sym_key in RISK_CONFIG.items():
        level = risk_map.get(sym_key, 'normal')
        if level not in RISK_COLORS:
            raise ValueError(f'Unknown risk level: {level!r}')
        if level == 'normal':
            continue
        p = _pos(joints, joint_name)
        r = JOINT_RADII.get(joint_name, 0.035) * 1.7
        ring = _ring(r).translate(p, inplace=False)
        meshes_risk.append((ring, RISK_COLORS[level]))

    return meshes_white, meshes_risk


def render_frame(plotter, joints, risk_map: dict, frame_idx: int, total_frames: int):
    plotter.set_background([*BG_COLOR])

    meshes_white, meshes_risk = build_character_mesh(joints, risk_map)

    # Draw white character
    plotter.add_mesh(pv.merge(meshes_white, merge_points=False),
                     name='body', color=WHITE, smooth_shading=True, reset_camera=False, render=False,
                     specular=0.4, specular_power=15, ambient=0.3)

    # Draw colored joint rings
    for index in range(len(RISK_CONFIG)):
        plotter.remove_actor(f'risk-{index}', reset_camera=False, render=False)
    for index, (mesh, color) in enumerate(meshes_risk):
        plotter.add_mesh(mesh, name=f'risk-{index}', color=color, opacity=0.85,
                         smooth_shading=True, ambient=0.8, reset_camera=False, render=False)

    # HUD text
    plotter.add_text(
        f'ARPT  |  Frame {frame_idx+1}/{total_frames}',
        name='hud', position='upper_left', font_size=11, color='white', font='courier', render=False
    )


def _open_writer(directory, fps, size):
    """AVFoundation requires a destination that does not already exist."""
    attempts = []
    for backend in (cv2.CAP_ANY, cv2.CAP_FFMPEG, cv2.CAP_AVFOUNDATION):
        for codec in ('avc1', 'mp4v'):
            path = Path(directory) / f'render-{backend}-{codec}.mp4'
            writer = cv2.VideoWriter(str(path), backend,
                                     cv2.VideoWriter_fourcc(*codec), fps, size)
            if writer.isOpened():
                print(f'  Encoder: {codec} ({writer.getBackendName()})', flush=True)
                return writer, path
            writer.release()
            attempts.append(f'{backend}/{codec}')
    raise RuntimeError('No working MP4 encoder. Tried: ' + ', '.join(attempts))


def _validate_video(path, expected_frames, size):
    capture = cv2.VideoCapture(str(path))
    count = 0
    try:
        if not capture.isOpened():
            raise RuntimeError('The encoded MP4 could not be opened.')
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if (frame.shape[1], frame.shape[0]) != size:
                raise RuntimeError('The encoded MP4 has incorrect dimensions.')
            count += 1
    finally:
        capture.release()
    if count != expected_frames:
        raise RuntimeError(f'Encoded {count} frames; expected {expected_frames}.')


def make_video(skel_path: str, output_path: str, fps: float = 24, step: int = 1,
               width: int = 720, height: int = 900):
    global pv
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError('fps must be positive and finite')
    if isinstance(step, bool) or not isinstance(step, int) or step < 1:
        raise ValueError('step must be a positive integer')
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 2 or v % 2 for v in (width, height)):
        raise ValueError('width and height must be positive even integers')
    source = Path(skel_path).expanduser().resolve()
    output = Path(output_path).expanduser().resolve()
    if output.suffix.lower() != '.mp4' or output == source:
        raise ValueError('output must be a separate .mp4 file')
    # Validate the binary layout before the parser allocates or unpacks frames.
    with source.open('rb') as recording:
        header = recording.read(8)
    if len(header) != 8:
        raise ValueError('Invalid .skel file: incomplete header')
    frame_count, joint_count = struct.unpack('<II', header)
    if frame_count == 0 or joint_count < 84:
        raise ValueError('The recording must contain frames with at least 84 joints')
    if source.stat().st_size != 8 + frame_count * (4 + joint_count * 12):
        raise ValueError('Invalid .skel file: size does not match its header')
    skel = parse_skel(str(source))
    frames = skel['frames']
    if not frames or skel['joint_count'] <= max(J.values()):
        raise ValueError('The recording must contain frames with at least 84 joints')
    if not all(np.asarray(f['joints']).shape == (joint_count, 3)
               and np.isfinite(f['joints']).all() for f in frames):
        raise ValueError('The recording contains non-finite joint coordinates')
    # Compute only the symmetry data needed here; this also supports one-frame files.
    from joint_analyzer import compute_joint_angles, compute_rom, compute_symmetry
    sym = compute_symmetry(compute_rom(compute_joint_angles(skel)))
    risk_map = {k: _risk_level(v['asymmetry_pct']) for k, v in sym.items()}
    sampled = frames[::step]
    points = np.array([[_pos(f['joints'], name) for name in J] for f in sampled])
    lower = points.min(axis=(0, 1)) - 0.15
    upper = points.max(axis=(0, 1)) + 0.15
    focal = (lower + upper) / 2
    # Fit the entire motion within both the horizontal and vertical field of view.
    radius = float(np.linalg.norm(upper - lower) / 2)
    half_fov = min(math.radians(22.5), math.atan(math.tan(math.radians(22.5)) * width / height))
    distance = max(2.2, radius / math.sin(half_fov))

    print('Loading PyVista / VTK...', flush=True)
    _load_renderer()
    print('3D renderer ready.', flush=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    # A sibling temporary file allows atomic replacement and preserves an old video on failure.
    with tempfile.TemporaryDirectory(prefix='.arpt-render-', dir=output.parent) as directory:
        writer, temporary = _open_writer(directory, fps, (width, height))
        plotter = None
        try:
            plotter = pv.Plotter(off_screen=True, window_size=[width, height])
            plotter.remove_all_lights()
            # Keep the floor fixed across the recording, including jumps.
            floor_z = float(points[:, [list(J).index('l_foot'), list(J).index('r_foot')], 2].min()) - 0.03
            ground = pv.Plane(center=(focal[0], focal[1], floor_z), direction=(0, 0, 1),
                              i_size=max(2.0, float(upper[0] - lower[0]) + 1),
                              j_size=max(2.0, float(upper[1] - lower[1]) + 1))
            plotter.add_mesh(ground, name='ground', color=(0.08, 0.10, 0.13),
                             reset_camera=False, render=False)
            plotter.add_text('Recording-wide ROM asymmetry', name='legend',
                             position='lower_left', font_size=9, color='white', render=False)
            for offset, intensity, color in (
                ((2, -2, 4), 0.9, 'white'),
                ((-2, 1, 3), 0.4, '#cce0ff'),
                ((0, 3, 1), 0.2, 'white'),
            ):
                plotter.add_light(pv.Light(position=focal + offset, focal_point=focal,
                                           intensity=intensity, color=color))
            print(f'  Rendering {len(sampled)} frames at {width}x{height} @ {fps:g}fps...', flush=True)
            for i, frame in enumerate(sampled):
                render_frame(plotter, frame['joints'], risk_map, i * step, len(frames))
                angle = math.radians(35 + 8 * math.sin(2 * math.pi * i / max(1, len(sampled) - 1)))
                direction = np.array([math.sin(angle), -math.cos(angle), 0.25])
                direction /= np.linalg.norm(direction)
                plotter.camera.position = focal + distance * direction
                plotter.camera.focal_point = focal
                plotter.camera.up = (0, 0, 1)
                plotter.camera.view_angle = 45
                plotter.reset_camera_clipping_range()
                if i == 0:
                    plotter.show(auto_close=False, interactive=False)
                else:
                    plotter.render()
                img = plotter.screenshot(return_img=True, transparent_background=False)
                if img is None or img.shape != (height, width, 3) or img.dtype != np.uint8:
                    raise RuntimeError('Renderer returned an invalid RGB frame')
                writer.write(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
                if (i + 1) % 20 == 0 or i == len(sampled) - 1:
                    print(f'    {i + 1}/{len(sampled)} frames written...', flush=True)
        finally:
            writer.release()
            if plotter is not None:
                plotter.close()
        _validate_video(temporary, len(sampled), (width, height))
        os.replace(temporary, output)
    print(f'Video saved: {output}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('skel_path', nargs='?', type=Path,
                        default=Path(__file__).resolve().parent / 'rec_20260919_164205.skel')
    parser.add_argument('-o', '--output', type=Path)
    parser.add_argument('--fps', type=float, default=24, help='Output FPS (default: 24)')
    parser.add_argument('--step', type=int, default=1, help='Render every Nth frame (speeds up playback)')
    parser.add_argument('--width', type=int, default=720)
    parser.add_argument('--height', type=int, default=900)
    args = parser.parse_args()
    output = args.output or args.skel_path.with_name(args.skel_path.stem + '_replay.mp4')
    print(f'Rendering 3D character video: {args.skel_path}', flush=True)
    try:
        make_video(args.skel_path, output, fps=args.fps, step=args.step,
                   width=args.width, height=args.height)
    except (ValueError, OSError, RuntimeError, ImportError) as exc:
        parser.exit(1, f'Error: {exc}\n')
    print('Done.', flush=True)
