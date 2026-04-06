"""Shallow git cloning and file discovery for ROS2 package repos."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

from ros2_indexer.config import REPOS_DIR, SAFE_NAME, SCRATCH_DIR
from ros2_indexer.models import RepoInfo

logger = logging.getLogger(__name__)


class RepoFetcher:
    """Clone repos and locate package files within them."""

    def clone(self, repo_info: RepoInfo) -> Path:
        """Shallow-clone a repository and return the clone path.

        If the target directory already exists (e.g. from a previous run with
        --keep-scratch), the clone is skipped and the existing path is returned.

        When repo_info.tag is set, attempts are made in order:
          1. tag as-is  (e.g. "0.2.1")
          2. tag with v-prefix  (e.g. "v0.2.1")
          3. source branch  (e.g. "rolling")

        This ensures released versions are fetched at their exact tag when
        available, falling back to the development branch otherwise.
        """
        if not SAFE_NAME.match(repo_info.name):
            raise ValueError(f"Invalid repo name: {repo_info.name!r}")
        if not repo_info.url.startswith("https://"):
            raise ValueError(f"Only https:// clone URLs are allowed, got: {repo_info.url!r}")

        target = REPOS_DIR / repo_info.name

        if target.exists():
            logger.info("Reusing existing clone: %s", target)
            return target

        REPOS_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)

        # Build ordered list of refs to try.
        refs: list[str] = []
        if repo_info.tag:
            refs.append(repo_info.tag)
            if not repo_info.tag.startswith("v"):
                refs.append(f"v{repo_info.tag}")
        refs.append(repo_info.branch)
        # Deduplicate while preserving order.
        seen: set[str] = set()
        refs = [r for r in refs if not (r in seen or seen.add(r))]  # type: ignore[func-returns-value]

        last_result = None
        for ref in refs:
            logger.info("Cloning %s (ref=%s) into %s", repo_info.url, ref, target)
            result = subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth=1",
                    f"--branch={ref}",
                    repo_info.url,
                    str(target),
                ],
                capture_output=True,
                text=True,
                timeout=120,
                env={
                    **os.environ,
                    "GIT_ALLOW_PROTOCOL": "https",
                    "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_KEY_0": "core.hooksPath",
                    "GIT_CONFIG_VALUE_0": "/dev/null",
                },
            )
            if result.returncode == 0:
                logger.info("Cloned at ref=%s", ref)
                return target
            # Remove partial clone directory before retrying.
            if target.exists():
                shutil.rmtree(target)
            logger.warning(
                "Clone at ref=%s failed: %s",
                ref,
                result.stderr.strip().splitlines()[-1]
                if result.stderr.strip()
                else "unknown error",
            )
            last_result = result

        # All refs exhausted — raise so cli.py can log and skip.
        raise subprocess.CalledProcessError(
            last_result.returncode,
            ["git", "clone", repo_info.url],
            stderr=last_result.stderr,
        )

    def find_package_dir(self, clone_path: Path, package_name: str) -> Path | None:
        """Locate the directory containing package.xml for *package_name*.

        Checks two common layouts:
          1. Subdirectory: ``clone_path / package_name / package.xml``
          2. Repo root:    ``clone_path / package.xml``

        Returns the directory that contains package.xml, or ``None`` if neither
        location has one.
        """
        if not SAFE_NAME.match(package_name):
            raise ValueError(f"Invalid package name: {package_name!r}")

        # Subdirectory layout (most common for multi-package repos)
        subdir = clone_path / package_name
        pkg_xml = subdir / "package.xml"
        if (
            pkg_xml.is_file()
            and not pkg_xml.is_symlink()
            and pkg_xml.resolve().is_relative_to(clone_path.resolve())
        ):
            return subdir

        # Root layout (single-package repo)
        pkg_xml = clone_path / "package.xml"
        if pkg_xml.is_file() and not pkg_xml.is_symlink():
            return clone_path

        return None

    def cleanup_scratch(self) -> None:
        """Delete the entire .scratch/ directory and all its contents."""
        if SCRATCH_DIR.exists():
            logger.info("Removing scratch directory: %s", SCRATCH_DIR)
            shutil.rmtree(SCRATCH_DIR)
