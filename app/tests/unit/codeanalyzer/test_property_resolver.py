"""
Unit tests for PropertyResolver functionality.

Strategy: Unit tests with mocked analyzer and real property file parsing.
Real: Property file parsing, @Value placeholder resolution with defaults
Mocked: Analyzer (with controlled classes), member variables

Test Responsibilities:
- Single function tests: Property value resolution from real .properties files
- Parse property reference syntax
- Lookup with default fallback
- Parameter value resolution
- Error paths (missing files, empty analyzer)
"""

from app.src.codeanalyzer.models import Annotation, MemberVariable, Parameter
from app.src.codeanalyzer.property_resolver import PropertyResolver


def _make_resolver(classes=None):
    analyzer = type("FakeAnalyzer", (), {"classes": classes or {}})()
    return PropertyResolver(analyzer)


def _make_class(member_variables=None, methods=None):
    return type(
        "FakeJavaClass",
        (),
        {
            "member_variables": member_variables or [],
            "methods": methods or [],
        },
    )()


# ---------------------------------------------------------------------------
# Existing test (kept as-is)
# ---------------------------------------------------------------------------


def test_property_resolver_resolves_property_value(tmp_path):
    analyzer = type("FakeAnalyzer", (), {"classes": {}})()
    member = MemberVariable(
        name="myProp",
        type="String",
        annotations=[Annotation(name="Value", values={"value": "${my.property}"})],
    )
    java_class = type("FakeJavaClass", (), {"member_variables": [member], "methods": []})()
    analyzer.classes = {"FakeClass": java_class}
    resolver = PropertyResolver(analyzer)
    # Create a properties file
    prop_file = tmp_path / "app.properties"
    prop_file.write_text("my.property=hello\n")
    resolver.load_properties_file(str(prop_file))
    changed = resolver.resolve_all()
    assert changed
    assert hasattr(member, "resolved_properties")
    assert member.resolved_properties["my.property"] == "hello"


# ---------------------------------------------------------------------------
# _parse_property_reference
# ---------------------------------------------------------------------------


def test_parse_property_reference_standard():
    resolver = _make_resolver()
    ref = resolver._parse_property_reference("${my.prop}")
    assert ref is not None
    assert ref.name == "my.prop"
    assert ref.default_value is None


def test_parse_property_reference_with_default():
    resolver = _make_resolver()
    ref = resolver._parse_property_reference("${my.prop:fallback}")
    assert ref is not None
    assert ref.name == "my.prop"
    assert ref.default_value == "fallback"


def test_parse_property_reference_not_spring_syntax():
    resolver = _make_resolver()
    assert resolver._parse_property_reference("plainString") is None
    assert resolver._parse_property_reference("${incomplete") is None


# ---------------------------------------------------------------------------
# _lookup_property
# ---------------------------------------------------------------------------


def test_lookup_property_found(tmp_path):
    resolver = _make_resolver()
    prop_file = tmp_path / "app.properties"
    prop_file.write_text("db.url=jdbc:mysql://localhost\n")
    resolver.load_properties_file(str(prop_file))
    ref = resolver._parse_property_reference("${db.url}")
    assert resolver._lookup_property(ref) == "jdbc:mysql://localhost"


def test_lookup_property_default_fallback():
    resolver = _make_resolver()
    ref = resolver._parse_property_reference("${missing.prop:default-val}")
    assert resolver._lookup_property(ref) == "default-val"


def test_lookup_property_no_default_returns_none():
    resolver = _make_resolver()
    ref = resolver._parse_property_reference("${missing.prop}")
    assert resolver._lookup_property(ref) is None


def test_lookup_property_file_priority(tmp_path):
    """Later-sorted file wins when same key exists in multiple files."""
    resolver = _make_resolver()
    f1 = tmp_path / "a.properties"
    f1.write_text("shared.key=from-a\n")
    f2 = tmp_path / "b.properties"
    f2.write_text("shared.key=from-b\n")
    resolver.load_properties_file(str(f1))
    resolver.load_properties_file(str(f2))
    ref = resolver._parse_property_reference("${shared.key}")
    # Sorted reverse by file path: b > a
    assert resolver._lookup_property(ref) == "from-b"


# ---------------------------------------------------------------------------
# _resolve_parameter_value
# ---------------------------------------------------------------------------


def test_resolve_parameter_value(tmp_path):
    resolver = _make_resolver()
    prop_file = tmp_path / "app.properties"
    prop_file.write_text("server.port=8080\n")
    resolver.load_properties_file(str(prop_file))
    param = Parameter(
        name="port",
        type="int",
        annotations=[Annotation(name="Value", values={"value": "${server.port}"})],
    )
    changed = resolver._resolve_parameter_value(param)
    assert changed is True
    assert param.resolved_properties["server.port"] == "8080"


def test_resolve_parameter_value_no_match():
    resolver = _make_resolver()
    param = Parameter(
        name="port",
        type="int",
        annotations=[Annotation(name="Value", values={"value": "${missing.prop}"})],
    )
    changed = resolver._resolve_parameter_value(param)
    assert changed is False


# ---------------------------------------------------------------------------
# _resolve_member_value pydantic fallback
# ---------------------------------------------------------------------------


def test_resolve_member_pydantic_fallback(tmp_path):
    """Frozen model falls back to __dict__ assignment."""
    resolver = _make_resolver()
    prop_file = tmp_path / "app.properties"
    prop_file.write_text("my.val=resolved\n")
    resolver.load_properties_file(str(prop_file))
    member = MemberVariable(
        name="field",
        type="String",
        annotations=[Annotation(name="Value", values={"value": "${my.val}"})],
    )
    changed = resolver._resolve_member_value(member)
    assert changed is True


# ---------------------------------------------------------------------------
# _parse_properties_file edge cases
# ---------------------------------------------------------------------------


def test_parse_properties_file_error():
    resolver = _make_resolver()
    result = resolver._parse_properties_file("/nonexistent/path.properties")
    assert result == {}


def test_parse_properties_file_comments_blanks(tmp_path):
    f = tmp_path / "test.properties"
    f.write_text("# comment\n\nkey=value\n  \n# another\nkey2=value2\n")
    resolver = _make_resolver()
    result = resolver._parse_properties_file(str(f))
    assert result == {"key": "value", "key2": "value2"}


# ---------------------------------------------------------------------------
# resolve_all empty
# ---------------------------------------------------------------------------


def test_resolve_all_empty_analyzer():
    resolver = _make_resolver()
    assert resolver.resolve_all() is False
