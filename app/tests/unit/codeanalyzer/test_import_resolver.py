"""
Unit tests for ImportResolver functionality.

Strategy: Unit tests with hand-created JavaClass/ImportDefinition objects and mocked analyzer.
Real: Import matching algorithms, scope determination, caching logic
Mocked: Analyzer (with controlled classes dictionary)

Test Responsibilities:
- Single function tests: Basic resolution, JDK scope detection, statistics tracking
- Additional tests from analyzer split: Cache behavior, type matching, location determination
"""

from app.src.codeanalyzer.import_resolver import ImportResolver
from app.src.codeanalyzer.models import (
    ImportDefinition,
    JavaClass,
    ReferenceScope,
    ResolvedLocation,
)


def make_java_class(name, package, imports=None):
    return JavaClass(
        name=name,
        package=package,
        imports=imports or [],
    )


def test_import_resolver_basic_resolution():
    analyzer = type("FakeAnalyzer", (), {"classes": {}})()
    classA = make_java_class("ClassA", "com.example.a")
    classB = make_java_class("ClassB", "com.example.b")
    analyzer.classes = {
        "com.example.a.ClassA": classA,
        "com.example.b.ClassB": classB,
    }
    import_def = ImportDefinition(fully_qualified_name="com.example.b.ClassB")
    classA.imports = [import_def]
    resolver = ImportResolver(analyzer)
    location = resolver.resolve_import_for_type("ClassB", classA)
    assert isinstance(location, ResolvedLocation)
    assert location.class_name == "ClassB"
    assert location.package_name == "com.example.b"
    assert location.scope == ReferenceScope.SAME_REPO_DIFFERENT_JAR


def test_import_resolver_jdk_scope():
    analyzer = type("FakeAnalyzer", (), {"classes": {}})()
    classA = make_java_class("ClassA", "com.example.a")
    import_def = ImportDefinition(fully_qualified_name="java.util.List")
    classA.imports = [import_def]
    resolver = ImportResolver(analyzer)
    location = resolver.resolve_import_for_type("List", classA)
    assert location.scope == ReferenceScope.JDK


def test_import_resolver_statistics():
    analyzer = type("FakeAnalyzer", (), {"classes": {}})()
    classA = make_java_class("ClassA", "com.example.a")
    import_def = ImportDefinition(fully_qualified_name="java.util.List")
    classA.imports = [import_def]
    resolver = ImportResolver(analyzer)
    resolver.resolve_import_for_type("List", classA)
    stats = resolver.get_import_statistics()
    assert stats["total_imports"] == 1
    assert stats["used_imports"] == 1
    assert stats["unused_imports"] == 0


# Tests moved from test_analyzer.py
def test_import_resolver_resolve_import_for_type_and_cache():
    """Test import resolver resolve_import_for_type and cache"""
    from app.src.codeanalyzer.models import (
        ImportDefinition,
        JavaClass,
        ReferenceScope,
    )

    # Create mock analyzer
    analyzer = type("FakeAnalyzer", (), {"classes": {}})()

    # Add a class with imports
    test_class = JavaClass(
        name="Test",
        package="com.example",
        imports=[
            ImportDefinition(fully_qualified_name="java.util.List"),
            ImportDefinition(fully_qualified_name="com.example.service.UserService"),
            ImportDefinition(fully_qualified_name="com.example.service.*", is_wildcard=True),
        ],
    )
    analyzer.classes = {test_class.fully_qualified_name: test_class}
    resolver = ImportResolver(analyzer)
    # Should resolve java.util.List as JDK
    loc = resolver.resolve_import_for_type("List", test_class)
    assert loc.scope == ReferenceScope.JDK
    # Should resolve UserService as SAME_JAR (since not in analyzer, will be THIRD_PARTY)
    loc2 = resolver.resolve_import_for_type("UserService", test_class)
    assert loc2.scope in (ReferenceScope.SAME_JAR, ReferenceScope.THIRD_PARTY)
    # Should resolve wildcard import
    loc3 = resolver.resolve_import_for_type("ProductService", test_class)
    assert loc3.scope in (ReferenceScope.SAME_JAR, ReferenceScope.THIRD_PARTY)
    # Should use cache
    assert "java.util.List" in resolver._import_cache


def test_import_resolver_used_imports_and_stats():
    """Test import resolver used imports and stats"""
    from app.src.codeanalyzer.models import ImportDefinition

    analyzer = type("FakeAnalyzer", (), {"classes": {}})()
    test_class = JavaClass(
        name="Test",
        package="com.example",
        imports=[
            ImportDefinition(fully_qualified_name="java.util.List"),
            ImportDefinition(fully_qualified_name="com.example.service.UserService"),
        ],
    )
    analyzer.classes = {test_class.fully_qualified_name: test_class}
    resolver = ImportResolver(analyzer)
    resolver.resolve_import_for_type("List", test_class)
    resolver.resolve_import_for_type("UserService", test_class)
    stats = resolver.get_import_statistics()
    assert stats["total_imports"] == 2
    assert stats["used_imports"] == 2
    assert stats["unused_imports"] == 0


def test_import_resolver_import_matches_type():
    """Test import resolver _import_matches_type method"""
    from app.src.codeanalyzer.models import ImportDefinition

    analyzer = type("FakeAnalyzer", (), {"classes": {}})()
    resolver = ImportResolver(analyzer)
    imp = ImportDefinition(fully_qualified_name="com.example.Foo")
    assert resolver._import_matches_type(imp, "Foo")
    wildcard = ImportDefinition(fully_qualified_name="com.example.*", is_wildcard=True)
    assert resolver._import_matches_type(wildcard, "Bar")


def test_import_resolver_determine_scope_from_path():
    """Test import resolver _determine_scope_from_path method"""
    from app.src.codeanalyzer.models import JavaClass, ReferenceScope

    analyzer = type("FakeAnalyzer", (), {"classes": {}})()
    resolver = ImportResolver(analyzer)
    classA = JavaClass(name="A", package="com.example")
    classB = JavaClass(name="B", package="com.example")
    classC = JavaClass(name="C", package="com.other")
    assert resolver._determine_scope_from_path(classA, classB) == ReferenceScope.SAME_JAR
    assert (
        resolver._determine_scope_from_path(classA, classC)
        == ReferenceScope.SAME_REPO_DIFFERENT_JAR
    )


def test_import_resolver_determine_import_location():
    """Test import resolver _determine_import_location method"""
    from app.src.codeanalyzer.models import (
        ImportDefinition,
        JavaClass,
        ReferenceScope,
    )

    # Create mock analyzer
    analyzer = type("FakeAnalyzer", (), {"classes": {}})()
    resolver = ImportResolver(analyzer)
    # Add a class to analyzer
    classA = JavaClass(name="A", package="com.example")
    analyzer.classes = {classA.fully_qualified_name: classA}
    # Should resolve to SAME_JAR
    loc = resolver._determine_import_location(classA.fully_qualified_name, classA)
    assert loc.scope == ReferenceScope.SAME_JAR
    # Should resolve to JDK
    loc2 = resolver._determine_import_location("java.util.List", classA)
    assert loc2.scope == ReferenceScope.JDK
    # Should resolve to THIRD_PARTY if not found
    loc3 = resolver._determine_import_location("com.unknown.Foo", classA)
    assert loc3.scope == ReferenceScope.THIRD_PARTY


def test_import_resolver_resolve_used_imports():
    """Test import resolver resolve_used_imports method"""
    analyzer = type("FakeAnalyzer", (), {"classes": {}})()
    resolver = ImportResolver(analyzer)
    # Should just return False
    assert resolver.resolve_used_imports() is False
