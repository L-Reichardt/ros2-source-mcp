"""Index loader: fetches ROS2 package JSON from GitHub Pages or local files."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

import httpx
from fastmcp.exceptions import ToolError

_DEFAULT_GH_ORG = "L-Reichardt"
_DEFAULT_GH_REPO = "ros2-source-mcp"

# Package names: letters, digits, underscores, hyphens. Prevents path traversal.
_SAFE_PACKAGE = re.compile(r"^[a-zA-Z0-9_-]+$")
# GitHub org/repo names: letters, digits, underscores, hyphens, dots.
_SAFE_GH_ID = re.compile(r"^[a-zA-Z0-9_.-]+$")


def validate_package_name(name: str) -> None:
    """Raise ToolError if the package name contains unsafe characters."""
    if not _SAFE_PACKAGE.match(name):
        raise ToolError(
            f"Invalid package name: {name!r}. "
            "Must contain only letters, digits, underscores, or hyphens."
        )


class IndexLoader:
    """Loads ROS2 package index data from GitHub Pages or a local directory.

    Data source priority:
      1. ROSINDEX_LOCAL_PATH env var (explicit override)
      2. Auto-detected local path (inside the repo, not MCPB)
      3. GitHub Pages HTTP fetch
    """

    def __init__(self) -> None:
        explicit = os.environ.get("ROSINDEX_LOCAL_PATH")
        if explicit:
            local = Path(explicit).resolve()
            if not local.is_dir():
                raise ValueError(f"ROSINDEX_LOCAL_PATH is not a directory: {explicit}")
            self._local_root: Path | None = local
        else:
            self._local_root = None

        gh_org = os.environ.get("ROSINDEX_GH_ORG", _DEFAULT_GH_ORG)
        gh_repo = os.environ.get("ROSINDEX_GH_REPO", _DEFAULT_GH_REPO)
        if not _SAFE_GH_ID.match(gh_org) or ".." in gh_org:
            raise ValueError(f"Invalid ROSINDEX_GH_ORG: {gh_org!r}")
        if not _SAFE_GH_ID.match(gh_repo) or ".." in gh_repo:
            raise ValueError(f"Invalid ROSINDEX_GH_REPO: {gh_repo!r}")
        self._base_url = f"https://{gh_org}.github.io/{gh_repo}/index"

        self._client: httpx.AsyncClient | None = None
        self._distros_cache: list[str] | None = None
        self._packages_cache: dict[str, list[dict[str, Any]]] = {}
        self._pkg_cache: dict[tuple[str, str], dict[str, Any]] = {}

    async def __aenter__(self) -> IndexLoader:
        if self._local_root is None:
            # Retry on 5xx/timeouts with exponential backoff (0.5s, 1s, 2s)
            transport = httpx.AsyncHTTPTransport(retries=3)
            self._client = httpx.AsyncClient(timeout=30.0, transport=transport)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def load_distros(self) -> list[str]:
        """Return distro names from distros.json (cached after first fetch)."""
        if self._distros_cache is None:
            self._distros_cache = await self._fetch(
                local_path=self._local_root / "distros.json" if self._local_root else None,
                url=f"{self._base_url}/distros.json",
                not_found_msg="distros.json not found. The index may need to be rebuilt.",
            )
        return self._distros_cache

    async def load_packages(self, distro: str) -> list[dict[str, Any]]:
        """Return the packages.json list for a distro (cached after first fetch)."""
        if distro not in self._packages_cache:
            self._packages_cache[distro] = await self._fetch(
                local_path=(
                    self._local_root / distro / "packages.json" if self._local_root else None
                ),
                url=f"{self._base_url}/{distro}/packages.json",
                not_found_msg=(
                    f"Distro '{distro}' not found. Use list_distros to see available distros."
                ),
            )
        return self._packages_cache[distro]

    async def load_package(self, distro: str, name: str) -> dict[str, Any]:
        """Return the full JSON for a single package (cached after first fetch)."""
        validate_package_name(name)
        key = (distro, name)
        if key not in self._pkg_cache:
            self._pkg_cache[key] = await self._fetch(
                local_path=(
                    self._local_root / distro / f"{name}.json" if self._local_root else None
                ),
                url=f"{self._base_url}/{distro}/{name}.json",
                not_found_msg=f"Package '{name}' not found in distro '{distro}'.",
            )
        return self._pkg_cache[key]

    async def _fetch(self, *, local_path: Path | None, url: str, not_found_msg: str) -> Any:
        """Unified local/remote fetch with consistent error handling."""
        if local_path is not None:
            try:
                content = await asyncio.to_thread(local_path.read_text, encoding="utf-8")
            except FileNotFoundError:
                raise ToolError(not_found_msg) from None
            return json.loads(content)
        if self._client is None:
            raise ToolError(
                "HTTP client not initialized. Use IndexLoader as an async context manager."
            )
        resp = await self._client.get(url)
        if resp.status_code == 404:
            raise ToolError(not_found_msg)
        resp.raise_for_status()
        return resp.json()
