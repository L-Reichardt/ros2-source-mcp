"""JSON serialization of PackageIndex to per-package and index files."""

from __future__ import annotations

import json
from pathlib import Path

from ros2_indexer.config import SAFE_NAME
from ros2_indexer.models import FieldDef, PackageIndex

# Map raw package.xml dep types to unambiguous MCP-friendly names.
_DEP_TYPE_LABELS = {
    "depend": "build_and_runtime",
    "build_depend": "build",
    "build_export_depend": "build_export",
    "buildtool_depend": "buildtool",
    "buildtool_export_depend": "buildtool_export",
    "exec_depend": "runtime",
    "run_depend": "runtime_legacy",
    "doc_depend": "doc",
    "test_depend": "test",
}


def _field_to_dict(f: FieldDef) -> dict:
    """Convert a FieldDef to a JSON-ready dict."""
    return {
        "type": f.type,
        "name": f.name,
        "comment": f.comment,
        "default": f.default or None,
        "is_constant": f.is_constant,
    }


def _package_to_dict(pkg: PackageIndex) -> dict:
    """Convert a PackageIndex into a JSON-serializable dict."""
    meta = pkg.metadata

    # Group dependencies by type, using human-readable labels
    deps: dict[str, list[str]] = {}
    for dep in meta.dependencies:
        label = _DEP_TYPE_LABELS.get(dep.dep_type, dep.dep_type)
        deps.setdefault(label, []).append(dep.name)

    messages: dict[str, dict] = {}
    for msg in pkg.messages:
        messages[msg.name] = {
            "description": msg.description,
            "raw": msg.raw_content,
            "fields": [_field_to_dict(f) for f in msg.fields],
        }

    services: dict[str, dict] = {}
    for srv in pkg.services:
        services[srv.name] = {
            "description": srv.description,
            "raw": srv.raw_content,
            "request_fields": [_field_to_dict(f) for f in srv.request_fields],
            "response_fields": [_field_to_dict(f) for f in srv.response_fields],
        }

    actions: dict[str, dict] = {}
    for action in pkg.actions:
        actions[action.name] = {
            "description": action.description,
            "raw": action.raw_content,
            "goal_fields": [_field_to_dict(f) for f in action.goal_fields],
            "result_fields": [_field_to_dict(f) for f in action.result_fields],
            "feedback_fields": [_field_to_dict(f) for f in action.feedback_fields],
        }

    return {
        "name": meta.name,
        "version": meta.version,
        "description": meta.description,
        "license": meta.license,
        "build_type": meta.build_type,
        "deprecated": meta.deprecated or None,
        "urls": meta.urls,
        "repo": {
            "name": pkg.repo.name,
            "url": pkg.repo.url,
            "branch": pkg.repo.branch,
        },
        "dependencies": {**deps, "depended_on_by": []},
        "messages": messages,
        "services": services,
        "actions": actions,
    }


def _package_to_summary(pkg: PackageIndex) -> dict:
    """Extract {name, description, version} for packages.json."""
    return {
        "name": pkg.metadata.name,
        "description": pkg.metadata.description,
        "version": pkg.metadata.version,
    }


def write_package_json(pkg: PackageIndex, output_dir: Path) -> Path:
    """Write index/{distro}/{package}.json and return the path."""
    if not SAFE_NAME.match(pkg.metadata.name):
        raise ValueError(f"Invalid package name for output: {pkg.metadata.name!r}")
    distro_dir = output_dir / pkg.distro
    distro_dir.mkdir(parents=True, exist_ok=True)
    out_path = distro_dir / f"{pkg.metadata.name}.json"
    out_path.write_text(
        json.dumps(_package_to_dict(pkg), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out_path


def write_packages_index(packages: list[PackageIndex], distro: str, output_dir: Path) -> Path:
    """Write index/{distro}/packages.json and return the path."""
    distro_dir = output_dir / distro
    distro_dir.mkdir(parents=True, exist_ok=True)
    summaries = sorted(
        (_package_to_summary(pkg) for pkg in packages),
        key=lambda s: s["name"],
    )
    out_path = distro_dir / "packages.json"
    out_path.write_text(
        json.dumps(summaries, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out_path


def write_distros_json(output_dir: Path) -> Path:
    """Write index/distros.json listing all distros that have a packages.json.

    Scans output_dir for subdirectories containing packages.json and writes
    a sorted list of their names. Run after build + crossref for each distro.
    """
    distros = sorted(
        d.name for d in output_dir.iterdir() if d.is_dir() and (d / "packages.json").exists()
    )
    out_path = output_dir / "distros.json"
    out_path.write_text(
        json.dumps(distros, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out_path
