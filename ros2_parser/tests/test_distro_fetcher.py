"""Tests for the distribution fetcher."""

from unittest.mock import patch

import pytest
import yaml

from ros2_indexer.fetchers.distro import DistroFetcher


def _load_fixture_yaml(fixtures_dir):
    """Load the distro_snippet.yaml fixture and return parsed dict."""
    path = fixtures_dir / "distro_snippet.yaml"
    return yaml.safe_load(path.read_text())


def test_build_package_map_multi_package_repo(fixtures_dir):
    """Test that packages under release.packages map to the correct repo."""
    data = _load_fixture_yaml(fixtures_dir)
    fetcher = DistroFetcher("jazzy")
    pkg_map = fetcher._build_package_map(data)

    # sensor_msgs, std_msgs, geometry_msgs should all map to common_interfaces
    assert "sensor_msgs" in pkg_map
    assert pkg_map["sensor_msgs"][0] == "common_interfaces"

    assert "std_msgs" in pkg_map
    assert pkg_map["std_msgs"][0] == "common_interfaces"

    assert "geometry_msgs" in pkg_map
    assert pkg_map["geometry_msgs"][0] == "common_interfaces"


def test_build_package_map_single_package_repo(fixtures_dir):
    """Test that repos with no release.packages use repo name as package name."""
    data = _load_fixture_yaml(fixtures_dir)
    fetcher = DistroFetcher("jazzy")
    pkg_map = fetcher._build_package_map(data)

    assert "single_pkg" in pkg_map
    assert pkg_map["single_pkg"][0] == "single_pkg"


# --- Tag parsing ---


@pytest.mark.parametrize(
    "release_version, expected_tag",
    [
        ("0.2.1-5", "0.2.1"),
        ("28.1.17-3", "28.1.17"),
        ("1.0.0-7", "1.0.0"),
        ("2.0.2-6", "2.0.2"),
        ("5.3.5-1", "5.3.5"),
        ("1.0.0", "1.0.0"),  # no suffix
        ("0.0.1-4", "0.0.1"),
    ],
)
def test_parse_semver_tag(release_version, expected_tag):
    assert DistroFetcher._parse_semver_tag(release_version) == expected_tag


# --- get_repo_info ---


def test_get_repo_info_branch_only(fixtures_dir):
    """Packages with no release.version get an empty tag and use source branch."""
    data = _load_fixture_yaml(fixtures_dir)
    fetcher = DistroFetcher("jazzy")

    with patch.object(fetcher, "fetch", return_value=data):
        repo_info = fetcher.get_repo_info("single_pkg")

    assert repo_info.name == "single_pkg"
    assert repo_info.url == "https://github.com/test/single_pkg.git"
    assert repo_info.branch == "jazzy"
    assert repo_info.tag == ""
    assert repo_info.packages == ["single_pkg"]


def test_get_repo_info_with_release_version(fixtures_dir):
    """Packages with release.version get a semver tag; source branch is retained as fallback."""
    data = _load_fixture_yaml(fixtures_dir)
    fetcher = DistroFetcher("jazzy")

    with patch.object(fetcher, "fetch", return_value=data):
        repo_info = fetcher.get_repo_info("sensor_msgs")

    assert repo_info.name == "common_interfaces"
    assert repo_info.url == "https://github.com/ros2/common_interfaces.git"
    assert repo_info.branch == "jazzy"  # source.version (fallback)
    assert repo_info.tag == "5.3.5"  # parsed from release.version "5.3.5-1"
    assert "sensor_msgs" in repo_info.packages
    assert "std_msgs" in repo_info.packages
    assert "geometry_msgs" in repo_info.packages


def test_get_repo_info_rolling_branch_with_version(fixtures_dir):
    """A package on 'rolling' source branch with a release.version gets both set."""
    data = _load_fixture_yaml(fixtures_dir)
    fetcher = DistroFetcher("jazzy")

    with patch.object(fetcher, "fetch", return_value=data):
        repo_info = fetcher.get_repo_info("versioned_rolling")

    assert repo_info.branch == "rolling"
    assert repo_info.tag == "0.2.1"


def test_get_repo_info_no_release_version_in_release_section(fixtures_dir):
    """A release section without a version field yields an empty tag."""
    data = _load_fixture_yaml(fixtures_dir)
    fetcher = DistroFetcher("jazzy")

    with patch.object(fetcher, "fetch", return_value=data):
        repo_info = fetcher.get_repo_info("no_release_version")

    assert repo_info.branch == "main"
    assert repo_info.tag == ""


def test_get_repo_info_unknown_package_raises(fixtures_dir):
    """Looking up a nonexistent package raises KeyError."""
    data = _load_fixture_yaml(fixtures_dir)
    fetcher = DistroFetcher("jazzy")

    with patch.object(fetcher, "fetch", return_value=data), pytest.raises(KeyError):
        fetcher.get_repo_info("nonexistent_pkg")
