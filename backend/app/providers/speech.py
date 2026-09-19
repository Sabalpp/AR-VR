import asyncio
import hashlib

import httpx
from fastapi import HTTPException

from app.config import settings

PHRASES = {
    "setup": "Sit comfortably and keep your right shoulder, elbow and wrist visible.",
    "reach": "Gently reach, then return to your starting position.",
    "tracking_lost": "Tracking paused. Bring your arm back into view.",
    "complete": "Your session is saved. Please tell your therapist how it felt.",
}
_cache = {}
_lock = asyncio.Lock()


async def speech(cue):
    if cue not in PHRASES:
        raise HTTPException(422, "Unapproved cue")
    if not settings.elevenlabs_api_key or not settings.elevenlabs_voice_id:
        raise HTTPException(503, "Speech provider is not configured")
    key = hashlib.sha256((settings.elevenlabs_voice_id + PHRASES[cue]).encode()).hexdigest()
    async with _lock:
        if key in _cache:
            return _cache[key]
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}",
                    headers={"xi-api-key": settings.elevenlabs_api_key},
                    json={"text": PHRASES[cue], "model_id": "eleven_multilingual_v2"},
                )
                r.raise_for_status()
                _cache[key] = r.content
                return r.content
        except httpx.HTTPError:
            raise HTTPException(503, "Speech unavailable; tracking can continue")
