"""Distro name validation for the ROS2 index MCP server."""

from __future__ import annotations

import re

# Reused verbatim from ros2_indexer/fetchers/distro.py — letter + lowercase alphanumeric/underscore.
# Prevents path traversal in both URL construction and local file paths.
_SAFE_DISTRO = re.compile(r"^[a-z][a-z0-9_]+$")


def validate_distro(distro: str) -> str:
    """Return distro if valid, raise ValueError if the name is unsafe.

    Valid names: lowercase letter followed by lowercase letters, digits, or underscores.
    Examples: 'jazzy', 'humble', 'iron', 'rolling'.
    """
    if not _SAFE_DISTRO.match(distro):
        raise ValueError(
            f"Invalid distro name: {distro!r}. "
            "Must start with a lowercase letter and contain only lowercase "
            "letters, digits, or underscores."
        )
    return distro
