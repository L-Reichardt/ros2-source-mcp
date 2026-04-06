"""Unit tests for IndexLoader (local path mode, caching)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from mcp_server.loader import IndexLoader
from mcp_server.tests.conftest import FAKE_DISTROS, FAKE_PACKAGES_LIST, FAKE_SENSOR_MSGS


@pytest.fixture
def local_index(tmp_path: Path) -> Path:
    """Create a minimal local index directory tree with distros.json."""
    (tmp_path / "distros.json").write_text(json.dumps(FAKE_DISTROS), encoding="utf-8")
    distro_dir = tmp_path / "jazzy"
    distro_dir.mkdir()
    (distro_dir / "packages.json").write_text(json.dumps(FAKE_PACKAGES_LIST), encoding="utf-8")
    (distro_dir / "sensor_msgs.json").write_text(json.dumps(FAKE_SENSOR_MSGS), encoding="utf-8")
    return tmp_path


@pytest.fixture
def set_local_index(local_index: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ROSINDEX_LOCAL_PATH at the local_index fixture."""
    monkeypatch.setenv("ROSINDEX_LOCAL_PATH", str(local_index))
    return local_index


@pytest.mark.asyncio
async def test_load_distros(set_local_index):
    async with IndexLoader() as loader:
        assert await loader.load_distros() == ["jazzy"]


@pytest.mark.asyncio
async def test_load_packages(set_local_index):
    async with IndexLoader() as loader:
        packages = await loader.load_packages("jazzy")
    assert len(packages) == len(FAKE_PACKAGES_LIST)


@pytest.mark.asyncio
async def test_load_package(set_local_index):
    async with IndexLoader() as loader:
        pkg = await loader.load_package("jazzy", "sensor_msgs")
    assert pkg["name"] == "sensor_msgs"
    assert "Image" in pkg["messages"]


@pytest.mark.asyncio
async def test_missing_package_raises(set_local_index):
    async with IndexLoader() as loader:
        with pytest.raises(ToolError, match="not found"):
            await loader.load_package("jazzy", "nonexistent_package_xyz")


@pytest.mark.asyncio
async def test_packages_are_cached(set_local_index):
    """Second call returns the cached object, not a fresh disk read."""
    async with IndexLoader() as loader:
        first = await loader.load_packages("jazzy")
        (set_local_index / "jazzy" / "packages.json").write_text("[]", encoding="utf-8")
        second = await loader.load_packages("jazzy")
    assert first is second
    assert len(second) == len(FAKE_PACKAGES_LIST)
