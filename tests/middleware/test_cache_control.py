"""
Tests for CacheControlMiddleware — Cloudflare-optimized cache headers.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response, StreamingResponse
from httpx import ASGITransport, AsyncClient

from app.middleware.cache_control import CacheControlMiddleware


def _make_app() -> FastAPI:
    """Create a minimal FastAPI app with CacheControlMiddleware wired in.

    Routes are carefully chosen to avoid catch-all parameter conflicts:
    - ``/api/v1/properties/special`` and ``/api/v1/properties/fail`` are
      registered *before* the ``{item_id}`` route so FastAPI matches them first.
    - No POST route on the same path as GET so automatic HEAD support works.
    """

    app = FastAPI()
    app.add_middleware(CacheControlMiddleware)

    @app.get("/api/v1/properties/special")
    async def properties_custom_header():
        return JSONResponse(
            content={"ok": True},
            headers={"Cache-Control": "public, max-age=60"},
        )

    @app.get("/api/v1/properties/fail")
    async def properties_error():
        return Response(status_code=500, content=b"fail")

    @app.get("/api/v1/properties/list")
    async def properties_list():
        return {"items": []}

    @app.get("/api/v1/properties/{item_id}")
    async def properties_detail(item_id: str):
        return {"id": item_id}

    @app.get("/api/v1/users/me")
    async def users_me():
        return {"user": "test"}

    @app.get("/api/v1/notifications/sse")
    async def notifications_sse():
        async def gen():
            yield "data: test\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    return app


@pytest.mark.asyncio
class TestAnonymousCacheHeaders:
    """Anonymous GET requests to cacheable paths should get public cache headers."""

    async def test_public_cache_control_header(self):
        app = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/properties/list")

        assert resp.status_code == 200
        cc = resp.headers.get("cache-control")
        assert cc is not None
        assert "public" in cc
        assert "max-age=300" in cc
        assert "s-maxage=300" in cc
        assert "stale-while-revalidate=600" in cc

    async def test_vary_header_set(self):
        app = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/properties/list")

        vary = resp.headers.get("vary")
        assert vary is not None
        assert "Authorization" in vary
        assert "Accept-Encoding" in vary

    async def test_no_cdn_header_for_anonymous(self):
        app = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/properties/list")

        assert "cloudflare-cdn-cache-control" not in resp.headers


@pytest.mark.asyncio
class TestAuthenticatedCacheHeaders:
    """Authenticated GET requests to cacheable paths should get private no-store."""

    async def test_private_no_store_header(self):
        app = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/properties/list",
                headers={"Authorization": "Bearer fake-token"},
            )

        assert resp.status_code == 200
        cc = resp.headers.get("cache-control")
        assert cc is not None
        assert "private" in cc
        assert "no-store" in cc

    async def test_cdn_no_store_for_authenticated(self):
        app = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/properties/list",
                headers={"Authorization": "Bearer fake-token"},
            )

        cdn_cc = resp.headers.get("cloudflare-cdn-cache-control")
        assert cdn_cc is not None
        assert cdn_cc == "no-store"

    async def test_vary_header_set_for_authed(self):
        app = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/properties/list",
                headers={"Authorization": "Bearer fake-token"},
            )

        vary = resp.headers.get("vary")
        assert vary is not None
        assert "Authorization" in vary
        assert "Accept-Encoding" in vary


@pytest.mark.asyncio
class TestNonCacheablePaths:
    """Paths not in the cacheable prefixes should not get cache headers."""

    async def test_non_cacheable_path_no_headers(self):
        app = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/users/me")

        assert resp.status_code == 200
        assert "cache-control" not in resp.headers
        assert "vary" not in resp.headers
        assert "cloudflare-cdn-cache-control" not in resp.headers

    async def test_post_request_no_headers(self):
        app = _make_app()

        @app.post("/api/v1/properties/create")
        async def properties_create():
            return {"created": True}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/properties/create")

        assert resp.status_code == 200
        assert "cache-control" not in resp.headers
        assert "vary" not in resp.headers


@pytest.mark.asyncio
class TestBlogCacheablePrefix:
    """Blog endpoints should also get cache headers."""

    async def test_blog_get_cached(self):
        app = FastAPI()
        app.add_middleware(CacheControlMiddleware)

        @app.get("/api/v1/blog/posts")
        async def blog_posts():
            return {"posts": []}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/blog/posts")

        assert resp.status_code == 200
        cc = resp.headers.get("cache-control")
        assert cc is not None
        assert "public" in cc


@pytest.mark.asyncio
class TestNon2xxResponses:
    """Non-2xx responses should not get cache headers."""

    async def test_500_no_cache_headers(self):
        app = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/properties/fail")

        assert resp.status_code == 500
        assert "cache-control" not in resp.headers
        assert "vary" not in resp.headers


@pytest.mark.asyncio
class TestEndpointCacheControlOverride:
    """Endpoints that set their own Cache-Control should not be overridden."""

    async def test_existing_cache_control_not_overridden(self):
        app = _make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/properties/special")

        assert resp.status_code == 200
        cc = resp.headers.get("cache-control")
        assert cc is not None
        assert "max-age=60" in cc
        # The middleware should not have added s-maxage or stale-while-revalidate
        assert "s-maxage" not in cc
        # Vary is always added for cacheable paths, even when the endpoint
        # sets its own Cache-Control — Cloudflare needs it for cache-key
        # segmentation.
        vary = resp.headers.get("vary")
        assert vary is not None
        assert "Authorization" in vary


@pytest.mark.asyncio
class TestMultipleCacheablePrefixes:
    """All declared cacheable prefixes should receive cache headers."""

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/properties/list",
            "/api/v1/blog/posts",
            "/api/v1/amenities/list",
            "/api/v1/faqs/public",
            "/api/v1/localities/search",
            "/api/v1/data-hub/circle-rates",
        ],
    )
    async def test_all_prefixes_cached(self, path: str):
        app = FastAPI()
        app.add_middleware(CacheControlMiddleware)

        @app.get(path)
        async def endpoint():
            return {"ok": True}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(path)

        assert resp.status_code == 200
        cc = resp.headers.get("cache-control")
        assert cc is not None
        assert "public" in cc
        vary = resp.headers.get("vary")
        assert vary is not None
        assert "Authorization" in vary


@pytest.mark.asyncio
class TestMCPRoutesSkipped:
    """MCP tool routes should not get cache headers (streaming)."""

    async def test_mcp_route_no_cache_headers(self):
        from unittest.mock import AsyncMock

        inner_app = AsyncMock()
        middleware = CacheControlMiddleware(inner_app)

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/mcp/tools/call",
            "headers": [],
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        inner_app.assert_called_once_with(scope, receive, send)

    async def test_mcp_oauth_path_processed(self):
        """MCP OAuth paths should NOT be skipped — they are normal HTTP."""
        app = FastAPI()
        app.add_middleware(CacheControlMiddleware)

        @app.get("/mcp/oauth/register")
        async def oauth_register():
            return {"ok": True}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/mcp/oauth/register")

        assert resp.status_code == 200
        # Not in _CACHEABLE_PATH_PREFIXES, so no cache headers
        assert "cache-control" not in resp.headers


@pytest.mark.asyncio
class TestWebsocketSkipped:
    """WebSocket scopes should not be processed by the middleware."""

    async def test_websocket_scope_skipped(self):
        """Middleware passes websocket scope through without modification."""
        from unittest.mock import AsyncMock

        inner_app = AsyncMock()
        middleware = CacheControlMiddleware(inner_app)

        scope = {"type": "websocket", "path": "/api/v1/properties/ws"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)
        inner_app.assert_called_once_with(scope, receive, send)
