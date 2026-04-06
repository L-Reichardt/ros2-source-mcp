"""Unit tests for MCP server tools using an in-process FastMCP client.

IndexLoader is patched to MockLoader — no HTTP or filesystem I/O.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from mcp_server.server import mcp
from mcp_server.tests.conftest import MockLoader


def unwrap(result) -> object:
    """Extract plain Python value from CallToolResult."""
    sc = result.structured_content
    if sc is not None and isinstance(sc, dict) and "result" in sc:
        return sc["result"]
    return result.data


@pytest.fixture
def patched_mcp():
    with patch("mcp_server.server.IndexLoader", MockLoader):
        yield mcp


# ---------------------------------------------------------------------------
# set_distro
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_distro(patched_mcp):
    async with Client(patched_mcp) as client:
        result = await client.call_tool("set_distro", {"distro": "jazzy"})
    data = unwrap(result)
    assert data["distro"] == "jazzy"
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_set_distro_invalid(patched_mcp):
    async with Client(patched_mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool("set_distro", {"distro": "../evil"})


@pytest.mark.asyncio
async def test_set_distro_not_indexed(patched_mcp):
    async with Client(patched_mcp) as client:
        with pytest.raises(ToolError, match="not indexed"):
            await client.call_tool("set_distro", {"distro": "humble"})


# ---------------------------------------------------------------------------
# list_distros
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_distros(patched_mcp):
    async with Client(patched_mcp) as client:
        result = await client.call_tool("list_distros", {})
    assert "jazzy" in unwrap(result)


# ---------------------------------------------------------------------------
# search_packages (returns names only)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_packages_with_explicit_distro(patched_mcp):
    async with Client(patched_mcp) as client:
        result = await client.call_tool("search_packages", {"query": "sensor", "distro": "jazzy"})
    results = unwrap(result)
    names = [r["name"] for r in results]
    assert "sensor_msgs" in names
    assert "nav2_msgs" not in names
    # Should return {name, description} dicts.
    assert all("description" in r for r in results)


@pytest.mark.asyncio
async def test_search_packages_with_session_distro(patched_mcp):
    async with Client(patched_mcp) as client:
        await client.call_tool("set_distro", {"distro": "jazzy"})
        result = await client.call_tool("search_packages", {"query": "sensor"})
    names = [r["name"] for r in unwrap(result)]
    assert "sensor_msgs" in names


@pytest.mark.asyncio
async def test_search_packages_no_distro_errors(patched_mcp):
    async with Client(patched_mcp) as client:
        with pytest.raises(ToolError, match="No distro configured"):
            await client.call_tool("search_packages", {"query": "sensor"})


@pytest.mark.asyncio
async def test_search_packages_no_match(patched_mcp):
    async with Client(patched_mcp) as client:
        result = await client.call_tool(
            "search_packages",
            {"query": "xyznonexistent", "distro": "jazzy"},
        )
    assert unwrap(result) == []


@pytest.mark.asyncio
async def test_search_packages_limit(patched_mcp):
    async with Client(patched_mcp) as client:
        result = await client.call_tool(
            "search_packages",
            {"query": "a", "distro": "jazzy", "limit": 2},
        )
    assert len(unwrap(result)) <= 2


# ---------------------------------------------------------------------------
# get_package (metadata + deps + interface names only)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_package_has_interface_names(patched_mcp):
    async with Client(patched_mcp) as client:
        result = await client.call_tool(
            "get_package",
            {"package": "sensor_msgs", "distro": "jazzy"},
        )
    pkg = unwrap(result)
    assert pkg["name"] == "sensor_msgs"
    assert "dependencies" in pkg
    # Interface names present, but NOT full definitions.
    assert "Image" in pkg["interface_names"]["messages"]
    assert "SetCameraInfo" in pkg["interface_names"]["services"]
    assert "messages" not in pkg
    assert "services" not in pkg
    assert "actions" not in pkg


@pytest.mark.asyncio
async def test_get_package_not_found(patched_mcp):
    async with Client(patched_mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool(
                "get_package",
                {"package": "nonexistent", "distro": "jazzy"},
            )


@pytest.mark.asyncio
async def test_get_package_invalid_name_rejected(patched_mcp):
    async with Client(patched_mcp) as client:
        with pytest.raises(ToolError, match="Invalid package name"):
            await client.call_tool(
                "get_package",
                {"package": "../../etc/passwd", "distro": "jazzy"},
            )


@pytest.mark.asyncio
async def test_get_package_with_session_distro(patched_mcp):
    async with Client(patched_mcp) as client:
        await client.call_tool("set_distro", {"distro": "jazzy"})
        result = await client.call_tool("get_package", {"package": "sensor_msgs"})
    assert unwrap(result)["name"] == "sensor_msgs"


# ---------------------------------------------------------------------------
# get_message (no raw by default)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_message_finds_message_no_raw(patched_mcp):
    async with Client(patched_mcp) as client:
        result = await client.call_tool(
            "get_message", {"package": "sensor_msgs", "message": "Image", "distro": "jazzy"}
        )
    iface = unwrap(result)
    assert iface["kind"] == "message"
    assert "raw" not in iface
    field_names = [f["name"] for f in iface["fields"]]
    assert "height" in field_names
    assert "width" in field_names
    assert "data" in field_names


@pytest.mark.asyncio
async def test_get_message_include_raw(patched_mcp):
    async with Client(patched_mcp) as client:
        result = await client.call_tool(
            "get_message",
            {"package": "sensor_msgs", "message": "Image", "distro": "jazzy", "include_raw": True},
        )
    iface = unwrap(result)
    assert "raw" in iface
    assert "uint32 height" in iface["raw"]


@pytest.mark.asyncio
async def test_get_message_finds_service(patched_mcp):
    async with Client(patched_mcp) as client:
        result = await client.call_tool(
            "get_message", {"package": "sensor_msgs", "message": "SetCameraInfo", "distro": "jazzy"}
        )
    iface = unwrap(result)
    assert iface["kind"] == "service"
    assert "request_fields" in iface
    assert "raw" not in iface


@pytest.mark.asyncio
async def test_get_message_finds_action(patched_mcp):
    async with Client(patched_mcp) as client:
        result = await client.call_tool(
            "get_message", {"package": "nav2_msgs", "message": "NavigateToPose", "distro": "jazzy"}
        )
    iface = unwrap(result)
    assert iface["kind"] == "action"
    assert "goal_fields" in iface
    assert "raw" not in iface


@pytest.mark.asyncio
async def test_get_message_not_found(patched_mcp):
    async with Client(patched_mcp) as client:
        with pytest.raises(ToolError, match="not found"):
            await client.call_tool(
                "get_message",
                {"package": "sensor_msgs", "message": "Nonexistent", "distro": "jazzy"},
            )


@pytest.mark.asyncio
async def test_get_message_with_session_distro(patched_mcp):
    async with Client(patched_mcp) as client:
        await client.call_tool("set_distro", {"distro": "jazzy"})
        result = await client.call_tool(
            "get_message",
            {"package": "sensor_msgs", "message": "Image"},
        )
    assert unwrap(result)["kind"] == "message"


# ---------------------------------------------------------------------------
# Full session flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_session_flow(patched_mcp):
    """Simulate a typical agentic session: set_distro → search → get_package → get_message."""
    async with Client(patched_mcp) as client:
        # 1. Set the distro.
        await client.call_tool("set_distro", {"distro": "jazzy"})

        # 2. Search for camera-related packages.
        search_result = await client.call_tool("search_packages", {"query": "sensor"})
        names = [r["name"] for r in unwrap(search_result)]
        assert "sensor_msgs" in names

        # 3. Get package details.
        pkg_result = await client.call_tool("get_package", {"package": "sensor_msgs"})
        pkg = unwrap(pkg_result)
        assert "Image" in pkg["interface_names"]["messages"]

        # 4. Get the specific message.
        msg_result = await client.call_tool(
            "get_message",
            {"package": "sensor_msgs", "message": "Image"},
        )
        msg = unwrap(msg_result)
        assert msg["kind"] == "message"
        assert any(f["name"] == "height" for f in msg["fields"])
