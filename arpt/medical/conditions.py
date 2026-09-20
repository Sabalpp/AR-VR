"""
Musculoskeletal condition catalogue — hip-down focus.

Each condition carries the metadata the diagnosis and triage layers need:
the body region, plain-language description, hallmark symptoms, the kinematic
signatures the ML model / analyzer should look for, and clinical urgency.

This is intentionally a curated, auditable knowledge base rather than something
the LLM invents on the fly — a medical device needs traceable reasoning.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Region(str, Enum):
    KNEE = "knee"
    HIP = "hip"
    ANKLE = "ankle"
    FOOT = "foot"
    LUMBAR = "lumbar"           # low back / pelvis
    NEUROMUSCULAR = "neuromuscular"


class Urgency(str, Enum):
    ROUTINE = "routine"
    SOON = "soon"
    URGENT = "urgent"


@dataclass(frozen=True)
class Condition:
    id: str
    name: str
    region: Region
    description: str
    symptoms: tuple[str, ...]
    kinematic_signatures: tuple[str, ...]   # what to look for in joint data
    recommended_tests: tuple[str, ...]      # test ids from tests.py
    default_urgency: Urgency = Urgency.ROUTINE
    icd10: str = ""                         # rough ICD-10 pointer for portal


CONDITIONS: dict[str, Condition] = {}


def _add(c: Condition) -> None:
    CONDITIONS[c.id] = c


# ── KNEE ────────────────────────────────────────────────────────────────────
_add(Condition(
    id="acl_deficiency",
    name="ACL Deficiency / Laxity",
    region=Region.KNEE,
    description="Anterior cruciate ligament insufficiency causing rotational knee instability.",
    symptoms=("knee gives way", "instability", "swelling after activity", "pivoting pain"),
    kinematic_signatures=(
        "excessive medial knee collapse (valgus) during single-leg loading",
        "reduced knee flexion under load (quadriceps avoidance)",
        "left/right knee ROM asymmetry",
    ),
    recommended_tests=("single_leg_squat", "hop_landing", "step_down"),
    default_urgency=Urgency.SOON,
    icd10="S83.5",
))
_add(Condition(
    id="meniscal_tear",
    name="Meniscal Tear",
    region=Region.KNEE,
    description="Tear of the knee meniscus producing mechanical locking/catching.",
    symptoms=("locking", "catching", "pain with squatting", "pain descending stairs"),
    kinematic_signatures=(
        "sudden restriction / hitch in knee flexion arc",
        "guarded, reduced knee flexion range",
        "asymmetric weight-bearing away from affected side",
    ),
    recommended_tests=("squat", "step_down", "deep_squat_hold"),
    default_urgency=Urgency.SOON,
    icd10="S83.2",
))
_add(Condition(
    id="pfps",
    name="Patellofemoral Pain Syndrome",
    region=Region.KNEE,
    description="Anterior knee pain from patellar maltracking under load.",
    symptoms=("pain behind kneecap", "pain with stairs", "pain after prolonged sitting"),
    kinematic_signatures=(
        "dynamic knee valgus during squat/step-down",
        "avoidance of deep knee flexion",
        "hip adduction / internal rotation during loading",
    ),
    recommended_tests=("step_down", "single_leg_squat", "squat"),
    default_urgency=Urgency.ROUTINE,
    icd10="M22.2",
))
_add(Condition(
    id="knee_oa",
    name="Knee Osteoarthritis",
    region=Region.KNEE,
    description="Degenerative cartilage loss producing stiffness and reduced motion.",
    symptoms=("chronic ache", "morning stiffness", "crepitus", "reduced range"),
    kinematic_signatures=(
        "globally reduced knee flexion ROM",
        "slow movement velocity",
        "stiff-legged compensatory gait/squat",
    ),
    recommended_tests=("squat", "sit_to_stand", "gait_walk"),
    default_urgency=Urgency.ROUTINE,
    icd10="M17",
))

# ── HIP ───────────────────────────────────────────────────────────────────—
_add(Condition(
    id="hip_oa",
    name="Hip Osteoarthritis",
    region=Region.HIP,
    description="Degenerative hip joint disease limiting flexion and rotation.",
    symptoms=("groin pain", "stiffness", "reduced hip motion", "limp"),
    kinematic_signatures=(
        "reduced hip flexion range during squat/hinge",
        "compensatory trunk lean toward affected side",
        "pelvic drop in single-leg stance",
    ),
    recommended_tests=("hip_hinge", "single_leg_balance", "squat"),
    default_urgency=Urgency.ROUTINE,
    icd10="M16",
))
_add(Condition(
    id="glute_med_weakness",
    name="Gluteus Medius Weakness (Trendelenburg)",
    region=Region.HIP,
    description="Hip abductor weakness causing pelvic instability in single-leg stance.",
    symptoms=("hip/buttock fatigue", "instability when walking", "knee cave-in"),
    kinematic_signatures=(
        "contralateral pelvic drop during single-leg stance (Trendelenburg sign)",
        "hip adduction and dynamic knee valgus",
        "trunk lateral lean to compensate",
    ),
    recommended_tests=("single_leg_balance", "single_leg_squat", "lateral_step"),
    default_urgency=Urgency.ROUTINE,
    icd10="M62.5",
))
_add(Condition(
    id="fai",
    name="Femoroacetabular Impingement",
    region=Region.HIP,
    description="Abnormal hip contact limiting deep flexion, often with groin pinch.",
    symptoms=("groin pinch in deep flexion", "pain sitting", "limited squat depth"),
    kinematic_signatures=(
        "hard end-range limit on hip flexion during deep squat",
        "posterior pelvic tilt / lumbar flexion to gain depth",
        "asymmetric hip flexion left vs right",
    ),
    recommended_tests=("deep_squat_hold", "hip_hinge", "squat"),
    default_urgency=Urgency.ROUTINE,
    icd10="M25.85",
))

# ── ANKLE / FOOT ─────────────────────────────────────────────────────────—
_add(Condition(
    id="ankle_instability",
    name="Chronic Ankle Instability",
    region=Region.ANKLE,
    description="Recurrent giving-way of the ankle after prior sprains.",
    symptoms=("ankle rolls", "instability on uneven ground", "recurrent sprains"),
    kinematic_signatures=(
        "excessive ankle sway in single-leg balance",
        "reduced dorsiflexion ROM",
        "large ankle motion asymmetry",
    ),
    recommended_tests=("single_leg_balance", "heel_raise", "lateral_step"),
    default_urgency=Urgency.ROUTINE,
    icd10="M25.37",
))
_add(Condition(
    id="limited_dorsiflexion",
    name="Limited Ankle Dorsiflexion",
    region=Region.ANKLE,
    description="Restricted ankle bend that drives compensations up the chain.",
    symptoms=("heel rises early in squat", "calf tightness", "forward trunk lean"),
    kinematic_signatures=(
        "low ankle dorsiflexion angle at squat bottom",
        "early heel-off / forward trunk lean to compensate",
        "asymmetric ankle ROM",
    ),
    recommended_tests=("squat", "heel_raise", "deep_squat_hold"),
    default_urgency=Urgency.ROUTINE,
    icd10="M24.57",
))

# ── LUMBAR / PELVIS ─────────────────────────────────────────────────────────
_add(Condition(
    id="lumbar_dysfunction",
    name="Lumbopelvic Movement Dysfunction",
    region=Region.LUMBAR,
    description="Poor lumbopelvic control causing back-dominant movement patterns.",
    symptoms=("low back pain with bending", "pain lifting", "stiffness"),
    kinematic_signatures=(
        "excessive lumbar flexion during hip hinge",
        "reduced hip contribution to forward bend",
        "trunk lean asymmetry",
    ),
    recommended_tests=("hip_hinge", "sit_to_stand", "squat"),
    default_urgency=Urgency.ROUTINE,
    icd10="M54.5",
))

# ── NEUROMUSCULAR ────────────────────────────────────────────────────────—
_add(Condition(
    id="balance_deficit",
    name="Balance / Proprioceptive Deficit",
    region=Region.NEUROMUSCULAR,
    description="Impaired postural control raising fall risk — key for rural elderly.",
    symptoms=("unsteadiness", "fear of falling", "near-falls", "needs support"),
    kinematic_signatures=(
        "high center-of-mass sway in quiet stance",
        "short single-leg stance tolerance",
        "wide, guarded movements",
    ),
    recommended_tests=("single_leg_balance", "tandem_stand", "sit_to_stand"),
    default_urgency=Urgency.SOON,
    icd10="R26.81",
))
_add(Condition(
    id="foot_drop",
    name="Foot Drop (Dorsiflexor Weakness)",
    region=Region.NEUROMUSCULAR,
    description="Weak ankle dorsiflexors, often neurological — steppage gait.",
    symptoms=("toe catches walking", "slapping foot", "trips easily"),
    kinematic_signatures=(
        "exaggerated hip/knee flexion in swing (steppage)",
        "foot plantarflexed through swing",
        "asymmetric foot clearance",
    ),
    recommended_tests=("gait_walk", "heel_raise", "toe_raise"),
    default_urgency=Urgency.URGENT,
    icd10="M21.37",
))


def by_region(region: Region) -> list[Condition]:
    return [c for c in CONDITIONS.values() if c.region == region]


def all_ids() -> list[str]:
    return list(CONDITIONS.keys())


def condition_catalog_for_prompt() -> list[dict]:
    """Compact serialization for LLM triage/diagnosis prompts."""
    return [
        {
            "id": c.id,
            "name": c.name,
            "region": c.region.value,
            "symptoms": list(c.symptoms),
            "signatures": list(c.kinematic_signatures),
            "tests": list(c.recommended_tests),
        }
        for c in CONDITIONS.values()
    ]
