"""Fetch and parse ROS2 distribution.yaml to map package names to repo info."""

from __future__ import annotations

import logging
import re

import httpx
import yaml

from ros2_indexer.config import DISTRO_DIR, DISTRO_YAML_URL
from ros2_indexer.models import RepoInfo

logger = logging.getLogger(__name__)


class DistroFetcher:
    """Downloads distribution.yaml and resolves package names to repository info."""

    _SAFE_DISTRO = re.compile(r"^[a-z][a-z0-9_]+$")

    def __init__(self, distro: str) -> None:
        if not self._SAFE_DISTRO.match(distro):
            raise ValueError(f"Invalid distro name: {distro!r}")
        self.distro = distro
        self._package_map: dict[str, tuple[str, dict]] | None = None

    def fetch(self) -> dict:
        """Download distribution.yaml (or read from cache) and return parsed YAML."""
        DISTRO_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = DISTRO_DIR / f"{self.distro}_distribution.yaml"

        if cache_path.exists():
            logger.info("Using cached distribution.yaml: %s", cache_path)
            raw = cache_path.read_text()
        else:
            url = DISTRO_YAML_URL.format(distro=self.distro)
            logger.info("Downloading distribution.yaml from %s", url)
            resp = httpx.get(url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            raw = resp.text
            cache_path.write_text(raw)
            logger.info("Cached distribution.yaml to %s", cache_path)

        return yaml.safe_load(raw)

    def _build_package_map(self, data: dict) -> dict[str, tuple[str, dict]]:
        """Build a reverse lookup: package_name -> (repo_name, repo_data).

        distribution.yaml lists packages under repositories.{repo_name}.release.packages.
        If a repo has no release.packages, the repo name itself is the sole package name.
        """
        package_map: dict[str, tuple[str, dict]] = {}
        repositories = data.get("repositories", {})

        for repo_name, repo_data in repositories.items():
            if repo_data is None:
                continue

            release = repo_data.get("release", {})
            packages = release.get("packages") if release else None

            if packages:
                for pkg in packages:
                    package_map[pkg] = (repo_name, repo_data)
            else:
                # No explicit package list -- repo name is the package name.
                package_map[repo_name] = (repo_name, repo_data)

        return package_map

    def list_packages(self) -> list[str]:
        """Return a sorted list of all package names in the distro."""
        if self._package_map is None:
            data = self.fetch()
            self._package_map = self._build_package_map(data)
        return sorted(self._package_map.keys())

    def get_repo_info(self, package_name: str) -> RepoInfo:
        """Look up a package in distribution.yaml and return its RepoInfo.

        Raises KeyError if the package is not found.
        """
        if self._package_map is None:
            data = self.fetch()
            self._package_map = self._build_package_map(data)

        if package_name not in self._package_map:
            raise KeyError(f"Package '{package_name}' not found in {self.distro} distribution.yaml")

        repo_name, repo_data = self._package_map[package_name]

        # Extract url, source branch, and release version.
        url, source_version, release_version = self._extract_url_and_version(repo_data)

        # Resolve the source branch: fall back to distro name if missing.
        branch = source_version if (source_version and source_version != "HEAD") else self.distro

        # Resolve the version tag: parse semver from release.version (strips "-N" suffix).
        tag = self._parse_semver_tag(release_version) if release_version else ""

        # Collect the full list of packages for this repo.
        release = repo_data.get("release", {})
        packages = list(release.get("packages") or []) if release else []
        if not packages:
            packages = [repo_name]

        return RepoInfo(
            name=repo_name,
            url=url,
            branch=branch,
            tag=tag,
            packages=packages,
        )

    def _extract_url_and_version(self, repo_data: dict) -> tuple[str, str, str]:
        """Extract (url, source_version, release_version) from repo data.

        source_version is the branch name (e.g. "jazzy", "rolling").
        release_version is the release iteration string (e.g. "0.2.1-5"), may be empty.
        """
        source = repo_data.get("source", {})
        source_url = (source or {}).get("url", "")
        source_version = (source or {}).get("version", "")

        if not source_url:
            doc = repo_data.get("doc", {})
            source_url = (doc or {}).get("url", "")
            source_version = (doc or {}).get("version", "")

        release = repo_data.get("release", {})
        release_version = (release or {}).get("version", "")

        return source_url, source_version, release_version

    @staticmethod
    def _parse_semver_tag(release_version: str) -> str:
        """Strip the release iteration suffix from a release.version string.

        Examples:
            "0.2.1-5"  → "0.2.1"
            "28.1.17-3" → "28.1.17"
            "1.0.0"    → "1.0.0"  (no suffix, unchanged)
        """
        return re.sub(r"-\d+$", "", release_version.strip())
