"""
Unit tests for interface autowire disambiguation.

Strategy: Unit tests with hand-created JavaClass objects and mocked dependencies.
Real: Autowire resolution logic for interface implementations
Mocked: Analyzer and TypeResolver

Test Responsibilities:
- Single function tests: Interface implementation disambiguation with multiple candidates
"""

import pytest

from app.src.codeanalyzer.autowire_resolver import (
    AmbiguousBeanReferenceError,
    AutowireResolver,
)
from app.src.codeanalyzer.models import ClassReferenceMemberVariable, JavaClass


def test_autowire_interface_implementation_disambiguation():
    # Setup analyzer with interface and two implementations
    analyzer = type("FakeAnalyzer", (), {})()
    interface = JavaClass(name="MyInterface", package="com.example")
    impl1 = JavaClass(name="MyInterfaceImpl1", package="com.example", implements=["MyInterface"])
    impl2 = JavaClass(name="MyInterfaceImpl2", package="com.example", implements=["MyInterface"])
    analyzer.classes = {
        interface.fully_qualified_name: interface,
        impl1.fully_qualified_name: impl1,
        impl2.fully_qualified_name: impl2,
    }
    # Create autowired member of interface type
    member = ClassReferenceMemberVariable(name="svc", type="MyInterface", is_autowired=True)
    member.unresolved_autowire = type(
        "UA",
        (),
        {"raw_value": "MyInterface", "mark_fully_resolved": lambda *a, **k: None},
    )()
    # Patch type_resolver to return the interface class
    analyzer.type_resolver = type("TR", (), {"resolve_type": lambda self, t, c: interface})()
    resolver = AutowireResolver(analyzer)
    # Expect ambiguity error
    with pytest.raises(AmbiguousBeanReferenceError):
        resolver._resolve_autowired_dependency(member, interface)
