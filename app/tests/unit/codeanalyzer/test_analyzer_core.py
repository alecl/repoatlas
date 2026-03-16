"""
Unit tests for core JavaAnalyzer functionality.

Strategy: Unit tests with hand-created model objects and mocked dependencies.
Real: Core analyzer algorithms (search, getters, basic operations)
Mocked: Resolution pipeline (_resolve_all_references), file operations

Test Responsibilities:
- TestJavaAnalyzerBasics: Initialization, pipeline triggering, empty state handling
- TestJavaAnalyzerSearch: Class search by name, path, package
- TestJavaAnalyzerGetters: Controllers, services, endpoints, dependencies retrieval
- TestJavaAnalyzerConstants: Constant handling and resolution integration
"""

from unittest.mock import MagicMock, patch

import pytest

from app.src.codeanalyzer.analyzer import JavaAnalyzer
from app.src.codeanalyzer.models import (
    Annotation,
    ClassCategory,
    ElementType,
    JavaClass,
    ReferenceLocation,
    RestControllerClass,
    ServiceClass,
    UnresolvedConstant,
)
from app.src.codeanalyzer.parser import JavaParser


class TestJavaAnalyzerBasics:
    """Test basic functionality of the JavaAnalyzer class - unit tests"""

    def test_initialization(self):
        """Test the initialization of JavaAnalyzer"""
        analyzer = JavaAnalyzer()
        assert analyzer.classes == {}
        assert analyzer.global_constants == {}

    def test_report_unresolved_references(self, sample_analyzer):
        """Test report_unresolved_references returns expected structure"""
        # Add a class with an unresolved annotation
        test_class = JavaClass(
            name="UnresolvedClass",
            package="com.example.unresolved",
            class_annotations=[
                Annotation(
                    name="TestAnno",
                    unresolved_values={
                        "foo": UnresolvedConstant(
                            raw_value="SOME_CONST",
                            location=ReferenceLocation(
                                class_name="UnresolvedClass",
                                element_type=ElementType.CLASS_ANNOTATION,
                                element_name="TestAnno",
                            ),
                        )
                    },
                )
            ],
        )
        sample_analyzer.classes[test_class.fully_qualified_name] = test_class
        unresolved = sample_analyzer.report_unresolved_references()
        assert "com.example.unresolved.UnresolvedClass" in unresolved
        assert unresolved["com.example.unresolved.UnresolvedClass"][0]["type"] == "annotation"

    def test_add_constants_triggers_resolve_pipeline(self, sample_analyzer, mocker):
        """Test add_constants triggers the resolution pipeline"""
        # Patch the _resolve_all_references method to check it is called
        called = {}

        def fake_resolve_all_references(*a, **kw):
            called["yes"] = True

        mocker.patch.object(
            sample_analyzer,
            "_resolve_all_references",
            side_effect=fake_resolve_all_references,
        )
        sample_analyzer.add_constants({"FOO": "BAR"})
        assert called["yes"]

    def test_get_all_service_dependencies_empty(self, sample_analyzer):
        """Test get_all_service_dependencies returns empty if no dependencies"""
        # Remove all service_variables
        for c in sample_analyzer.get_controllers():
            c.member_variables = []
        deps = sample_analyzer.get_all_service_dependencies()
        assert deps == {}

    def test_get_service_method_calls_empty(self, sample_analyzer):
        """Test get_service_method_calls returns empty if no method calls"""
        for c in sample_analyzer.get_controllers():
            c.methods = []
        calls = sample_analyzer.get_service_method_calls()
        assert calls == {}

    def test_get_dependencies_graph_empty(self, sample_analyzer):
        """Test get_dependencies_graph returns empty if no dependencies"""
        for c in sample_analyzer.classes.values():
            c.member_variables = []
        graph = sample_analyzer.get_dependencies_graph()
        assert graph == {}


class TestJavaAnalyzerSearch:
    """Test search functionality of the JavaAnalyzer class - unit tests"""

    def test_find_class_by_name_dot_in_middle(self, sample_analyzer):
        """Test find_class_by_name with partial qualified name"""
        # Should match by suffix
        results = sample_analyzer.find_class_by_name("web.UserController")
        assert len(results) == 1
        assert results[0].name == "UserController"

    def test_find_unique_class_by_name_raises(self, sample_analyzer):
        """Test find_unique_class_by_name raises MultipleJavaClassMatchError"""
        another = JavaClass(name="ProductController", package="com.other.web")
        sample_analyzer.classes[another.fully_qualified_name] = another
        with pytest.raises(Exception):
            sample_analyzer.find_unique_class_by_name("ProductController")

    def test_find_class_by_path_relative_and_absolute(self, sample_analyzer):
        """Test find_class_by_path with both relative and absolute paths"""
        ctrl = sample_analyzer.get_controllers()[0]
        # Absolute
        found = sample_analyzer.find_class_by_path(ctrl.absolute_path)
        assert found is not None
        # Relative
        found2 = sample_analyzer.find_class_by_path(ctrl.relative_path, is_relative=True)
        assert found2 is not None

    def test_find_class_by_package_multiple(self, sample_analyzer):
        """Test find_class_by_package returns all in package"""
        results = sample_analyzer.find_class_by_package("com.example.web")
        assert {c.name for c in results} == {"UserController", "ProductController"}

    def test_find_classes_by_endpoint_prefix(self, sample_analyzer):
        """Test find_classes_by_endpoint finds controllers by exact endpoint path prefix"""
        # Debug - let's see what endpoints actually exist in our controllers
        print("\nEndpoints in sample_analyzer:")
        for controller in sample_analyzer.get_controllers():
            print(f"Controller: {controller.name}, Base path: {controller.base_endpoint_path}")
            for endpoint in controller.endpoints:
                full_paths = endpoint.get_full_path(controller.base_endpoint_path)
                for http_method, path in full_paths.items():
                    print(f"  {http_method}: {path}")

        # Should match with exact path prefix
        results = sample_analyzer.find_classes_by_endpoint(["/api/users"])
        assert any(c.name == "UserController" for c in results)

        # Should match with exact path prefix
        results = sample_analyzer.find_classes_by_endpoint(["/api/products"])
        assert any(c.name == "ProductController" for c in results)

        # Should match all three using common prefix
        results = sample_analyzer.find_classes_by_endpoint(["/api"])
        assert {c.name for c in results} == {
            "UserController",
            "ProductController",
            "OrderController",
        }

        # Non-prefix paths should NOT match (previously this was a substring match)
        results = sample_analyzer.find_classes_by_endpoint(["users"])
        assert len(results) == 0

        # Should match OrderController's full base path
        results = sample_analyzer.find_classes_by_endpoint(["/api/orders/v2/long/path"])
        assert any(c.name == "OrderController" for c in results), (
            f"OrderController not found with path '/api/orders/v2/long/path'. Available controllers: {[c.name for c in sample_analyzer.get_controllers()]}"
        )

        # Should match OrderController's full endpoint path (base + method)
        results = sample_analyzer.find_classes_by_endpoint(["/api/orders/v2/long/path/history"])
        assert any(c.name == "OrderController" for c in results)

        # Mid-path segment should not match as prefix
        results = sample_analyzer.find_classes_by_endpoint(["orders/v2"])
        assert len(results) == 0

        # Just the method path should not match as a standalone path
        results = sample_analyzer.find_classes_by_endpoint(["/history"])
        assert len(results) == 0

        # Completely unrelated path should not match
        results = sample_analyzer.find_classes_by_endpoint(["/notfound"])
        assert len(results) == 0

    def test_find_classes_by_endpoint_with_base_paths(self, sample_analyzer):
        """Test find_classes_by_endpoint with various base path combinations"""
        # Test with single base path
        results = sample_analyzer.find_classes_by_endpoint(
            ["/users"], optional_base_paths=["/api"]
        )
        assert any(c.name == "UserController" for c in results)

        # Test multiple search terms
        results = sample_analyzer.find_classes_by_endpoint(
            ["/users", "/products"], optional_base_paths=["/api"]
        )
        assert {c.name for c in results} == {"UserController", "ProductController"}

        # Test multiple base paths
        results = sample_analyzer.find_classes_by_endpoint(
            ["/users"], optional_base_paths=["/api", "/v1/api"]
        )
        assert any(c.name == "UserController" for c in results)

        # Test slash handling variations - base path without trailing slash
        results = sample_analyzer.find_classes_by_endpoint(["users"], optional_base_paths=["/api"])
        assert any(c.name == "UserController" for c in results)

        # Test slash handling variations - base path with trailing slash
        results = sample_analyzer.find_classes_by_endpoint(
            ["users"], optional_base_paths=["/api/"]
        )
        assert any(c.name == "UserController" for c in results)

        # Test slash handling variations - term with leading slash
        results = sample_analyzer.find_classes_by_endpoint(["/users"], optional_base_paths=["api"])
        assert any(c.name == "UserController" for c in results)

        # Test slash handling variations - neither base path nor term has slashes
        results = sample_analyzer.find_classes_by_endpoint(["users"], optional_base_paths=["api"])
        assert any(c.name == "UserController" for c in results)

        # Test slash handling variations - double slash normalization
        results = sample_analyzer.find_classes_by_endpoint(
            ["/users"], optional_base_paths=["/api/"]
        )
        assert any(c.name == "UserController" for c in results)

        # Test nested base paths for OrderController
        results = sample_analyzer.find_classes_by_endpoint(
            ["/history"], optional_base_paths=["/api/orders/v2/long/path"]
        )
        assert any(c.name == "OrderController" for c in results), (
            "OrderController not found with '/history' and base path '/api/orders/v2/long/path'"
        )

        # Also test with no leading slash on history path
        results = sample_analyzer.find_classes_by_endpoint(
            ["history"], optional_base_paths=["/api/orders/v2/long/path"]
        )
        assert any(c.name == "OrderController" for c in results)

        # Test with mixed slash formats
        results = sample_analyzer.find_classes_by_endpoint(
            ["history"], optional_base_paths=["api/orders/v2/long/path/"]
        )
        assert any(c.name == "OrderController" for c in results)

        # No match when base path doesn't lead to valid endpoint
        results = sample_analyzer.find_classes_by_endpoint(
            ["/admin"], optional_base_paths=["/api"]
        )
        assert len(results) == 0

        # Original term that doesn't match should still not match with base paths
        results = sample_analyzer.find_classes_by_endpoint(
            ["notfound"], optional_base_paths=["/api"]
        )
        assert len(results) == 0

    def test_resolve_type_to_class_java_lang(self, sample_analyzer):
        """Test resolve_type_to_class for java.lang types"""
        # Add a fake java.lang.String class
        string_class = JavaClass(name="String", package="java.lang")
        sample_analyzer.classes[string_class.fully_qualified_name] = string_class
        test_class = JavaClass(name="Test", package="com.example")
        found = sample_analyzer.resolve_type_to_class("String", test_class)
        assert found is not None
        assert found.package == "java.lang"

    def test_find_class_by_name(self, sample_analyzer):
        """Test finding classes by name"""
        # Find existing class
        results = sample_analyzer.find_class_by_name("UserController")
        assert len(results) == 1
        assert results[0].name == "UserController"

        # Find by qualified name
        results = sample_analyzer.find_class_by_name("com.example.web.UserController")
        assert len(results) == 1
        assert results[0].name == "UserController"

        # Find non-existing class
        results = sample_analyzer.find_class_by_name("NonExistentClass")
        assert len(results) == 0

    def test_find_unique_class_by_name(self, sample_analyzer):
        """Test finding a unique class by name or qualified name"""
        # Find unique by simple name
        result = sample_analyzer.find_unique_class_by_name("UserController")
        assert result.name == "UserController"
        # Find unique by qualified name
        result = sample_analyzer.find_unique_class_by_name("com.example.web.UserController")
        assert result.name == "UserController"
        # Not found
        with pytest.raises(KeyError):
            sample_analyzer.find_unique_class_by_name("NonExistentClass")

        # Add another class with the same simple name but different package
        another = JavaClass(name="UserController", package="com.other.web")
        sample_analyzer.classes[another.fully_qualified_name] = another

        # Now ambiguous by simple name
        with pytest.raises(Exception) as excinfo:
            sample_analyzer.find_unique_class_by_name("UserController")
        assert "Multiple classes found" in str(excinfo.value)

        # Still unique by fully qualified name
        result = sample_analyzer.find_unique_class_by_name("com.example.web.UserController")
        assert result.package == "com.example.web"

    def test_find_class_by_path(self, sample_analyzer):
        """Test finding a class by path"""
        # Find by absolute path
        result = sample_analyzer.find_class_by_path("/path/to/com/example/web/UserController.java")
        assert result is not None
        assert result.name == "UserController"

        # Find by relative path
        result = sample_analyzer.find_class_by_path(
            "com/example/web/UserController.java", is_relative=True
        )
        assert result is not None
        assert result.name == "UserController"

        # Find non-existent path
        result = sample_analyzer.find_class_by_path("non/existent/path.java")
        assert result is None

    def test_find_class_by_package(self, sample_analyzer):
        """Test finding classes in a package"""
        # Find classes in existing package
        results = sample_analyzer.find_class_by_package("com.example.web")
        assert len(results) == 2
        assert {cls.name for cls in results} == {"UserController", "ProductController"}

        # Find classes in non-existent package
        results = sample_analyzer.find_class_by_package("com.nonexistent")
        assert len(results) == 0

    def test_resolve_type_to_class(self, sample_analyzer):
        """Test resolving a type name to a JavaClass"""
        from app.src.codeanalyzer.models import ImportDefinition

        # Create a class with imports for testing
        test_class = JavaClass(
            name="TestClass",
            package="com.example.test",
            imports=[
                ImportDefinition(fully_qualified_name="com.example.service.UserService"),
                ImportDefinition(fully_qualified_name="com.example.service", is_wildcard=True),
            ],
        )

        # Resolve a class with a direct import
        result = sample_analyzer.resolve_type_to_class("UserService", test_class)
        assert result is not None
        assert result.name == "UserService"

        # Resolve a class with a wildcard import
        result = sample_analyzer.resolve_type_to_class("ProductService", test_class)
        assert result is not None
        assert result.name == "ProductService"

        # Resolve using a fully qualified name
        result = sample_analyzer.resolve_type_to_class(
            "com.example.service.UserService", test_class
        )
        assert result is not None
        assert result.name == "UserService"

        # Try to resolve a non-existent class
        result = sample_analyzer.resolve_type_to_class("NonExistentClass", test_class)
        assert result is None


class TestJavaAnalyzerGetters:
    """Test getter methods in the JavaAnalyzer class - unit tests"""

    def test_get_controllers(self, sample_analyzer):
        """Test getting all controllers"""
        controllers = sample_analyzer.get_controllers()
        # Check that all three controllers are present, including OrderController
        assert len(controllers) == 3
        assert {c.name for c in controllers} == {
            "UserController",
            "ProductController",
            "OrderController",
        }
        assert all(isinstance(c, RestControllerClass) for c in controllers)

    def test_get_services(self, sample_analyzer):
        """Test getting all services"""
        services = sample_analyzer.get_services()
        assert len(services) == 2
        assert {s.name for s in services} == {"UserService", "ProductService"}
        assert all(isinstance(s, ServiceClass) for s in services)

    def test_get_all_endpoints(self, sample_analyzer):
        """Test getting all endpoints from controllers"""
        endpoints = sample_analyzer.get_all_endpoints()

        # Verify the endpoints for both controllers
        assert "UserController" in endpoints
        assert "ProductController" in endpoints

        # Verify UserController endpoints
        user_endpoints = endpoints["UserController"]
        assert "GET" in user_endpoints
        assert len(user_endpoints["GET"]) == 2
        assert ("/api/users", "getUsers") in user_endpoints["GET"]
        assert ("/api/users/{id}", "getUser") in user_endpoints["GET"]

        # Verify ProductController endpoints
        product_endpoints = endpoints["ProductController"]
        assert "GET" in product_endpoints
        assert len(product_endpoints["GET"]) == 1
        assert ("/api/products", "getProducts") in product_endpoints["GET"]

    def test_get_all_service_dependencies(self, sample_analyzer):
        """Test getting all service dependencies from controllers"""
        dependencies = sample_analyzer.get_all_service_dependencies()

        # Verify both controllers have dependencies
        assert "UserController" in dependencies
        assert "ProductController" in dependencies

        # Verify UserController dependencies
        user_deps = dependencies["UserController"]
        assert len(user_deps) == 1
        assert user_deps[0].name == "userService"
        assert user_deps[0].type == "UserService"

        # Verify ProductController dependencies
        product_deps = dependencies["ProductController"]
        assert len(product_deps) == 1
        assert product_deps[0].name == "productService"
        assert product_deps[0].type == "ProductService"

    def test_get_service_method_calls(self, sample_analyzer):
        """Test getting service method calls from controllers"""
        method_calls = sample_analyzer.get_service_method_calls()

        # Verify both controllers have method calls
        assert "UserController" in method_calls

        # Verify UserController method calls
        user_calls = method_calls["UserController"]
        assert "getUsers" in user_calls
        assert "getUser" in user_calls
        assert user_calls["getUsers"][0].method_name == "findAll"
        assert user_calls["getUser"][0].method_name == "findById"

        # Verify ProductController method calls
        assert "ProductController" in method_calls
        product_calls = method_calls["ProductController"]
        assert "getProducts" in product_calls
        assert product_calls["getProducts"][0].method_name == "findAll"

    def test_get_dependencies_graph(self, sample_analyzer):
        """Test creating a dependency graph between classes"""
        graph = sample_analyzer.get_dependencies_graph()

        # Verify controllers depend on services
        assert "com.example.web.UserController" in graph
        assert "com.example.web.ProductController" in graph

        # Check the dependencies
        user_deps = graph["com.example.web.UserController"]
        assert "UserService" in user_deps

        product_deps = graph["com.example.web.ProductController"]
        assert "ProductService" in product_deps


class TestJavaAnalyzerConstants:
    """Test constant handling in the JavaAnalyzer class - unit tests"""

    def test_add_constants(self, sample_analyzer, constants_map):
        """Test adding global constants"""
        # Add constants
        sample_analyzer.add_constants(constants_map)

        # Verify constants were added to the analyzer
        assert sample_analyzer.global_constants == constants_map

        # Verify constants were propagated to all classes
        for cls in sample_analyzer.classes.values():
            for key, value in constants_map.items():
                assert key in cls.constants
                assert cls.constants[key] == value

    def test_add_constants_local_override(self, sample_analyzer):
        """Local constants should not be overwritten by global constants."""
        # Create class with a local constant
        local_class = JavaClass(
            name="LocalClass", package="com.example", constants={"KEY": "local"}
        )
        sample_analyzer.classes[local_class.fully_qualified_name] = local_class

        # Add global constant with the same key
        sample_analyzer.add_constants({"KEY": "global"})

        # Local constant remains unchanged
        assert local_class.constants["KEY"] == "local"
        # global_constants should be updated
        assert sample_analyzer.global_constants["KEY"] == "global"

    def test_peek_expression_value_handles_chained(self, sample_analyzer):
        """Test peek_expression_value handles chained constant references"""
        from app.src.codeanalyzer.constant_resolver import ConstantResolver

        # Add classes and constants
        classA = JavaClass(name="A", package="com.example", constants={"B": "B.C"})
        classB = JavaClass(name="B", package="com.example", constants={"C": "final-value"})
        sample_analyzer.classes[classA.fully_qualified_name] = classA
        sample_analyzer.classes[classB.fully_qualified_name] = classB
        resolver = ConstantResolver(sample_analyzer)
        val = resolver.peek_expression_value("A", "B")
        assert val == "final-value"

    def test_peek_expression_value_handles_nonexistent(self, sample_analyzer):
        """Test peek_expression_value raises for missing class"""
        from app.src.codeanalyzer.constant_resolver import ConstantResolver

        resolver = ConstantResolver(sample_analyzer)
        with pytest.raises(KeyError):
            resolver.peek_expression_value("NoSuchClass", "ANY")


class TestJavaAnalyzerDependencyLoading:
    """Test dependency loading and category-based retrieval."""

    def test_load_class_with_dependencies_not_found(self, sample_analyzer):
        with pytest.raises(ValueError, match="not found"):
            sample_analyzer.load_class_with_dependencies("NonExistentClass")

    def test_load_class_with_dependencies_basic(self, sample_analyzer):
        # UserController has source set so it can be loaded
        ctrl = sample_analyzer.find_class_by_name("UserController")[0]
        ctrl.source_code = "// dummy source"
        result = sample_analyzer.load_class_with_dependencies("UserController")
        assert any(c.name == "UserController" for c in result)

    def test_get_classes_by_category_no_deps(self, sample_analyzer):
        result = sample_analyzer.get_classes_by_category_with_dependencies(
            ClassCategory.SERVICE, load_dependencies=False
        )
        assert all(c.category == ClassCategory.SERVICE for c in result)
        assert len(result) >= 2

    def test_get_classes_by_category_with_deps(self, sample_analyzer):
        # Give controllers source so load_class_with_dependencies works
        for c in sample_analyzer.get_controllers():
            c.source_code = "// source"
        result = sample_analyzer.get_classes_by_category_with_dependencies(
            ClassCategory.CONTROLLER, load_dependencies=True
        )
        assert all(c.category == ClassCategory.CONTROLLER for c in result)

    def test_filter_java_classes_no_filter(self, sample_analyzer):
        all_classes = sample_analyzer.filter_java_classes(None)
        assert len(all_classes) == len(sample_analyzer.classes)

    def test_filter_java_classes_with_filter(self, sample_analyzer):
        services = sample_analyzer.filter_java_classes(
            lambda cls: cls.category == ClassCategory.SERVICE
        )
        assert all(c.category == ClassCategory.SERVICE for c in services)
        assert len(services) >= 2


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
