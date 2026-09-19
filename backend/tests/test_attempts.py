"""Synthetic attempts must be inspectable without turning misses or gaps into reps."""

from test_system import client as client
from test_system import frame, setup


def samples(distances, start=0):
    frames = []
    for seq, distance in enumerate(distances, start):
        f = frame(seq, mode="quest")
        f["joints"]["right_wrist"]["z"] = 0.5 + distance
        frames.append(f)
    return frames


def test_missed_then_corrected_attempt_is_indexed_and_deduplicated(client):
    auth, s, device, _ = setup(client, mode="quest")
    path = f"/api/v1/sessions/{s['id']}"
    frames = samples([0.5, 0.5, 0.22, 0.22, 0.5, 0.5, 0.05, 0.05, 0.5, 0.5])
    r = client.post(path + "/movement", headers=device, json={"frames": frames})
    assert r.status_code == 200, r.text
    assert r.json()["state"]["repetitions"] == 1
    assert r.json()["state"]["attempts_target_not_held"] == 1
    assert r.json()["state"]["attempts_completed"] == 1
    client.post(path + "/movement", headers=device, json={"frames": frames})
    replay = client.get(path + "/replay", headers=auth).json()
    attempts = [f["attempt_event"] for f in replay["frames"] if "attempt_event" in f]
    assert [a["outcome"] for a in attempts] == ["target_not_held", "completed"]
    assert [a["start_seq"] for a in attempts] == [2, 6]
    assert len({a["id"] for a in attempts}) == 2
    client.post(path + "/complete", headers=device, json={})
    report = client.get(path + "/report", headers=auth).json()
    assert len(report["content"]["attempt_evidence"]) == 2
    assert "target_attempts" in report["content"]["observation_codes"]


def test_tracking_loss_interrupts_attempt_without_miss_or_rep(client):
    auth, s, device, _ = setup(client, mode="quest")
    path = f"/api/v1/sessions/{s['id']}"
    frames = samples([0.5, 0.5, 0.22, 0.22, 0.5, 0.5])
    frames[3]["tracking_valid"] = False
    r = client.post(path + "/movement", headers=device, json={"frames": frames})
    assert r.json()["state"]["repetitions"] == 0
    assert r.json()["state"].get("attempts_target_not_held", 0) == 0
    assert r.json()["state"]["attempts_interrupted"] == 1


def test_miss_feedback_has_replay_attempt_id(client):
    _, s, _, device = setup(client, mode="quest")
    with client.websocket_connect("/api/v1/ws/" + s["id"]) as ws:
        ws.send_json(
            {
                "version": 1,
                "type": "device.join",
                "id": "join",
                "payload": {"token": device["device_token"]},
            }
        )
        ws.receive_json()
        ws.receive_json()
        for f in samples([0.5, 0.5, 0.22, 0.22, 0.5, 0.5]):
            ws.send_json(
                {"version": 1, "type": "tracking.frame", "id": str(f["seq"]), "payload": f}
            )
            message = ws.receive_json()
            assert message["type"] == "session.state"
        feedback = ws.receive_json()
        assert feedback["type"] == "exercise.feedback"
        assert feedback["payload"]["cue_id"] == "adjust"
        assert feedback["payload"]["attempt_id"].endswith(":2")
