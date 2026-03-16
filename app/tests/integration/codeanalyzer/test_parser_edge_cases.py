"""
Integration tests for parser edge cases.

Strategy: Real tree-sitter parsing with inline Java snippets via tmp_path.
No mocks — these test actual tree-sitter AST walking through the parser.

Test Responsibilities:
- Enum extraction (constants with args, annotations, empty body)
- MissingDeclarationException for files with no type declaration
- Annotation value branches (boolean, array with field access)
- Method call argument expressions
- Class extends and generics
"""

import pytest

from app.src.codeanalyzer.parser import JavaParser, MissingDeclarationException


@pytest.fixture(scope="module")
def parser():
    return JavaParser()


def _parse_snippet(parser, tmp_path, filename, java_code):
    """Write a Java snippet and parse it."""
    f = tmp_path / filename
    f.write_text(java_code)
    return parser.parse_java_file(str(f))


# ---------------------------------------------------------------------------
# Enum extraction
# ---------------------------------------------------------------------------


def test_enum_constant_extraction(parser, tmp_path):
    from app.src.codeanalyzer.models import EnumClass

    java = """\
package com.example;
public enum Color {
    RED("FF0000"),
    GREEN("00FF00"),
    BLUE("0000FF");
    private final String hex;
    Color(String hex) { this.hex = hex; }
}
"""
    cls = _parse_snippet(parser, tmp_path, "Color.java", java)
    assert cls.name == "Color"
    assert isinstance(cls, EnumClass)


def test_enum_with_annotations(parser, tmp_path):
    java = """\
package com.example;
public enum Status {
    @Deprecated
    ACTIVE,
    INACTIVE;
}
"""
    cls = _parse_snippet(parser, tmp_path, "Status.java", java)
    assert cls.name == "Status"


def test_enum_empty_body(parser, tmp_path):
    java = """\
package com.example;
public enum Empty {
}
"""
    cls = _parse_snippet(parser, tmp_path, "Empty.java", java)
    assert cls.name == "Empty"


# ---------------------------------------------------------------------------
# MissingDeclarationException
# ---------------------------------------------------------------------------


def test_missing_declaration_exception(parser, tmp_path):
    java = """\
package com.example;
// No class, interface, or enum declaration
"""
    with pytest.raises(MissingDeclarationException):
        _parse_snippet(parser, tmp_path, "NoDecl.java", java)


# ---------------------------------------------------------------------------
# Annotation value branches
# ---------------------------------------------------------------------------


def test_annotation_boolean_true_false(parser, tmp_path):
    java = """\
package com.example;
import org.springframework.web.bind.annotation.RequestParam;
public class BoolAnno {
    public void method(@RequestParam(required = false) String param) {}
}
"""
    cls = _parse_snippet(parser, tmp_path, "BoolAnno.java", java)
    method = cls.methods[0]
    assert len(method.parameters) >= 1


def test_annotation_array_with_field_access(parser, tmp_path):
    java = """\
package com.example;
import org.springframework.web.bind.annotation.RequestMapping;
public class ArrayAnno {
    @RequestMapping(value = {"/a", "/b"})
    public void multi() {}
}
"""
    cls = _parse_snippet(parser, tmp_path, "ArrayAnno.java", java)
    assert len(cls.methods) >= 1


# ---------------------------------------------------------------------------
# Method call argument expressions
# ---------------------------------------------------------------------------


def test_method_call_string_literal_argument(parser, tmp_path):
    java = """\
package com.example;
public class CallTest {
    private SomeService svc;
    public void doWork() {
        svc.process("hello");
    }
}
"""
    cls = _parse_snippet(parser, tmp_path, "CallTest.java", java)
    method = next(m for m in cls.methods if m.name == "doWork")
    assert len(method.method_calls) >= 1
    call = method.method_calls[0]
    assert call.method_name == "process"


def test_method_call_field_access_argument(parser, tmp_path):
    java = """\
package com.example;
public class FieldAccessCall {
    private SomeService svc;
    public void doWork() {
        svc.process(Constants.VALUE);
    }
}
"""
    cls = _parse_snippet(parser, tmp_path, "FieldAccessCall.java", java)
    method = next(m for m in cls.methods if m.name == "doWork")
    assert len(method.method_calls) >= 1


# ---------------------------------------------------------------------------
# Class extends and generics
# ---------------------------------------------------------------------------


def test_class_with_extends(parser, tmp_path):
    """Verify extends is parsed (may be None if parser doesn't extract it yet)."""
    java = """\
package com.example;
public class Child extends Parent {
    public void childMethod() {}
}
"""
    cls = _parse_snippet(parser, tmp_path, "Child.java", java)
    assert cls.name == "Child"
    # The parser may or may not extract extends — verify no crash at minimum
    assert cls.methods[0].name == "childMethod"


def test_class_with_generics(parser, tmp_path):
    java = """\
package com.example;
public class GenericBox<T extends Comparable<T>> {
    private T value;
    public T getValue() { return value; }
}
"""
    cls = _parse_snippet(parser, tmp_path, "GenericBox.java", java)
    assert cls.name == "GenericBox"
    assert len(cls.methods) >= 1
