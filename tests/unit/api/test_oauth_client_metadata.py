from __future__ import annotations

import ipaddress
import socket
from typing import Any

import pytest

from app.api.api_v1.endpoints.oauth import helpers


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "100.64.0.1",
        "::1",
        "fc00::1",
    ],
)
def test_metadata_ip_filter_rejects_non_public_addresses(ip: str):
    assert helpers._is_public_metadata_ip(ipaddress.ip_address(ip)) is False


def test_metadata_ip_filter_allows_global_addresses():
    assert helpers._is_public_metadata_ip(ipaddress.ip_address("8.8.8.8")) is True


@pytest.mark.asyncio
async def test_resolve_public_metadata_ips_rejects_any_private_result(monkeypatch):
    def fake_getaddrinfo(*args: Any, **kwargs: Any):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443)),
        ]

    monkeypatch.setattr(helpers.socket, "getaddrinfo", fake_getaddrinfo)

    assert await helpers._resolve_public_metadata_ips("client.example", 443) == []


@pytest.mark.asyncio
async def test_fetch_client_metadata_rejects_unsafe_url_shapes():
    assert await helpers.fetch_client_metadata("http://client.example/metadata.json") is None
    assert await helpers.fetch_client_metadata("https://user:pass@client.example/metadata.json") is None
    assert await helpers.fetch_client_metadata("https://localhost/metadata.json") is None
    assert await helpers.fetch_client_metadata("https://client.example:444/metadata.json") is None


@pytest.mark.asyncio
async def test_fetch_client_metadata_uses_validated_ip_and_not_shared_client(monkeypatch):
    client_id = "https://client.example/metadata.json"
    calls: dict[str, Any] = {}

    async def fake_resolve(host: str, port: int) -> list[str]:
        calls["resolved"] = (host, port)
        return ["8.8.8.8"]

    async def fake_fetch(parsed: Any, ip: str, **kwargs: Any) -> dict[str, Any]:
        calls["fetched"] = (parsed.hostname, ip)
        return {
            "client_id": client_id,
            "client_name": "Test Client",
            "redirect_uris": ["https://client.example/callback"],
        }

    def fail_shared_client():
        raise AssertionError("shared HTTP client must not be used for metadata fetch")

    monkeypatch.setattr(helpers, "_resolve_public_metadata_ips", fake_resolve)
    monkeypatch.setattr(helpers, "_fetch_metadata_from_validated_ip", fake_fetch)

    import app.core.http as http_module

    monkeypatch.setattr(http_module, "get_general_client", fail_shared_client)

    metadata = await helpers.fetch_client_metadata(client_id)

    assert metadata is not None
    assert metadata["client_name"] == "Test Client"
    assert calls["resolved"] == ("client.example", 443)
    assert calls["fetched"] == ("client.example", "8.8.8.8")


@pytest.mark.asyncio
async def test_fetch_client_metadata_rejects_mismatched_metadata(monkeypatch):
    async def fake_resolve(host: str, port: int) -> list[str]:
        return ["8.8.8.8"]

    async def fake_fetch(parsed: Any, ip: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "client_id": "https://attacker.example/metadata.json",
            "client_name": "Wrong Client",
            "redirect_uris": ["https://client.example/callback"],
        }

    monkeypatch.setattr(helpers, "_resolve_public_metadata_ips", fake_resolve)
    monkeypatch.setattr(helpers, "_fetch_metadata_from_validated_ip", fake_fetch)

    assert await helpers.fetch_client_metadata("https://client.example/metadata.json") is None


@pytest.mark.asyncio
async def test_fetch_client_metadata_rejects_missing_required_fields(monkeypatch):
    async def fake_resolve(host: str, port: int) -> list[str]:
        return ["8.8.8.8"]

    async def fake_fetch(parsed: Any, ip: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "client_id": "https://client.example/metadata.json",
            "client_name": "Missing Redirects",
        }

    monkeypatch.setattr(helpers, "_resolve_public_metadata_ips", fake_resolve)
    monkeypatch.setattr(helpers, "_fetch_metadata_from_validated_ip", fake_fetch)

    assert await helpers.fetch_client_metadata("https://client.example/metadata.json") is None
