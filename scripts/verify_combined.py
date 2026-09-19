"""Exercise combined mode over public HTTPS/WSS with explicitly synthetic streams.

Creates one labeled synthetic session; never deletes records. Uses root .env.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import websockets
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


async def main():
    env = dotenv_values(ROOT / ".env")
    origin = env["PUBLIC_ORIGIN"]
    async with httpx.AsyncClient(base_url=origin, timeout=30) as client:

        async def post(path, body, token=None, expected=200):
            result = await client.post(
                "/api/v1" + path,
                json=body,
                headers={"Authorization": "Bearer " + token} if token else {},
            )
            assert result.status_code == expected, (path, result.status_code)
            return result.json()

        user = (
            await post(
                "/auth/login",
                {"email": "patient@demo.local", "password": env["DEMO_PASSWORD"]},
            )
        )["access_token"]
        assignments = await client.get(
            "/api/v1/assignments", headers={"Authorization": "Bearer " + user}
        )
        assignments.raise_for_status()
        session = await post(
            "/sessions",
            {
                "assignment_id": assignments.json()[0]["id"],
                "mode": "combined",
                "is_synthetic": True,
            },
            user,
            201,
        )
        sid = session["id"]
        path = "/sessions/" + sid
        devices = []
        for source in ("simulator_phone", "simulator_quest"):
            pairing = await post(path + "/pairing", {"source": source}, user)
            devices.append(
                await post(
                    "/devices/pair",
                    {
                        "code": pairing["code"],
                        "expected_source": source,
                        "label": "SYNTHETIC combined acceptance",
                    },
                )
            )
        phone, quest = devices
        await post(path + "/resume", {}, quest["device_token"], 409)
        ready = asyncio.Event()
        stop = asyncio.Event()
        phone_frames = 0

        async def stream_phone():
            nonlocal phone_frames
            while not stop.is_set():
                frame = {
                    "seq": phone_frames,
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "coordinate_system": "image_normalized",
                    "units": "normalized",
                    "image_width": 1000,
                    "image_height": 1000,
                    "tracking_valid": True,
                    "joints": {
                        "right_shoulder": {
                            "x": 0.7 if phone_frames % 20 >= 10 else 0.5,
                            "y": 0.3,
                            "visibility": 1,
                        },
                        "right_hip": {"x": 0.5, "y": 0.7, "visibility": 1},
                    },
                }
                result = await post(
                    path + "/movement", {"frames": [frame]}, phone["device_token"]
                )
                if result["state"].get("phone_setup_ready"):
                    ready.set()
                phone_frames += 1
                await asyncio.sleep(0.1)

        phone_task = asyncio.create_task(stream_phone())
        try:
            await asyncio.wait_for(ready.wait(), 20)
            ws_url = origin.replace("https://", "wss://", 1) + "/api/v1/ws/" + sid
            async with websockets.connect(ws_url) as ws:

                async def exchange(kind, payload):
                    request_id = str(uuid4())
                    await ws.send(
                        json.dumps(
                            {
                                "version": 1,
                                "type": kind,
                                "id": request_id,
                                "payload": payload,
                            }
                        )
                    )
                    while True:
                        message = json.loads(await asyncio.wait_for(ws.recv(), 20))
                        assert message["type"] != "error", message
                        if (
                            message["type"] == "session.config"
                            and kind == "device.join"
                        ):
                            assert (
                                message["payload"]["config"]["audio_owner"] == "quest"
                            )
                        if message.get("payload", {}).get("ack_id") == request_id:
                            return message["payload"]

                await exchange("device.join", {"token": quest["device_token"]})
                await exchange("session.resume", {})
                config = session["config_snapshot"]
                target = config["quest_target_m"]
                seq = 0
                for distance in (
                    config["quest_return_m"] + 0.15,
                    config["quest_reach_m"] / 2,
                    config["quest_return_m"] + 0.15,
                ):
                    for _ in range(6):
                        result = await exchange(
                            "tracking.frame",
                            {
                                "seq": seq,
                                "captured_at": datetime.now(timezone.utc).isoformat(),
                                "coordinate_system": "quest_local",
                                "units": "meters",
                                "tracking_valid": True,
                                "joints": {
                                    "right_wrist": {
                                        "x": target["x"] + distance,
                                        "y": target["y"],
                                        "z": target["z"],
                                        "visibility": 1,
                                    }
                                },
                            },
                        )
                        seq += 1
                        await asyncio.sleep(0.1)
                assert result["repetitions"] == 1, result
                await exchange("session.pause", {})
                stop.set()
                await phone_task
                completed = await exchange("session.complete", {})
                assert completed["repetitions"] == 1
        finally:
            stop.set()
            if not phone_task.done():
                phone_task.cancel()
            await asyncio.gather(phone_task, return_exceptions=True)
        replay = await client.get(
            "/api/v1" + path + "/replay", headers={"Authorization": "Bearer " + user}
        )
        replay.raise_for_status()
        data = replay.json()
        kinds = sorted({f["measurement_kind"] for f in data["frames"]})
        assert len(kinds) == 2
        assert len([r for r in data["repetitions"] if r["authoritative"]]) == 1
        report_response = await client.get(
            "/api/v1" + path + "/report", headers={"Authorization": "Bearer " + user}
        )
        report_response.raise_for_status()
        report = report_response.json()
        assert "trunk_observation" in report["content"]["observation_codes"]
        result = {
            "kind": "synthetic_combined_https_wss_verification",
            "session_id": sid,
            "phone_frames": phone_frames,
            "quest_frames": seq,
            "repetitions": 1,
            "measurement_kinds": kinds,
            "setup_gate_verified": True,
            "phone_audio_owner": False,
            "report_model": report["model"],
            "real_hardware_tested": False,
        }
        (ROOT / "docs/evidence/tiger-combined.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
