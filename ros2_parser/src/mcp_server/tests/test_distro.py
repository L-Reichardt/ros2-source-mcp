"""Unit tests for distro name validation."""

import pytest

from mcp_server.distro import validate_distro


def test_valid_distros():
    assert validate_distro("jazzy") == "jazzy"
    assert validate_distro("humble") == "humble"
    assert validate_distro("iron") == "iron"
    assert validate_distro("rolling") == "rolling"
    assert validate_distro("ros2_test") == "ros2_test"


def test_uppercase_rejected():
    with pytest.raises(ValueError, match="Invalid distro"):
        validate_distro("Jazzy")


def test_path_traversal_rejected():
    with pytest.raises(ValueError, match="Invalid distro"):
        validate_distro("../evil")


def test_slash_rejected():
    with pytest.raises(ValueError, match="Invalid distro"):
        validate_distro("foo/bar")


def test_empty_string_rejected():
    with pytest.raises(ValueError, match="Invalid distro"):
        validate_distro("")


def test_starts_with_digit_rejected():
    with pytest.raises(ValueError, match="Invalid distro"):
        validate_distro("2jazzy")
