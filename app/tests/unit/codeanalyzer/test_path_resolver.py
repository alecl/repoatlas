"""
Unit tests for PathResolver functionality.

Strategy: Unit tests with hand-created controller objects and mocked dependencies.
Real: Path composition algorithms, constant placeholder resolution
Mocked: Analyzer and ConstantResolver (controlled path resolution)

Test Responsibilities:
- Single function tests: Constant path resolution in REST endpoint mappings
"""

from app.src.codeanalyzer.models import JavaClass, RestControllerClass, RestEndpoint
from app.src.codeanalyzer.path_resolver import PathResolver


def test_path_resolver_resolves_constant_paths():
    analyzer = type("FakeAnalyzer", (), {"classes": {}})()
    controller = RestControllerClass(
        name="TestController",
        package="com.example.web",
        class_annotations=[],
        member_variables=[],
        methods=[
            RestEndpoint(
                name="getTest",
                return_type="String",
                path_mappings={"GET": "Constants.BASE_PATH"},
            )
        ],
    )
    analyzer.classes = {"com.example.web.TestController": controller}
    resolver = PathResolver(analyzer)
    # Patch constant_resolver to always resolve to "/api/v1"
    resolver.constant_resolver = type(
        "FakeConstantResolver",
        (),
        {"_resolve_constant_chain": lambda self, unresolved, context_class: "/api/v1"},
    )()
    changed = resolver.resolve_all()
    assert changed
    assert controller.methods[0].path_mappings["GET"] == "/api/v1"
