import asyncio
import json
from unittest.mock import patch

import httpx

from app.providers.gemini import summarize

METRICS = {
    "repetitions": 2,
    "tracking_gaps": 1,
    "invalid_frames": 1,
    "measurement_kind": "projected_2d_elbow_degrees",
    "is_synthetic": True,
}


class FakeClient:
    def __init__(self, output=None, failure=False):
        self.output = output
        self.failure = failure

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def post(self, *args, **kwargs):
        if self.failure:
            raise httpx.ConnectError("provider unavailable")
        return httpx.Response(
            200,
            request=httpx.Request("POST", "https://example.test"),
            json={"candidates": [{"content": {"parts": [{"text": json.dumps(self.output)}]}}]},
        )


def test_unconfigured_report_preserves_measurements_and_notes():
    with patch("app.providers.gemini.settings.gemini_api_key", ""):
        model, report = asyncio.run(summarize(METRICS, "Patient says it felt tiring."))
    assert model == "deterministic"
    assert report["summary"] == "Recorded 2 completed reach-and-return cycles."
    assert report["patient_notes"] == "Patient says it felt tiring."


def test_provider_failure_preserves_review():
    with (
        patch("app.providers.gemini.settings.gemini_api_key", "test"),
        patch(
            "app.providers.gemini.httpx.AsyncClient",
            return_value=FakeClient(failure=True),
        ),
    ):
        model, report = asyncio.run(summarize(METRICS, ""))
    assert model == "deterministic-fallback"
    assert "2 completed" in report["summary"]


def test_invented_numerical_claim_rejected_structurally():
    with (
        patch("app.providers.gemini.settings.gemini_api_key", "test"),
        patch(
            "app.providers.gemini.httpx.AsyncClient",
            return_value=FakeClient(
                {
                    "observation_codes": ["completed_cycles"],
                    "summary": "Eleven perfect repetitions",
                }
            ),
        ),
    ):
        model, report = asyncio.run(summarize(METRICS, ""))
    assert model == "deterministic-fallback"
    assert "Eleven" not in json.dumps(report)


def test_unsupported_or_omitted_fact_rejected():
    with (
        patch("app.providers.gemini.settings.gemini_api_key", "test"),
        patch(
            "app.providers.gemini.httpx.AsyncClient",
            return_value=FakeClient({"observation_codes": ["quest_measurement"]}),
        ),
    ):
        model, _ = asyncio.run(summarize(METRICS, ""))
    assert model == "deterministic-fallback"


def test_valid_grounded_selection():
    codes = [
        "tracking_loss",
        "synthetic_capture",
        "completed_cycles",
        "projected_measurement",
    ]
    with (
        patch("app.providers.gemini.settings.gemini_api_key", "test"),
        patch(
            "app.providers.gemini.httpx.AsyncClient",
            return_value=FakeClient({"observation_codes": codes}),
        ),
    ):
        model, report = asyncio.run(summarize(METRICS, ""))
    assert model != "deterministic-fallback"
    assert report["observation_codes"] == codes
