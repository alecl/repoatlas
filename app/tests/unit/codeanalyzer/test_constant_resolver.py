"""
Unit tests for ConstantResolver functionality.

Strategy: Unit tests with hand-created JavaClass objects and mocked analyzer.
Real: Constant resolution algorithms, chaining logic, global constant handling
Mocked: Analyzer (with controlled classes and global_constants dictionaries)

Test Responsibilities:
- Single function tests: Simple, cross-class, chained, and global constant resolution
- Additional tests from analyzer split: resolve_all, annotations, class references
"""

from app.src.codeanalyzer.constant_resolver import ConstantResolver
from app.src.codeanalyzer.models import (
    Annotation,
    ElementType,
    JavaClass,
    ReferenceLocation,
    UnresolvedConstant,
)


def test_constant_resolver_resolves_simple_constant():
    analyzer = type("FakeAnalyzer", (), {"classes": {}})()
    java_class = JavaClass(
        name="TestClass",
        package="com.example.test",
        constants={"BASE_PATH": "/api/v1"},
    )
    analyzer.classes = {"com.example.test.TestClass": java_class}
    resolver = ConstantResolver(analyzer)
    unresolved = UnresolvedConstant(
        raw_value="BASE_PATH",
        location=ReferenceLocation(
            class_name="TestClass",
            element_type=ElementType.CLASS_ANNOTATION,
            element_name="RequestMapping",
        ),
    )
    value = resolver._resolve_constant_chain(unresolved, java_class)
    assert value == "/api/v1"


def test_constant_resolver_resolves_cross_class_constant():
    analyzer = type("FakeAnalyzer", (), {"classes": {}})()
    classA = JavaClass(
        name="Constants",
        package="com.example.test",
        constants={"BASE_PATH": "/api/v1"},
    )
    classB = JavaClass(
        name="UserConstants",
        package="com.example.test",
        constants={"USER_PATH": "Constants.BASE_PATH"},
    )
    analyzer.classes = {
        "com.example.test.Constants": classA,
        "com.example.test.UserConstants": classB,
    }
    resolver = ConstantResolver(analyzer)
    unresolved = UnresolvedConstant(
        raw_value="UserConstants.USER_PATH",
        location=ReferenceLocation(
            class_name="TestClass",
            element_type=ElementType.CLASS_ANNOTATION,
            element_name="RequestMapping",
        ),
    )
    value = resolver._resolve_constant_chain(unresolved, classB)
    assert value == "/api/v1"


def test_constant_resolver_resolves_chain():
    analyzer = type("FakeAnalyzer", (), {"classes": {}})()
    classA = JavaClass(
        name="Constants",
        package="com.example.test",
        constants={"BASE_PATH": "/api/v1"},
    )
    classB = JavaClass(
        name="UserConstants",
        package="com.example.test",
        constants={"USER_PATH": "Constants.BASE_PATH"},
    )
    classC = JavaClass(
        name="ApiConstants",
        package="com.example.test",
        constants={"API_PATH": "UserConstants.USER_PATH"},
    )
    analyzer.classes = {
        "com.example.test.Constants": classA,
        "com.example.test.UserConstants": classB,
        "com.example.test.ApiConstants": classC,
    }
    resolver = ConstantResolver(analyzer)
    unresolved = UnresolvedConstant(
        raw_value="ApiConstants.API_PATH",
        location=ReferenceLocation(
            class_name="TestClass",
            element_type=ElementType.CLASS_ANNOTATION,
            element_name="RequestMapping",
        ),
    )
    value = resolver._resolve_constant_chain(unresolved, classC)
    assert value == "/api/v1"


def test_constant_resolver_resolves_global_constant():
    analyzer = type("FakeAnalyzer", (), {"classes": {}, "global_constants": {}})()
    analyzer.global_constants = {
        "GLOBAL_CONST": "global-value",
        "OtherClass.VALUE": "other-value",
    }
    java_class = JavaClass(
        name="TestClass",
        package="com.example.test",
        constants={},
    )
    analyzer.classes = {"com.example.test.TestClass": java_class}
    resolver = ConstantResolver(analyzer)
    unresolved = UnresolvedConstant(
        raw_value="GLOBAL_CONST",
        location=ReferenceLocation(
            class_name="TestClass",
            element_type=ElementType.CLASS_ANNOTATION,
            element_name="RequestMapping",
        ),
    )
    value = resolver._resolve_constant_chain(unresolved, java_class)
    assert value == "global-value"

    unresolved2 = UnresolvedConstant(
        raw_value="OtherClass.VALUE",
        location=ReferenceLocation(
            class_name="TestClass",
            element_type=ElementType.CLASS_ANNOTATION,
            element_name="RequestMapping",
        ),
    )
    value2 = resolver._resolve_constant_chain(unresolved2, java_class)
    assert value2 == "other-value"


def test_constant_resolver_resolves_class_and_global_constants():
    analyzer = type("FakeAnalyzer", (), {"classes": {}, "global_constants": {}})()
    # Class constant
    classA = JavaClass(
        name="Constants",
        package="com.example.test",
        constants={"BASE_PATH": "/api/v1"},
    )
    # Global constant
    analyzer.global_constants = {
        "Constants.BASE_PATH": "/api/v1",
        "GLOBAL_CONST": "global-value",
    }
    analyzer.classes = {
        "com.example.test.Constants": classA,
    }
    resolver = ConstantResolver(analyzer)
    # Should resolve from class constant
    unresolved = UnresolvedConstant(
        raw_value="BASE_PATH",
        location=ReferenceLocation(
            class_name="Constants",
            element_type=ElementType.CLASS_ANNOTATION,
            element_name="RequestMapping",
        ),
    )
    value = resolver._resolve_constant_chain(unresolved, classA)
    assert value == "/api/v1"

    # Should resolve from global constant if not found in class
    unresolved2 = UnresolvedConstant(
        raw_value="GLOBAL_CONST",
        location=ReferenceLocation(
            class_name="Constants",
            element_type=ElementType.CLASS_ANNOTATION,
            element_name="RequestMapping",
        ),
    )
    value2 = resolver._resolve_constant_chain(unresolved2, classA)
    assert value2 == "global-value"


# Tests moved from test_analyzer.py
def test_constant_resolver_resolve_all_and_class_constants():
    """Test constant resolver resolve_all and class constants"""
    from app.src.codeanalyzer.models import (
        Annotation,
        ElementType,
        JavaClass,
        ReferenceLocation,
        UnresolvedConstant,
    )

    # Mock analyzer
    analyzer = type("FakeAnalyzer", (), {"classes": {}})()

    # Add a class with an unresolved constant
    test_class = JavaClass(
        name="C",
        package="com.example",
        class_annotations=[
            Annotation(
                name="Anno",
                unresolved_values={
                    "foo": UnresolvedConstant(
                        raw_value="SOME_CONST",
                        location=ReferenceLocation(
                            class_name="C",
                            element_type=ElementType.CLASS_ANNOTATION,
                            element_name="Anno",
                        ),
                    )
                },
            )
        ],
        constants={"SOME_CONST": "resolved"},
    )
    analyzer.classes = {test_class.fully_qualified_name: test_class}
    resolver = ConstantResolver(analyzer)
    changed = resolver.resolve_all()
    assert changed is True
    # Should now be resolved
    anno = test_class.class_annotations[0]
    assert "foo" in anno.values
    assert anno.values["foo"] == "resolved"


def test_constant_resolver_get_all_annotations():
    """Test constant resolver _get_all_annotations method"""
    test_class = JavaClass(
        name="C",
        package="com.example",
        class_annotations=[Annotation(name="A")],
        member_variables=[],
        methods=[],
    )
    analyzer = type("FakeAnalyzer", (), {"classes": {}})()
    analyzer.classes = {test_class.fully_qualified_name: test_class}
    resolver = ConstantResolver(analyzer)
    annos = list(resolver._get_all_annotations(test_class))
    assert any(a.name == "A" for a in annos)


def test_constant_resolver_resolve_class_reference():
    """Test constant resolver _resolve_class_reference method"""
    resolver = ConstantResolver(analyzer=type("Fake", (), {})())
    classA = JavaClass(name="A", package="com.example")
    analyzer = type("FakeAnalyzer", (), {"classes": {}})()
    analyzer.classes = {classA.fully_qualified_name: classA}
    resolver.analyzer = analyzer
    found = resolver._resolve_class_reference("A", classA)
    assert found == classA
    found2 = resolver._resolve_class_reference("com.example.A", classA)
    assert found2 == classA


def test_constant_resolver_looks_like_constant_reference():
    """Test constant resolver _looks_like_constant_reference method"""
    resolver = ConstantResolver(analyzer=type("Fake", (), {})())
    assert resolver._looks_like_constant_reference("A.B")
    assert not resolver._looks_like_constant_reference("/foo")
    assert not resolver._looks_like_constant_reference("true")
    assert not resolver._looks_like_constant_reference(123)
