import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Device, Repetition
from app.repositories.access import session_access
from app.schemas.api import Batch, Envelope, Frame
from app.services.security import authenticate
from app.services.sessions import ingest, transition

router = APIRouter()


@router.websocket("/api/v1/ws/{session_id}")
async def socket(ws: WebSocket, session_id: str):
    await ws.accept()

    async def send(kind, payload):
        await ws.send_json({"version": 1, "type": kind, "payload": payload})

    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=10)
        msg = Envelope.model_validate_json(raw)
        if msg.type != "device.join":
            raise HTTPException(401, "device.join required first")
        with SessionLocal() as db:
            token_raw = msg.payload.get("token", "")
            device = authenticate(token_raw, db)
            if not isinstance(device, Device):
                raise HTTPException(403, "Device token required")
            session = session_access(db, device, session_id)
            await send(
                "session.config",
                {
                    "config": session.config_snapshot,
                    "mode": session.mode,
                    "authoritative_counter": "backend",
                    "device_id": device.id,
                    "last_seq": device.last_seq,
                    "server_time": datetime.now(timezone.utc).isoformat(),
                },
            )
            await send("session.state", {**session.state, "ack_id": msg.id})
        # Sequential reads + Uvicorn ws-max-queue 32 provide bounded backpressure.
        while True:
            raw = await ws.receive_text()
            if len(raw) > 65536:
                raise HTTPException(413, "Message too large")
            try:
                msg = Envelope.model_validate_json(raw)
                with SessionLocal() as db:
                    device = authenticate(token_raw, db)
                    session = session_access(db, device, session_id, True)
                    previous_reps = session.state["repetitions"]
                    previous_tracking = session.state.get("tracking_valid", False)
                    if msg.type == "tracking.frame":
                        result = ingest(
                            db,
                            session,
                            device,
                            Batch(frames=[Frame.model_validate(msg.payload)]),
                        )
                        state = result["state"]
                    elif msg.type.startswith("session."):
                        state = transition(db, session, msg.type.split(".")[1])
                    elif msg.type == "device.status":
                        offset = msg.payload.get("clock_offset_ms")
                        if offset is not None:
                            if (
                                not isinstance(offset, (int, float))
                                or not -86400000 < offset < 86400000
                            ):
                                raise HTTPException(422, "Invalid clock offset")
                            device.clock_offset_ms = offset
                        if (
                            msg.payload.get("tracking_valid") is False
                            and session.state.get("authoritative_device_id") == device.id
                        ):
                            session.state = {
                                **session.state,
                                "tracking_valid": False,
                                "phase": "waiting_return",
                                "candidate_since": None,
                            }
                        db.commit()
                        state = session.state
                    elif msg.type == "exercise.event":
                        # Local event is explicitly non-authoritative; idempotent via event sequence.
                        seq = msg.payload.get("seq")
                        name = msg.payload.get("name", "")
                        if (
                            not isinstance(seq, int)
                            or seq < 0
                            or not isinstance(name, str)
                            or len(name) > 100
                        ):
                            raise HTTPException(
                                422,
                                "Event requires nonnegative seq and name <=100 chars",
                            )
                        if session.completed_at:
                            raise HTTPException(409, "Session complete")
                        name = "local:" + name[:94]
                        if not db.scalar(
                            select(Repetition).where(
                                Repetition.device_id == device.id,
                                Repetition.seq == seq,
                                Repetition.name == name,
                            )
                        ):
                            stamp = datetime.fromisoformat(
                                msg.payload["occurred_at"].replace("Z", "+00:00")
                            )
                            if stamp.tzinfo is None:
                                raise ValueError("Timezone required")
                            db.add(
                                Repetition(
                                    session_id=session.id,
                                    device_id=device.id,
                                    seq=seq,
                                    captured_at=stamp,
                                    source=device.source,
                                    name=name,
                                    authoritative=False,
                                )
                            )
                            db.commit()
                        state = session.state
                    else:
                        raise HTTPException(422, "Already joined")
                    await send("session.state", {**state, "ack_id": msg.id})
                    if msg.type == "tracking.frame" and state["repetitions"] > previous_reps:
                        await send(
                            "exercise.feedback",
                            {
                                "message": "Reach-and-return cycle recorded.",
                                "cue_id": "reach",
                            },
                        )
                    elif (
                        msg.type == "tracking.frame"
                        and previous_tracking
                        and not state.get("tracking_valid")
                    ):
                        await send(
                            "exercise.feedback",
                            {
                                "message": "Tracking paused. Bring your arm back into view.",
                                "cue_id": "tracking_lost",
                            },
                        )
                    if msg.type == "session.complete":
                        await send(
                            "session.summary",
                            {
                                "session_id": session.id,
                                "repetitions": state["repetitions"],
                                "report_path": f"/api/v1/sessions/{session.id}/report",
                            },
                        )
            except (ValidationError, ValueError, KeyError):
                await send(
                    "error",
                    {
                        "code": "validation_error",
                        "message": "Invalid message payload",
                        "ack_id": getattr(msg, "id", None),
                        "retryable": False,
                    },
                )
            except HTTPException as exc:
                await send(
                    "error",
                    {
                        "code": str(exc.status_code),
                        "message": exc.detail,
                        "ack_id": msg.id,
                        "retryable": exc.status_code == 429,
                    },
                )
    except (HTTPException, ValidationError, asyncio.TimeoutError):
        await send(
            "error",
            {
                "code": "unauthorized",
                "message": "Join rejected or timed out",
                "retryable": False,
            },
        )
        await ws.close(code=4401)
    except WebSocketDisconnect:
        pass
