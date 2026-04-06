"""Data models for ROS2 package indexing."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RepoInfo:
    """Repository info from distribution.yaml."""

    name: str  # repo name (e.g. "common_interfaces")
    url: str  # git clone URL
    branch: str  # source branch (e.g. "jazzy"), used as fallback
    tag: str = ""  # semver tag from release.version (e.g. "0.2.1"), preferred over branch
    packages: list[str] = field(default_factory=list)  # packages in this repo


# ---------------------------------------------------------------------------
# Message / Service models
# ---------------------------------------------------------------------------


@dataclass
class FieldDef:
    """A single field in a .msg or .srv definition."""

    type: str  # e.g. "uint32", "sensor_msgs/Image"
    name: str  # e.g. "height"
    comment: str = ""  # inline comment
    default: str = ""  # default value if specified
    is_constant: bool = False  # true if it's a constant definition


@dataclass
class MessageDef:
    """A parsed .msg file."""

    name: str  # e.g. "Image"
    filename: str  # e.g. "Image.msg"
    raw_content: str  # full file content (included verbatim in output)
    description: str = ""  # first meaningful comment from the file
    fields: list[FieldDef] = field(default_factory=list)


@dataclass
class ServiceDef:
    """A parsed .srv file."""

    name: str  # e.g. "SetCameraInfo"
    filename: str  # e.g. "SetCameraInfo.srv"
    raw_content: str  # full file content
    description: str = ""  # first meaningful comment from the file
    request_fields: list[FieldDef] = field(default_factory=list)
    response_fields: list[FieldDef] = field(default_factory=list)


@dataclass
class ActionDef:
    """A parsed .action file (goal / result / feedback sections)."""

    name: str  # e.g. "Fibonacci"
    filename: str  # e.g. "Fibonacci.action"
    raw_content: str  # full file content
    description: str = ""  # first meaningful comment from the file
    goal_fields: list[FieldDef] = field(default_factory=list)
    result_fields: list[FieldDef] = field(default_factory=list)
    feedback_fields: list[FieldDef] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Dependency / Package metadata
# ---------------------------------------------------------------------------


@dataclass
class Dependency:
    """A package dependency with its type."""

    name: str
    dep_type: str  # build_depend, exec_depend, depend, etc.


@dataclass
class PackageMetadata:
    """Metadata extracted from package.xml."""

    name: str
    version: str
    description: str
    license: str
    build_type: str  # ament_cmake, ament_python, cmake, etc.
    urls: list[dict[str, str]] = field(default_factory=list)  # [{uri, type}]
    dependencies: list[Dependency] = field(default_factory=list)
    deprecated: str = ""


# ---------------------------------------------------------------------------
# Top-level index model
# ---------------------------------------------------------------------------


@dataclass
class PackageIndex:
    """All indexed data for a single package, ready for JSON serialization."""

    metadata: PackageMetadata
    repo: RepoInfo
    distro: str
    messages: list[MessageDef] = field(default_factory=list)
    services: list[ServiceDef] = field(default_factory=list)
    actions: list[ActionDef] = field(default_factory=list)
