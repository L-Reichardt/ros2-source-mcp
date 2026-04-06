"""Integration tests that require network access.

Run with: pytest tests/test_integration.py -v -m integration

Package selection:
  Branch packages  — source.version is a distro branch, verify branch cloning.
  Versioned packages — release.version diverges from source.version, verify tag cloning.
"""

import json

import pytest

from ros2_indexer.cli import build_cmd
from ros2_indexer.fetchers.distro import DistroFetcher


def _run(tmp_path, package, distro="jazzy"):
    build_cmd(
        distro=distro,
        package=package,
        output_dir=tmp_path,
        keep_scratch=False,
    )
    return tmp_path / distro


def _load_package_json(distro_dir, package):
    path = distro_dir / f"{package}.json"
    assert path.exists(), f"Missing {package}.json"
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Branch-based packages (source.version = jazzy branch)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.parametrize(
    "package",
    [
        "sensor_msgs",
        "std_msgs",
        "geometry_msgs",
        "rclcpp",
        "builtin_interfaces",
    ],
)
def test_branch_packages(tmp_path, package):
    distro_dir = _run(tmp_path, package)
    data = _load_package_json(distro_dir, package)
    assert data["name"] == package
    assert "version" in data
    assert "dependencies" in data


# ---------------------------------------------------------------------------
# Versioned packages (release.version → semver tag clone)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.parametrize(
    "package, expected_tag",
    [
        ("adaptive_component", "0.2.1"),
        ("ackermann_msgs", "2.0.2"),
        ("actuator_msgs", "0.0.1"),
        ("ackermann_nlmpc", "1.0.3"),
        ("acado_vendor", "1.0.0"),
    ],
)
def test_versioned_packages(tmp_path, package, expected_tag):
    fetcher = DistroFetcher("jazzy")
    repo_info = fetcher.get_repo_info(package)
    assert repo_info.tag == expected_tag, (
        f"{package}: expected tag={expected_tag!r}, got {repo_info.tag!r}"
    )
    distro_dir = _run(tmp_path, package)
    data = _load_package_json(distro_dir, package)
    assert data["name"] == package


# ---------------------------------------------------------------------------
# Full pipeline — sensor_msgs (C++ package with messages)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_full_pipeline_sensor_msgs(tmp_path):
    distro_dir = _run(tmp_path, "sensor_msgs")
    data = _load_package_json(distro_dir, "sensor_msgs")

    # Basic metadata
    assert data["name"] == "sensor_msgs"
    assert data["version"]
    assert data["license"]
    assert data["repo"]["name"] == "common_interfaces"

    # Messages present
    assert "Image" in data["messages"]
    image = data["messages"]["Image"]
    assert image["description"]
    assert "uint32" in image["raw"]
    assert len(image["fields"]) > 0
    field_names = [f["name"] for f in image["fields"]]
    assert "height" in field_names
    assert "width" in field_names

    # Dependencies present
    deps = data["dependencies"]
    assert any("ament_cmake" in deps.get(dt, []) for dt in deps)
    assert any("builtin_interfaces" in deps.get(dt, []) for dt in deps)

    # packages.json written
    packages_json = distro_dir / "packages.json"
    assert packages_json.exists()
    index = json.loads(packages_json.read_text())
    names = [p["name"] for p in index]
    assert "sensor_msgs" in names


# ---------------------------------------------------------------------------
# Full pipeline — rclcpp (C++ package, no messages)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_full_pipeline_rclcpp(tmp_path):
    distro_dir = _run(tmp_path, "rclcpp")
    data = _load_package_json(distro_dir, "rclcpp")

    assert data["name"] == "rclcpp"
    assert data["messages"] == {}
    assert data["services"] == {}
    assert data["actions"] == {}
    assert len(data["dependencies"]) > 0
