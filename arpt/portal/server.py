"""
Doctor portal web server (FastAPI).

API:
  GET  /health                  -> liveness/readiness probe
  GET  /api/overview            -> aggregate clinic stats
  GET  /api/queue               -> urgency-sorted work queue
  GET  /api/reports             -> list all reports
  GET  /api/reports/{id}        -> full report JSON
  POST /api/reports/{id}/review -> submit physician verification
  GET  /api/reports/{id}/video  -> stream replay video
  GET  /api/reports/{id}/skel   -> download raw skeletal recording
  WS   /ws/coach                -> realtime voice exercise coach for the headset

In production the built React dashboard (dashboard/build) is served from `/`
with SPA fallback, so the whole product runs as one service. In development the
Vite dev server proxies /api here instead.

Run:  uvicorn arpt.portal.server:app --port 8000
"""
from __future__ import annotations

import asyncio
import hmac
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from .payload import list_reports, triage_queue, overview, REPORTS_DIR
from ..ai import config as ai_config
from ..ai.coach import ExerciseCoach
from ..medical.tests import TESTS

app = FastAPI(title="Meta Care Doctor Portal", version="1.0.0")

# ── Paths ────────────────────────────────────────────────────────────────────
STATIC_DIR = Path(__file__).parent / "static"
RECORDINGS_DIR = Path("recordings")
SPA_BUILD_DIR = Path("dashboard/build")

# ── CORS ─────────────────────────────────────────────────────────────────────
# Allowed origins are configurable; default covers the Vite dev server. Set
# METACARE_CORS_ORIGINS="https://portal.example.com" in production.
_origins = os.environ.get(
    "METACARE_CORS_ORIGINS",
    "http://127.0.0.1:3000,http://localhost:3000",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Validation ───────────────────────────────────────────────────────────────
_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _safe_id(report_id: str) -> str:
    """Reject anything that isn't a plain id — prevents path traversal."""
    if not _ID_RE.match(report_id):
        raise HTTPException(400, "invalid report id")
    return report_id


class ReviewSubmission(BaseModel):
    confirmed_diagnosis: str | None = None
    notes: str = ""
    reviewed_by: str = "Dr."
    status: str = "confirmed"

    @field_validator("status")
    @classmethod
    def _status_ok(cls, v: str) -> str:
        if v not in {"confirmed", "revised"}:
            raise ValueError("status must be 'confirmed' or 'revised'")
        return v

    @field_validator("reviewed_by")
    @classmethod
    def _reviewer_ok(cls, v: str) -> str:
        return v.strip() or "Dr."


def _load(report_id: str) -> dict:
    path = REPORTS_DIR / f"{_safe_id(report_id)}.json"
    if not path.exists():
        raise HTTPException(404, f"report {report_id} not found")
    return json.loads(path.read_text())


def _save(report: dict) -> None:
    rid = _safe_id(report["report_id"])
    (REPORTS_DIR / f"{rid}.json").write_text(json.dumps(report, indent=2))


# ── API ──────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "reports": len(list(REPORTS_DIR.glob("*.json"))) if REPORTS_DIR.exists() else 0,
        "spa_built": SPA_BUILD_DIR.exists(),
    }


@app.get("/api/overview")
def api_overview():
    return overview()


@app.get("/api/queue")
def api_queue():
    return triage_queue()


@app.get("/api/reports")
def api_list():
    return list_reports()


@app.get("/api/reports/{report_id}")
def api_get(report_id: str):
    return _load(report_id)


@app.post("/api/reports/{report_id}/review")
def api_review(report_id: str, body: ReviewSubmission):
    report = _load(report_id)
    report["physician_review"].update({
        "status": body.status,
        "confirmed_diagnosis": body.confirmed_diagnosis,
        "notes": body.notes,
        "reviewed_by": body.reviewed_by,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    })
    _save(report)
    return {"ok": True, "review": report["physician_review"]}


@app.get("/api/reports/{report_id}/video")
def api_video(report_id: str):
    report = _load(report_id)
    art = report["artifacts"]
    name = art.get("replay_video")
    candidates = [
        art.get("replay_video_path"),
        name,
        f"recordings/{name}" if name else None,
    ]
    for c in candidates:
        if c and Path(c).exists():
            return FileResponse(c, media_type="video/mp4")
    raise HTTPException(404, "no replay video")


@app.get("/api/reports/{report_id}/skel")
def api_skel(report_id: str):
    report = _load(report_id)
    name = report["artifacts"].get("skel_file")
    # Only serve by basename out of the recordings dir — never an arbitrary path.
    if not name or "/" in name or "\\" in name:
        raise HTTPException(404, "no skel file")
    path = RECORDINGS_DIR / name
    if not path.exists():
        raise HTTPException(404, "no skel file")
    return FileResponse(path, media_type="application/octet-stream", filename=name)


# ── Realtime exercise coach (headset) ────────────────────────────────────────
# Protocol (see arpt/ai/coach.py for event shapes):
#   headset -> server
#     1st message, JSON: {"type": "start", "test_ids": [...], "patient_summary": "..."}
#                    or  {"type": "start", "pain": "..."}   (server runs triage)
#     binary:            16 kHz 16-bit mono PCM mic audio
#     JSON:              {"type": "motion", ...FrameState fields, "test_id"}
#                        {"type": "rep", "test_id", "accepted", "reached_goal",
#                         "peak_angle", "violations"}
#   server -> headset
#     JSON:   {"type": "session", "tests": [...], "patient_summary"}
#     binary: 24 kHz 16-bit mono PCM coach speech
#     JSON:   transcript / control / interrupted / turn_complete / error events
COACH_TOKEN = os.environ.get("METACARE_COACH_TOKEN", "")
ExerciseCoachFactory = ExerciseCoach  # overridable in tests


async def _coach_battery(start: dict) -> tuple[list, str]:
    ids = start.get("test_ids")
    summary = str(start.get("patient_summary") or "")
    if not ids and start.get("pain"):
        from ..ai import gemini
        triage = await run_in_threadpool(gemini.triage_pain, str(start["pain"]))
        ids = triage["prescribed_tests"]
        summary = summary or triage["patient_summary"]
    battery = [TESTS[i] for i in (ids or []) if i in TESTS]
    return battery, summary


@app.websocket("/ws/coach")
async def ws_coach(ws: WebSocket):
    if COACH_TOKEN and not hmac.compare_digest(
            ws.query_params.get("token", ""), COACH_TOKEN):
        await ws.close(code=1008, reason="invalid token")
        return
    await ws.accept()

    async def fail(msg: str, code: int = 1011):
        await ws.send_json({"type": "error", "message": msg})
        await ws.close(code=code)

    if not ai_config.gemini_available():
        return await fail("GEMINI_API_KEY is not configured on the server")
    try:
        start = await ws.receive_json()
    except (WebSocketDisconnect, ValueError):
        return
    if not isinstance(start, dict) or start.get("type") != "start":
        return await fail("first message must be {\"type\": \"start\", ...}", 1003)

    try:
        battery, summary = await _coach_battery(start)
    except Exception as e:  # noqa: BLE001 - triage is an external call
        return await fail(f"triage failed: {e}")
    if not battery:
        return await fail(f"no valid tests; known ids: {sorted(TESTS)}", 1003)
    await ws.send_json({"type": "session", "tests": [t.id for t in battery],
                        "patient_summary": summary})

    try:
        async with ExerciseCoachFactory(battery, summary) as coach:
            async def uplink():
                while True:
                    msg = await ws.receive()
                    if msg["type"] == "websocket.disconnect":
                        return
                    if msg.get("bytes"):
                        await coach.send_audio(msg["bytes"])
                    elif msg.get("text"):
                        try:
                            data = json.loads(msg["text"])
                        except ValueError:
                            continue
                        if data.get("type") == "motion":
                            await coach.on_motion(data)
                        elif data.get("type") == "rep":
                            await coach.on_rep(data)

            async def downlink():
                async for event in coach.events():
                    if event["type"] == "audio":
                        await ws.send_bytes(event["data"])
                    else:
                        await ws.send_json(event)

            tasks = [asyncio.create_task(uplink()), asyncio.create_task(downlink())]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
            for t in done:
                if t.exception() and not isinstance(t.exception(), WebSocketDisconnect):
                    raise t.exception()
    except WebSocketDisconnect:
        return
    except Exception as e:  # noqa: BLE001 - surface Live API errors to the headset
        try:
            await fail(f"coach session error: {e}")
        except Exception:  # noqa: BLE001 - socket already gone
            pass
        return
    try:
        await ws.close()
    except Exception:  # noqa: BLE001
        pass


# ── Frontend ─────────────────────────────────────────────────────────────────
# Prefer the built React dashboard; fall back to the lightweight static portal.
if SPA_BUILD_DIR.exists():
    assets = SPA_BUILD_DIR / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/", response_class=HTMLResponse)
    def spa_index():
        return (SPA_BUILD_DIR / "index.html").read_text()

    # SPA fallback: any non-API path returns index.html (client-side routing).
    @app.get("/{full_path:path}", response_class=HTMLResponse)
    def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "not found")
        candidate = SPA_BUILD_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return (SPA_BUILD_DIR / "index.html").read_text()

else:
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (STATIC_DIR / "index.html").read_text()
