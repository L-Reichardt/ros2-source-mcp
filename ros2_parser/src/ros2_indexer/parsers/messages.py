"""Parse .msg and .srv ROS2 message/service definition files."""

from __future__ import annotations

import re
from pathlib import Path

from ros2_indexer.models import ActionDef, FieldDef, MessageDef, ServiceDef


def _first_comment(raw_content: str) -> str:
    """Extract the first meaningful # comment from a .msg/.srv/.action file."""
    for line in raw_content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        text = stripped.lstrip("#").strip()
        if not text or all(c == "#" for c in text):
            continue
        if len(text) > 120:
            text = text[:117] + "..."
        return text
    return ""


def parse_field(line: str) -> FieldDef | None:
    """Parse a single field line. Return None for comments and blank lines."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    # Split off inline comment
    comment = ""
    if "#" in stripped:
        # Find the first # that isn't inside the field definition
        code_part, _, comment = stripped.partition("#")
        stripped = code_part.strip()
        comment = comment.strip()

    # Check for constant: type NAME=value (or type NAME = value)
    # Constants have an = sign in the name/value portion
    const_match = re.match(r"^(\S+)\s+(\w+)\s*=\s*(.+)$", stripped)
    if const_match:
        return FieldDef(
            type=const_match.group(1),
            name=const_match.group(2),
            default=const_match.group(3).strip(),
            comment=comment,
            is_constant=True,
        )

    # Regular field: type name [default_value]
    parts = stripped.split()
    if len(parts) < 2:
        return None

    field_type = parts[0]
    field_name = parts[1]
    default = " ".join(parts[2:]) if len(parts) > 2 else ""

    return FieldDef(
        type=field_type,
        name=field_name,
        default=default,
        comment=comment,
        is_constant=False,
    )


def parse_msg_file(path: Path) -> MessageDef:
    """Parse a .msg file into a MessageDef."""
    raw_content = path.read_text(encoding="utf-8")
    fields: list[FieldDef] = []

    for line in raw_content.splitlines():
        field = parse_field(line)
        if field is not None:
            fields.append(field)

    return MessageDef(
        name=path.stem,
        filename=path.name,
        raw_content=raw_content,
        description=_first_comment(raw_content),
        fields=fields,
    )


def parse_srv_file(path: Path) -> ServiceDef:
    """Parse a .srv file into a ServiceDef."""
    raw_content = path.read_text(encoding="utf-8")
    request_fields: list[FieldDef] = []
    response_fields: list[FieldDef] = []

    # Split on --- separator
    in_response = False
    for line in raw_content.splitlines():
        if line.strip() == "---":
            in_response = True
            continue

        field = parse_field(line)
        if field is None:
            continue

        if in_response:
            response_fields.append(field)
        else:
            request_fields.append(field)

    return ServiceDef(
        name=path.stem,
        filename=path.name,
        raw_content=raw_content,
        description=_first_comment(raw_content),
        request_fields=request_fields,
        response_fields=response_fields,
    )


def parse_all_messages(msg_dir: Path) -> list[MessageDef]:
    """Parse all .msg files in a directory."""
    if not msg_dir.is_dir():
        return []
    return sorted(
        (parse_msg_file(p) for p in msg_dir.glob("*.msg")),
        key=lambda m: m.name,
    )


def parse_all_services(srv_dir: Path) -> list[ServiceDef]:
    """Parse all .srv files in a directory."""
    if not srv_dir.is_dir():
        return []
    return sorted(
        (parse_srv_file(p) for p in srv_dir.glob("*.srv")),
        key=lambda s: s.name,
    )


def parse_action_file(path: Path) -> ActionDef:
    """Parse a .action file into an ActionDef (goal / result / feedback sections)."""
    raw_content = path.read_text(encoding="utf-8")
    goal_fields: list[FieldDef] = []
    result_fields: list[FieldDef] = []
    feedback_fields: list[FieldDef] = []

    # Three sections separated by ---
    section = 0
    targets = [goal_fields, result_fields, feedback_fields]
    for line in raw_content.splitlines():
        if line.strip() == "---":
            section += 1
            continue
        f = parse_field(line)
        if f is not None and section < 3:
            targets[section].append(f)

    return ActionDef(
        name=path.stem,
        filename=path.name,
        raw_content=raw_content,
        description=_first_comment(raw_content),
        goal_fields=goal_fields,
        result_fields=result_fields,
        feedback_fields=feedback_fields,
    )


def parse_all_actions(action_dir: Path) -> list[ActionDef]:
    """Parse all .action files in a directory."""
    if not action_dir.is_dir():
        return []
    return sorted(
        (parse_action_file(p) for p in action_dir.glob("*.action")),
        key=lambda a: a.name,
    )
