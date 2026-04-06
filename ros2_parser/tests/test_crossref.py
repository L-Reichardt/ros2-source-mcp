"""Unit tests for the crossref command (reverse dependency computation)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ros2_indexer.cli import app

runner = CliRunner()


def _write_pkg(distro_dir: Path, name: str, deps: dict) -> None:
    """Write a minimal package JSON with given dependencies."""
    data = {
        "name": name,
        "version": "1.0.0",
        "description": f"Test package {name}",
        "dependencies": {**deps, "depended_on_by": []},
        "messages": {},
        "services": {},
        "actions": {},
    }
    (distro_dir / f"{name}.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _read_pkg(distro_dir: Path, name: str) -> dict:
    return json.loads((distro_dir / f"{name}.json").read_text(encoding="utf-8"))


def _setup_index(tmp_path: Path) -> Path:
    """Create a 4-package test index with a known dependency graph.

    A depends on B (runtime) and C (build)
    B depends on C (runtime)
    C has no forward deps
    D depends on A (runtime)
    """
    distro_dir = tmp_path / "jazzy"
    distro_dir.mkdir(parents=True)
    # packages.json must exist (crossref skips it by name)
    (distro_dir / "packages.json").write_text("[]", encoding="utf-8")

    _write_pkg(distro_dir, "pkg_a", {"runtime": ["pkg_b"], "build": ["pkg_c"]})
    _write_pkg(distro_dir, "pkg_b", {"runtime": ["pkg_c"]})
    _write_pkg(distro_dir, "pkg_c", {})
    _write_pkg(distro_dir, "pkg_d", {"runtime": ["pkg_a"]})
    return tmp_path


def test_crossref_computes_reverse_deps(tmp_path: Path):
    """Verify the correct reverse dependency mapping."""
    index_dir = _setup_index(tmp_path)
    result = runner.invoke(app, ["crossref", "--distro", "jazzy", "--output-dir", str(index_dir)])
    assert result.exit_code == 0

    # pkg_a is depended on by pkg_d
    assert _read_pkg(index_dir / "jazzy", "pkg_a")["dependencies"]["depended_on_by"] == ["pkg_d"]
    # pkg_b is depended on by pkg_a
    assert _read_pkg(index_dir / "jazzy", "pkg_b")["dependencies"]["depended_on_by"] == ["pkg_a"]
    # pkg_c is depended on by both pkg_a (build) and pkg_b (runtime)
    assert _read_pkg(index_dir / "jazzy", "pkg_c")["dependencies"]["depended_on_by"] == [
        "pkg_a",
        "pkg_b",
    ]
    # pkg_d has no reverse deps
    assert _read_pkg(index_dir / "jazzy", "pkg_d")["dependencies"]["depended_on_by"] == []


def test_crossref_is_idempotent(tmp_path: Path):
    """Running crossref twice produces the same result (no duplicate entries)."""
    index_dir = _setup_index(tmp_path)

    runner.invoke(app, ["crossref", "--distro", "jazzy", "--output-dir", str(index_dir)])
    first_pass = _read_pkg(index_dir / "jazzy", "pkg_c")["dependencies"]["depended_on_by"]

    runner.invoke(app, ["crossref", "--distro", "jazzy", "--output-dir", str(index_dir)])
    second_pass = _read_pkg(index_dir / "jazzy", "pkg_c")["dependencies"]["depended_on_by"]

    assert first_pass == second_pass


def test_crossref_missing_distro_dir(tmp_path: Path):
    """crossref on a non-existent distro directory exits with error."""
    result = runner.invoke(
        app, ["crossref", "--distro", "nonexistent", "--output-dir", str(tmp_path)]
    )
    assert result.exit_code == 1


def test_crossref_preserves_forward_deps(tmp_path: Path):
    """crossref should not modify existing forward dependencies."""
    index_dir = _setup_index(tmp_path)
    runner.invoke(app, ["crossref", "--distro", "jazzy", "--output-dir", str(index_dir)])

    pkg_a = _read_pkg(index_dir / "jazzy", "pkg_a")
    assert pkg_a["dependencies"]["runtime"] == ["pkg_b"]
    assert pkg_a["dependencies"]["build"] == ["pkg_c"]
