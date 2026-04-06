"""ROS2 package index MCP server.

Provides read-only access to the ROS2 package index for LLMs writing ROS2 code.
The LLM should call set_distro first to configure the active distribution, then
use search_packages, get_package, and get_message to look up what it needs.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from mcp_server.distro import validate_distro
from mcp_server.loader import IndexLoader, validate_package_name

_DISTRO_STATE_KEY = "distro"


@asynccontextmanager
async def lifespan(server: FastMCP):
    async with IndexLoader() as loader:
        yield {"loader": loader}


mcp = FastMCP(
    name="ros2-index",
    instructions=(
        "This server provides read-only access to the ROS2 package index. "
        "Use it to look up package metadata, interface definitions, and "
        "dependency graphs while writing ROS2 code.\n\n"
        "IMPORTANT — first call: use set_distro to configure the active ROS2 "
        "distribution. To determine it, run `echo $ROS_DISTRO` on the user's "
        "machine (set by ROS2 installation). Confirm with `echo $ROS_VERSION` "
        "(should be 2). Common values: 'jazzy', 'humble', 'iron', 'rolling'. "
        "If unknown, call list_distros to see what's indexed, then ask the user.\n\n"
        "After set_distro, all other tools use the session distro automatically. "
        "You can override per-call by passing the distro parameter explicitly."
    ),
    lifespan=lifespan,
)


def _loader(ctx: Context) -> IndexLoader:
    return ctx.lifespan_context["loader"]


async def _resolve_distro(ctx: Context, distro: str | None) -> str:
    """Return the distro to use: explicit param > session state > error."""
    if distro:
        try:
            validate_distro(distro)
        except ValueError as e:
            raise ToolError(str(e)) from e
        return distro
    session_distro = await ctx.get_state(_DISTRO_STATE_KEY)
    if session_distro:
        return session_distro
    raise ToolError(
        "No distro configured. Call set_distro first, or pass distro explicitly. "
        "Run `echo $ROS_DISTRO` to find the user's active distribution."
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool
async def set_distro(distro: str, ctx: Context) -> dict[str, Any]:
    """Set the active ROS2 distribution for this session.

    Call this FIRST before using other tools. All subsequent calls will use
    this distro unless you pass a distro parameter explicitly.

    To determine the distro: run `echo $ROS_DISTRO` on the user's machine.
    Use list_distros to see what distributions are available in the index.

    Args:
        distro: ROS2 distribution name (e.g. 'jazzy', 'humble', 'iron').
    """
    d = await _resolve_distro(ctx, distro)
    available = await _loader(ctx).load_distros()
    if d not in available:
        raise ToolError(f"Distro '{d}' is not indexed. Available: {available}")
    await ctx.set_state(_DISTRO_STATE_KEY, d)
    return {"distro": d, "status": "active", "available": available}


@mcp.tool
async def list_distros(ctx: Context) -> list[str]:
    """List ROS2 distributions available in the index.

    Returns a list of distro name strings (e.g. ['jazzy']).
    Use this to discover what's available before calling set_distro.
    """
    return await _loader(ctx).load_distros()


@mcp.tool
async def search_packages(
    query: str,
    ctx: Context,
    distro: str | None = None,
    limit: int = 20,
) -> list[dict[str, str]]:
    """Search ROS2 packages by name or description keyword (case-insensitive).

    Returns [{name, description}] for matching packages, up to `limit` results.
    Use this to discover packages by topic (e.g. 'camera', 'nav', 'laser').
    Then call get_package for full details on a specific package.

    Args:
        query: Substring to match against package names and descriptions.
        distro: Override session distro (optional if set_distro was called).
        limit: Max results (default 20).
    """
    if len(query) > 500:
        raise ToolError("Query too long (max 500 characters).")
    limit = max(1, min(limit, 100))
    d = await _resolve_distro(ctx, distro)
    packages = await _loader(ctx).load_packages(d)
    q = query.lower()
    matches = [
        {"name": p["name"], "description": p.get("description", "")}
        for p in packages
        if q in p["name"].lower() or q in p.get("description", "").lower()
    ]
    return matches[:limit]


@mcp.tool
async def get_package(package: str, ctx: Context, distro: str | None = None) -> dict[str, Any]:
    """Get full metadata for a ROS2 package: description, dependencies, and interface names.

    Returns: name, version, description, license, build_type, repo info,
    dependencies by type, and lists of message/service/action NAMES defined
    in this package (not their full definitions — use get_message for that).

    Args:
        package: Exact package name (e.g. 'sensor_msgs', 'rclcpp', 'nav2_msgs').
        distro: Override session distro (optional if set_distro was called).
    """
    validate_package_name(package)
    d = await _resolve_distro(ctx, distro)
    data = await _loader(ctx).load_package(d, package)

    result = dict(data)
    msgs = result.pop("messages", {})
    srvs = result.pop("services", {})
    acts = result.pop("actions", {})

    result["interface_names"] = {
        "messages": sorted(msgs.keys()),
        "services": sorted(srvs.keys()),
        "actions": sorted(acts.keys()),
    }
    return result


@mcp.tool
async def get_message(
    package: str,
    message: str,
    ctx: Context,
    distro: str | None = None,
    include_raw: bool = False,
) -> dict[str, Any]:
    """Get the definition of a single ROS2 message, service, or action.

    Searches messages first, then services, then actions. Returns structured
    field definitions for code generation:
      - message: {kind, description, fields: [{type, name, comment, default, is_constant}]}
      - service: {kind, description, request_fields, response_fields}
      - action:  {kind, description, goal_fields, result_fields, feedback_fields}

    Set include_raw=true to also get the verbatim .msg/.srv/.action file content.

    Args:
        package: Package name (e.g. 'sensor_msgs').
        message: Interface name without prefix (e.g. 'Image', not 'sensor_msgs/Image').
        distro: Override session distro (optional if set_distro was called).
        include_raw: Include the raw file content (default false, saves tokens).
    """
    validate_package_name(package)
    d = await _resolve_distro(ctx, distro)
    data = await _loader(ctx).load_package(d, package)

    for kind, key in (("message", "messages"), ("service", "services"), ("action", "actions")):
        interfaces = data.get(key, {})
        if message in interfaces:
            result = {"kind": kind, **interfaces[message]}
            if not include_raw:
                result.pop("raw", None)
            return result

    # Build a helpful error with available names.
    available = (
        sorted(data.get("messages", {}).keys())[:10]
        + sorted(data.get("services", {}).keys())[:10]
        + sorted(data.get("actions", {}).keys())[:10]
    )
    raise ToolError(
        f"Interface '{message}' not found in package '{package}'. Available: {available}"
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
