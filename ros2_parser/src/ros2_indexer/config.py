"""Constants, paths, and defaults."""

import re
from pathlib import Path

# Safe name pattern for repo names, package names, and filesystem identifiers.
SAFE_NAME = re.compile(r"^[a-zA-Z0-9_.-]+$")

# Base directory of the ros2_indexer project
PROJECT_DIR = Path(__file__).resolve().parent.parent.parent

SCRATCH_DIR = PROJECT_DIR / ".scratch"
REPOS_DIR = SCRATCH_DIR / "repos"
DISTRO_DIR = SCRATCH_DIR / "distro"
INDEX_DIR = PROJECT_DIR / "index"

DISTRO_YAML_URL = (
    "https://raw.githubusercontent.com/ros/rosdistro/master/{distro}/distribution.yaml"
)
