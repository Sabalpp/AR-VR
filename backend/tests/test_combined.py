"""Isolated synthetic fixtures; these tests do not establish hardware acceptance."""

from datetime import datetime, timedelta, timezone

import pytest
from test_system import client as client
from test_system import frame, login

from app.schemas.api import ExerciseConfig, Frame
from app.services.movement import trunk_lean


def torso(seq, captured_at, x=0.5, valid=True):
    value = frame(seq)
    value.update(captured_at=captured_at.isoformat(), tracking_valid=valid)
    value["joints"] = {
        "right_shoulder": {"x": x, "y": 0.3, "visibility": 1},
        "right_hip": {"x": 0.5, "y": 0.7, "visibility": 1},
    }
    return value


def test_trunk_geometry_visibility_and_aspect():
    stamp = datetime.now(timezone.utc)
    config = ExerciseConfig().model_dump()
    value = torso(0, stamp)
    assert trunk_lean(Frame(**value), config) == 0
    value["joints"]["right_shoulder"]["x"] = 0.7
    value["image_width"] = 2000
    assert trunk_lean(Frame(**value), config) == pytest.approx(45)
    value["joints"]["right_hip"]["inferred"] = True
    assert trunk_lean(Frame(**value), config) is None
    value["joints"].pop("right_hip")
    assert trunk_lean(Frame(**value), config) is None


def combined(c):
    auth = login(c)
    assignment = c.get("/api/v1/assignments", headers=auth).json()[0]
    session = c.post(
        "/api/v1/sessions",
        headers=auth,
        json={
            "assignment_id": assignment["id"],
            "mode": "combined",
            "is_synthetic": True,
        },
    ).json()
    path = "/api/v1/sessions/" + session["id"]
    devices = []
    for source in ("simulator_phone", "simulator_quest"):
        pairing = c.post(path + "/pairing", headers=auth, json={"source": source}).json()
        device = c.post(
            "/api/v1/devices/pair", json={"code": pairing["code"], "expected_source": source}
        ).json()
        devices.append({"Authorization": "Bearer " + device["device_token"]})
    return auth, session, path, *devices


def test_combined_readiness_counter_isolation_and_review(client, monkeypatch):
    stamp = datetime.now(timezone.utc)
    monkeypatch.setattr("app.services.sessions.now", lambda: stamp)
    auth, session, path, phone, quest = combined(client)
    assert session["state"]["status"] == "paused"
    assert session["config_snapshot"]["audio_owner"] == "quest"
    assert client.post(path + "/resume", headers=quest, json={}).status_code == 409
    frames = [torso(i, stamp - timedelta(milliseconds=1100 - i * 100)) for i in range(12)]
    result = client.post(path + "/movement", headers=phone, json={"frames": frames}).json()
    assert result["state"]["phone_setup_ready"]
    assert result["state"]["repetitions"] == 0
    assert client.post(path + "/resume", headers=phone, json={}).status_code == 403
    assert client.post(path + "/resume", headers=quest, json={}).status_code == 200
    quest_frames = [frame(i, reach=3 <= i < 6, mode="quest") for i in range(9)]
    result = client.post(path + "/movement", headers=quest, json={"frames": quest_frames}).json()
    assert result["state"]["repetitions"] == 1
    lean = torso(12, stamp + timedelta(milliseconds=100), x=0.8)
    result = client.post(path + "/movement", headers=phone, json={"frames": [lean]}).json()
    assert result["state"]["repetitions"] == 1
    assert result["state"]["phone_trunk_review"]
    before = result["state"]["trunk_review_frames"]
    duplicate = client.post(path + "/movement", headers=phone, json={"frames": [lean]}).json()
    assert duplicate["accepted"] == 0
    assert duplicate["state"]["trunk_review_frames"] == before
    client.post(path + "/complete", headers=quest, json={})
    replay = client.get(path + "/replay", headers=auth).json()
    assert {f["measurement_kind"] for f in replay["frames"]} == {
        "projected_2d_trunk_lean_degrees",
        "quest_hand_target_distance_m",
    }
    assert len(replay["repetitions"]) == 1
    report = client.get(path + "/report", headers=auth).json()
    assert report["metrics_used"]["trunk_review_frames"] == 1
    assert "trunk_observation" in report["content"]["observation_codes"]


def test_stale_and_hidden_torso_do_not_unlock_resume(client, monkeypatch):
    stamp = datetime.now(timezone.utc)
    monkeypatch.setattr("app.services.sessions.now", lambda: stamp)
    _, _, path, phone, quest = combined(client)
    old = [torso(i, stamp - timedelta(seconds=20 - i / 10)) for i in range(12)]
    client.post(path + "/movement", headers=phone, json={"frames": old})
    assert client.post(path + "/resume", headers=quest, json={}).status_code == 409
    recent = [torso(i + 12, stamp - timedelta(milliseconds=1100 - i * 100)) for i in range(12)]
    client.post(path + "/movement", headers=phone, json={"frames": recent})
    assert client.post(path + "/resume", headers=quest, json={}).status_code == 200
    client.post(path + "/pause", headers=phone, json={})
    client.post(path + "/movement", headers=phone, json={"frames": [torso(24, stamp, valid=False)]})
    assert client.post(path + "/resume", headers=quest, json={}).status_code == 409


def test_idle_headset_receives_browser_controls(client):
    auth, session, path, _, quest = combined(client)
    with client.websocket_connect("/api/v1/ws/" + session["id"]) as ws:
        ws.send_json(
            {
                "version": 1,
                "type": "device.join",
                "id": "join",
                "payload": {"token": quest["Authorization"].split()[1]},
            }
        )
        assert ws.receive_json()["type"] == "session.config"
        ws.receive_json()
        client.post(path + "/complete", headers=auth, json={})
        event = ws.receive_json()
        assert event["type"] == "session.state"
        assert event["payload"]["status"] == "complete"
        assert event["payload"]["ack_id"] == ""


def test_disconnected_phone_expires_without_new_frames(client, monkeypatch):
    stamp = datetime.now(timezone.utc)
    monkeypatch.setattr("app.services.sessions.now", lambda: stamp)
    auth, _, path, phone, quest = combined(client)
    frames = [torso(i, stamp - timedelta(milliseconds=1100 - i * 100)) for i in range(12)]
    client.post(path + "/movement", headers=phone, json={"frames": frames})
    assert client.get(path, headers=auth).json()["state"]["phone_setup_ready"]
    monkeypatch.setattr("app.services.sessions.now", lambda: stamp + timedelta(seconds=5))
    state = client.get(path, headers=auth).json()["state"]
    assert not state["phone_setup_ready"]
    assert not state["phone_tracking_valid"]
    assert state["phone_trunk_lean_deg"] is None
    assert client.post(path + "/resume", headers=quest, json={}).status_code == 409
