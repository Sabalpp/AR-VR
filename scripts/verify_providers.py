"""Live provider smoke check using fictional data; never print credentials.

Run with backend/.venv/bin/python scripts/verify_providers.py.
Makes one Gemini request and generates one short ElevenLabs setup cue.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
for key, value in dotenv_values(ROOT / ".env").items():
    if value is not None:
        os.environ.setdefault(key, value)
sys.path.insert(0, str(ROOT / "backend"))

from app.providers.gemini import summarize
from app.providers.speech import speech
from fastapi import HTTPException


async def main():
    model, report = await summarize(
        {
            "repetitions": 1,
            "tracking_gaps": 0,
            "invalid_frames": 0,
            "measurement_kind": "projected_2d_elbow_degrees",
            "is_synthetic": True,
        },
        "Synthetic provider verification only.",
    )
    grounded = report[
        "summary"
    ] == "Recorded 1 completed reach-and-return cycles." and set(
        report["observation_codes"]
    ) == {
        "completed_cycles",
        "projected_measurement",
        "synthetic_capture",
        "patient_notes",
    }
    result = {
        "gemini": {
            "result": "PASS"
            if grounded and model not in ("deterministic", "deterministic-fallback")
            else "FAIL",
            "model": model,
            "grounding_version": report["grounding_version"],
        }
    }
    try:
        audio = await speech("setup")
        # MP3 output begins with ID3 metadata or an MPEG audio frame header.
        mp3 = audio.startswith(b"ID3") or (
            len(audio) > 1 and audio[0] == 255 and audio[1] & 224 == 224
        )
        result["elevenlabs"] = {
            "result": "PASS" if mp3 and len(audio) > 100 else "FAIL",
            "audio_bytes": len(audio),
            "mp3_header_valid": mp3,
        }
    except HTTPException as exc:
        result["elevenlabs"] = {
            "result": "FAIL",
            "status": exc.status_code,
            "detail": exc.detail,
        }
    evidence = ROOT / "docs/evidence/live-providers.json"
    evidence.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if all(check["result"] == "PASS" for check in result.values()) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
