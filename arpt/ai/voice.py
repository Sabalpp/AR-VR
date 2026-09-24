"""
Voice layer for the device: speech-out (ElevenLabs TTS) and speech-in
(transcription via Gemini). Both degrade gracefully when API keys are absent so
the rest of the pipeline runs in development without them.

speak(text)                 -> bytes | None   (MP3 audio for the headset)
transcribe(audio_bytes)     -> str            (patient's spoken complaint)
GeminiLiveSession           -> realtime bidirectional voice (async), used for
                               the conversational "explain your pain" step.
"""
from __future__ import annotations

import base64
from pathlib import Path

import requests

from .config import (ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL,
                     GEMINI_LIVE_MODEL, gemini_client)


# ── Speech out (ElevenLabs) ──────────────────────────────────────────────────

def speak(text: str, voice_id: str | None = None, out_path: str | None = None) -> bytes | None:
    """
    Synthesize speech with ElevenLabs. Returns MP3 bytes, or None if no API key.
    If out_path is given, also writes the audio there.
    """
    if not ELEVENLABS_API_KEY:
        print(f"[voice] (no ELEVENLABS_API_KEY) would speak: {text!r}")
        return None

    voice = voice_id or ELEVENLABS_VOICE_ID
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
    resp = requests.post(
        url,
        headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": ELEVENLABS_MODEL,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=30,
    )
    resp.raise_for_status()
    audio = resp.content
    if out_path:
        Path(out_path).write_bytes(audio)
    return audio


def list_voices() -> list[dict]:
    if not ELEVENLABS_API_KEY:
        return []
    resp = requests.get("https://api.elevenlabs.io/v1/voices",
                        headers={"xi-api-key": ELEVENLABS_API_KEY}, timeout=15)
    resp.raise_for_status()
    return [{"voice_id": v["voice_id"], "name": v["name"]}
            for v in resp.json().get("voices", [])]


# ── Speech in (Gemini transcription) ─────────────────────────────────────────

def transcribe(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """Transcribe patient audio to text using Gemini multimodal."""
    from google.genai import types
    client = gemini_client()
    resp = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=[
            "Transcribe this patient's spoken description of their pain, verbatim.",
            types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
        ],
    )
    return resp.text.strip()


# ── Realtime conversational voice (Gemini Live) ──────────────────────────────

class GeminiLiveSession:
    """
    Thin async wrapper around the Gemini Live API (default model
    gemini-3.1-flash-live-preview). Used for the conversational intake
    ("Explain what pain you are experiencing") and by the exercise coach
    (arpt/ai/coach.py). Usage:

        async with GeminiLiveSession(system_prompt) as live:
            await live.send_audio(chunk)          # stream mic in (16 kHz PCM)
            async for reply in live.responses():  # stream audio (24 kHz PCM) / text out
                ...

    Optional features: `tools` (function declarations — synchronous only on
    3.1 Flash Live), `transcribe` (input + output transcripts), `voice`
    (prebuilt voice name) and `thinking_level` (minimal|low|medium|high).
    """
    def __init__(self, system_prompt: str, model: str | None = None, *,
                 tools: list[dict] | None = None, transcribe: bool = False,
                 voice: str | None = None, thinking_level: str | None = None):
        self.system_prompt = system_prompt
        self.model = model or GEMINI_LIVE_MODEL
        self.tools = tools
        self.transcribe = transcribe
        self.voice = voice
        self.thinking_level = thinking_level
        self._client = gemini_client()
        self._session = None
        self._cm = None

    def _config(self):
        from google.genai import types
        kwargs = {}
        if self.tools:
            kwargs["tools"] = [{"function_declarations": self.tools}]
        if self.transcribe:
            kwargs["input_audio_transcription"] = types.AudioTranscriptionConfig()
            kwargs["output_audio_transcription"] = types.AudioTranscriptionConfig()
        if self.voice:
            kwargs["speech_config"] = types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice)))
        if self.thinking_level:
            kwargs["thinking_config"] = types.ThinkingConfig(thinking_level=self.thinking_level)
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=self.system_prompt,
            **kwargs,
        )

    async def __aenter__(self):
        self._cm = self._client.aio.live.connect(model=self.model, config=self._config())
        self._session = await self._cm.__aenter__()
        return self

    async def __aexit__(self, *exc):
        if self._cm:
            await self._cm.__aexit__(*exc)

    async def send_audio(self, pcm_bytes: bytes, sample_rate: int = 16000):
        from google.genai import types
        await self._session.send_realtime_input(
            audio=types.Blob(data=pcm_bytes, mime_type=f"audio/pcm;rate={sample_rate}")
        )

    async def send_text(self, text: str):
        """Inject text into the live conversation (e.g. a motion-tracking cue)."""
        await self._session.send_realtime_input(text=text)

    async def send_tool_responses(self, responses: list[dict]):
        """Answer tool calls: [{"id": ..., "name": ..., "response": {...}}]."""
        from google.genai import types
        await self._session.send_tool_response(function_responses=[
            types.FunctionResponse(id=r["id"], name=r["name"], response=r["response"])
            for r in responses
        ])

    async def responses(self):
        """Yield server messages. Each receive() call covers one model turn, so
        loop it to keep listening for the whole session. Ends when the server
        closes the connection (a turn that yields nothing)."""
        while True:
            got_any = False
            async for response in self._session.receive():
                got_any = True
                yield response
            if not got_any:
                return


# ── Standard device prompts ──────────────────────────────────────────────────

PROMPTS = {
    "greeting": "Welcome. I'm here to help understand your pain. When you're ready, "
                "tell me where it hurts and what makes it worse.",
    "analyzing": "Thank you. Analyzing what you told me.",
    "test_intro": "Based on what you described, I'd like you to do a short movement test.",
    "redo": "Let's try that again. Follow the green guide and move slowly.",
    "done": "Great work. I've recorded your movement and I'm preparing your results "
            "for the doctor.",
}
