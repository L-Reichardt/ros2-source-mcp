"""CLI entry point for ros2-indexer."""

from __future__ import annotations

import json
import logging
import subprocess
from collections import defaultdict
from pathlib import Path

import typer

from ros2_indexer.config import INDEX_DIR
from ros2_indexer.fetchers.distro import DistroFetcher
from ros2_indexer.fetchers.repo import RepoFetcher
from ros2_indexer.models import PackageIndex
from ros2_indexer.parsers.messages import (
    parse_all_actions,
    parse_all_messages,
    parse_all_services,
)
from ros2_indexer.parsers.package_xml import parse_package_xml
from ros2_indexer.serializer import write_distros_json, write_package_json, write_packages_index

app = typer.Typer(help="Build JSON indexes of ROS2 packages for MCP server consumption.")


# ---------------------------------------------------------------------------
# build command
# ---------------------------------------------------------------------------


def _build_single_package(
    package: str,
    distro: str,
    distro_fetcher: DistroFetcher,
    repo_fetcher: RepoFetcher,
    output_dir: Path,
) -> PackageIndex | None:
    """Build index for a single package. Returns PackageIndex on success, None on failure."""
    typer.echo(f"\n--- {package} ---")

    # 1. Resolve package → repo info
    try:
        repo_info = distro_fetcher.get_repo_info(package)
    except KeyError as e:
        typer.echo(f"  SKIP: {e}", err=True)
        return None

    if not repo_info.url:
        typer.echo(f"  SKIP: no source URL for '{package}'", err=True)
        return None

    typer.echo(f"  Repo: {repo_info.name} (branch: {repo_info.branch})")

    # 2. Clone the repo
    try:
        clone_path = repo_fetcher.clone(repo_info)
    except subprocess.CalledProcessError as e:
        typer.echo(
            f"  SKIP: git clone failed for {repo_info.url} (branch: {repo_info.branch}): {e}",
            err=True,
        )
        return None

    # 3. Find the package directory
    package_dir = repo_fetcher.find_package_dir(clone_path, package)
    if package_dir is None:
        typer.echo(
            f"  SKIP: no package.xml found for '{package}' in {clone_path}",
            err=True,
        )
        return None

    # 4. Parse package.xml
    try:
        metadata = parse_package_xml(package_dir / "package.xml")
    except Exception as e:
        typer.echo(f"  SKIP: failed to parse package.xml: {e}", err=True)
        return None

    typer.echo(f"  Version: {metadata.version}, Build type: {metadata.build_type}")

    # 5. Parse messages, services, and actions
    messages = parse_all_messages(package_dir / "msg")
    services = parse_all_services(package_dir / "srv")
    actions = parse_all_actions(package_dir / "action")
    typer.echo(f"  Messages: {len(messages)}, Services: {len(services)}, Actions: {len(actions)}")

    # 6. Assemble PackageIndex
    pkg = PackageIndex(
        metadata=metadata,
        repo=repo_info,
        distro=distro,
        messages=messages,
        services=services,
        actions=actions,
    )

    # 7. Write per-package JSON
    out_path = write_package_json(pkg, output_dir)
    typer.echo(f"  Written: {out_path}")

    return pkg


@app.command("build")
def build_cmd(
    distro: str = typer.Option("jazzy", help="ROS2 distro name"),
    package: str | None = typer.Option(
        None, help="Single package to build (default: all packages)"
    ),
    output_dir: Path = typer.Option(INDEX_DIR, help="Output directory"),
    keep_scratch: bool = typer.Option(False, help="Keep .scratch/ directory after building"),
) -> None:
    """Build JSON indexes for ROS2 package(s)."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    distro_fetcher = DistroFetcher(distro)
    repo_fetcher = RepoFetcher()

    packages = [package] if package else distro_fetcher.list_packages()
    if not package:
        typer.echo(f"Found {len(packages)} packages in {distro}")

    succeeded: list[PackageIndex] = []
    failed_names: list[str] = []

    for pkg_name in packages:
        result = _build_single_package(pkg_name, distro, distro_fetcher, repo_fetcher, output_dir)
        if result is not None:
            succeeded.append(result)
        else:
            failed_names.append(pkg_name)

    # Write global packages.json index and distros.json manifest
    if succeeded:
        idx_path = write_packages_index(succeeded, distro, output_dir)
        typer.echo(f"\nPackages index: {idx_path}")
        distros_path = write_distros_json(output_dir)
        typer.echo(f"Distros manifest: {distros_path}")

    typer.echo(f"\n{'=' * 40}")
    typer.echo(
        f"Done: {len(succeeded)} succeeded, {len(failed_names)} failed out of {len(packages)}"
    )
    if failed_names:
        typer.echo(f"Failed packages: {', '.join(failed_names[:20])}")
        if len(failed_names) > 20:
            typer.echo(f"  ... and {len(failed_names) - 20} more")

    if not keep_scratch:
        repo_fetcher.cleanup_scratch()
        typer.echo("Cleaned up .scratch/")


# ---------------------------------------------------------------------------
# crossref command
# ---------------------------------------------------------------------------


@app.command("crossref")
def crossref_cmd(
    distro: str = typer.Option("jazzy", help="ROS2 distro name"),
    output_dir: Path = typer.Option(INDEX_DIR, help="Index directory"),
) -> None:
    """Add depended_on_by (reverse dependencies) into dependencies of every package JSON.

    Reads all {package}.json files in index/{distro}/, builds a reverse
    dependency map, and writes a sorted "depended_on_by" list into each
    package's "dependencies" object. Run this after 'build' completes.
    """
    distro_dir = output_dir / distro
    if not distro_dir.is_dir():
        typer.echo(f"Error: {distro_dir} does not exist. Run 'build' first.", err=True)
        raise typer.Exit(1)

    # 1. Load all package JSONs
    pkg_files = sorted(distro_dir.glob("*.json"))
    pkg_files = [f for f in pkg_files if f.name != "packages.json"]

    packages: dict[str, dict] = {}
    for path in pkg_files:
        data = json.loads(path.read_text(encoding="utf-8"))
        packages[data["name"]] = data

    typer.echo(f"Loaded {len(packages)} packages from {distro_dir}")

    # 2. Build reverse dependency map: dep_name → [packages that depend on it]
    #    Skip "depended_on_by" — that's our output field, not a forward dependency.
    depended_on_by: dict[str, list[str]] = defaultdict(list)
    for pkg_name, data in packages.items():
        for dep_type, dep_list in data.get("dependencies", {}).items():
            if dep_type == "depended_on_by":
                continue
            for dep_name in dep_list:
                depended_on_by[dep_name].append(pkg_name)

    # 3. Write depended_on_by into each package's dependencies object
    updated = 0
    for pkg_name, data in packages.items():
        rev_deps = sorted(depended_on_by.get(pkg_name, []))
        data.setdefault("dependencies", {})["depended_on_by"] = rev_deps
        path = distro_dir / f"{pkg_name}.json"
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        updated += 1

    typer.echo(f"Updated {updated} packages with reverse dependencies")

    # Stats
    with_rev = sum(1 for d in packages.values() if d.get("dependencies", {}).get("depended_on_by"))
    max_dep = max(
        (
            (name, len(d.get("dependencies", {}).get("depended_on_by", [])))
            for name, d in packages.items()
        ),
        key=lambda x: x[1],
        default=("", 0),
    )
    typer.echo(f"  {with_rev} packages have at least one reverse dependency")
    if max_dep[1] > 0:
        typer.echo(f"  Most depended on: {max_dep[0]} ({max_dep[1]} packages)")


if __name__ == "__main__":
    app()
