import asyncio
from unittest.mock import patch

import httpx
import pytest
from fastapi import HTTPException

from app.providers import speech as provider


def test_speech_missing_credentials_is_optional():
    with patch.object(provider.settings, "elevenlabs_api_key", ""):
        with pytest.raises(HTTPException) as error:
            asyncio.run(provider.speech("setup"))
    assert error.value.status_code == 503


def test_speech_rejects_unapproved_text():
    with pytest.raises(HTTPException) as error:
        asyncio.run(provider.speech("invent a treatment instruction"))
    assert error.value.status_code == 422


def test_speech_provider_failure_and_cache():
    class Client:
        calls = 0
        fail = True

        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            Client.calls += 1
            if Client.fail:
                raise httpx.ConnectError("provider offline")
            return httpx.Response(
                200, request=httpx.Request("POST", "https://example.test"), content=b"fixture audio"
            )

    async def run():
        provider._cache.clear()
        with pytest.raises(HTTPException) as error:
            await provider.speech("setup")
        assert error.value.status_code == 503
        Client.fail = False
        first = await provider.speech("setup")
        second = await provider.speech("setup")
        assert first == second == b"fixture audio"
        assert Client.calls == 2
        provider._cache.clear()

    with (
        patch.object(provider.settings, "elevenlabs_api_key", "fixture"),
        patch.object(provider.settings, "elevenlabs_voice_id", "fixture"),
        patch.object(provider.httpx, "AsyncClient", Client),
    ):
        asyncio.run(run())
