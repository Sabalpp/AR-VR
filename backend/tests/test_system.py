import os
import tempfile

os.environ.setdefault("DATABASE_URL", "sqlite:///" + tempfile.mktemp(suffix=".db"))
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routes import _attempts
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import Patient, User
from app.seed import seed
from app.services.security import password_hash


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed()
    _attempts.clear()
    with TestClient(app) as c:
        yield c


def login(c, role="patient"):
    r = c.post(
        "/api/v1/auth/login",
        json={
            "email": role + "@demo.local",
            "password": os.getenv(
                "DEMO_PASSWORD",
                "DemoPatient123!" if role == "patient" else "DemoTherapist123!",
            ),
        },
    )
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def setup(c, mode="phone", synthetic=True):
    auth = login(c)
    assignments = c.get("/api/v1/assignments", headers=auth).json()
    s = c.post(
        "/api/v1/sessions",
        headers=auth,
        json={
            "assignment_id": assignments[0]["id"],
            "mode": mode,
            "is_synthetic": synthetic,
        },
    ).json()
    pair = c.post(
        f"/api/v1/sessions/{s['id']}/pairing",
        headers=auth,
        json={"source": "simulator" if synthetic else mode},
    ).json()
    d = c.post("/api/v1/devices/pair", json={"code": pair["code"], "label": "TEST ONLY"}).json()
    return auth, s, {"Authorization": "Bearer " + d["device_token"]}, d


def frame(seq, reach=False, valid=True, mode="phone"):
    # 90-degree return, 180-degree reach, image aspect 1.
    joints = {
        n: {"x": x, "y": y, "z": z, "visibility": 1}
        for n, x, y, z in [
            ("right_shoulder", 0.3, 0.4, 0),
            ("right_elbow", 0.5, 0.4, 0),
            ("right_wrist", 0.7 if reach else 0.5, 0.4 if reach else 0.6, 0),
        ]
    }
    if mode == "quest":
        joints = {"right_wrist": {"x": 0, "y": 1, "z": 0.5 if reach else 1, "visibility": 1}}
    return {
        "seq": seq,
        "captured_at": (datetime.now(timezone.utc) + timedelta(milliseconds=seq * 400)).isoformat(),
        "coordinate_system": "image_normalized" if mode == "phone" else "quest_local",
        "units": "normalized" if mode == "phone" else "meters",
        "image_width": 1000,
        "image_height": 1000,
        "tracking_valid": valid,
        "joints": joints,
    }


def test_count_dedup_pause_complete_and_replay(client):
    auth, s, device, _ = setup(client)
    path = f"/api/v1/sessions/{s['id']}"
    frames = [frame(i, i in [2, 3]) for i in range(6)]
    r = client.post(path + "/movement", headers=device, json={"frames": frames})
    assert r.status_code == 200, r.text
    assert r.json()["state"]["repetitions"] == 1
    r = client.post(path + "/movement", headers=device, json={"frames": frames})
    assert r.json()["duplicates"] == 6
    client.post(path + "/pause", headers=device)
    r = client.post(
        path + "/movement",
        headers=device,
        json={"frames": [frame(i, i in [8, 9]) for i in range(6, 12)]},
    )
    assert r.json()["state"]["repetitions"] == 1
    for _ in range(2):
        assert client.post(path + "/complete", headers=device).status_code == 200
    assert (
        client.post(path + "/movement", headers=device, json={"frames": [frame(20)]}).status_code
        == 409
    )
    report = client.get(path + "/report", headers=auth)
    assert report.status_code == 200, report.text
    assert report.json()["metrics_used"]["repetitions"] == 1
    assert len(client.get(path + "/replay", headers=auth).json()["frames"]) == 12
    assert (
        client.post(
            path + "/checkin",
            headers=auth,
            json={"pain": 2, "effort": 4, "notes": "Felt comfortable"},
        ).status_code
        == 200
    )


def test_auth_pair_expiry_single_use_and_scope(client):
    auth, s, device, d = setup(client)
    assert client.get("/api/v1/patients").status_code in (401, 403)
    other = client.post(
        "/api/v1/sessions", headers=auth, json={"assignment_id": s["assignment_id"]}
    ).json()
    assert client.get("/api/v1/sessions/" + other["id"], headers=device).status_code == 403
    with SessionLocal() as db:
        u = User(
            email="stranger@test.local",
            name="Stranger",
            role="patient",
            password_hash=password_hash("1234567890"),
        )
        db.add(u)
        db.flush()
        db.add(Patient(user_id=u.id, name="Other fictional"))
        db.commit()
    t = client.post(
        "/api/v1/auth/login",
        json={"email": "stranger@test.local", "password": "1234567890"},
    ).json()["access_token"]
    assert (
        client.get(
            "/api/v1/sessions/" + s["id"], headers={"Authorization": "Bearer " + t}
        ).status_code
        == 404
    )
    p = client.post(
        "/api/v1/sessions/" + other["id"] + "/pairing",
        headers=auth,
        json={"source": "phone"},
    ).json()
    assert client.post("/api/v1/devices/pair", json={"code": p["code"]}).status_code == 200
    assert client.post("/api/v1/devices/pair", json={"code": p["code"]}).status_code == 401
    for _ in range(6):
        result = client.post("/api/v1/devices/pair", json={"code": "BADCODE"})
    assert result.status_code == 429


def test_tracking_loss_and_secondary_stream(client):
    auth, s, device, _ = setup(client, mode="quest", synthetic=False)
    path = f"/api/v1/sessions/{s['id']}"
    p = client.post(path + "/pairing", headers=auth, json={"source": "phone"}).json()
    secondary = client.post("/api/v1/devices/pair", json={"code": p["code"]}).json()
    second = {"Authorization": "Bearer " + secondary["device_token"]}
    r = client.post(
        path + "/movement",
        headers=second,
        json={"frames": [frame(i, i in [2, 3]) for i in range(6)]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["state"]["repetitions"] == 0
    frames = [frame(i, i in [2, 3], valid=i != 3, mode="quest") for i in range(6)]
    r = client.post(path + "/movement", headers=device, json={"frames": frames})
    assert r.json()["state"]["repetitions"] == 0
    frames = [frame(i, i in [8, 9], mode="quest") for i in range(6, 12)]
    r = client.post(path + "/movement", headers=device, json={"frames": frames})
    assert r.json()["state"]["repetitions"] == 1


def test_websocket_auth_reconnect_ack(client):
    auth, s, device, d = setup(client)
    for _ in range(2):
        with client.websocket_connect("/api/v1/ws/" + s["id"]) as ws:
            ws.send_json(
                {
                    "version": 1,
                    "id": "join",
                    "type": "device.join",
                    "payload": {"token": d["device_token"]},
                }
            )
            assert ws.receive_json()["type"] == "session.config"
            assert ws.receive_json()["payload"]["ack_id"] == "join"
            ws.send_json(
                {
                    "version": 1,
                    "id": "frame",
                    "type": "tracking.frame",
                    "payload": frame(0),
                }
            )
            assert ws.receive_json()["payload"]["ack_id"] == "frame"
    assert (
        len(client.get("/api/v1/sessions/" + s["id"] + "/replay", headers=auth).json()["frames"])
        == 1
    )
    with client.websocket_connect("/api/v1/ws/" + s["id"]) as ws:
        ws.send_json(
            {
                "version": 1,
                "id": "bad",
                "type": "device.join",
                "payload": {"token": "no"},
            }
        )
        assert ws.receive_json()["type"] == "error"


def test_invalid_coordinates_and_config(client):
    auth, s, device, _ = setup(client)
    f = frame(0)
    f["joints"]["right_wrist"]["x"] = 3
    r = client.post(
        "/api/v1/sessions/" + s["id"] + "/movement",
        headers=device,
        json={"frames": [f]},
    )
    assert r.json()["state"]["tracking_valid"] is False
    f = frame(1)
    f["joints"]["right_wrist"]["x"] = float("inf")
    from pydantic import ValidationError

    from app.schemas.api import Frame

    with pytest.raises(ValidationError):
        Frame.model_validate(f)


def test_pairing_expiry_and_stale_resume(client):
    auth, s, device, _ = setup(client)
    path = f"/api/v1/sessions/{s['id']}"
    from app.models import Device

    p = client.post(path + "/pairing", headers=auth, json={"source": "simulator"}).json()
    import hashlib

    with SessionLocal() as db:
        d = db.scalar(
            select(Device).where(
                Device.pairing_hash == hashlib.sha256(p["code"].encode()).hexdigest()
            )
        )
        d.pairing_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    assert client.post("/api/v1/devices/pair", json={"code": p["code"]}).status_code == 401
    stale = [frame(i, i in [2, 3]) for i in range(6)]
    for f in stale:
        f["captured_at"] = (
            datetime.now(timezone.utc)
            - timedelta(minutes=1)
            + timedelta(milliseconds=f["seq"] * 400)
        ).isoformat()
    client.post(path + "/pause", headers=device)
    client.post(path + "/resume", headers=device)
    r = client.post(path + "/movement", headers=device, json={"frames": stale})
    assert r.json()["state"]["repetitions"] == 0
    assert r.json()["state"]["invalid_frames"] == 6


def test_provider_failure_and_batch_limit(client):
    auth, s, device, _ = setup(client)
    path = f"/api/v1/sessions/{s['id']}"
    assert client.get("/api/v1/speech/reach", headers=auth).status_code == 503
    assert (
        client.post(
            path + "/movement",
            headers=device,
            json={"frames": [frame(i) for i in range(61)]},
        ).status_code
        == 422
    )
    client.post(path + "/complete", headers=device)
    assert client.get(path + "/report", headers=auth).status_code == 200


def test_wrong_pairing_source_does_not_consume_code(client):
    auth = login(client)
    assignment = client.get("/api/v1/assignments", headers=auth).json()[0]
    session = client.post(
        "/api/v1/sessions", headers=auth, json={"assignment_id": assignment["id"], "mode": "quest"}
    ).json()
    pairing = client.post(
        "/api/v1/sessions/" + session["id"] + "/pairing", headers=auth, json={"source": "quest"}
    ).json()
    wrong = client.post(
        "/api/v1/devices/pair", json={"code": pairing["code"], "expected_source": "phone"}
    )
    assert wrong.status_code == 422
    correct = client.post(
        "/api/v1/devices/pair", json={"code": pairing["code"], "expected_source": "quest"}
    )
    assert correct.status_code == 200
    assert correct.json()["source"] == "quest"
