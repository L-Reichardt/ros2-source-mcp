"""Integration tests: hit the real local index.

Run with:
    uv run pytest -m integration src/mcp_server/tests/test_integration.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_server.loader import IndexLoader

pytestmark = pytest.mark.integration

INDEX_DIR = Path(__file__).resolve().parents[3] / "index"
_skip_no_index = pytest.mark.skipif(
    not (INDEX_DIR / "distros.json").exists(),
    reason=f"Local index not found at {INDEX_DIR}",
)


@_skip_no_index
@pytest.mark.asyncio
async def test_load_distros(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ROSINDEX_LOCAL_PATH", str(INDEX_DIR))
    async with IndexLoader() as loader:
        distros = await loader.load_distros()
    assert "jazzy" in distros


@_skip_no_index
@pytest.mark.asyncio
async def test_load_packages(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ROSINDEX_LOCAL_PATH", str(INDEX_DIR))
    async with IndexLoader() as loader:
        packages = await loader.load_packages("jazzy")
    assert len(packages) >= 1700
    names = {p["name"] for p in packages}
    assert "sensor_msgs" in names


@_skip_no_index
@pytest.mark.asyncio
async def test_load_package_sensor_msgs(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ROSINDEX_LOCAL_PATH", str(INDEX_DIR))
    async with IndexLoader() as loader:
        pkg = await loader.load_package("jazzy", "sensor_msgs")
    assert pkg["name"] == "sensor_msgs"
    assert "Image" in pkg["messages"]
    image_fields = {f["name"] for f in pkg["messages"]["Image"]["fields"]}
    assert {"height", "width", "data", "encoding"}.issubset(image_fields)


@_skip_no_index
@pytest.mark.asyncio
async def test_nonexistent_package_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ROSINDEX_LOCAL_PATH", str(INDEX_DIR))
    from fastmcp.exceptions import ToolError

    async with IndexLoader() as loader:
        with pytest.raises(ToolError, match="not found"):
            await loader.load_package("jazzy", "nonexistent_package_xyz_abc_123")
