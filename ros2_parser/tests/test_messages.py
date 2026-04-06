"""Tests for the message and service parsers."""

from ros2_indexer.parsers.messages import (
    _first_comment,
    parse_action_file,
    parse_field,
    parse_msg_file,
    parse_srv_file,
)


class TestParseField:
    """Tests for parse_field."""

    def test_regular_field(self):
        """Test parsing a standard field line."""
        field = parse_field("uint32 height")
        assert field is not None
        assert field.type == "uint32"
        assert field.name == "height"
        assert field.is_constant is False
        assert field.default == ""

    def test_field_with_package_prefix(self):
        """Test parsing a field with a package-qualified type."""
        field = parse_field("std_msgs/Header header")
        assert field is not None
        assert field.type == "std_msgs/Header"
        assert field.name == "header"

    def test_array_field(self):
        """Test parsing a field with an array type."""
        field = parse_field("uint8[] data")
        assert field is not None
        assert field.type == "uint8[]"
        assert field.name == "data"

    def test_constant(self):
        """Test parsing a constant definition with = sign."""
        field = parse_field("uint8 JPEG=0")
        assert field is not None
        assert field.is_constant is True
        assert field.type == "uint8"
        assert field.name == "JPEG"
        assert field.default == "0"

    def test_constant_with_spaces(self):
        """Test parsing a constant with spaces around the = sign."""
        field = parse_field("uint8 FORMAT = 1")
        assert field is not None
        assert field.is_constant is True
        assert field.name == "FORMAT"
        assert field.default == "1"

    def test_comment_line_returns_none(self):
        """Test that a comment-only line returns None."""
        result = parse_field("# This is a comment")
        assert result is None

    def test_blank_line_returns_none(self):
        """Test that an empty/blank line returns None."""
        assert parse_field("") is None
        assert parse_field("   ") is None

    def test_field_with_inline_comment(self):
        """Test parsing a field that has an inline comment."""
        field = parse_field("uint32 height  # image height in pixels")
        assert field is not None
        assert field.type == "uint32"
        assert field.name == "height"
        assert field.comment == "image height in pixels"


class TestFirstComment:
    """Tests for _first_comment description extraction."""

    def test_extracts_first_comment(self):
        assert _first_comment("# Hello world\nuint32 x\n") == "Hello world"

    def test_skips_empty_comments(self):
        assert _first_comment("#\n# Real comment\nuint32 x\n") == "Real comment"

    def test_skips_decoration_comments(self):
        assert _first_comment("###\n# Real comment\n") == "Real comment"

    def test_returns_empty_when_no_comments(self):
        assert _first_comment("uint32 x\nfloat64 y\n") == ""

    def test_truncates_long_comments(self):
        long = "# " + "a" * 200
        result = _first_comment(long)
        assert len(result) <= 120
        assert result.endswith("...")


class TestParseMsgFile:
    """Tests for parse_msg_file."""

    def test_msg_file(self, fixtures_dir):
        """Test parsing a .msg file produces correct MessageDef."""
        msg = parse_msg_file(fixtures_dir / "Image.msg")
        assert msg.name == "Image"
        assert msg.filename == "Image.msg"
        assert "std_msgs/Header header" in msg.raw_content
        # 7 fields: header, height, width, encoding, is_bigendian, step, data
        assert len(msg.fields) == 7

    def test_msg_description_extracted(self, fixtures_dir):
        """Test that description is extracted from the first comment."""
        msg = parse_msg_file(fixtures_dir / "Image.msg")
        assert msg.description == "This message contains an uncompressed image"

    def test_msg_field_types(self, fixtures_dir):
        """Test that field types are parsed correctly from the msg file."""
        msg = parse_msg_file(fixtures_dir / "Image.msg")
        field_types = {f.name: f.type for f in msg.fields}
        assert field_types["header"] == "std_msgs/Header"
        assert field_types["height"] == "uint32"
        assert field_types["data"] == "uint8[]"


class TestParseSrvFile:
    """Tests for parse_srv_file."""

    def test_srv_file_splits_on_separator(self, fixtures_dir):
        """Test that .srv file is split on --- into request and response."""
        srv = parse_srv_file(fixtures_dir / "SetCameraInfo.srv")
        assert srv.name == "SetCameraInfo"
        assert srv.filename == "SetCameraInfo.srv"

    def test_srv_description_extracted(self, fixtures_dir):
        """Test that description is extracted from the first comment."""
        srv = parse_srv_file(fixtures_dir / "SetCameraInfo.srv")
        assert "camera stores the given CameraInfo" in srv.description

    def test_srv_request_fields(self, fixtures_dir):
        """Test that request fields are correctly parsed."""
        srv = parse_srv_file(fixtures_dir / "SetCameraInfo.srv")
        assert len(srv.request_fields) == 1
        assert srv.request_fields[0].type == "sensor_msgs/CameraInfo"
        assert srv.request_fields[0].name == "camera_info"

    def test_srv_response_fields(self, fixtures_dir):
        """Test that response fields are correctly parsed."""
        srv = parse_srv_file(fixtures_dir / "SetCameraInfo.srv")
        assert len(srv.response_fields) == 2
        response_names = [f.name for f in srv.response_fields]
        assert "success" in response_names
        assert "status_message" in response_names


class TestParseActionFile:
    """Tests for parse_action_file."""

    def test_action_file_sections(self, fixtures_dir):
        """Test that .action file is split into goal/result/feedback."""
        action = parse_action_file(fixtures_dir / "Fibonacci.action")
        assert action.name == "Fibonacci"
        assert len(action.goal_fields) == 1
        assert action.goal_fields[0].name == "order"
        assert len(action.result_fields) == 1
        assert action.result_fields[0].name == "sequence"
        assert len(action.feedback_fields) == 1
        assert action.feedback_fields[0].name == "partial_sequence"

    def test_action_description_extracted(self, fixtures_dir):
        """Test that description is extracted from the first comment."""
        action = parse_action_file(fixtures_dir / "Fibonacci.action")
        assert "Fibonacci sequence" in action.description
