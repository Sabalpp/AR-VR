"""
Tests for the Gemini Live exercise coach (arpt/ai/coach.py) and the /ws/coach
headset socket. A fake Live session stands in for Gemini, so no network or API
key is needed.

Run:  venv/bin/python -m pytest tests/test_coach.py -q
"""
import asyncio
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from arpt.ai.coach import (ExerciseCoach, MotionCueTracker, build_coach_prompt,
                           coach_tools)
from arpt.medical.tests import TESTS

BATTERY = [TESTS["squat"], TESTS["step_down"]]


# ── Fake Gemini Live ──────────────────────────────────────────────────────────
def _call(name, **args):
    return NS(tool_call=NS(function_calls=[NS(id=f"id_{name}", name=name, args=args)]),
              server_content=None)


def _content(audio=None, said=None, heard=None, done=False, interrupted=False):
    parts = [NS(inline_data=NS(data=audio))] if audio else []
    return NS(tool_call=None, server_content=NS(
        model_turn=NS(parts=parts) if parts else None,
        input_transcription=NS(text=heard) if heard else None,
        output_transcription=NS(text=said) if said else None,
        interrupted=interrupted, turn_complete=done))


class FakeLive:
    script: list = []

    def __init__(self, prompt, **kwargs):
        self.prompt, self.kwargs = prompt, kwargs
        self.sent_text, self.sent_audio, self.tool_replies = [], [], []
        FakeLive.last = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        pass

    async def send_text(self, text):
        self.sent_text.append(text)

    async def send_audio(self, pcm, sample_rate=16000):
        self.sent_audio.append(pcm)

    async def send_tool_responses(self, replies):
        self.tool_replies.extend(replies)

    async def responses(self):
        for msg in self.script:
            await asyncio.sleep(0)
            yield msg


# ── Prompt & tools ────────────────────────────────────────────────────────────
def test_prompt_lists_battery_and_safety_rules():
    p = build_coach_prompt(BATTERY, "left knee gives way on stairs")
    assert "left knee gives way on stairs" in p
    for t in BATTERY:
        assert f"id: {t.id}" in p and t.instruction in p
    assert "Keep the hips level as you lower." in p      # form-gate cue
    assert "Never diagnose" in p and "end_session" in p


def test_tools_restrict_test_ids_to_battery():
    tools = {t["name"]: t for t in coach_tools(BATTERY)}
    assert set(tools) == {"start_test", "request_redo", "complete_test", "end_session"}
    enum = tools["start_test"]["parameters"]["properties"]["test_id"]["enum"]
    assert enum == ["squat", "step_down"]


# ── Motion cues ───────────────────────────────────────────────────────────────
def _frame(t, phase="descend", state="yellow", gate=None, angle=150, target=120):
    return {"test_id": "squat", "phase": phase, "state": state, "angle": angle,
            "target": target, "gate_violation": gate, "t": t}


def test_cues_are_sparse():
    tr = MotionCueTracker()
    assert len(tr.update(_frame(0.0))) == 1               # phase start
    assert tr.update(_frame(0.1)) == []                   # steady motion: silent
    assert tr.update(_frame(0.2)) == []


def test_gate_violation_debounced():
    tr = MotionCueTracker(gate_cooldown_s=4)
    tr.update(_frame(0.0))
    msg = "Keep your chest a little more upright."
    assert any(msg in c for c in tr.update(_frame(1.0, gate=msg)))
    assert tr.update(_frame(2.0, gate=msg)) == []         # within cooldown
    assert any(msg in c for c in tr.update(_frame(5.5, gate=msg)))


def test_stall_reported_once():
    tr = MotionCueTracker(stall_s=3)
    tr.update(_frame(0.0, state="red"))
    assert tr.update(_frame(2.0, state="red")) == []
    stall = tr.update(_frame(3.5, state="red"))
    assert stall and "stopped moving" in stall[0]
    assert tr.update(_frame(6.0, state="red")) == []


def test_green_hold_cue_uses_phase_hold_time():
    tr = MotionCueTracker()
    tr.update(_frame(0.0, phase="bottom"))
    cues = tr.update(_frame(0.5, phase="bottom", state="green"))
    assert cues == ["[motion] Target reached in phase 'bottom'. Hold for 1s."]


def test_rep_result_summary():
    tr = MotionCueTracker()
    assert "accepted" in tr.rep_result({"test_id": "squat", "accepted": True,
                                        "reached_goal": True, "peak_angle": 92.4})
    bad = tr.rep_result({"test_id": "squat", "accepted": False, "reached_goal": False,
                         "violations": ["Keep your chest a little more upright."]})
    assert "rejected" in bad and "target depth" in bad and "chest" in bad


# ── Coach session ─────────────────────────────────────────────────────────────
async def _run(script):
    FakeLive.script = script
    async with ExerciseCoach(BATTERY, "knee pain", live_factory=FakeLive) as coach:
        events = [e async for e in coach.events()]
    return coach, FakeLive.last, events


def test_coach_relays_audio_transcripts_and_controls():
    coach, live, events = asyncio.run(_run([
        _call("start_test", test_id="squat"),
        _content(audio=b"\x00\x01", said="Let's start "),
        _content(said="with a squat.", done=True),
        _content(heard="okay"),
        _call("request_redo", test_id="squat", cue="Chest up"),
        _call("complete_test", test_id="squat"),
    ]))
    assert live.kwargs["transcribe"] and live.kwargs["tools"]
    assert live.sent_text[0].startswith("[session]")          # kickoff
    assert {"type": "audio", "data": b"\x00\x01"} in events
    controls = [e for e in events if e["type"] == "control"]
    assert [c["action"] for c in controls] == ["start_test", "request_redo", "complete_test"]
    assert controls[1]["cue"] == "Chest up"
    assert live.tool_replies[-1]["response"]["remaining_tests"] == ["step_down"]
    assert coach.transcript == [{"role": "coach", "text": "Let's start with a squat."},
                                {"role": "patient", "text": "okay"}]


def test_coach_rejects_tests_outside_battery():
    _, live, events = asyncio.run(_run([_call("start_test", test_id="hop_landing")]))
    assert not [e for e in events if e["type"] == "control"]
    assert live.tool_replies[0]["response"]["ok"] is False


def test_end_session_stops_after_goodbye_turn():
    coach, _, events = asyncio.run(_run([
        _call("end_session", reason="safety"),
        _content(said="Please sit down.", done=True),
        _content(said="should never be sent"),
    ]))
    assert coach.ended == "safety"
    assert {"type": "control", "action": "end_session", "reason": "safety"} in events
    assert events[-1] == {"type": "turn_complete"}


def test_motion_frames_become_cues():
    async def go():
        FakeLive.script = []
        async with ExerciseCoach(BATTERY, live_factory=FakeLive) as coach:
            await coach.on_motion(_frame(0.0))
            await coach.on_motion(_frame(0.1))
            await coach.on_rep({"test_id": "squat", "accepted": True, "peak_angle": 91})
        return FakeLive.last
    live = asyncio.run(go())
    cues = [t for t in live.sent_text if t.startswith("[motion]")]
    assert len(cues) == 2 and "rep accepted" in cues[1]


# ── Headset WebSocket ─────────────────────────────────────────────────────────
@pytest.fixture
def ws_client(monkeypatch):
    import arpt.portal.server as server
    monkeypatch.setattr(server.ai_config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(server, "COACH_TOKEN", "")
    monkeypatch.setattr(server, "ExerciseCoachFactory",
                        lambda battery, summary: ExerciseCoach(battery, summary,
                                                               live_factory=FakeLive))
    return server, TestClient(server.app)


def test_ws_coach_round_trip(ws_client):
    _, client = ws_client
    FakeLive.script = [_call("start_test", test_id="squat"),
                       _content(audio=b"pcm-out", said="Hi.", done=True),
                       _call("end_session", reason="completed"),
                       _content(done=True)]
    with client.websocket_connect("/ws/coach") as ws:
        ws.send_json({"type": "start", "test_ids": ["squat", "bogus"],
                      "patient_summary": "knee pain"})
        assert ws.receive_json() == {"type": "session", "tests": ["squat"],
                                     "patient_summary": "knee pain"}
        assert ws.receive_json() == {"type": "control", "action": "start_test",
                                     "test_id": "squat"}
        assert ws.receive_bytes() == b"pcm-out"
        assert ws.receive_json()["type"] == "transcript"


def test_ws_coach_requires_token_when_configured(ws_client, monkeypatch):
    from starlette.websockets import WebSocketDisconnect
    server, client = ws_client
    monkeypatch.setattr(server, "COACH_TOKEN", "s3cret")
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/coach?token=wrong") as ws:
            ws.receive_json()
    assert exc.value.code == 1008


def test_ws_coach_rejects_empty_battery(ws_client):
    _, client = ws_client
    with client.websocket_connect("/ws/coach") as ws:
        ws.send_json({"type": "start", "test_ids": ["nope"]})
        err = ws.receive_json()
        assert err["type"] == "error" and "no valid tests" in err["message"]


def test_ws_coach_needs_gemini_key(ws_client, monkeypatch):
    server, client = ws_client
    monkeypatch.setattr(server.ai_config, "GEMINI_API_KEY", "")
    with client.websocket_connect("/ws/coach") as ws:
        assert "GEMINI_API_KEY" in ws.receive_json()["message"]
