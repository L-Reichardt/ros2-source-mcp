"""Tests for the package.xml parser."""

from ros2_indexer.parsers.package_xml import parse_package_xml


def test_basic_metadata(fixtures_dir):
    """Test that basic metadata fields are parsed correctly."""
    meta = parse_package_xml(fixtures_dir / "package.xml")
    assert meta.name == "test_pkg"
    assert meta.version == "1.2.3"
    assert meta.description == "A test package for unit testing."
    assert meta.license == "Apache License 2.0"
    assert meta.build_type == "ament_cmake"


def test_urls(fixtures_dir):
    """Test that URLs are parsed with their type attributes."""
    meta = parse_package_xml(fixtures_dir / "package.xml")
    assert len(meta.urls) == 1
    assert meta.urls[0]["uri"] == "https://github.com/test/test_pkg"
    assert meta.urls[0]["type"] == "repository"


def test_dependencies(fixtures_dir):
    """Test that all dependency types are collected correctly."""
    meta = parse_package_xml(fixtures_dir / "package.xml")

    dep_names = [d.name for d in meta.dependencies]
    dep_types = {d.name: d.dep_type for d in meta.dependencies}

    # All expected deps present
    assert "ament_cmake" in dep_names
    assert "std_msgs" in dep_names
    assert "rclcpp" in dep_names
    assert "builtin_interfaces" in dep_names
    assert "ament_lint_auto" in dep_names

    # Check specific dep_type values
    assert dep_types["ament_cmake"] == "buildtool_depend"
    assert dep_types["ament_lint_auto"] == "test_depend"
    assert dep_types["builtin_interfaces"] == "depend"
    assert dep_types["rclcpp"] == "exec_depend"


def test_dependencies_include_all_types(fixtures_dir):
    """Test that build_depend, exec_depend, depend, test_depend are all present."""
    meta = parse_package_xml(fixtures_dir / "package.xml")
    dep_type_set = {d.dep_type for d in meta.dependencies}
    assert "buildtool_depend" in dep_type_set
    assert "build_depend" in dep_type_set
    assert "exec_depend" in dep_type_set
    assert "depend" in dep_type_set
    assert "test_depend" in dep_type_set
