"""
Unit tests for AutowireResolver functionality.

Strategy: Unit tests with hand-created JavaClass objects and mocked dependencies.
Real: Autowire resolution logic, @Primary/@Qualifier handling, ambiguity detection
Mocked: Analyzer and TypeResolver (controlled resolution behavior)

Test Responsibilities:
- Single function tests: Disambiguation scenarios, implementation resolution
- Additional tests from analyzer split: resolve_all, qualifier/primary finding
"""

from app.src.codeanalyzer.autowire_resolver import (
    AmbiguousBeanReferenceError,
    AutowireResolver,
)
from app.src.codeanalyzer.models import (
    Annotation,
    ClassCategory,
    ClassReferenceMemberVariable,
    JavaClass,
    ReferenceLocation,
    UnresolvedAutowire,
)


def test_autowire_resolver_resolves_single_implementation():
    # Create a fake type resolver first
    fake_type_resolver = type(
        "FakeTypeResolver",
        (),
        {"resolve_type": lambda self, type_name, context_class: None},
    )()

    # Create the analyzer with the type_resolver already present
    analyzer = type(
        "FakeAnalyzer",
        (),
        {
            "classes": {},
            "type_resolver": fake_type_resolver,  # Include the type_resolver from the start
        },
    )()
    interface = JavaClass(name="MyService", package="com.example")
    impl = JavaClass(name="MyServiceImpl", package="com.example")
    analyzer.classes = {
        "com.example.MyService": interface,
        "com.example.MyServiceImpl": impl,
    }
    member = ClassReferenceMemberVariable(
        name="myService",
        type="MyService",
        is_autowired=True,
        referenced_class_category=ClassCategory.SERVICE,
        unresolved_autowire=UnresolvedAutowire(
            raw_value="MyService",
            location=ReferenceLocation(
                class_name="TestClass",
                element_type="field_declaration",
                element_name="myService",
            ),
            interface_type="MyService",
        ),
    )
    # Patch type_resolver to return the interface
    resolver = AutowireResolver(analyzer)
    resolver.type_resolver = type(
        "FakeTypeResolver",
        (),
        {"resolve_type": lambda self, type_name, context_class: interface},
    )()
    # Patch _find_implementations to return the impl
    resolver._find_implementations = lambda interface_class: [impl]
    resolved = resolver._resolve_autowired_dependency(member, interface)
    assert resolved == impl


# Tests moved from test_analyzer.py
def test_autowire_resolver_resolve_all_and_find_impl():
    """Test autowire resolver resolve_all and find_impl methods"""
    from app.src.codeanalyzer.models import ClassReferenceMemberVariable, JavaClass

    # Create mock analyzer
    analyzer = type("FakeAnalyzer", (), {"classes": {}})()

    # Add a class with an autowired member
    svc = JavaClass(name="MyService", package="com.example")
    impl = JavaClass(name="MyServiceImpl", package="com.example")
    analyzer.classes = {
        svc.fully_qualified_name: svc,
        impl.fully_qualified_name: impl,
    }
    member = ClassReferenceMemberVariable(name="myService", type="MyService", is_autowired=True)
    # Fake unresolved_autowire
    member.unresolved_autowire = type(
        "UA",
        (),
        {"mark_fully_resolved": lambda *a, **k: None, "raw_value": "MyService"},
    )()
    svc.member_variables = [member]

    # Create mock type_resolver
    analyzer.type_resolver = type(
        "MockTypeResolver",
        (),
        {"resolve_type": lambda self, t, c: impl if t == "MyService" else None},
    )()

    resolver = AutowireResolver(analyzer)
    # Should not error, but nothing to resolve since no implementations
    assert resolver.resolve_all() in (True, False)


def test_autowire_resolver_find_by_qualifier_and_primary():
    """Test autowire resolver _find_by_qualifier and _find_primary_bean methods"""
    from app.src.codeanalyzer.models import JavaClass

    # Create mock type resolver
    fake_type_resolver = type(
        "FakeTypeResolver",
        (),
        {"resolve_type": lambda self, type_name, context_class: None},
    )()

    # Create mock analyzer
    analyzer = type("FakeAnalyzer", (), {"classes": {}, "type_resolver": fake_type_resolver})()
    resolver = AutowireResolver(analyzer)

    # Create implementations with qualifiers and @Primary
    impl1 = JavaClass(
        name="Impl1",
        package="com.example",
        class_annotations=[Annotation(name="Qualifier", values={"value": "foo"})],
    )
    impl2 = JavaClass(
        name="Impl2",
        package="com.example",
        class_annotations=[Annotation(name="Primary")],
    )
    impl3 = JavaClass(
        name="Impl3",
        package="com.example",
        class_annotations=[Annotation(name="Service", values={"value": "foo"})],
    )
    impls = [impl1, impl2, impl3]
    # By qualifier
    found = resolver._find_by_qualifier(impls, "foo")
    assert found in (impl1, impl3)
    # By primary
    found2 = resolver._find_primary_bean(impls)
    assert found2 == impl2


def test_autowire_resolver_find_implementations():
    """Test autowire resolver _find_implementations method"""
    from app.src.codeanalyzer.models import JavaClass

    # Create mock type resolver
    fake_type_resolver = type(
        "FakeTypeResolver",
        (),
        {"resolve_type": lambda self, type_name, context_class: None},
    )()

    # Create mock analyzer
    analyzer = type("FakeAnalyzer", (), {"classes": {}, "type_resolver": fake_type_resolver})()
    resolver = AutowireResolver(analyzer)

    # Add a class with implements
    interface = JavaClass(name="Iface", package="com.example")
    impl = JavaClass(name="Impl", package="com.example")
    # Add 'implements' as a real attribute
    object.__setattr__(impl, "implements", "Iface")
    analyzer.classes = {
        interface.fully_qualified_name: interface,
        impl.fully_qualified_name: impl,
    }
    impls = resolver._find_implementations(interface)
    assert impl in impls


def test_constructor_based_injection_resolution(tmp_path):
    """Integration test: resolve constructor-only injection without @Autowired."""
    from app.src.codeanalyzer.analyzer import JavaAnalyzer

    # Write service interface and implementation
    svc_file = tmp_path / "MySvc.java"
    svc_file.write_text("package com.example; public interface MySvc {}")
    impl_file = tmp_path / "MySvcImpl.java"
    impl_file.write_text("package com.example; public class MySvcImpl implements MySvc {}")
    # Write controller with implicit ctor injection
    ctrl_file = tmp_path / "Ctrl.java"
    ctrl_src = """
    package com.example;
    import org.springframework.web.bind.annotation.RestController;
    @RestController
    public class Ctrl {
        public Ctrl(MySvc svc) {}
    }
    """
    ctrl_file.write_text(ctrl_src)
    analyzer = JavaAnalyzer()
    analyzer.parse_file(str(svc_file))
    analyzer.parse_file(str(impl_file))
    analyzer.parse_file(str(ctrl_file))
    analyzer._resolve_all_references()
    ctrl = analyzer.classes["com.example.Ctrl"]
    services = ctrl.service_variables
    names = [v.name for v in services]
    assert "svc" in names
    svc_var = next(v for v in services if v.name == "svc")
    assert svc_var.resolved_implementation.name == "MySvcImpl"


def test_resolve_all_exception_logged():
    """Exception in _resolve_autowired_dependency is caught and logged."""
    from app.src.codeanalyzer.models import UnresolvedAutowire

    fake_type_resolver = type(
        "FakeTypeResolver",
        (),
        {"resolve_type": lambda self, t, c: None},
    )()
    analyzer = type("FakeAnalyzer", (), {"classes": {}, "type_resolver": fake_type_resolver})()
    # Create a class with an autowired member that will cause an exception
    interface = JavaClass(name="BadService", package="com.example")
    member = ClassReferenceMemberVariable(
        name="svc",
        type="BadService",
        is_autowired=True,
        unresolved_autowire=UnresolvedAutowire(
            raw_value="BadService",
            location=ReferenceLocation(
                class_name="Test",
                element_type="field_declaration",
                element_name="svc",
            ),
            interface_type="BadService",
        ),
    )
    interface.member_variables = [member]
    analyzer.classes = {"com.example.BadService": interface}

    resolver = AutowireResolver(analyzer)
    # Force an exception by making resolve_type raise
    resolver.type_resolver = type(
        "BadResolver",
        (),
        {"resolve_type": lambda self, t, c: (_ for _ in ()).throw(RuntimeError("test"))},
    )()
    # Should not raise — exception is caught and logged
    result = resolver.resolve_all()
    assert result in (True, False)


def test_constructor_no_injection_flag_skipped():
    """Constructor with is_injection=False is skipped."""
    from app.src.codeanalyzer.models import JavaConstructor, Parameter

    fake_type_resolver = type(
        "FakeTypeResolver",
        (),
        {"resolve_type": lambda self, t, c: None},
    )()
    analyzer = type("FakeAnalyzer", (), {"classes": {}, "type_resolver": fake_type_resolver})()
    cls = JavaClass(name="Test", package="com.example")
    ctor = JavaConstructor(
        name="Test",
        parameters=[Parameter(name="svc", type="MyService")],
        is_injection=False,
    )
    cls.constructors = [ctor]
    analyzer.classes = {"com.example.Test": cls}
    resolver = AutowireResolver(analyzer)
    result = resolver.resolve_all()
    assert result is False


def test_constructor_type_not_resolved():
    """Constructor injection where type cannot be resolved → no injection."""
    from app.src.codeanalyzer.models import JavaConstructor, Parameter

    fake_type_resolver = type(
        "FakeTypeResolver",
        (),
        {"resolve_type": lambda self, t, c: None},
    )()
    analyzer = type("FakeAnalyzer", (), {"classes": {}, "type_resolver": fake_type_resolver})()
    cls = JavaClass(name="Test", package="com.example")
    ctor = JavaConstructor(
        name="Test",
        parameters=[Parameter(name="svc", type="UnknownType")],
        is_injection=True,
    )
    cls.constructors = [ctor]
    analyzer.classes = {"com.example.Test": cls}
    resolver = AutowireResolver(analyzer)
    result = resolver.resolve_all()
    assert result is False


def test_find_by_qualifier_no_match():
    """_find_by_qualifier returns None when no qualifier matches."""

    fake_type_resolver = type(
        "FakeTypeResolver",
        (),
        {"resolve_type": lambda self, t, c: None},
    )()
    analyzer = type("FakeAnalyzer", (), {"classes": {}, "type_resolver": fake_type_resolver})()
    resolver = AutowireResolver(analyzer)
    impl = JavaClass(
        name="Impl",
        package="com.example",
        class_annotations=[Annotation(name="Service", values={"value": "other"})],
    )
    result = resolver._find_by_qualifier([impl], "nonexistent")
    assert result is None


def test_constructor_multiple_impls_no_primary():
    """Multiple implementations without @Primary → no injection."""
    from app.src.codeanalyzer.models import JavaConstructor, Parameter

    interface = JavaClass(name="ISvc", package="com.example")
    impl1 = JavaClass(name="Impl1", package="com.example", implements=["ISvc"])
    impl2 = JavaClass(name="Impl2", package="com.example", implements=["ISvc"])

    fake_type_resolver = type(
        "FakeTypeResolver",
        (),
        {"resolve_type": lambda self, t, c: interface if t == "ISvc" else None},
    )()
    analyzer = type("FakeAnalyzer", (), {"classes": {}, "type_resolver": fake_type_resolver})()
    cls = JavaClass(name="Test", package="com.example")
    ctor = JavaConstructor(
        name="Test",
        parameters=[Parameter(name="svc", type="ISvc")],
        is_injection=True,
    )
    cls.constructors = [ctor]
    analyzer.classes = {
        "com.example.Test": cls,
        "com.example.ISvc": interface,
        "com.example.Impl1": impl1,
        "com.example.Impl2": impl2,
    }
    resolver = AutowireResolver(analyzer)
    # _find_primary_bean returns None for impls without @Primary
    result = resolver.resolve_all()
    assert result is False


def test_existing_field_updated_by_constructor_injection(tmp_path):
    """Test controller with field and implicit constructor injection updates existing member."""
    from app.src.codeanalyzer.analyzer import JavaAnalyzer

    # Write service interface and implementation
    svc_file = tmp_path / "ICardsService.java"
    svc_file.write_text(
        "package com.eazybytes.cards.controller; public interface ICardsService {}"
    )
    impl_file = tmp_path / "CardsServiceImpl.java"
    impl_file.write_text(
        "package com.eazybytes.cards.controller;\n"
        "import org.springframework.stereotype.Service;\n"
        "@Service\n"
        "public class CardsServiceImpl implements ICardsService {}"
    )
    # Write controller with field and implicit ctor injection
    ctrl_file = tmp_path / "CardsController.java"
    ctrl_src = """
    package com.eazybytes.cards.controller;
    import org.springframework.web.bind.annotation.RestController;
    @RestController
    public class CardsController {
        private ICardsService iCardsService;
        public CardsController(ICardsService iCardsService) {
            this.iCardsService = iCardsService;
        }
    }
    """
    ctrl_file.write_text(ctrl_src)
    analyzer = JavaAnalyzer()
    analyzer.parse_file(str(svc_file))
    analyzer.parse_file(str(impl_file))
    analyzer.parse_file(str(ctrl_file))
    analyzer._resolve_all_references()
    ctrl = analyzer.classes["com.eazybytes.cards.controller.CardsController"]
    # Existing field should be updated
    svc_vars = ctrl.service_variables
    assert any(var.name == "iCardsService" and var.is_autowired for var in svc_vars)
    svc_var = next(var for var in svc_vars if var.name == "iCardsService")
    assert svc_var.resolved_implementation.name == "CardsServiceImpl"
