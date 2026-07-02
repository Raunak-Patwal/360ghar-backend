"""
Tests for MCP tool registration on user and admin servers.

Verifies that tools are properly registered and have correct annotations
per Apps SDK compliance.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.mcp.admin import admin_mcp
from app.mcp.chatgpt import WIDGETS
from app.mcp.user.server import user_mcp


class TestRegistrationImplementation:
    """Tests that registration verification avoids FastMCP private internals."""

    def test_user_server_does_not_use_private_fastmcp_component_store(self):
        source = Path("app/mcp/user/server.py").read_text()

        assert "local_provider" not in source
        assert "_components" not in source


class TestDiscoveryToolRegistration:
    """Tests that discovery tools are properly registered on the MCP server."""

    @pytest.mark.asyncio
    async def test_discovery_tools_exist(self):
        tools = await user_mcp.list_tools()
        names = [t.name for t in tools]
        discovery = [n for n in names if n.startswith("discovery_")]
        assert len(discovery) >= 5, f"Expected >= 5 discovery tools, got: {discovery}"

    @pytest.mark.asyncio
    async def test_discovery_search_registered(self):
        tools = await user_mcp.list_tools()
        names = [t.name for t in tools]
        assert "discovery_search" in names

    @pytest.mark.asyncio
    async def test_discovery_property_get_registered(self):
        tools = await user_mcp.list_tools()
        names = [t.name for t in tools]
        assert "discovery_property_get" in names

    @pytest.mark.asyncio
    async def test_discovery_feed_registered(self):
        tools = await user_mcp.list_tools()
        names = [t.name for t in tools]
        assert "discovery_feed" in names

    @pytest.mark.asyncio
    async def test_discovery_amenities_registered(self):
        tools = await user_mcp.list_tools()
        names = [t.name for t in tools]
        assert "discovery_amenities" in names

    @pytest.mark.asyncio
    async def test_discovery_recommendations_registered(self):
        tools = await user_mcp.list_tools()
        names = [t.name for t in tools]
        assert "discovery_recommendations" in names


class TestVisitToolRegistration:
    """Tests that visit tools are properly registered."""

    @pytest.mark.asyncio
    async def test_visits_schedule_registered(self):
        tools = await user_mcp.list_tools()
        names = [t.name for t in tools]
        assert "visits_schedule" in names

    @pytest.mark.asyncio
    async def test_visits_list_registered(self):
        tools = await user_mcp.list_tools()
        names = [t.name for t in tools]
        assert "visits_list" in names

    @pytest.mark.asyncio
    async def test_visits_get_registered(self):
        tools = await user_mcp.list_tools()
        names = [t.name for t in tools]
        assert "visits_get" in names

    @pytest.mark.asyncio
    async def test_visits_cancel_registered(self):
        tools = await user_mcp.list_tools()
        names = [t.name for t in tools]
        assert "visits_cancel" in names


class TestOwnerToolRegistration:
    """Tests that owner tools are properly registered."""

    @pytest.mark.asyncio
    async def test_owner_properties_list_registered(self):
        tools = await user_mcp.list_tools()
        names = [t.name for t in tools]
        assert "owner_properties_list" in names

    @pytest.mark.asyncio
    async def test_owner_properties_create_registered(self):
        tools = await user_mcp.list_tools()
        names = [t.name for t in tools]
        assert "owner_properties_create" in names

    @pytest.mark.asyncio
    async def test_owner_dashboard_overview_registered(self):
        tools = await user_mcp.list_tools()
        names = [t.name for t in tools]
        assert "owner_dashboard_overview" in names


class TestBookingToolRegistration:
    """Tests that booking tools are properly registered."""

    @pytest.mark.asyncio
    async def test_bookings_create_registered(self):
        tools = await user_mcp.list_tools()
        names = [t.name for t in tools]
        assert "bookings_create" in names

    @pytest.mark.asyncio
    async def test_bookings_list_registered(self):
        tools = await user_mcp.list_tools()
        names = [t.name for t in tools]
        assert "bookings_list" in names


class TestAdminToolRegistration:
    """Tests that admin MCP tools are properly registered."""

    @pytest.mark.asyncio
    async def test_agent_tools_on_admin_server(self):
        tools = await admin_mcp.list_tools()
        names = [t.name for t in tools]
        agent_tools = [n for n in names if n.startswith("agent_")]
        assert len(agent_tools) >= 5, f"Expected >= 5 agent tools, got: {agent_tools}"

    @pytest.mark.asyncio
    async def test_admin_system_status_registered(self):
        tools = await admin_mcp.list_tools()
        names = [t.name for t in tools]
        assert "admin_system_status" in names


class TestToolAnnotations:
    """Tests that MCP tools have proper annotations per Apps SDK compliance."""

    GUEST_USER_TOOLS = {
        "bookings_check_availability",
        "bookings_get_pricing",
        "discovery_search",
        "discovery_property_get",
        "discovery_feed",
        "discovery_amenities",
        "user_system_status",
    }

    ADMIN_WIDGET_TOOLS = {
        "agent_bookings_list_all": "ui://widget/visitlistwidget.html",
        "agent_dashboard_overview": "ui://widget/ownerdashboardwidget.html",
        "agent_leases_list": "ui://widget/leasemanagementwidget.html",
        "agent_maintenance_list": "ui://widget/maintenancewidget.html",
        "agent_properties_get": "ui://widget/propertydetailswidget.html",
        "agent_properties_list": "ui://widget/ownerdashboardwidget.html",
        "agent_rent_list_due": "ui://widget/rentcollectionwidget.html",
        "agent_rent_record_payment": "ui://widget/rentcollectionwidget.html",
    }

    @pytest.mark.asyncio
    async def test_discovery_read_tools_have_read_only_hint(self):
        """Pure read/discovery tools should have readOnlyHint=True."""
        read_only_tools = {"discovery_search", "discovery_property_get", "discovery_feed", "discovery_amenities"}
        tools = await user_mcp.list_tools()
        for tool in tools:
            if tool.name in read_only_tools:
                ann = tool.annotations
                read_only = getattr(ann, "readOnlyHint", None)
                assert read_only is True, f"{tool.name} should be readOnly, got {read_only}"

    @pytest.mark.asyncio
    async def test_all_tools_have_security_schemes(self):
        tools = await user_mcp.list_tools()
        for tool in tools:
            ann = tool.annotations
            schemes = getattr(ann, "securitySchemes", None)
            assert schemes is not None, f"{tool.name} missing securitySchemes"

    @pytest.mark.asyncio
    async def test_user_tool_security_schemes_match_auth_boundary(self):
        tools = await user_mcp.list_tools()
        for tool in tools:
            ann = tool.annotations
            schemes = getattr(ann, "securitySchemes", [])
            scheme_types = [scheme["type"] for scheme in schemes]
            expected = (
                ["noauth", "oauth2"]
                if tool.name in self.GUEST_USER_TOOLS
                else ["oauth2"]
            )
            assert scheme_types == expected, f"{tool.name} security schemes should be {expected}"

    @pytest.mark.asyncio
    async def test_admin_tools_are_oauth_only(self):
        tools = await admin_mcp.list_tools()
        for tool in tools:
            ann = tool.annotations
            schemes = getattr(ann, "securitySchemes", [])
            scheme_types = [scheme["type"] for scheme in schemes]
            assert scheme_types == ["oauth2"], f"{tool.name} should require OAuth"

    @pytest.mark.asyncio
    async def test_admin_widget_tools_advertise_output_templates(self):
        tools = await admin_mcp.list_tools()
        tools_by_name = {tool.name: tool for tool in tools}

        for tool_name, expected_uri in self.ADMIN_WIDGET_TOOLS.items():
            tool = tools_by_name[tool_name]
            assert tool.meta is not None
            assert tool.meta.get("openai/outputTemplate") == expected_uri
            assert tool.meta.get("ui/resourceUri") == expected_uri

    @pytest.mark.asyncio
    async def test_registered_widget_tools_match_widget_registry(self):
        user_tools = await user_mcp.list_tools()
        admin_tools = await admin_mcp.list_tools()
        tools = [*user_tools, *admin_tools]
        tools_by_name = {tool.name: tool for tool in tools}

        for widget_name, config in WIDGETS.items():
            expected_uri = f"ui://widget/{widget_name.lower()}.html"
            for tool_name in config["tools"]:
                if tool_name not in tools_by_name:
                    continue

                tool = tools_by_name[tool_name]
                assert tool.meta is not None
                assert tool.meta.get("openai/outputTemplate") == expected_uri
                assert tool.meta.get("ui/resourceUri") == expected_uri

    @pytest.mark.asyncio
    async def test_total_tool_count(self):
        tools = await user_mcp.list_tools()
        assert len(tools) >= 30, f"Expected >= 30 user tools, got {len(tools)}"
