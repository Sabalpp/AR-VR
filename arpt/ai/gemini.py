"""
Gemini diagnosis pipeline (refactored, knowledge-base grounded).

Two stages:
  triage_pain()  — spoken complaint -> suspected conditions (from the curated
                   catalogue) -> test battery, via medical.mapping.
  diagnose()     — kinematic analysis + motion outcomes -> ranked ailments with
                   confidence scores and clinical reasoning.

Both constrain Gemini to the auditable condition catalogue rather than letting
it free-associate diagnoses — important for a medical device.
"""
from __future__ import annotations

import json
import time

from .config import gemini_client, GEMINI_MODEL
from ..core.skel import parse_skel
from ..core.kinematics import analyze
from ..medical.conditions import condition_catalog_for_prompt, CONDITIONS
from ..medical.mapping import select_test_battery, regions_for_conditions


def _call(prompt: str, retries: int = 4) -> str:
    client = gemini_client()
    last = None
    for attempt in range(retries):
        try:
            resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            return resp.text.strip()
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < retries - 1 and ("503" in str(e) or "429" in str(e)):
                time.sleep(3 * (attempt + 1))
            else:
                raise
    raise last


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


TRIAGE_PROMPT = """You are the triage module of an FDA-style musculoskeletal screening device.
The patient described their pain as:
"{pain}"

Choose the most likely conditions ONLY from this catalogue (use the exact ids):
{catalog}

Respond ONLY with JSON:
{{
  "suspected_condition_ids": ["id1", "id2", ...],   // up to 5, most likely first
  "patient_summary": "one plain-language sentence reflecting their complaint"
}}"""


def triage_pain(pain: str) -> dict:
    prompt = TRIAGE_PROMPT.format(
        pain=pain,
        catalog=json.dumps(condition_catalog_for_prompt(), indent=1),
    )
    data = _parse_json(_call(prompt))
    ids = [i for i in data.get("suspected_condition_ids", []) if i in CONDITIONS]
    battery = select_test_battery(ids)
    return {
        "suspected_condition_ids": ids,
        "suspected_conditions": [CONDITIONS[i].name for i in ids],
        "regions": [r.value for r in regions_for_conditions(ids)],
        "prescribed_tests": [t.id for t in battery],
        "prescribed_test_names": [t.name for t in battery],
        "patient_summary": data.get("patient_summary", pain),
    }


DIAGNOSIS_PROMPT = """You are the diagnostic module of a musculoskeletal screening device.
Patient complaint: "{pain}"
Test performed: {test}
Recording: {frames} frames over {duration}s.

Candidate conditions (choose ONLY from these ids):
{catalog}

Objective kinematic analysis:
{analysis}

Motion-quality outcome for the test:
{motion}

Weigh the kinematic signatures against the data. Respond ONLY with JSON:
{{
  "ailments": [
    {{"condition_id": "id", "name": "...", "confidence": 0.0-1.0,
      "affected_side": "left|right|bilateral", "severity": "mild|moderate|severe",
      "reasoning": "cite the specific metrics that support this"}}
  ],
  "key_findings": ["objective finding 1", "..."],
  "recommended_followup": "what the physician should examine/order next",
  "urgency": "routine|soon|urgent"
}}
List up to 4 ailments, most likely first."""


def diagnose(pain: str, skel_path: str, test_name: str = "movement_test",
             motion_summary: dict | None = None) -> dict:
    rec = parse_skel(skel_path)
    analysis = analyze(rec, include_frames=False)
    prompt = DIAGNOSIS_PROMPT.format(
        pain=pain, test=test_name,
        frames=analysis.frame_count, duration=analysis.duration_s,
        catalog=json.dumps(condition_catalog_for_prompt(), indent=1),
        analysis=json.dumps(analysis.summary(), indent=1),
        motion=json.dumps(motion_summary or {}, indent=1),
    )
    result = _parse_json(_call(prompt))
    result["objective_analysis"] = analysis.summary()
    return result


def run_pipeline(pain: str, skel_path: str, test_name: str = "movement_test",
                 motion_summary: dict | None = None) -> dict:
    triage = triage_pain(pain)
    diagnosis = diagnose(pain, skel_path, test_name, motion_summary)
    return {"triage": triage, "diagnosis": diagnosis}
