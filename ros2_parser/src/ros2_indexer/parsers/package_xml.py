"""Parse package.xml files into PackageMetadata."""

from __future__ import annotations

from pathlib import Path

import defusedxml.ElementTree as ET

from ros2_indexer.models import Dependency, PackageMetadata

_DEP_TYPES = (
    "build_depend",
    "build_export_depend",
    "buildtool_depend",
    "buildtool_export_depend",
    "exec_depend",
    "doc_depend",
    "run_depend",
    "test_depend",
    "depend",
)


def _text(element: ET.Element | None, default: str = "") -> str:
    """Get text content of an element, or default if missing/empty."""
    if element is None or element.text is None:
        return default
    return element.text.strip()


def parse_package_xml(path: Path) -> PackageMetadata:
    """Parse a package.xml file and return PackageMetadata."""
    tree = ET.parse(path)
    root = tree.getroot()

    name = _text(root.find("name"))
    version = _text(root.find("version"))
    description = _text(root.find("description"))
    pkg_license = _text(root.find("license"))

    # Build type from /package/export/build_type
    export = root.find("export")
    if export is not None:
        build_type = _text(export.find("build_type"), "ament_cmake")
    else:
        build_type = "ament_cmake"

    # URLs
    urls = [
        {
            "uri": _text(u),
            "type": u.attrib.get("type", "website"),
        }
        for u in root.findall("url")
        if _text(u)
    ]

    # Dependencies - collect all types, deduplicate by (name, dep_type)
    seen: set[tuple[str, str]] = set()
    dependencies: list[Dependency] = []
    for dep_type in _DEP_TYPES:
        for elem in root.findall(dep_type):
            dep_name = _text(elem)
            if dep_name and (dep_name, dep_type) not in seen:
                seen.add((dep_name, dep_type))
                dependencies.append(Dependency(name=dep_name, dep_type=dep_type))

    # Deprecated
    deprecated = ""
    if export is not None:
        deprecated = _text(export.find("deprecated"))

    return PackageMetadata(
        name=name,
        version=version,
        description=description,
        license=pkg_license,
        build_type=build_type,
        urls=urls,
        dependencies=dependencies,
        deprecated=deprecated,
    )
