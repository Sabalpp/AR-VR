"""
Doctor-portal payload builder.

Assembles a single verifiable report per patient session: complaint, triage,
objective kinematics, motion-quality outcome, ML + Gemini diagnoses, and file
artifacts (skeletal recording, replay video). Reports are persisted as JSON
under reports/ so the portal server can list and serve them.
"""
from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..core.skel import parse_skel
from ..core.kinematics import analyze
from ..core.motion_state import evaluate_rep, summarize_states
from ..core.kinematics import compute_angles
from ..medical.tests import TESTS
from ..medical.conditions import CONDITIONS

REPORTS_DIR = Path("reports")


def _b64(path: str | None) -> str | None:
    if not path or not Path(path).exists():
        return None
    return base64.b64encode(Path(path).read_bytes()).decode()


def build_report(
    skel_path: str,
    pain_description: str,
    test_id: str,
    patient_id: str = "patient_001",
    triage: dict | None = None,
    gemini_diagnosis: dict | None = None,
    ml_predictions: list[dict] | None = None,
    replay_video_path: str | None = None,
    embed_files: bool = False,
) -> dict:
    rec = parse_skel(skel_path)
    analysis = analyze(rec, include_frames=False)

    # Motion-quality outcome for the prescribed test.
    motion = {}
    if test_id in TESTS:
        angles = compute_angles(rec)
        rep = evaluate_rep(angles, TESTS[test_id])
        motion = {
            "test_id": test_id,
            "accepted": rep.accepted,
            "reached_goal": rep.reached_goal,
            "peak_angle": rep.peak_angle,
            "violations": rep.violations,
            "state_distribution": summarize_states(rep.frames)["pct"],
        }

    # Enrich ML predictions with human-readable names.
    ml = []
    for p in (ml_predictions or []):
        cid = p.get("condition_id")
        ml.append({
            **p,
            "name": CONDITIONS[cid].name if cid in CONDITIONS else cid,
            "region": CONDITIONS[cid].region.value if cid in CONDITIONS else None,
        })

    report = {
        "report_id": str(uuid.uuid4())[:8],
        "meta": {
            "patient_id": patient_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "device": "ARPT / Meta Quest 3",
            "skel_file": Path(skel_path).name,
            "frame_count": analysis.frame_count,
            "duration_s": analysis.duration_s,
            "test_id": test_id,
            "test_name": TESTS[test_id].name if test_id in TESTS else test_id,
        },
        "patient_report": {
            "pain_description": pain_description,
            "triage": triage or {},
        },
        "objective_metrics": {
            "range_of_motion": analysis.rom,
            "symmetry": analysis.symmetry,
            "velocities": analysis.velocities,
            "pelvic_tilt_mean_mm": analysis.pelvic_tilt_mean_mm,
        },
        "motion_quality": motion,
        "diagnosis": {
            "gemini": gemini_diagnosis or {},
            "ml_model": ml,
        },
        "physician_review": {
            "status": "pending",       # pending | confirmed | revised
            "confirmed_diagnosis": None,
            "notes": "",
            "reviewed_by": None,
            "reviewed_at": None,
        },
        "artifacts": {
            "skel_file": Path(skel_path).name,
            "replay_video": Path(replay_video_path).name if replay_video_path else None,
            # Full (relative) path so the server can locate it regardless of dir.
            "replay_video_path": str(replay_video_path) if replay_video_path else None,
        },
    }

    if embed_files:
        report["artifacts"]["skel_b64"] = _b64(skel_path)
        report["artifacts"]["replay_video_b64"] = _b64(replay_video_path)

    return report


def save_report(report: dict, reports_dir: str | Path = REPORTS_DIR) -> Path:
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(exist_ok=True)
    path = reports_dir / f"{report['report_id']}.json"
    path.write_text(json.dumps(report, indent=2))
    return path


_URGENCY_RANK = {"urgent": 0, "soon": 1, "routine": 2}


def list_reports(reports_dir: str | Path = REPORTS_DIR) -> list[dict]:
    reports_dir = Path(reports_dir)
    if not reports_dir.exists():
        return []
    out = []
    for p in sorted(reports_dir.glob("*.json"), reverse=True):
        try:
            r = json.loads(p.read_text())
            gemini = r["diagnosis"]["gemini"]
            top = (gemini.get("ailments") or [{}])[0]
            out.append({
                "report_id": r["report_id"],
                "patient_id": r["meta"]["patient_id"],
                "timestamp_utc": r["meta"]["timestamp_utc"],
                "test_name": r["meta"]["test_name"],
                "status": r["physician_review"]["status"],
                "urgency": gemini.get("urgency", "routine"),
                "top_ailment": top.get("name"),
                "top_confidence": top.get("confidence"),
                "top_region": top.get("region") or _region_of(top.get("name")),
            })
        except (KeyError, json.JSONDecodeError):
            continue
    return out


def _region_of(ailment_name: str | None) -> str | None:
    if not ailment_name:
        return None
    for c in CONDITIONS.values():
        if c.name == ailment_name:
            return c.region.value
    return None


def triage_queue(reports_dir: str | Path = REPORTS_DIR) -> list[dict]:
    """Reports ordered for a physician's work queue: pending first, then by
    urgency (urgent -> soon -> routine), then most recent."""
    reports = list_reports(reports_dir)
    # list_reports already returns newest-first; stable-sort preserves that
    # recency ordering within equal (pending, urgency) groups.
    return sorted(reports, key=lambda r: (
        r["status"] != "pending",                       # pending float to top
        _URGENCY_RANK.get(r["urgency"], 3),             # urgent first
    ))


def overview(reports_dir: str | Path = REPORTS_DIR) -> dict:
    """Aggregate stats for the dashboard landing view."""
    reports = list_reports(reports_dir)
    total = len(reports)
    by_status: dict[str, int] = {}
    by_urgency: dict[str, int] = {}
    by_region: dict[str, int] = {}
    by_ailment: dict[str, int] = {}
    agree = disagree = reviewed = 0

    for r in reports:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        by_urgency[r["urgency"]] = by_urgency.get(r["urgency"], 0) + 1
        if r.get("top_region"):
            by_region[r["top_region"]] = by_region.get(r["top_region"], 0) + 1
        if r.get("top_ailment"):
            by_ailment[r["top_ailment"]] = by_ailment.get(r["top_ailment"], 0) + 1
        if r["status"] in ("confirmed", "revised"):
            reviewed += 1
            if r["status"] == "confirmed":
                agree += 1
            else:
                disagree += 1

    return {
        "total": total,
        "pending": by_status.get("pending", 0),
        "urgent_pending": sum(
            1 for r in reports if r["status"] == "pending" and r["urgency"] == "urgent"
        ),
        "by_status": by_status,
        "by_urgency": by_urgency,
        "by_region": dict(sorted(by_region.items(), key=lambda x: -x[1])),
        "top_ailments": dict(sorted(by_ailment.items(), key=lambda x: -x[1])[:6]),
        "reviewed": reviewed,
        "ai_agreement_pct": round(agree / reviewed * 100, 1) if reviewed else None,
    }
