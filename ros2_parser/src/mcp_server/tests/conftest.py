"""Shared test fixtures for mcp_server tests."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Minimal fake package data mirroring the real JSON schema
# ---------------------------------------------------------------------------

FAKE_DISTROS = ["jazzy"]

FAKE_SENSOR_MSGS = {
    "name": "sensor_msgs",
    "version": "5.3.7",
    "description": (
        "A package containing some sensor data related message and service definitions."
    ),
    "license": "Apache License 2.0",
    "build_type": "ament_cmake",
    "deprecated": None,
    "urls": [],
    "repo": {
        "name": "common_interfaces",
        "url": "https://github.com/ros2/common_interfaces.git",
        "branch": "jazzy",
    },
    "dependencies": {
        "buildtool": ["ament_cmake", "rosidl_default_generators"],
        "runtime": ["rclcpp"],
        "build_and_runtime": [
            "builtin_interfaces",
            "std_msgs",
            "geometry_msgs",
        ],
        "test": ["ament_lint_auto"],
        "depended_on_by": ["cv_bridge", "image_transport"],
    },
    "messages": {
        "Image": {
            "description": "This message contains an uncompressed image.",
            "raw": (
                "# This message contains an uncompressed image.\n"
                "uint32 height\nuint32 width\nstring encoding\n"
                "uint8 is_bigendian\nuint32 step\nuint8[] data\n"
            ),
            "fields": [
                {
                    "type": "uint32",
                    "name": "height",
                    "comment": "image height",
                    "default": None,
                    "is_constant": False,
                },
                {
                    "type": "uint32",
                    "name": "width",
                    "comment": "image width",
                    "default": None,
                    "is_constant": False,
                },
                {
                    "type": "string",
                    "name": "encoding",
                    "comment": "Encoding of pixels",
                    "default": None,
                    "is_constant": False,
                },
                {
                    "type": "uint8",
                    "name": "is_bigendian",
                    "comment": "",
                    "default": None,
                    "is_constant": False,
                },
                {
                    "type": "uint32",
                    "name": "step",
                    "comment": "Full row length in bytes",
                    "default": None,
                    "is_constant": False,
                },
                {
                    "type": "uint8[]",
                    "name": "data",
                    "comment": "actual matrix data",
                    "default": None,
                    "is_constant": False,
                },
            ],
        },
    },
    "services": {
        "SetCameraInfo": {
            "description": "Store camera calibration info.",
            "raw": (
                "sensor_msgs/CameraInfo camera_info\n---\nbool success\nstring status_message\n"
            ),
            "request_fields": [
                {
                    "type": "sensor_msgs/CameraInfo",
                    "name": "camera_info",
                    "comment": "",
                    "default": None,
                    "is_constant": False,
                },
            ],
            "response_fields": [
                {
                    "type": "bool",
                    "name": "success",
                    "comment": "",
                    "default": None,
                    "is_constant": False,
                },
                {
                    "type": "string",
                    "name": "status_message",
                    "comment": "",
                    "default": None,
                    "is_constant": False,
                },
            ],
        },
    },
    "actions": {},
}

FAKE_NAV2_MSGS = {
    "name": "nav2_msgs",
    "version": "1.3.5",
    "description": "Navigation2 messages and actions.",
    "license": "Apache License 2.0",
    "build_type": "ament_cmake",
    "deprecated": None,
    "urls": [],
    "repo": {
        "name": "navigation2",
        "url": "https://github.com/ros-navigation/navigation2.git",
        "branch": "jazzy",
    },
    "dependencies": {
        "buildtool": ["ament_cmake"],
        "build_and_runtime": ["action_msgs", "geometry_msgs"],
        "depended_on_by": [],
    },
    "messages": {},
    "services": {},
    "actions": {
        "NavigateToPose": {
            "description": "Navigate to a pose",
            "raw": (
                "geometry_msgs/PoseStamped pose\n"
                "string behavior_tree\n"
                "---\n"
                "std_msgs/Empty result\n"
                "---\n"
                "geometry_msgs/PoseStamped current_pose\n"
            ),
            "goal_fields": [
                {
                    "type": "geometry_msgs/PoseStamped",
                    "name": "pose",
                    "comment": "",
                    "default": None,
                    "is_constant": False,
                },
                {
                    "type": "string",
                    "name": "behavior_tree",
                    "comment": "",
                    "default": None,
                    "is_constant": False,
                },
            ],
            "result_fields": [
                {
                    "type": "std_msgs/Empty",
                    "name": "result",
                    "comment": "",
                    "default": None,
                    "is_constant": False,
                },
            ],
            "feedback_fields": [
                {
                    "type": "geometry_msgs/PoseStamped",
                    "name": "current_pose",
                    "comment": "",
                    "default": None,
                    "is_constant": False,
                },
            ],
        },
    },
}

FAKE_PACKAGES_LIST = [
    {
        "name": "action_msgs",
        "description": "Action messages",
        "version": "2.0.3",
    },
    {
        "name": "nav2_msgs",
        "description": "Navigation2 messages and actions.",
        "version": "1.3.5",
    },
    {
        "name": "sensor_msgs",
        "description": (
            "A package containing some sensor data related message and service definitions."
        ),
        "version": "5.3.7",
    },
    {
        "name": "std_msgs",
        "description": "Standard ROS messages",
        "version": "5.0.0",
    },
]


class MockLoader:
    """In-memory loader returning fake data without I/O."""

    async def __aenter__(self) -> MockLoader:
        return self

    async def __aexit__(self, *_: object) -> None:
        pass

    async def load_distros(self) -> list[str]:
        return FAKE_DISTROS

    async def load_packages(self, distro: str) -> list[dict]:
        return FAKE_PACKAGES_LIST

    async def load_package(self, distro: str, name: str) -> dict:
        from fastmcp.exceptions import ToolError

        packages = {
            "sensor_msgs": FAKE_SENSOR_MSGS,
            "nav2_msgs": FAKE_NAV2_MSGS,
        }
        if name not in packages:
            raise ToolError(f"Package '{name}' not found in distro '{distro}'.")
        return packages[name]


@pytest.fixture
def mock_loader() -> MockLoader:
    return MockLoader()
