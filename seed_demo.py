"""
Seed the portal with varied demo reports WITHOUT calling Gemini (rate-limit safe).
Uses real .skel recordings + real kinematic analysis; diagnosis blocks are
hand-authored so the dashboard has an urgent/soon/routine mix, and each patient
gets their own rendered movement-replay video.
"""
import shutil
from pathlib import Path
from arpt.portal.payload import build_report, save_report, REPORTS_DIR

DEMOS = [
    dict(
        skel="recordings/rec_20260919_164205.skel", test_id="step_down",
        video="rec_20260919_164205_replay.mp4",
        patient_id="patient_kathmandu_014",
        pain="My left knee is unstable and gives way going down stairs, and it locks up sometimes.",
        triage={"suspected_conditions": ["Meniscal Tear", "ACL Deficiency / Laxity"]},
        gemini=dict(
            urgency="soon",
            ailments=[
                dict(condition_id="meniscal_tear", name="Meniscal Tear",
                     confidence=0.88, affected_side="left", severity="moderate", region="knee",
                     reasoning="Mechanical locking with guarded knee flexion and 31% knee ROM asymmetry."),
                dict(condition_id="acl_deficiency", name="ACL Deficiency / Laxity",
                     confidence=0.82, affected_side="left", severity="moderate", region="knee",
                     reasoning="Reported giving-way with quadriceps-avoidance movement pattern."),
                dict(condition_id="pfps", name="Patellofemoral Pain Syndrome",
                     confidence=0.52, affected_side="left", severity="mild", region="knee",
                     reasoning="Pain descending stairs consistent with patellar loading."),
            ],
            key_findings=["Guarded left knee flexion during step-down",
                          "31% left/right knee ROM asymmetry",
                          "Compensatory weight-shift away from the left leg"],
            recommended_followup="McMurray and Lachman tests; MRI of the left knee.",
        ),
    ),
    dict(
        skel="recordings/rec_20260919_163945.skel", test_id="single_leg_balance",
        video="recordings/rec_20260919_163945_replay.mp4",
        patient_id="patient_pokhara_007",
        pain="I feel unsteady on my feet and I'm scared of falling when I stand up.",
        triage={"suspected_conditions": ["Balance / Proprioceptive Deficit"]},
        gemini=dict(
            urgency="urgent",
            ailments=[
                dict(condition_id="balance_deficit", name="Balance / Proprioceptive Deficit",
                     confidence=0.81, affected_side="bilateral", severity="moderate",
                     region="neuromuscular",
                     reasoning="Short single-leg stance tolerance and high postural sway; elevated fall risk."),
                dict(condition_id="glute_med_weakness", name="Gluteus Medius Weakness (Trendelenburg)",
                     confidence=0.44, affected_side="left", severity="mild", region="hip",
                     reasoning="Mild contralateral pelvic drop during stance."),
            ],
            key_findings=["Very short single-leg stance tolerance", "High center-of-mass sway"],
            recommended_followup="Falls-risk assessment; consider vestibular/neuro referral.",
        ),
    ),
    dict(
        skel="recordings/rec_20260919_163554.skel", test_id="single_leg_squat",
        video="recordings/rec_20260919_163554_replay.mp4",
        patient_id="patient_jumla_022",
        pain="My hip and knee ache and my knee caves inward when I go down stairs.",
        triage={"suspected_conditions": ["Gluteus Medius Weakness", "Patellofemoral Pain Syndrome"]},
        gemini=dict(
            urgency="routine",
            ailments=[
                dict(condition_id="glute_med_weakness", name="Gluteus Medius Weakness (Trendelenburg)",
                     confidence=0.72, affected_side="right", severity="moderate", region="hip",
                     reasoning="Dynamic knee valgus with pelvic drop during single-leg loading."),
                dict(condition_id="pfps", name="Patellofemoral Pain Syndrome",
                     confidence=0.58, affected_side="right", severity="mild", region="knee",
                     reasoning="Knee valgus and avoidance of deep flexion consistent with patellar maltracking."),
            ],
            key_findings=["Dynamic knee valgus on the right", "Pelvic drop during single-leg squat"],
            recommended_followup="Hip abductor strength testing; gait assessment.",
        ),
    ),
]


def main():
    # Fresh start so demo data is consistent.
    if REPORTS_DIR.exists():
        for p in REPORTS_DIR.glob("*.json"):
            p.unlink()

    for d in DEMOS:
        video = d["video"] if Path(d["video"]).exists() else None
        report = build_report(
            skel_path=d["skel"], pain_description=d["pain"], test_id=d["test_id"],
            patient_id=d["patient_id"], triage=d["triage"], gemini_diagnosis=d["gemini"],
            ml_predictions=[], replay_video_path=video,
        )
        save_report(report)
        top = d["gemini"]["ailments"][0]
        vid = "✓ video" if video else "no video"
        print(f"seeded {report['report_id']}  {d['patient_id']:24s} {d['gemini']['urgency']:7s} {vid}  {top['name']}")


if __name__ == "__main__":
    main()
