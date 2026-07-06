from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI

from app.infrastructure import lifespan as lifespan_module
from app.infrastructure import mcp as mcp_module
from app.infrastructure.lifespan import create_lifespan
from app.infrastructure.mcp import LazyMCPHTTPApp, build_mcp_http_apps


class _DisposableEngine:
    def __init__(self, events: list[str], name: str) -> None:
        self._events = events
        self._name = name

    async def dispose(self) -> None:
        self._events.append(f"dispose:{self._name}")


class _InnerMCPApp:
    def __init__(self, events: list[str], name: str) -> None:
        self._events = events
        self._name = name

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        self._events.append(f"call:{self._name}")

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        self._events.append(f"enter:{self._name}")
        try:
            yield
        finally:
            self._events.append(f"exit:{self._name}")


class _LifespanRequiredMCPApp:
    def __init__(self, events: list[str], name: str) -> None:
        self._events = events
        self._name = name
        self._initialized = False

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if not self._initialized:
            raise RuntimeError(
                "FastMCP's StreamableHTTPSessionManager task group was not initialized"
            )
        self._events.append(f"call:{self._name}:{scope['path']}")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        self._events.append(f"enter:{self._name}")
        self._initialized = True
        try:
            yield
        finally:
            self._initialized = False
            self._events.append(f"exit:{self._name}")


class _RouterOnlyMCPApp:
    def __init__(self, events: list[str], name: str) -> None:
        self._events = events
        self._name = name
        self.router = SimpleNamespace(lifespan_context=self._lifespan)

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        self._events.append(f"enter:{self._name}")
        try:
            yield
        finally:
            self._events.append(f"exit:{self._name}")


def test_build_mcp_http_apps_returns_lifespan_aware_wrappers() -> None:
    user_mcp_app, admin_mcp_app = build_mcp_http_apps()

    assert isinstance(user_mcp_app, LazyMCPHTTPApp)
    assert isinstance(admin_mcp_app, LazyMCPHTTPApp)
    assert callable(getattr(user_mcp_app, "lifespan", None))
    assert callable(getattr(admin_mcp_app, "lifespan", None))


@pytest.mark.asyncio
async def test_lazy_mcp_http_app_lifespan_enters_inner_app(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    def build_inner(server_name: str) -> _InnerMCPApp:
        return _InnerMCPApp(events, server_name)

    monkeypatch.setattr(mcp_module, "_build_mcp_http_app", build_inner)

    async with LazyMCPHTTPApp("user").lifespan(FastAPI()):
        assert events == ["enter:user"]

    assert events == ["enter:user", "exit:user"]


@pytest.mark.asyncio
async def test_parent_lifespan_initializes_lazy_mcp_app_before_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    user_mcp_app = LazyMCPHTTPApp("user")
    admin_mcp_app = LazyMCPHTTPApp("admin")

    def build_inner(server_name: str) -> _LifespanRequiredMCPApp:
        return _LifespanRequiredMCPApp(events, server_name)

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        events.append(f"send:{message['type']}")

    monkeypatch.setattr(mcp_module, "_build_mcp_http_app", build_inner)
    monkeypatch.setattr(lifespan_module, "mark_engines_disposing", lambda: events.append("mark"))
    monkeypatch.setattr(lifespan_module, "engine", _DisposableEngine(events, "engine"))
    monkeypatch.setattr(lifespan_module, "bg_engine", _DisposableEngine(events, "bg_engine"))

    app_lifespan = create_lifespan(
        testing=True,
        user_mcp_app=user_mcp_app,
        admin_mcp_app=admin_mcp_app,
    )

    async with app_lifespan(FastAPI()):
        await user_mcp_app(
            {"type": "http", "method": "POST", "path": "/mcp", "headers": []},
            receive,
            send,
        )

    assert events == [
        "enter:user",
        "enter:admin",
        "call:user:/mcp",
        "send:http.response.start",
        "send:http.response.body",
        "mark",
        "dispose:engine",
        "dispose:bg_engine",
        "exit:admin",
        "exit:user",
    ]


@pytest.mark.asyncio
async def test_create_lifespan_supports_starlette_router_lifespan_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(lifespan_module, "mark_engines_disposing", lambda: events.append("mark"))
    monkeypatch.setattr(lifespan_module, "engine", _DisposableEngine(events, "engine"))
    monkeypatch.setattr(lifespan_module, "bg_engine", _DisposableEngine(events, "bg_engine"))

    app_lifespan = create_lifespan(
        testing=True,
        user_mcp_app=_RouterOnlyMCPApp(events, "user"),
        admin_mcp_app=_RouterOnlyMCPApp(events, "admin"),
    )

    async with app_lifespan(FastAPI()):
        assert events == ["enter:user", "enter:admin"]

    assert events == [
        "enter:user",
        "enter:admin",
        "mark",
        "dispose:engine",
        "dispose:bg_engine",
        "exit:admin",
        "exit:user",
    ]


@pytest.mark.asyncio
async def test_create_lifespan_rejects_mcp_app_without_lifespan() -> None:
    app_lifespan = create_lifespan(
        testing=True,
        user_mcp_app=object(),
        admin_mcp_app=object(),
    )

    with pytest.raises(TypeError, match="user MCP app must expose a lifespan context"):
        async with app_lifespan(FastAPI()):
            pass


@pytest.mark.asyncio
async def test_non_production_required_startup_failures_record_degraded_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    async def fail_database_ready() -> None:
        events.append("required:db")
        raise RuntimeError("db down")

    async def fail_migrations() -> None:
        events.append("required:ddl")
        raise RuntimeError("ddl down")

    async def optional_startup(app: FastAPI) -> None:
        events.append("optional")

    async def noop_async() -> None:
        pass

    monkeypatch.setattr(lifespan_module.settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(lifespan_module, "_validate_deeplink_config", lambda: None)
    monkeypatch.setattr(lifespan_module, "_verify_database_ready", fail_database_ready)
    monkeypatch.setattr(lifespan_module, "_apply_pending_migrations", fail_migrations)
    monkeypatch.setattr(lifespan_module, "_run_optional_startup", optional_startup)
    monkeypatch.setattr(lifespan_module, "shutdown_scheduler", lambda: None)
    monkeypatch.setattr(lifespan_module, "_shutdown_ai_providers", noop_async)
    monkeypatch.setattr(lifespan_module, "_shutdown_shared_http_clients", noop_async)
    monkeypatch.setattr(lifespan_module, "close_all_http_clients", noop_async)
    monkeypatch.setattr(lifespan_module, "_shutdown_cache", noop_async)
    monkeypatch.setattr(lifespan_module, "_shutdown_notification_executor", lambda: None)
    monkeypatch.setattr(lifespan_module, "mark_engines_disposing", lambda: None)
    monkeypatch.setattr(lifespan_module, "engine", _DisposableEngine(events, "engine"))
    monkeypatch.setattr(lifespan_module, "bg_engine", _DisposableEngine(events, "bg_engine"))

    app = FastAPI()
    app_lifespan = create_lifespan(
        testing=False,
        user_mcp_app=_RouterOnlyMCPApp(events, "user"),
        admin_mcp_app=_RouterOnlyMCPApp(events, "admin"),
    )

    async with app_lifespan(app):
        events.append("yield")

    assert app.state.startup_degraded is True
    assert app.state.startup_errors == [
        {"phase": "database_readiness", "error": "db down"},
        {"phase": "startup_migrations", "error": "ddl down"},
    ]
    assert "optional" in events
    assert "yield" in events


@pytest.mark.asyncio
async def test_production_required_startup_failure_aborts_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    async def fail_database_ready() -> None:
        events.append("required:db")
        raise RuntimeError("db down")

    async def optional_startup(app: FastAPI) -> None:
        events.append("optional")

    monkeypatch.setattr(lifespan_module.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(lifespan_module, "_validate_deeplink_config", lambda: None)
    monkeypatch.setattr(lifespan_module, "_verify_database_ready", fail_database_ready)
    monkeypatch.setattr(lifespan_module, "_run_optional_startup", optional_startup)

    app_lifespan = create_lifespan(
        testing=False,
        user_mcp_app=_RouterOnlyMCPApp(events, "user"),
        admin_mcp_app=_RouterOnlyMCPApp(events, "admin"),
    )

    with pytest.raises(RuntimeError, match="db down"):
        async with app_lifespan(FastAPI()):
            pass

    assert "optional" not in events
    assert events == ["enter:user", "enter:admin", "required:db", "exit:admin", "exit:user"]
