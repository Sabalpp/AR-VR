"""
Realtime exercise coach: a Gemini Live voice (gemini-3.1-flash-live-preview)
that acts as a physical-therapy expert and talks the patient through their
prescribed movement-test battery.

The coach hears the patient (16 kHz PCM mic audio from the headset) and speaks
back (24 kHz PCM). It also "sees" the movement: the headset streams per-frame
motion states from the motion-state engine, and MotionCueTracker condenses them
into a few text cues (phase changes, form-gate violations, stalls, holds) that
are injected into the conversation so the coach can react to what the patient
is actually doing.

The coach drives the VR flow through tools, which are relayed to the headset as
control events:
    start_test(test_id)          -> show the green-path guide for a test
    request_redo(test_id, cue)   -> reset the rep (redo loop)
    complete_test(test_id)       -> mark the test done
    end_session(reason)          -> stop (finished, pain, patient request, safety)

Clinical decision support only: the coach guides movement and never diagnoses.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable

from ..medical.tests import TESTS, MovementTest
from .config import GEMINI_LIVE_VOICE
from .voice import GeminiLiveSession


# ── System prompt ────────────────────────────────────────────────────────────

COACH_PROMPT = """You are the voice of Meta Care, a musculoskeletal screening device. You speak
as an experienced, warm physical therapist guiding a patient, who is wearing a VR
headset, through a short series of movement tests. A remote physician reviews
the results later.

Patient's complaint (their own words, summarized): {summary}

Movement tests to run, in this order:
{battery}

How the session works:
- The headset shows a translucent green "ghost" pose to follow. The patient's
  limbs turn red when still, yellow while moving, and green when they reach the target.
- Before each test, call start_test with its id. Then explain the movement in
  one or two short, plain sentences and demonstrate the idea verbally.
- Messages starting with "[motion]" are live tracking data from the headset, not
  speech from the patient. Use them to give short, specific cues ("a little
  lower", "keep your hips level", "hold it there"). Do not read them aloud and
  don't respond to every one. Stay quiet while the patient is moving well.
- If a rep fails a form check, give the correction cue kindly and call
  request_redo. Allow at most 2 redos per test, then call complete_test and move on.
- When a test's reps are done, call complete_test and briefly encourage the patient.
- After the last test, thank the patient, tell them their results are going to
  the doctor, and call end_session with reason "completed".

Safety rules (these override everything else):
- If the patient reports sharp, sudden or worsening pain, numbness, chest pain,
  dizziness, shortness of breath, or feels unsteady or at risk of falling:
  tell them to stop and sit or hold onto something stable, then call
  end_session with reason "safety". If it sounds like an emergency, tell them to
  take the headset off and call emergency services.
- Never push past comfort. "Only as far as is comfortable" is always correct.
- Never diagnose, name conditions, or predict results. If asked, say the doctor
  will review their results and follow up.
- If the patient wants to stop, stop. Call end_session with reason "patient_request".

Style: calm, encouraging, and brief. Speak in short sentences, one instruction
at a time. Speak in the patient's language if they use one other than English."""


def _describe_test(t: MovementTest) -> str:
    phases = ", ".join(
        f"{p.name} ({p.joint_angle.replace('_', ' ')} {p.start_deg:.0f}->{p.goal_deg:.0f} deg"
        + (f", hold {p.hold_s:g}s" if p.hold_s else "") + ")"
        for p in t.phases
    )
    lines = [
        f"- id: {t.id} | {t.name} | {t.reps} rep(s)" + (", each side" if t.bilateral else ""),
        f"  Instruction: {t.instruction}",
        f"  Phases: {phases}",
    ]
    if t.form_gates:
        cues = "; ".join(f'"{g.message}"' for g in t.form_gates)
        lines.append(f"  Form cues: {cues}")
    return "\n".join(lines)


def build_coach_prompt(battery: list[MovementTest], patient_summary: str = "") -> str:
    return COACH_PROMPT.format(
        summary=patient_summary or "not provided",
        battery="\n".join(_describe_test(t) for t in battery),
    )


# ── Tools (synchronous function calling on 3.1 Flash Live) ───────────────────

END_REASONS = ["completed", "safety", "patient_request"]


def coach_tools(battery: list[MovementTest]) -> list[dict]:
    test_id = {"type": "STRING", "enum": [t.id for t in battery],
               "description": "Movement test id."}
    return [
        {"name": "start_test",
         "description": "Show the green-path guide for a movement test on the headset "
                        "and start tracking it.",
         "parameters": {"type": "OBJECT", "properties": {"test_id": test_id},
                        "required": ["test_id"]}},
        {"name": "request_redo",
         "description": "Reset the current repetition so the patient can try again.",
         "parameters": {"type": "OBJECT", "properties": {
             "test_id": test_id,
             "cue": {"type": "STRING", "description": "Short correction shown on the headset."}},
             "required": ["test_id"]}},
        {"name": "complete_test",
         "description": "Mark a movement test as finished.",
         "parameters": {"type": "OBJECT", "properties": {"test_id": test_id},
                        "required": ["test_id"]}},
        {"name": "end_session",
         "description": "End the guided session.",
         "parameters": {"type": "OBJECT", "properties": {
             "reason": {"type": "STRING", "enum": END_REASONS}},
             "required": ["reason"]}},
    ]


# ── Motion cues ──────────────────────────────────────────────────────────────

@dataclass
class MotionCueTracker:
    """
    Turns the per-frame motion-state stream (~30-90 Hz) into sparse text cues
    for the coach, so the model gets context without being flooded.

    Frames are dicts shaped like motion_state.FrameState:
        {"test_id", "phase", "state": "red|yellow|green", "angle", "target",
         "gate_violation": str|None, "t": seconds (optional)}
    """
    stall_s: float = 3.0           # red this long mid-test -> "stopped moving"
    gate_cooldown_s: float = 4.0   # don't repeat the same form cue faster than this
    clock: Callable[[], float] = time.monotonic

    _test: str | None = field(default=None, init=False)
    _phase: str | None = field(default=None, init=False)
    _red_since: float | None = field(default=None, init=False)
    _stall_sent: bool = field(default=False, init=False)
    _green_sent: bool = field(default=False, init=False)
    _last_gate: dict[str, float] = field(default_factory=dict, init=False)

    def update(self, frame: dict) -> list[str]:
        now = float(frame.get("t", self.clock()))
        test_id = frame.get("test_id")
        phase = frame.get("phase")
        state = frame.get("state")
        cues: list[str] = []

        if test_id != self._test:
            self._test, self._phase = test_id, None
            self._last_gate.clear()
        if phase != self._phase:
            self._phase = phase
            self._green_sent = False
            self._red_since, self._stall_sent = None, False
            cues.append(f"[motion] {self._name(test_id)}: phase '{phase}' started, "
                        f"target {self._deg(frame.get('target'))}.")

        gate = frame.get("gate_violation")
        if gate and now - self._last_gate.get(gate, float("-inf")) >= self.gate_cooldown_s:
            self._last_gate[gate] = now
            cues.append(f"[motion] Form check failed: {gate}")

        if state == "red":
            if self._red_since is None:
                self._red_since = now
            elif not self._stall_sent and now - self._red_since >= self.stall_s:
                self._stall_sent = True
                cues.append(f"[motion] Patient has stopped moving for "
                            f"{now - self._red_since:.0f}s at {self._deg(frame.get('angle'))} "
                            f"(target {self._deg(frame.get('target'))}).")
        else:
            self._red_since, self._stall_sent = None, False

        if state == "green" and not self._green_sent:
            self._green_sent = True
            hold = self._hold_s(test_id, phase)
            cues.append(f"[motion] Target reached in phase '{phase}'."
                        + (f" Hold for {hold:g}s." if hold else ""))

        return cues

    def rep_result(self, result: dict) -> str:
        """Summarize a finished rep ({"test_id", "accepted", "reached_goal",
        "peak_angle", "violations"}) as a cue."""
        name = self._name(result.get("test_id"))
        if result.get("accepted"):
            return f"[motion] {name}: rep accepted (peak {self._deg(result.get('peak_angle'))})."
        why = "; ".join(result.get("violations") or [])
        if not result.get("reached_goal"):
            why = "; ".join(filter(None, ["did not reach the target depth", why]))
        return f"[motion] {name}: rep rejected ({why or 'form check failed'})."

    @staticmethod
    def _name(test_id: str | None) -> str:
        return TESTS[test_id].name if test_id in TESTS else str(test_id)

    @staticmethod
    def _deg(v: Any) -> str:
        return f"{float(v):.0f} deg" if isinstance(v, (int, float)) else "?"

    @staticmethod
    def _hold_s(test_id: str | None, phase: str | None) -> float:
        if test_id not in TESTS:
            return 0.0
        return next((p.hold_s for p in TESTS[test_id].phases if p.name == phase), 0.0)


# ── Coach session ────────────────────────────────────────────────────────────

KICKOFF = ("[session] The patient has the headset on and is ready. Greet them "
           "briefly, then begin the first movement test.")


class ExerciseCoach:
    """
    One guided exercise session. Usage:

        async with ExerciseCoach(battery, patient_summary) as coach:
            await coach.send_audio(pcm16k)           # mic in
            await coach.on_motion(frame)             # motion-state frames in
            await coach.on_rep(rep_result)           # finished reps in
            async for event in coach.events():       # to the headset
                ...

    Events:
        {"type": "audio", "data": bytes}                     24 kHz 16-bit PCM
        {"type": "transcript", "role": "patient"|"coach", "text": str}
        {"type": "control", "action": "start_test"|"request_redo"|
                             "complete_test"|"end_session", ...args}
        {"type": "interrupted"}                               patient barged in
        {"type": "turn_complete"}

    The stream ends after the turn in which the coach calls end_session.
    """

    def __init__(self, battery: list[MovementTest], patient_summary: str = "", *,
                 voice: str | None = None,
                 live_factory: Callable[..., GeminiLiveSession] = GeminiLiveSession,
                 cues: MotionCueTracker | None = None):
        if not battery:
            raise ValueError("ExerciseCoach needs at least one movement test")
        self.battery = battery
        self.cues = cues or MotionCueTracker()
        self.transcript: list[dict] = []
        self.completed: list[str] = []
        self.ended: str | None = None
        self._live = live_factory(
            build_coach_prompt(battery, patient_summary),
            tools=coach_tools(battery),
            transcribe=True,
            voice=voice or GEMINI_LIVE_VOICE,
            thinking_level="minimal",
        )

    async def __aenter__(self):
        await self._live.__aenter__()
        await self._live.send_text(KICKOFF)
        return self

    async def __aexit__(self, *exc):
        await self._live.__aexit__(*exc)

    async def send_audio(self, pcm_bytes: bytes, sample_rate: int = 16000):
        await self._live.send_audio(pcm_bytes, sample_rate)

    async def on_motion(self, frame: dict):
        for cue in self.cues.update(frame):
            await self._live.send_text(cue)

    async def on_rep(self, result: dict):
        await self._live.send_text(self.cues.rep_result(result))

    async def events(self) -> AsyncIterator[dict]:
        async for msg in self._live.responses():
            if getattr(msg, "tool_call", None):
                controls, replies = self._handle_tool_calls(msg.tool_call.function_calls)
                await self._live.send_tool_responses(replies)
                for c in controls:
                    yield c
                continue

            sc = getattr(msg, "server_content", None)
            if not sc:
                continue
            if sc.model_turn:
                for part in sc.model_turn.parts or []:
                    if part.inline_data and part.inline_data.data:
                        yield {"type": "audio", "data": part.inline_data.data}
            for role, tr in (("patient", sc.input_transcription),
                             ("coach", sc.output_transcription)):
                if tr and tr.text:
                    self._log(role, tr.text)
                    yield {"type": "transcript", "role": role, "text": tr.text}
            if sc.interrupted:
                yield {"type": "interrupted"}
            if sc.turn_complete:
                yield {"type": "turn_complete"}
                if self.ended:  # let the coach finish its goodbye, then stop
                    return

    def _handle_tool_calls(self, calls) -> tuple[list[dict], list[dict]]:
        valid_tests = {t.id for t in self.battery}
        controls, replies = [], []
        for fc in calls:
            args = dict(fc.args or {})
            result: dict = {"ok": True}
            if fc.name in ("start_test", "request_redo", "complete_test"):
                if args.get("test_id") not in valid_tests:
                    result = {"ok": False, "error": f"unknown test_id; use one of {sorted(valid_tests)}"}
                else:
                    controls.append({"type": "control", "action": fc.name, **args})
                    if fc.name == "complete_test" and args["test_id"] not in self.completed:
                        self.completed.append(args["test_id"])
                    remaining = [t.id for t in self.battery if t.id not in self.completed]
                    result["remaining_tests"] = remaining
            elif fc.name == "end_session":
                reason = args.get("reason") if args.get("reason") in END_REASONS else "completed"
                self.ended = reason
                controls.append({"type": "control", "action": "end_session", "reason": reason})
            else:
                result = {"ok": False, "error": f"unknown tool {fc.name}"}
            replies.append({"id": fc.id, "name": fc.name, "response": result})
        return controls, replies

    def _log(self, role: str, text: str):
        # Transcription arrives in fragments; merge consecutive ones per speaker.
        if self.transcript and self.transcript[-1]["role"] == role:
            self.transcript[-1]["text"] += text
        else:
            self.transcript.append({"role": role, "text": text})
