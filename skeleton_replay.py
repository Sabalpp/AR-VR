"""
Generates a character-style skeleton replay from a .skel file.
Renders a 3rd-person 2D projected character with filled body segments,
capsule limbs, and risk-colored joints.
Outputs: animated GIF + per-frame PNG snapshots + summary image.
"""
import os
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.animation as animation
from matplotlib.patches import FancyBboxPatch, Circle, FancyArrowPatch
import matplotlib.patheffects as pe

from skel_parser import parse_skel, LOWER_BODY
from joint_analyzer import analyze

# ── Colors ────────────────────────────────────────────────────────────────────
COLOR_SKIN      = '#e8c49a'
COLOR_SUIT      = '#1a237e'     # dark blue body suit
COLOR_SUIT_LO   = '#283593'
COLOR_NORMAL    = '#00e5ff'
COLOR_RISK_LOW  = '#ffeb3b'
COLOR_RISK_MED  = '#ff9800'
COLOR_RISK_HIGH = '#f44336'
COLOR_SHADOW    = '#00000055'
COLOR_BG        = '#0d1117'
COLOR_GRID      = '#1e2a35'
COLOR_FLOOR     = '#161b22'

# ── Joint indices (OVRBody2) ───────────────────────────────────────────────────
J = {
    'root': 0, 'hips': 1,
    'spine_lo': 2, 'spine_mid': 3, 'spine_up': 4, 'chest': 5,
    'neck': 6, 'head': 7,
    'l_shoulder': 8,  'l_upper_arm': 10, 'l_lower_arm': 11, 'l_hand': 18,
    'r_shoulder': 13, 'r_upper_arm': 15, 'r_lower_arm': 16, 'r_hand': 44,
    'l_thigh': 70, 'l_shin': 71, 'l_ankle': 73, 'l_foot': 76,
    'r_thigh': 77, 'r_shin': 78, 'r_ankle': 80, 'r_foot': 83,
}

RISK_JOINTS = {70, 71, 77, 78, 73, 80, 1}


def risk_color(pct: float) -> str:
    if pct < 15:  return COLOR_NORMAL
    if pct < 35:  return COLOR_RISK_LOW
    if pct < 60:  return COLOR_RISK_MED
    return COLOR_RISK_HIGH


def build_risk_map(analysis: dict) -> dict:
    sym = analysis['symmetry']
    r = {}
    for idx in [70, 71, 77, 78]:
        r[idx] = risk_color(sym['knee']['asymmetry_pct'])
    for idx in [73, 80]:
        r[idx] = risk_color(sym['ankle']['asymmetry_pct'])
    r[1] = risk_color(sym['hip']['asymmetry_pct'])
    return r


# ── 3/4 isometric projection ──────────────────────────────────────────────────
# Projects world (x, y, z) → screen (sx, sy)
# y = height (up), x = left/right, z = depth
CAM_YAW   = math.radians(25)   # rotate around vertical
CAM_PITCH = math.radians(12)   # tilt down slightly

def project(x, y, z):
    # yaw rotation
    rx = x * math.cos(CAM_YAW) + z * math.sin(CAM_YAW)
    rz = -x * math.sin(CAM_YAW) + z * math.cos(CAM_YAW)
    # pitch rotation (affects height and depth)
    ry = y * math.cos(CAM_PITCH) - rz * math.sin(CAM_PITCH)
    # screen coords: x stays, y is height on screen
    return rx, ry


def jpos(joints, name):
    idx = J[name]
    p = joints[idx]
    return project(p[0], p[1], p[2])


# ── Drawing helpers ────────────────────────────────────────────────────────────

def capsule(ax, p1, p2, radius, color, alpha=1.0, zorder=3):
    """Draw a filled capsule (thick rounded line segment) between two 2D points."""
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) + 1e-9
    nx, ny = -dy / length * radius, dx / length * radius

    xs = [x1 + nx, x2 + nx, x2 - nx, x1 - nx]
    ys = [y1 + ny, y2 + ny, y2 - ny, y1 - ny]
    poly = mpatches.Polygon(list(zip(xs, ys)), closed=True,
                             facecolor=color, edgecolor='none', alpha=alpha, zorder=zorder)
    ax.add_patch(poly)
    ax.add_patch(Circle((x1, y1), radius, color=color, alpha=alpha, zorder=zorder))
    ax.add_patch(Circle((x2, y2), radius, color=color, alpha=alpha, zorder=zorder))


def draw_character(ax, joints, risk_map, frame_idx, total_frames, analysis):
    ax.cla()
    ax.set_facecolor(COLOR_BG)
    ax.set_aspect('equal')
    ax.axis('off')

    # ── compute projected positions for all named joints ──
    p = {name: jpos(joints, name) for name in J}

    # center view on hips
    cx, cy = p['hips']
    ax.set_xlim(cx - 0.55, cx + 0.55)
    ax.set_ylim(cy - 0.85, cy + 0.95)

    # ── floor shadow (ellipse under feet) ──
    floor_y = min(p['l_foot'][1], p['r_foot'][1]) - 0.04
    shadow = mpatches.Ellipse((cx, floor_y), 0.32, 0.06,
                               color='#000000', alpha=0.35, zorder=1)
    ax.add_patch(shadow)

    # ── floor line ──
    ax.axhline(floor_y, color=COLOR_FLOOR, linewidth=1.2, zorder=1, alpha=0.5)

    # ── BACK limbs (drawn first so front limbs overlap) ──
    # Determine which leg is "back" by depth (z)
    l_z = joints[J['l_thigh']][2]
    r_z = joints[J['r_thigh']][2]
    back_leg  = 'l' if l_z > r_z else 'r'
    front_leg = 'r' if back_leg == 'l' else 'l'
    back_arm  = 'l' if joints[J['l_upper_arm']][2] > joints[J['r_upper_arm']][2] else 'r'
    front_arm = 'r' if back_arm == 'l' else 'l'

    def draw_leg(side, is_back):
        thigh_c = risk_map.get(J[f'{side}_thigh'], COLOR_SUIT)
        shin_c  = risk_map.get(J[f'{side}_shin'],  COLOR_SUIT_LO)
        foot_c  = risk_map.get(J[f'{side}_ankle'], COLOR_SKIN)
        alpha = 0.55 if is_back else 1.0
        r_thigh = 0.038 if not is_back else 0.030
        r_shin  = 0.028 if not is_back else 0.022
        r_foot  = 0.018
        z = 2 if is_back else 4
        capsule(ax, p[f'{side}_thigh'], p[f'{side}_shin'],  r_thigh, thigh_c, alpha=alpha, zorder=z)
        capsule(ax, p[f'{side}_shin'],  p[f'{side}_ankle'], r_shin,  shin_c,  alpha=alpha, zorder=z)
        capsule(ax, p[f'{side}_ankle'], p[f'{side}_foot'],  r_foot,  foot_c,  alpha=alpha, zorder=z)

    def draw_arm(side, is_back):
        alpha = 0.55 if is_back else 1.0
        r_up  = 0.025 if not is_back else 0.018
        r_lo  = 0.020 if not is_back else 0.015
        z = 2 if is_back else 6
        capsule(ax, p[f'{side}_shoulder'],  p[f'{side}_upper_arm'], r_up, COLOR_SUIT,    alpha=alpha, zorder=z)
        capsule(ax, p[f'{side}_upper_arm'], p[f'{side}_lower_arm'], r_up, COLOR_SUIT,    alpha=alpha, zorder=z)
        capsule(ax, p[f'{side}_lower_arm'], p[f'{side}_hand'],      r_lo, COLOR_SUIT_LO, alpha=alpha, zorder=z)
        ax.add_patch(Circle(p[f'{side}_hand'], 0.022, color=COLOR_SKIN, zorder=z+1, alpha=alpha))

    draw_leg(back_leg, is_back=True)
    draw_arm(back_arm, is_back=True)

    # ── TORSO ──
    # Filled polygon: shoulders + hips
    ls = p['l_shoulder']; rs = p['r_shoulder']
    lh = p['hips'];       rh = p['hips']
    # widen hips slightly
    hw = 0.06
    torso_xs = [ls[0], rs[0], p['hips'][0] + hw, p['hips'][0] - hw]
    torso_ys = [ls[1], rs[1], p['hips'][1],       p['hips'][1]]
    torso_poly = mpatches.Polygon(list(zip(torso_xs, torso_ys)), closed=True,
                                   facecolor=COLOR_SUIT, edgecolor='none', alpha=0.95, zorder=3)
    ax.add_patch(torso_poly)

    # chest highlight strip
    mid_sh_x = (ls[0] + rs[0]) / 2
    mid_sh_y = (ls[1] + rs[1]) / 2
    ax.plot([mid_sh_x, p['hips'][0]], [mid_sh_y, p['hips'][1]],
            color='#3949ab', linewidth=2.5, zorder=4, alpha=0.6)

    # spine
    capsule(ax, p['hips'], p['chest'], 0.032, COLOR_SUIT, zorder=3)

    # shoulder width bar
    capsule(ax, p['l_shoulder'], p['r_shoulder'], 0.028, COLOR_SUIT, zorder=4)

    # ── FRONT limbs ──
    draw_leg(front_leg, is_back=False)
    draw_arm(front_arm, is_back=False)

    # ── HEAD ──
    neck  = p['neck']
    head  = p['head']
    # neck
    capsule(ax, p['chest'], neck, 0.022, COLOR_SKIN, zorder=5)
    # head sphere
    head_r = 0.072
    ax.add_patch(Circle(head, head_r, color=COLOR_SKIN, zorder=6))
    # face direction indicator (nose dot)
    ax.add_patch(Circle((head[0] + 0.025, head[1] - 0.01), 0.012,
                         color='#a0522d', zorder=7))
    # hair/helmet cap
    cap = mpatches.Arc(head, head_r * 2.1, head_r * 2.1,
                       angle=0, theta1=20, theta2=200,
                       color='#1a237e', linewidth=5, zorder=7)
    ax.add_patch(cap)

    # ── Risk joint glows ──
    for idx, color in risk_map.items():
        if color == COLOR_NORMAL:
            continue
        name = next((k for k, v in J.items() if v == idx), None)
        if name and name in p:
            glow = Circle(p[name], 0.045, color=color, alpha=0.25, zorder=8)
            dot  = Circle(p[name], 0.018, color=color, alpha=0.9,  zorder=9)
            ax.add_patch(glow)
            ax.add_patch(dot)

    # ── HUD overlay ──
    ax.text(0.02, 0.97, f'ARPT Medical  |  Frame {frame_idx+1}/{total_frames}',
            transform=ax.transAxes, color='white', fontsize=7.5,
            va='top', fontfamily='monospace',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#161b22', alpha=0.7))

    # Urgency / risk legend
    sym = analysis['symmetry']
    lines = [
        (risk_color(sym['knee']['asymmetry_pct']),   f"Knee   {sym['knee']['asymmetry_pct']:.0f}% asym"),
        (risk_color(sym['ankle']['asymmetry_pct']),  f"Ankle  {sym['ankle']['asymmetry_pct']:.0f}% asym"),
        (risk_color(sym['hip']['asymmetry_pct']),    f"Hip    {sym['hip']['asymmetry_pct']:.0f}% asym"),
    ]
    for i, (c, txt) in enumerate(lines):
        ax.text(0.98, 0.97 - i * 0.07, txt,
                transform=ax.transAxes, color=c, fontsize=7,
                va='top', ha='right', fontfamily='monospace')


# ── Public API ────────────────────────────────────────────────────────────────

def make_summary_panel(analysis: dict, output_path: str):
    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    fig.patch.set_facecolor(COLOR_BG)
    fig.suptitle('ARPT — Joint Analysis Summary', color='white', fontsize=13, fontweight='bold')

    # Panel 1: ROM
    ax = axes[0]
    ax.set_facecolor('#161b22')
    rom = analysis['rom']
    joints_plot = ['left_knee', 'right_knee', 'left_hip', 'right_hip', 'left_ankle', 'right_ankle']
    labels = ['L Knee', 'R Knee', 'L Hip', 'R Hip', 'L Ankle', 'R Ankle']
    ranges = [rom[j]['range'] for j in joints_plot]
    colors = ['#00e5ff' if 'left' in j else '#e91e63' for j in joints_plot]
    bars = ax.barh(labels, ranges, color=colors, alpha=0.85)
    ax.set_xlabel('Range of Motion (°)', color='grey', fontsize=8)
    ax.set_title('Joint ROM', color='white', fontsize=10)
    ax.tick_params(colors='white', labelsize=8)
    ax.spines[:].set_color('#2d3748')
    for bar, val in zip(bars, ranges):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                f'{val:.1f}°', va='center', color='white', fontsize=7)

    # Panel 2: Symmetry
    ax2 = axes[1]
    ax2.set_facecolor('#161b22')
    sym = analysis['symmetry']
    joint_names = list(sym.keys())
    asym_vals = [sym[j]['asymmetry_pct'] for j in joint_names]
    bar_colors = [risk_color(v) for v in asym_vals]
    ax2.bar(joint_names, asym_vals, color=bar_colors, alpha=0.9)
    ax2.axhline(15, color='#ffeb3b', linestyle='--', linewidth=1, alpha=0.6, label='Low threshold')
    ax2.axhline(35, color='#ff9800', linestyle='--', linewidth=1, alpha=0.6, label='Med threshold')
    ax2.set_ylabel('Asymmetry %', color='grey', fontsize=8)
    ax2.set_title('Left/Right Symmetry', color='white', fontsize=10)
    ax2.tick_params(colors='white', labelsize=8)
    ax2.spines[:].set_color('#2d3748')
    ax2.legend(fontsize=7, facecolor='#1e2a35', labelcolor='white', loc='upper right')
    for i, (name, val) in enumerate(zip(joint_names, asym_vals)):
        ax2.text(i, val + 1, f'{val:.0f}%', ha='center', color='white', fontsize=8)

    # Panel 3: Metrics table
    ax3 = axes[2]
    ax3.set_facecolor('#161b22')
    ax3.axis('off')
    ax3.set_title('Key Metrics', color='white', fontsize=10)
    metrics = [
        ('Pelvic Tilt (mean)', f"{analysis['pelvic_tilt_mean_mm']:.1f} mm"),
        ('Trunk Lean (mean)',  f"{analysis['rom']['trunk_lean']['mean']:.1f}°"),
        ('L Knee ROM',         f"{analysis['rom']['left_knee']['range']:.1f}°"),
        ('R Knee ROM',         f"{analysis['rom']['right_knee']['range']:.1f}°"),
        ('Knee Asymmetry',     f"{analysis['symmetry']['knee']['asymmetry_pct']:.1f}%"),
        ('Ankle Asymmetry',    f"{analysis['symmetry']['ankle']['asymmetry_pct']:.1f}%"),
        ('Frame Count',        str(analysis['frame_count'])),
    ]
    for i, (k, v) in enumerate(metrics):
        y = 0.88 - i * 0.12
        ax3.text(0.05, y, k, transform=ax3.transAxes, color='#90a4ae', fontsize=9)
        color = 'white'
        if 'Asymmetry' in k:
            color = risk_color(float(v.replace('%', '')))
        ax3.text(0.65, y, v, transform=ax3.transAxes, color=color, fontsize=9, fontweight='bold')

    plt.tight_layout()
    plt.savefig(output_path, dpi=120, bbox_inches='tight', facecolor=COLOR_BG)
    plt.close()
    print(f'Summary saved: {output_path}')


def make_replay_gif(skel_path: str, output_path: str, fps: int = 15, step: int = 2):
    skel     = parse_skel(skel_path)
    analysis = analyze(skel_path)
    risk_map = build_risk_map(analysis)
    frames   = skel['frames']
    sampled  = frames[::step]

    fig, ax = plt.subplots(figsize=(5, 7))
    fig.patch.set_facecolor(COLOR_BG)
    ax.set_facecolor(COLOR_BG)

    def update(i):
        draw_character(ax, sampled[i]['joints'], risk_map, i * step, len(frames), analysis)

    ani = animation.FuncAnimation(fig, update, frames=len(sampled), interval=1000 // fps)
    ani.save(output_path, writer='pillow', fps=fps, dpi=100)
    plt.close()
    print(f'Replay GIF saved: {output_path}')


def make_key_frames(skel_path: str, output_dir: str, n_frames: int = 6):
    os.makedirs(output_dir, exist_ok=True)
    skel     = parse_skel(skel_path)
    analysis = analyze(skel_path)
    risk_map = build_risk_map(analysis)
    frames   = skel['frames']
    n        = len(frames) - 1
    indices  = [int(round(i * n / (n_frames - 1))) for i in range(n_frames)]

    paths = []
    for num, idx in enumerate(indices):
        fig, ax = plt.subplots(figsize=(4, 6))
        fig.patch.set_facecolor(COLOR_BG)
        ax.set_facecolor(COLOR_BG)
        draw_character(ax, frames[idx]['joints'], risk_map, idx, len(frames), analysis)
        out = os.path.join(output_dir, f'frame_{num:02d}_{idx:04d}.png')
        plt.savefig(out, dpi=100, bbox_inches='tight', facecolor=COLOR_BG)
        plt.close()
        paths.append(out)

    print(f'Key frames saved to: {output_dir}')
    return paths


if __name__ == '__main__':
    import sys
    skel_path = sys.argv[1] if len(sys.argv) > 1 else 'rec_20260919_164205.skel'
    base = os.path.splitext(os.path.basename(skel_path))[0]

    print(f'Rendering character replay for: {skel_path}')
    make_summary_panel(analyze(skel_path), f'{base}_summary.png')
    make_replay_gif(skel_path, f'{base}_replay.gif', fps=12, step=2)
    make_key_frames(skel_path, f'{base}_frames/', n_frames=6)
    print('Done.')
