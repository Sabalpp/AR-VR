"""
End-to-end patient session orchestrator — the full device flow in one place.

    wear headset -> speak pain -> triage -> prescribe test -> (VR guides test) ->
    record .skel -> motion-quality check / redo -> diagnose (Gemini + ML) ->
    build doctor-portal report.

This is the seam the VR front-end and the CLI demo both call.
"""
from __future__ import annotations

from pathlib import Path

from .core.skel import parse_skel
from .core.kinematics import compute_angles
from .core.motion_state import evaluate_rep, summarize_states
from .medical.tests import TESTS
from .ai import gemini, voice
from .ml.infer import ConditionClassifier
from .portal.payload import build_report, save_report


def run_session(pain_description: str, skel_path: str,
                patient_id: str = "patient_001",
                test_id: str | None = None,
                replay_video_path: str | None = None,
                speak_prompts: bool = False) -> dict:
    if speak_prompts:
        voice.speak(voice.PROMPTS["analyzing"])

    # 1. Triage the complaint -> suspected conditions + test battery.
    triage = gemini.triage_pain(pain_description)
    chosen_test = test_id or (triage["prescribed_tests"][0] if triage["prescribed_tests"] else "squat")

    # 2. Motion-quality check on the recorded test (drives redo loop upstream).
    rec = parse_skel(skel_path)
    motion_summary = {}
    if chosen_test in TESTS:
        rep = evaluate_rep(compute_angles(rec), TESTS[chosen_test])
        motion_summary = {
            "accepted": rep.accepted,
            "reached_goal": rep.reached_goal,
            "peak_angle": rep.peak_angle,
            "violations": rep.violations,
            "states": summarize_states(rep.frames)["pct"],
        }

    # 3. Diagnosis: Gemini (knowledge-base grounded) + ML model if trained.
    diagnosis = gemini.diagnose(pain_description, skel_path,
                                TESTS.get(chosen_test).name if chosen_test in TESTS else chosen_test,
                                motion_summary)

    clf = ConditionClassifier()
    ml_preds = clf.predict_file(skel_path, threshold=0.3) if clf.available else []

    # 4. Build + persist the doctor-portal report.
    report = build_report(
        skel_path=skel_path,
        pain_description=pain_description,
        test_id=chosen_test,
        patient_id=patient_id,
        triage=triage,
        gemini_diagnosis=diagnosis,
        ml_predictions=ml_preds,
        replay_video_path=replay_video_path,
    )
    path = save_report(report)

    if speak_prompts:
        voice.speak(voice.PROMPTS["done"])

    return {"report": report, "report_path": str(path), "motion": motion_summary}


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser(description="Run a full ARPT patient session.")
    ap.add_argument("skel")
    ap.add_argument("--pain", default="Chronic left knee pain, unstable going down stairs, sometimes locks up.")
    ap.add_argument("--patient", default="patient_001")
    ap.add_argument("--test", default=None)
    ap.add_argument("--video", default=None)
    args = ap.parse_args()

    result = run_session(args.pain, args.skel, args.patient, args.test, args.video)
    print(f"\nReport saved: {result['report_path']}")
    r = result["report"]
    print(f"Report ID: {r['report_id']}  |  Test: {r['meta']['test_name']}")
    print("\nTop ailments:")
    for a in (r["diagnosis"]["gemini"].get("ailments") or [])[:4]:
        print(f"  {int(a.get('confidence',0)*100):3d}%  {a['name']} ({a.get('affected_side','?')})")
