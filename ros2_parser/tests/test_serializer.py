"""Tests for the JSON serializer."""

import json

from ros2_indexer.models import (
    Dependency,
    FieldDef,
    MessageDef,
    PackageIndex,
    PackageMetadata,
    RepoInfo,
    ServiceDef,
)
from ros2_indexer.serializer import write_package_json, write_packages_index


def _make_pkg(name="test_pkg", distro="jazzy"):
    """Create a minimal PackageIndex for testing."""
    meta = PackageMetadata(
        name=name,
        version="1.0.0",
        description="A test package.",
        license="Apache-2.0",
        build_type="ament_cmake",
        urls=[{"uri": "https://github.com/test/test_pkg", "type": "repository"}],
        dependencies=[
            Dependency(name="rclcpp", dep_type="build_depend"),
            Dependency(name="std_msgs", dep_type="depend"),
            Dependency(name="ament_lint_auto", dep_type="test_depend"),
        ],
    )
    repo = RepoInfo(name="test_repo", url="https://github.com/test/test_repo.git", branch="jazzy")
    msg = MessageDef(
        name="Greeting",
        filename="Greeting.msg",
        raw_content="# A greeting message\nstring text\n",
        description="A greeting message",
        fields=[FieldDef(type="string", name="text")],
    )
    srv = ServiceDef(
        name="Echo",
        filename="Echo.srv",
        raw_content="# Echo service\nstring input\n---\nstring output\n",
        description="Echo service",
        request_fields=[FieldDef(type="string", name="input")],
        response_fields=[FieldDef(type="string", name="output")],
    )
    return PackageIndex(
        metadata=meta,
        repo=repo,
        distro=distro,
        messages=[msg],
        services=[srv],
    )


def test_write_package_json_creates_file(tmp_path):
    """Test that write_package_json creates {distro}/{package}.json."""
    pkg = _make_pkg()
    path = write_package_json(pkg, tmp_path)
    assert path.exists()
    assert path.name == "test_pkg.json"
    assert path.parent.name == "jazzy"


def test_package_json_structure(tmp_path):
    """Test the top-level keys of the package JSON."""
    pkg = _make_pkg()
    path = write_package_json(pkg, tmp_path)
    data = json.loads(path.read_text())

    assert data["name"] == "test_pkg"
    assert data["version"] == "1.0.0"
    assert data["description"] == "A test package."
    assert data["license"] == "Apache-2.0"
    assert data["build_type"] == "ament_cmake"
    assert data["repo"]["name"] == "test_repo"
    assert data["repo"]["url"] == "https://github.com/test/test_repo.git"
    assert data["repo"]["branch"] == "jazzy"


def test_dependencies_grouped_by_type(tmp_path):
    """Test that dependencies are grouped by dep_type in the JSON."""
    pkg = _make_pkg()
    path = write_package_json(pkg, tmp_path)
    data = json.loads(path.read_text())

    deps = data["dependencies"]
    assert "rclcpp" in deps["build"]
    assert "std_msgs" in deps["build_and_runtime"]
    assert "ament_lint_auto" in deps["test"]


def test_messages_serialized(tmp_path):
    """Test that messages are serialized with description, raw, and fields."""
    pkg = _make_pkg()
    path = write_package_json(pkg, tmp_path)
    data = json.loads(path.read_text())

    assert "Greeting" in data["messages"]
    msg = data["messages"]["Greeting"]
    assert msg["description"] == "A greeting message"
    assert "string text" in msg["raw"]
    assert len(msg["fields"]) == 1
    assert msg["fields"][0]["type"] == "string"
    assert msg["fields"][0]["name"] == "text"
    assert msg["fields"][0]["default"] is None


def test_services_serialized(tmp_path):
    """Test that services are serialized with request and response fields."""
    pkg = _make_pkg()
    path = write_package_json(pkg, tmp_path)
    data = json.loads(path.read_text())

    assert "Echo" in data["services"]
    srv = data["services"]["Echo"]
    assert srv["description"] == "Echo service"
    assert len(srv["request_fields"]) == 1
    assert len(srv["response_fields"]) == 1


def test_write_packages_index(tmp_path):
    """Test that packages.json is written with sorted summaries."""
    pkg_a = _make_pkg(name="alpha_pkg")
    pkg_z = _make_pkg(name="zeta_pkg")
    path = write_packages_index([pkg_z, pkg_a], "jazzy", tmp_path)

    assert path.exists()
    assert path.name == "packages.json"
    data = json.loads(path.read_text())

    assert len(data) == 2
    assert data[0]["name"] == "alpha_pkg"  # sorted
    assert data[1]["name"] == "zeta_pkg"
    assert "description" in data[0]
    assert "version" in data[0]
