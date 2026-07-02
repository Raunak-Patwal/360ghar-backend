from __future__ import annotations

import asyncio
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from app.services.notifications import fcm


@pytest.fixture(autouse=True)
def reset_fcm_state() -> None:
    fcm._fcm_credentials = None
    fcm._fcm_token_expiry = 0.0
    fcm._fcm_available = None
    fcm._fcm_refresh_lock = asyncio.Lock()


def _install_fake_google_auth(
    monkeypatch: pytest.MonkeyPatch,
    credentials_factory: Any,
) -> None:
    google_module = ModuleType("google")
    google_auth_module = ModuleType("google.auth")
    google_transport_module = ModuleType("google.auth.transport")
    request_module = ModuleType("google.auth.transport.requests")
    google_oauth2_module = ModuleType("google.oauth2")
    service_account_module = ModuleType("google.oauth2.service_account")

    class FakeRequest:
        pass

    request_module.Request = FakeRequest
    service_account_module.Credentials = SimpleNamespace(
        from_service_account_file=credentials_factory
    )
    google_module.auth = google_auth_module
    google_module.oauth2 = google_oauth2_module
    google_auth_module.transport = google_transport_module
    google_transport_module.requests = request_module
    google_oauth2_module.service_account = service_account_module

    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.auth", google_auth_module)
    monkeypatch.setitem(sys.modules, "google.auth.transport", google_transport_module)
    monkeypatch.setitem(sys.modules, "google.auth.transport.requests", request_module)
    monkeypatch.setitem(sys.modules, "google.oauth2", google_oauth2_module)
    monkeypatch.setitem(sys.modules, "google.oauth2.service_account", service_account_module)


@pytest.mark.asyncio
async def test_access_token_refresh_is_async_and_serialized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refresh_calls = 0
    to_thread_calls = 0
    credential_loads: list[tuple[str, list[str]]] = []

    class FakeCredentials:
        token = "initial-token"

        def refresh(self, request: object) -> None:
            nonlocal refresh_calls
            refresh_calls += 1
            self.token = f"refreshed-token-{refresh_calls}"

    credentials = FakeCredentials()

    def credentials_factory(path: str, scopes: list[str]) -> FakeCredentials:
        credential_loads.append((path, scopes))
        return credentials

    async def fake_to_thread(func: Any, *args: Any, **kwargs: Any) -> Any:
        nonlocal to_thread_calls
        to_thread_calls += 1
        await asyncio.sleep(0)
        return func(*args, **kwargs)

    _install_fake_google_auth(monkeypatch, credentials_factory)
    monkeypatch.setattr(fcm.os.path, "exists", lambda path: True)
    monkeypatch.setattr(
        fcm,
        "settings",
        SimpleNamespace(
            FIREBASE_PROJECT_ID="firebase-project",
            GOOGLE_APPLICATION_CREDENTIALS="/tmp/firebase.json",
        ),
    )
    monkeypatch.setattr(fcm.asyncio, "to_thread", fake_to_thread)

    tokens = await asyncio.gather(*(fcm._access_token() for _ in range(5)))

    assert tokens == ["refreshed-token-1"] * 5
    assert refresh_calls == 1
    assert to_thread_calls == 1
    assert credential_loads == [("/tmp/firebase.json", [fcm.FCM_SCOPE])]


@pytest.mark.asyncio
async def test_access_token_returns_none_when_credentials_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        fcm,
        "settings",
        SimpleNamespace(
            FIREBASE_PROJECT_ID="firebase-project",
            GOOGLE_APPLICATION_CREDENTIALS="/missing/firebase.json",
        ),
    )
    monkeypatch.setattr(fcm.os.path, "exists", lambda path: False)

    assert await fcm._access_token() is None
    assert fcm._fcm_available is False


@pytest.mark.asyncio
async def test_access_token_refresh_failure_remains_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeCredentials:
        token = None

        def refresh(self, request: object) -> None:
            raise RuntimeError("temporary refresh failure")

    def credentials_factory(path: str, scopes: list[str]) -> FakeCredentials:
        return FakeCredentials()

    _install_fake_google_auth(monkeypatch, credentials_factory)
    monkeypatch.setattr(fcm.os.path, "exists", lambda path: True)
    monkeypatch.setattr(
        fcm,
        "settings",
        SimpleNamespace(
            FIREBASE_PROJECT_ID="firebase-project",
            GOOGLE_APPLICATION_CREDENTIALS="/tmp/firebase.json",
        ),
    )

    assert await fcm._access_token() is None
    assert fcm._fcm_available is None


@pytest.mark.asyncio
async def test_send_message_awaits_access_token(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_access_token() -> str:
        return "async-token"

    class FakeResponse:
        def raise_for_status(self) -> None:
            captured["status_checked"] = True

        def json(self) -> dict[str, str]:
            return {"name": "projects/test/messages/1"}

    class FakeClient:
        async def post(
            self,
            url: str,
            headers: dict[str, str],
            json: dict[str, Any],
        ) -> FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(
        fcm,
        "settings",
        SimpleNamespace(
            FIREBASE_PROJECT_ID="firebase-project",
            GOOGLE_APPLICATION_CREDENTIALS="/tmp/firebase.json",
        ),
    )
    monkeypatch.setattr(fcm, "_access_token", fake_access_token)
    monkeypatch.setattr(fcm, "_get_fcm_client", lambda: FakeClient())

    message = {"message": {"token": "device-token"}}
    result = await fcm.send_message(message)

    assert result == {"name": "projects/test/messages/1"}
    assert captured["status_checked"] is True
    assert captured["url"] == (
        "https://fcm.googleapis.com/v1/projects/firebase-project/messages:send"
    )
    assert captured["headers"] == {"Authorization": "Bearer async-token"}
    assert captured["json"] == message
