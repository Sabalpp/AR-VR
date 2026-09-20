"""
Movement test catalogue.

Each test is a guided task the VR device walks the patient through. It defines:
- the instruction spoken to the patient (ElevenLabs / device speech-out)
- the primary joints tracked
- the reference movement phases used to build the green-path guide and to
  drive the red/yellow/green motion-state coloring
- form gates that trigger the "redo" loop when violated
- which kinematic metrics the test yields for diagnosis

Phase model: a test is a sequence of phases, each targeting an angle moving
toward a goal (e.g. knee flexion 170° -> 90°). The form guide interpolates the
target skeleton along these phases; the motion-state engine compares the live
angle against the phase goal to color the limb.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Phase:
    name: str
    joint_angle: str          # angle key from kinematics.ANGLE_DEFS
    start_deg: float
    goal_deg: float
    tolerance_deg: float = 12.0
    hold_s: float = 0.0       # seconds to hold at goal


@dataclass(frozen=True)
class FormGate:
    """A condition that must stay within bounds or the rep is rejected."""
    metric: str               # e.g. "trunk_lean", "pelvic_tilt", angle key
    max_abs: float            # allowed absolute deviation / value
    message: str              # spoken correction cue


@dataclass(frozen=True)
class MovementTest:
    id: str
    name: str
    instruction: str
    tracked_joints: tuple[str, ...]
    phases: tuple[Phase, ...]
    form_gates: tuple[FormGate, ...] = field(default_factory=tuple)
    reps: int = 3
    bilateral: bool = True    # performed per-side


TESTS: dict[str, MovementTest] = {}


def _add(t: MovementTest) -> None:
    TESTS[t.id] = t


_add(MovementTest(
    id="squat",
    name="Bilateral Squat",
    instruction="Stand tall, then slowly squat down as far as is comfortable, and rise back up.",
    tracked_joints=("left_knee", "right_knee", "left_hip", "right_hip", "trunk_lean"),
    phases=(
        Phase("descend", "left_knee", 170, 90, tolerance_deg=15),
        Phase("bottom", "left_knee", 90, 90, hold_s=1.0),
        Phase("ascend", "left_knee", 90, 170, tolerance_deg=15),
    ),
    form_gates=(
        FormGate("trunk_lean", 45.0, "Keep your chest a little more upright."),
    ),
))
_add(MovementTest(
    id="single_leg_squat",
    name="Single-Leg Squat",
    instruction="Stand on one leg and slowly bend that knee into a small squat, then rise.",
    tracked_joints=("left_knee", "left_hip", "pelvic_tilt"),
    phases=(
        Phase("descend", "left_knee", 175, 120, tolerance_deg=18),
        Phase("ascend", "left_knee", 120, 175, tolerance_deg=18),
    ),
    form_gates=(
        FormGate("pelvic_tilt", 0.04, "Keep your hips level, don't let one side drop."),
    ),
))
_add(MovementTest(
    id="step_down",
    name="Step-Down",
    instruction="Stand on the step and slowly lower the other foot toward the floor, then come back up.",
    tracked_joints=("left_knee", "left_hip", "pelvic_tilt"),
    phases=(
        Phase("lower", "left_knee", 175, 130, tolerance_deg=15),
        Phase("raise", "left_knee", 130, 175, tolerance_deg=15),
    ),
    form_gates=(
        FormGate("pelvic_tilt", 0.04, "Keep the hips level as you lower."),
    ),
))
_add(MovementTest(
    id="hip_hinge",
    name="Hip Hinge",
    instruction="Keep your back straight and bend forward from the hips, pushing them back, then stand up.",
    tracked_joints=("left_hip", "right_hip", "trunk_lean"),
    phases=(
        Phase("hinge", "left_hip", 175, 100, tolerance_deg=18),
        Phase("return", "left_hip", 100, 175, tolerance_deg=18),
    ),
    form_gates=(
        FormGate("trunk_lean", 70.0, "Hinge from the hips, don't round your back."),
    ),
))
_add(MovementTest(
    id="deep_squat_hold",
    name="Deep Squat Hold",
    instruction="Squat down as deep as you comfortably can and hold the position.",
    tracked_joints=("left_knee", "left_hip", "left_ankle", "trunk_lean"),
    phases=(
        Phase("descend", "left_knee", 170, 70, tolerance_deg=20),
        Phase("hold", "left_knee", 70, 70, hold_s=3.0),
    ),
    reps=1,
))
_add(MovementTest(
    id="single_leg_balance",
    name="Single-Leg Balance",
    instruction="Stand on one leg and hold your balance as still as you can.",
    tracked_joints=("l_ankle", "hips", "pelvic_tilt"),
    phases=(
        Phase("hold", "left_ankle", 100, 100, hold_s=10.0, tolerance_deg=25),
    ),
    form_gates=(
        FormGate("pelvic_tilt", 0.05, "Try to keep your hips level."),
    ),
    reps=1,
))
_add(MovementTest(
    id="tandem_stand",
    name="Tandem Stand",
    instruction="Place one foot directly in front of the other, heel to toe, and hold.",
    tracked_joints=("hips", "pelvic_tilt", "trunk_lean"),
    phases=(
        Phase("hold", "trunk_lean", 90, 90, hold_s=10.0, tolerance_deg=15),
    ),
    reps=1,
))
_add(MovementTest(
    id="sit_to_stand",
    name="Sit-to-Stand",
    instruction="From sitting, stand up fully without using your hands, then sit back down.",
    tracked_joints=("left_knee", "right_knee", "left_hip", "trunk_lean"),
    phases=(
        Phase("stand", "left_knee", 90, 175, tolerance_deg=15),
        Phase("sit", "left_knee", 175, 90, tolerance_deg=15),
    ),
    reps=5,
))
_add(MovementTest(
    id="heel_raise",
    name="Heel Raise",
    instruction="Rise up onto the balls of your feet as high as you can, then lower slowly.",
    tracked_joints=("left_ankle", "right_ankle"),
    phases=(
        Phase("raise", "left_ankle", 100, 130, tolerance_deg=15),
        Phase("lower", "left_ankle", 130, 100, tolerance_deg=15),
    ),
))
_add(MovementTest(
    id="toe_raise",
    name="Toe Raise",
    instruction="Keep your heels down and lift your toes and forefoot off the floor.",
    tracked_joints=("left_ankle", "right_ankle"),
    phases=(
        Phase("lift", "left_ankle", 100, 80, tolerance_deg=12),
        Phase("lower", "left_ankle", 80, 100, tolerance_deg=12),
    ),
))
_add(MovementTest(
    id="lateral_step",
    name="Lateral Step",
    instruction="Step sideways, load onto that leg in a small squat, then return.",
    tracked_joints=("left_knee", "left_hip", "pelvic_tilt"),
    phases=(
        Phase("load", "left_knee", 175, 140, tolerance_deg=18),
        Phase("return", "left_knee", 140, 175, tolerance_deg=18),
    ),
    form_gates=(
        FormGate("pelvic_tilt", 0.04, "Keep your hips level as you load the leg."),
    ),
))
_add(MovementTest(
    id="hop_landing",
    name="Hop and Land",
    instruction="Do a small hop forward and land softly on both feet, holding the landing.",
    tracked_joints=("left_knee", "right_knee", "pelvic_tilt"),
    phases=(
        Phase("land", "left_knee", 175, 140, tolerance_deg=20),
        Phase("stabilize", "left_knee", 140, 140, hold_s=2.0, tolerance_deg=20),
    ),
    form_gates=(
        FormGate("pelvic_tilt", 0.05, "Land with hips level and knees tracking forward."),
    ),
))
_add(MovementTest(
    id="gait_walk",
    name="Walking Gait",
    instruction="Walk normally back and forth at a comfortable pace.",
    tracked_joints=("left_knee", "right_knee", "left_hip", "right_hip", "left_ankle", "right_ankle"),
    phases=(
        Phase("cycle", "left_knee", 170, 130, tolerance_deg=30),
    ),
    reps=1,
    bilateral=False,
))


def test_catalog_for_prompt() -> list[dict]:
    return [
        {"id": t.id, "name": t.name, "instruction": t.instruction,
         "tracked_joints": list(t.tracked_joints)}
        for t in TESTS.values()
    ]
