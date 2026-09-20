"""Central config for API keys and model names, read from environment.

Secrets are never hard-coded. Set them via environment variables (a local
`.env` is supported if python-dotenv is installed). Calls that need a missing
key raise a clear, actionable error rather than silently failing.
"""
from __future__ import annotations

import os

# Optional .env support for local development.
try:  # pragma: no cover - convenience only
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # noqa: BLE001
    pass


# Gemini (Google GenAI)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_LIVE_MODEL = os.environ.get("GEMINI_LIVE_MODEL", "gemini-2.0-flash-live-001")

# ElevenLabs
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "Rachel")
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_turbo_v2_5")


class MissingCredential(RuntimeError):
    """Raised when an operation needs an API key that isn't configured."""


def require_gemini_key() -> str:
    if not GEMINI_API_KEY:
        raise MissingCredential(
            "GEMINI_API_KEY is not set. Export it (or add it to a .env file) "
            "before using AI triage/diagnosis. Get a key at "
            "https://aistudio.google.com/apikey"
        )
    return GEMINI_API_KEY


def gemini_available() -> bool:
    return bool(GEMINI_API_KEY)


def gemini_client():
    from google import genai

    return genai.Client(api_key=require_gemini_key())
