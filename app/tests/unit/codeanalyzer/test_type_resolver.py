"""
Unit tests for TypeResolver functionality.

Strategy: Unit tests with hand-created JavaClass/ImportDefinition objects and mocked analyzer.
Real: Type resolution algorithms, import matching, wildcard imports
Mocked: Analyzer (with controlled classes dictionary)

Test Responsibilities:
- Single function tests: Import resolution, wildcard imports, same-package resolution,
  resolved class population
"""

from app.src.codeanalyzer.models import (
    ClassReferenceMemberVariable,
    ElementType,
    ImportDefinition,
    JavaClass,
    ReferenceLocation,
    UnresolvedType,
)
from app.src.codeanalyzer.type_resolver import TypeResolver


def test_type_resolver_resolves_imported_type():
    analyzer = type("FakeAnalyzer", (), {"classes": {}})()
    imported = JavaClass(name="UserService", package="com.example.service")
    analyzer.classes = {"com.example.service.UserService": imported}
    test_class = JavaClass(
        name="TestClass",
        package="com.example.test",
        imports=[ImportDefinition(fully_qualified_name="com.example.service.UserService")],
    )
    resolver = TypeResolver(analyzer)
    result = resolver.resolve_type("UserService", test_class)
    assert result == imported


def test_type_resolver_populates_resolved_class():
    # Setup a fake analyzer with two classes
    analyzer = type("FakeAnalyzer", (), {})()
    svc = JavaClass(name="Svc", package="com.example")
    impl = JavaClass(name="Impl", package="com.example")
    analyzer.classes = {
        svc.fully_qualified_name: svc,
        impl.fully_qualified_name: impl,
    }

    # Create a member variable with an unresolved type
    var = ClassReferenceMemberVariable(
        name="svcVar",
        type="Impl",
        unresolved_type=UnresolvedType(
            raw_value="Impl",
            location=ReferenceLocation(
                class_name="Svc",
                element_type=ElementType.FIELD_DECLARATION,
                element_name="svcVar",
            ),
            is_interface=False,
            is_generic=False,
        ),
    )
    svc.member_variables = [var]

    # Resolve types
    resolver = TypeResolver(analyzer)
    changed = resolver.resolve_all()

    assert changed is True
    assert var.resolved_class is impl


def test_type_resolver_resolves_wildcard_import():
    analyzer = type("FakeAnalyzer", (), {"classes": {}})()
    imported = JavaClass(name="UserService", package="com.example.service")
    analyzer.classes = {"com.example.service.UserService": imported}
    test_class = JavaClass(
        name="TestClass",
        package="com.example.test",
        imports=[ImportDefinition(fully_qualified_name="com.example.service", is_wildcard=True)],
    )
    resolver = TypeResolver(analyzer)
    result = resolver.resolve_type("UserService", test_class)
    assert result == imported


def test_type_resolver_resolves_same_package():
    analyzer = type("FakeAnalyzer", (), {"classes": {}})()
    imported = JavaClass(name="UserService", package="com.example.test")
    analyzer.classes = {"com.example.test.UserService": imported}
    test_class = JavaClass(
        name="TestClass",
        package="com.example.test",
        imports=[],
    )
    resolver = TypeResolver(analyzer)
    result = resolver.resolve_type("UserService", test_class)
    assert result == imported
