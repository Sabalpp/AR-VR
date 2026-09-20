"""
Test suite for the shipped ARPT / Meta Care package.

Covers the core pipeline (parse -> kinematics -> motion state), the medical
knowledge base and test selection, the portal payload/aggregation, and the
API's security-relevant behaviors (path traversal, review validation).

Run:  venv/bin/python -m pytest tests/ -q
"""
import json
import struct
import tempfile
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from arpt.core.skel import parse_skel, JOINTS
from arpt.core.kinematics import analyze, compute_angles
from arpt.core.motion_state import evaluate_rep, MotionState, green_path_target
from arpt.medical.conditions import CONDITIONS
from arpt.medical.tests import TESTS
from arpt.medical.mapping import select_test_battery
from arpt.medical.mapping import tests_for_condition as _tests_for_condition

REC = "recordings/rec_20260919_164205.skel"


# ── Core: parser ──────────────────────────────────────────────────────────────
def test_parse_real_recording():
    rec = parse_skel(REC)
    assert rec.frame_count == 290
    assert rec.joint_count == 84
    assert rec.positions.shape == (290, 84, 3)
    assert rec.fps > 0


def test_parse_rejects_truncated_file():
    with tempfile.NamedTemporaryFile(suffix=".skel", delete=False) as f:
        f.write(struct.pack("<II", 10, 84))  # header claims 10 frames, no data
        path = f.name
    with pytest.raises(ValueError):
        parse_skel(path)


# ── Core: kinematics ──────────────────────────────────────────────────────────
def test_analyze_produces_expected_metrics():
    a = analyze(parse_skel(REC), include_frames=False)
    assert set(a.symmetry) == {"knee", "hip", "ankle"}
    for region in a.symmetry.values():
        assert 0 <= region["asymmetry_pct"] <= 200
    assert "left_knee" in a.rom
    assert a.duration_s > 0


# ── Core: motion state / green path ───────────────────────────────────────────
def test_green_path_interpolates_within_bounds():
    test = TESTS["squat"]
    lo = min(p.goal_deg for p in test.phases)
    hi = max(p.start_deg for p in test.phases)
    for prog in (0.0, 0.25, 0.5, 0.75, 1.0):
        target = green_path_target(test, "left_knee", prog)
        assert lo - 1 <= target <= hi + 1


def test_evaluate_rep_returns_states_and_summary():
    rep = evaluate_rep(compute_angles(parse_skel(REC)), TESTS["squat"])
    assert rep.frames
    assert all(f.state in MotionState for f in rep.frames)
    assert isinstance(rep.accepted, bool)


# ── Medical knowledge base ────────────────────────────────────────────────────
def test_every_condition_maps_to_real_tests():
    for cid in CONDITIONS:
        for t in _tests_for_condition(cid):
            assert t.id in TESTS


def test_test_battery_covers_suspected_conditions():
    battery = select_test_battery(["acl_deficiency", "pfps", "glute_med_weakness"])
    assert 1 <= len(battery) <= 4
    chosen = {t.id for t in battery}
    # every suspected condition should be probed by at least one chosen test
    for cid in ["acl_deficiency", "pfps", "glute_med_weakness"]:
        assert chosen & set(CONDITIONS[cid].recommended_tests)


def test_test_battery_handles_unknown_ids():
    battery = select_test_battery(["not_a_real_condition"])
    assert len(battery) >= 1  # falls back to a default battery


# ── Portal payload / aggregation ──────────────────────────────────────────────
def test_build_and_aggregate_report(tmp_path, monkeypatch):
    import arpt.portal.payload as payload
    monkeypatch.setattr(payload, "REPORTS_DIR", tmp_path)

    report = payload.build_report(
        skel_path=REC, pain_description="test knee pain", test_id="squat",
        patient_id="p_test",
        gemini_diagnosis={"urgency": "soon", "ailments": [
            {"condition_id": "meniscal_tear", "name": "Meniscal Tear",
             "confidence": 0.9, "region": "knee"}]},
    )
    payload.save_report(report, tmp_path)

    listed = payload.list_reports(tmp_path)
    assert len(listed) == 1
    assert listed[0]["urgency"] == "soon"

    ov = payload.overview(tmp_path)
    assert ov["total"] == 1
    assert ov["by_region"].get("knee") == 1

    q = payload.triage_queue(tmp_path)
    assert q[0]["status"] == "pending"


# ── API security & validation ─────────────────────────────────────────────────
@pytest.fixture
def client():
    from arpt.portal.server import app
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_path_traversal_blocked(client):
    r = client.get("/api/reports/..%2f..%2fetc%2fpasswd")
    assert r.status_code in (400, 404)


def test_invalid_report_id_rejected(client):
    r = client.get("/api/reports/not a valid id!")
    assert r.status_code == 400


def test_review_status_validation(client):
    # need a real report id
    q = client.get("/api/queue").json()
    if not q:
        pytest.skip("no reports seeded")
    rid = q[0]["report_id"]
    bad = client.post(f"/api/reports/{rid}/review", json={"status": "hacked"})
    assert bad.status_code == 422
    good = client.post(f"/api/reports/{rid}/review",
                       json={"status": "confirmed", "reviewed_by": "Dr. Test"})
    assert good.status_code == 200
    assert good.json()["review"]["status"] == "confirmed"


def test_missing_report_404(client):
    r = client.get("/api/reports/deadbeef00")
    assert r.status_code == 404
