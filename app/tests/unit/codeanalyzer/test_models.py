"""
Unit tests for Pydantic model classes.

Strategy: Pure unit tests with hand-created model instances.
Real: Model validation, computed properties, string representations
Mocked: Nothing (no external dependencies)

Test Responsibilities:
- TestAnnotation: Annotation model behavior and string formatting
- TestMethodCallInfo: Method call tracking and representation
- TestParameter: Parameter model with annotations
- TestJavaMethod: Method model with parameters, annotations, exceptions
- TestRestEndpoint: REST endpoint path composition and HTTP methods
- TestMemberVariable: Basic member variable model behavior
- TestClassReferenceMemberVariable: Class reference variables with autowiring
- TestImportDefinition: Import statement model and package parsing
- TestJavaClass: Core Java class model with members and methods
- TestRestControllerClass: Controller-specific functionality and endpoints
- TestServiceClass: Service-specific model behavior
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from app.src.codeanalyzer.models import (
    Annotation,
    ArgumentExpressionType,
    ClassCategory,
    ClassReferenceMemberVariable,
    ImportDefinition,
    JavaClass,
    JavaConstructor,
    JavaMethod,
    MemberVariable,
    MemberVariableCategory,
    MethodCallArgument,
    MethodCallInfo,
    Parameter,
    RestControllerClass,
    RestEndpoint,
    ServiceClass,
)


class TestAnnotation:
    """Test cases for the Annotation model."""

    def test_annotation_without_values(self):
        """Test an annotation without values."""
        anno = Annotation(name="Test")
        assert anno.name == "Test"
        assert anno.values == {}
        assert str(anno) == "@Test"

    def test_annotation_with_single_value(self):
        """Test an annotation with a single value."""
        anno = Annotation(name="RequestMapping", values={"value": "/api"})
        assert anno.name == "RequestMapping"
        assert anno.values == {"value": "/api"}
        assert str(anno) == "@RequestMapping(value='/api')"

    def test_annotation_with_multiple_values(self):
        """Test an annotation with multiple values."""
        anno = Annotation(
            name="RequestMapping",
            values={"value": "/api", "produces": "application/json"},
        )
        assert anno.values == {"value": "/api", "produces": "application/json"}
        assert "@RequestMapping(" in str(anno)
        assert "value='/api'" in str(anno)
        assert "produces='application/json'" in str(anno)

    def test_annotation_with_default_value(self):
        """Test an annotation with a default (unnamed) value."""
        anno = Annotation(name="RequestMapping", values={"": "/api"})
        assert anno.values == {"": "/api"}
        assert str(anno) == "@RequestMapping(='/api')"


class TestMethodCallInfo:
    """Test cases for the MethodCallInfo model."""

    def test_method_call_basic(self):
        """Test basic properties of MethodCallInfo."""
        call = MethodCallInfo(
            target_name="userService",
            method_name="findById",
            target_type="UserService",
            target_class_category=ClassCategory.SERVICE,
            arguments=[
                MethodCallArgument(
                    position=0,
                    raw_expression="123",
                    expression_type=ArgumentExpressionType.LITERAL,
                )
            ],
        )
        assert call.target_name == "userService"
        assert call.method_name == "findById"
        assert call.target_type == "UserService"
        assert call.arg_count == 1
        assert call.package_name is None

    def test_method_call_with_package(self):
        """Test MethodCallInfo with package name."""
        call = MethodCallInfo(
            target_name="userService",
            method_name="findById",
            target_type="UserService",
            target_class_category=ClassCategory.SERVICE,
            package_name="com.example.service",
            arguments=[
                MethodCallArgument(
                    position=0,
                    raw_expression="123",
                    expression_type=ArgumentExpressionType.LITERAL,
                )
            ],
        )
        assert call.package_name == "com.example.service"
        assert "com.example.service" in str(call)

    def test_method_call_string_representation(self):
        """Test string representation of MethodCallInfo."""
        call = MethodCallInfo(
            target_name="userService",
            method_name="findById",
            target_type="UserService",
            target_class_category=ClassCategory.SERVICE,
        )
        assert str(call) == "userService.findById()"

    def test_method_call_with_arguments(self):
        """Test MethodCallInfo with detailed arguments."""
        arg1 = MethodCallArgument(
            position=0,
            raw_expression="123",
            expression_type=ArgumentExpressionType.LITERAL,
        )
        arg2 = MethodCallArgument(
            position=1,
            raw_expression="name",
            expression_type=ArgumentExpressionType.IDENTIFIER,
        )

        call = MethodCallInfo(
            target_name="userService",
            method_name="findById",
            target_type="UserService",
            target_class_category=ClassCategory.SERVICE,
            arguments=[arg1, arg2],
        )

        assert call.arg_count == 2
        assert len(call.arguments) == 2
        assert call.arguments[0].raw_expression == "123"

    def test_method_call_target_category(self):
        """Test MethodCallInfo target category functionality."""
        call = MethodCallInfo(
            target_name="userService",
            method_name="findById",
            target_type="UserService",
            target_class_category=ClassCategory.SERVICE,
        )
        assert call.is_target_category(ClassCategory.SERVICE)
        assert not call.is_target_category(ClassCategory.REPOSITORY)

    def test_method_call_backward_compatibility(self):
        """Test backward compatibility properties."""
        call = MethodCallInfo(
            target_name="userService",
            method_name="findById",
            target_type="UserService",
            target_class_category=ClassCategory.SERVICE,
        )
        # Backward compatibility
        assert call.target_name == "userService"
        assert call.target_type == "UserService"


class TestParameter:
    """Test cases for the Parameter model."""

    def test_parameter_without_annotations(self):
        """Test a parameter without annotations."""
        param = Parameter(name="id", type="Long")
        assert param.name == "id"
        assert param.type == "Long"
        assert param.annotations == []
        assert str(param) == "Long id"

    def test_parameter_with_annotation(self):
        """Test a parameter with an annotation."""
        anno = Annotation(name="PathVariable", values={"value": "id"})
        param = Parameter(name="id", type="Long", annotations=[anno])
        assert len(param.annotations) == 1
        assert param.annotations[0].name == "PathVariable"
        assert str(param) == "@PathVariable(value='id') Long id"

    def test_parameter_with_multiple_annotations(self):
        """Test a parameter with multiple annotations."""
        anno1 = Annotation(name="PathVariable", values={"value": "id"})
        anno2 = Annotation(name="Valid")
        param = Parameter(name="id", type="Long", annotations=[anno1, anno2])
        assert len(param.annotations) == 2
        assert "@PathVariable" in str(param)
        assert "@Valid" in str(param)


class TestJavaMethod:
    """Test cases for the JavaMethod model."""

    def test_method_basic_properties(self):
        """Test a method with basic properties."""
        method = JavaMethod(name="testMethod", return_type="String")
        assert method.name == "testMethod"
        assert method.return_type == "String"
        assert method.parameters == []
        assert method.annotations == []
        assert method.exceptions == []
        assert method.modifiers == []
        assert method.method_calls == []

    def test_method_with_parameters(self):
        """Test a method with parameters."""
        param1 = Parameter(name="id", type="Long")
        param2 = Parameter(name="name", type="String")
        method = JavaMethod(name="testMethod", return_type="String", parameters=[param1, param2])
        assert len(method.parameters) == 2
        assert "Long id" in str(method)
        assert "String name" in str(method)

    def test_method_with_annotations_and_modifiers(self):
        """Test a method with annotations and modifiers."""
        anno = Annotation(name="Override")
        method = JavaMethod(
            name="testMethod",
            return_type="String",
            annotations=[anno],
            modifiers=["public", "final"],
        )
        assert len(method.annotations) == 1
        assert method.modifiers == ["public", "final"]
        assert "@Override" in str(method)
        assert "public final" in str(method)

    def test_method_with_exceptions(self):
        """Test a method with exceptions."""
        method = JavaMethod(
            name="testMethod",
            return_type="String",
            exceptions=["IOException", "RuntimeException"],
        )
        assert method.exceptions == ["IOException", "RuntimeException"]
        assert "throws IOException, RuntimeException" in str(method)

    def test_add_method_call(self):
        """Test adding a method call to a method."""
        method = JavaMethod(name="testMethod", return_type="String")

        method.add_method_call(
            target_name="userService",
            method_name="findById",
            target_type="UserService",
            target_class_category=ClassCategory.SERVICE,
        )

        assert len(method.method_calls) == 1
        assert method.method_calls[0].target_name == "userService"
        assert method.method_calls[0].method_name == "findById"
        assert method.method_calls[0].target_type == "UserService"
        assert method.method_calls[0].arg_count == 0

    def test_get_service_calls(self):
        """Test filtering method calls by service category."""
        method = JavaMethod(name="testMethod", return_type="String")

        # Add service call
        method.add_method_call(
            target_name="userService",
            method_name="findById",
            target_type="UserService",
            target_class_category=ClassCategory.SERVICE,
        )

        # Add repository call
        method.add_method_call(
            target_name="userRepository",
            method_name="save",
            target_type="UserRepository",
            target_class_category=ClassCategory.REPOSITORY,
        )

        service_calls = method.get_service_calls()
        assert len(service_calls) == 1
        assert service_calls[0].target_name == "userService"

    def test_get_method_calls_by_category(self):
        """Test filtering method calls by any category."""
        method = JavaMethod(name="testMethod", return_type="String")

        method.add_method_call(
            target_name="userRepository",
            method_name="save",
            target_type="UserRepository",
            target_class_category=ClassCategory.REPOSITORY,
        )

        repo_calls = method.get_method_calls_by_category(ClassCategory.REPOSITORY)
        assert len(repo_calls) == 1

        service_calls = method.get_method_calls_by_category(ClassCategory.SERVICE)
        assert len(service_calls) == 0


class TestRestEndpoint:
    """Test cases for the RestEndpoint model."""

    def test_endpoint_basic(self):
        """Test a REST endpoint with basic properties."""
        endpoint = RestEndpoint(
            name="getItem",
            return_type="ResponseEntity<Item>",
            path_mappings={"GET": "/items/{id}"},
        )
        assert endpoint.name == "getItem"
        assert endpoint.path_mappings == {"GET": "/items/{id}"}

    def test_get_full_path_with_base_path(self):
        """Test getting full path with a base path."""
        endpoint = RestEndpoint(
            name="getItem",
            return_type="ResponseEntity<Item>",
            path_mappings={"GET": "/items/{id}"},
        )
        full_paths = endpoint.get_full_path("/api")
        assert full_paths == {"GET": "/api/items/{id}"}

    def test_get_full_path_with_trailing_slash(self):
        """Test getting full path with a base path that has a trailing slash."""
        endpoint = RestEndpoint(
            name="getItem",
            return_type="ResponseEntity<Item>",
            path_mappings={"GET": "/items/{id}"},
        )
        full_paths = endpoint.get_full_path("/api/")
        assert full_paths == {"GET": "/api/items/{id}"}

    def test_get_full_path_with_empty_base_path(self):
        """Test getting full path with an empty base path."""
        endpoint = RestEndpoint(
            name="getItem",
            return_type="ResponseEntity<Item>",
            path_mappings={"GET": "/items/{id}"},
        )
        full_paths = endpoint.get_full_path("")
        assert full_paths == {"GET": "/items/{id}"}

    def test_get_full_path_with_no_leading_slash(self):
        """Test getting full path with a path that has no leading slash."""
        endpoint = RestEndpoint(
            name="getItem",
            return_type="ResponseEntity<Item>",
            path_mappings={"GET": "items/{id}"},
        )
        full_paths = endpoint.get_full_path("/api")
        assert full_paths == {"GET": "/api/items/{id}"}

    def test_get_full_path_with_empty_path(self):
        """Test getting full path with an empty path."""
        endpoint = RestEndpoint(
            name="getItems",
            return_type="ResponseEntity<List<Item>>",
            path_mappings={"GET": ""},
        )
        full_paths = endpoint.get_full_path("/api")
        assert full_paths == {"GET": "/api"}

    def test_get_full_path_with_multiple_methods(self):
        """Test getting full path with multiple HTTP methods."""
        endpoint = RestEndpoint(
            name="handleItem",
            return_type="ResponseEntity<Item>",
            path_mappings={"GET": "/items/{id}", "DELETE": "/items/{id}"},
        )
        full_paths = endpoint.get_full_path("/api")
        assert full_paths == {"GET": "/api/items/{id}", "DELETE": "/api/items/{id}"}

    def test_get_full_path_multi_value(self):
        """Test getting full paths when path_mappings value is a list."""
        endpoint = RestEndpoint(
            name="multiItem",
            return_type="ResponseEntity<Item>",
            path_mappings={"GET": ["/a", "/b"]},
        )
        full_paths = endpoint.get_full_path("/base")
        assert full_paths == {"GET": ["/base/a", "/base/b"]}


class TestMemberVariable:
    """Test cases for the MemberVariable model."""

    def test_member_variable_basic(self):
        """Test a basic member variable."""
        var = MemberVariable(name="count", type="int")
        assert var.name == "count"
        assert var.type == "int"
        assert var.category == MemberVariableCategory.OTHER
        assert var.annotations == []
        assert var.modifiers == []
        assert str(var) == "int count"

    def test_member_variable_with_annotations(self):
        """Test a member variable with annotations."""
        anno = Annotation(name="JsonProperty", values={"value": "item_count"})
        var = MemberVariable(name="count", type="int", annotations=[anno])
        assert len(var.annotations) == 1
        assert str(var) == "@JsonProperty(value='item_count') int count"

    def test_member_variable_with_modifiers(self):
        """Test a member variable with modifiers."""
        var = MemberVariable(name="count", type="int", modifiers=["private", "final"])
        assert var.modifiers == ["private", "final"]
        assert str(var) == "private final int count"

    def test_member_variable_with_category(self):
        """Test a member variable with a specific category."""
        var = MemberVariable(
            name="items", type="List<Item>", category=MemberVariableCategory.COLLECTION
        )
        assert var.category == MemberVariableCategory.COLLECTION


class TestClassReferenceMemberVariable:
    """Test cases for the ClassReferenceMemberVariable model."""

    def test_class_reference_basic(self):
        """Test a basic class reference member variable."""
        var = ClassReferenceMemberVariable(name="userService", type="UserService")
        assert var.name == "userService"
        assert var.type == "UserService"
        assert var.category == MemberVariableCategory.CLASS_REFERENCE
        assert not var.is_autowired
        assert var.qualifier is None
        assert var.referenced_class_category == ClassCategory.UNKNOWN
        assert str(var) == "UserService userService"

    def test_class_reference_with_autowired(self):
        """Test a class reference with autowired annotation."""
        var = ClassReferenceMemberVariable(
            name="userService", type="UserService", is_autowired=True
        )
        assert var.is_autowired
        assert str(var) == "@Autowired UserService userService"

    def test_class_reference_with_qualifier(self):
        """Test a class reference with qualifier annotation."""
        var = ClassReferenceMemberVariable(
            name="userService",
            type="UserService",
            is_autowired=True,
            qualifier="userServiceImpl",
        )
        assert var.qualifier == "userServiceImpl"
        assert str(var) == '@Autowired @Qualifier("userServiceImpl") UserService userService'

    def test_class_reference_with_referenced_category(self):
        """Test a class reference with a specific referenced class category."""
        var = ClassReferenceMemberVariable(
            name="userService",
            type="UserService",
            referenced_class_category=ClassCategory.SERVICE,
        )
        assert var.referenced_class_category == ClassCategory.SERVICE


class TestImportDefinition:
    """Test cases for the ImportDefinition model."""

    def test_import_definition_basic(self):
        """Test a basic import definition."""
        import_def = ImportDefinition(fully_qualified_name="com.example.model.User")
        assert import_def.fully_qualified_name == "com.example.model.User"
        assert import_def.is_static is False
        assert import_def.is_wildcard is False
        assert import_def.package_name == "com.example.model"
        assert import_def.class_name == "User"

    def test_import_definition_static(self):
        """Test a static import definition."""
        import_def = ImportDefinition(
            fully_qualified_name="com.example.util.Constants.API_PATH", is_static=True
        )
        assert import_def.is_static
        assert import_def.package_name == "com.example.util.Constants"
        assert import_def.class_name == "API_PATH"

    def test_import_definition_wildcard(self):
        """Test a wildcard import definition."""
        import_def = ImportDefinition(fully_qualified_name="com.example.model", is_wildcard=True)
        assert import_def.is_wildcard
        assert import_def.package_name == "com.example.model"
        assert import_def.class_name == ""


class TestJavaClass:
    """Test cases for the JavaClass model."""

    def test_java_class_basic(self):
        """Test a basic Java class."""
        cls = JavaClass(name="TestClass", package="com.example.test")
        assert cls.name == "TestClass"
        assert cls.package == "com.example.test"
        assert cls.fully_qualified_name == "com.example.test.TestClass"
        assert cls.class_annotations == []
        assert cls.member_variables == []
        assert cls.methods == []
        assert cls.imports == []
        assert cls.constants == {}
        assert cls.category == ClassCategory.UNKNOWN
        assert cls.filename == ""
        assert cls.relative_path == ""
        assert cls.absolute_path == ""

    def test_java_class_with_annotations(self):
        """Test a Java class with annotations."""
        anno = Annotation(name="Component")
        cls = JavaClass(name="TestClass", package="com.example.test", class_annotations=[anno])
        assert len(cls.class_annotations) == 1
        assert cls.class_annotations[0].name == "Component"

    def test_java_class_with_members_and_methods(self):
        """Test a Java class with member variables and methods."""
        var = MemberVariable(name="count", type="int")
        method = JavaMethod(name="getCount", return_type="int")
        cls = JavaClass(
            name="TestClass",
            package="com.example.test",
            member_variables=[var],
            methods=[method],
        )
        assert len(cls.member_variables) == 1
        assert len(cls.methods) == 1
        assert cls.member_variables[0].name == "count"
        assert cls.methods[0].name == "getCount"

    def test_get_class_references(self):
        """Test getting all class reference member variables."""
        var1 = MemberVariable(name="count", type="int", category=MemberVariableCategory.PRIMITIVE)
        var2 = ClassReferenceMemberVariable(name="userService", type="UserService")
        var3 = ClassReferenceMemberVariable(name="orderService", type="OrderService")

        cls = JavaClass(
            name="TestClass",
            package="com.example.test",
            member_variables=[var1, var2, var3],
        )

        class_refs = cls.get_class_references()
        assert len(class_refs) == 2
        assert all(isinstance(var, ClassReferenceMemberVariable) for var in class_refs)
        assert {var.name for var in class_refs} == {"userService", "orderService"}

    def test_find_member_variable_by_name(self):
        """Test finding a member variable by name."""
        var1 = MemberVariable(name="count", type="int")
        var2 = MemberVariable(name="name", type="String")

        cls = JavaClass(
            name="TestClass", package="com.example.test", member_variables=[var1, var2]
        )

        found_var = cls.find_member_variable_by_name("name")
        assert found_var is not None
        assert found_var.name == "name"
        assert found_var.type == "String"

        not_found_var = cls.find_member_variable_by_name("unknown")
        assert not_found_var is None

    def test_resolve_class_type(self):
        """Test resolving a class type using TypeResolver."""
        from app.src.codeanalyzer.type_resolver import TypeResolver

        import1 = ImportDefinition(fully_qualified_name="com.example.model.User")
        import2 = ImportDefinition(fully_qualified_name="com.example.util", is_wildcard=True)

        cls = JavaClass(name="TestClass", package="com.example.test", imports=[import1, import2])

        resolver = TypeResolver(analyzer=None)

        # Exact match via explicit import
        assert resolver.resolve_class_type("User", cls) == (
            "User",
            "com.example.model.User",
        )

        # Wildcard import resolution
        assert resolver.resolve_class_type("Constants", cls) == (
            "Constants",
            "com.example.util.Constants",
        )

        # Java lang class fallback (same package)
        assert resolver.resolve_class_type("String", cls) == (
            "String",
            "com.example.test.String",
        )

        # Wildcard-import fallback (util.* applies)
        assert resolver.resolve_class_type("AnotherClass", cls) == (
            "AnotherClass",
            "com.example.util.AnotherClass",
        )


class TestRestControllerClass:
    """Test cases for the RestControllerClass model."""

    def test_controller_class_basic(self):
        """Test a basic controller class."""
        controller = RestControllerClass(name="UserController", package="com.example.web")
        assert controller.name == "UserController"
        assert controller.package == "com.example.web"
        assert controller.category == ClassCategory.CONTROLLER
        assert controller.base_endpoint_path == ""

    def test_controller_class_with_base_path(self):
        """Test a controller class with a base path."""
        controller = RestControllerClass(
            name="UserController",
            package="com.example.web",
            class_annotations=[Annotation(name="RequestMapping", values={"value": "/api/users"})],
        )
        assert controller.base_endpoint_path == "/api/users"

    def test_controller_class_with_path_attribute(self):
        """Test a controller class with path attribute in RequestMapping."""
        controller = RestControllerClass(
            name="UserController",
            package="com.example.web",
            class_annotations=[Annotation(name="RequestMapping", values={"path": "/api/users"})],
        )
        assert controller.base_endpoint_path == "/api/users"

    def test_controller_class_with_default_attribute(self):
        """Test a controller class with default attribute in RequestMapping."""
        controller = RestControllerClass(
            name="UserController",
            package="com.example.web",
            class_annotations=[Annotation(name="RequestMapping", values={"": "/api/users"})],
        )
        assert controller.base_endpoint_path == "/api/users"

    def test_service_variables(self):
        """Test getting service variables from a controller."""
        var1 = MemberVariable(name="count", type="int", category=MemberVariableCategory.PRIMITIVE)
        var2 = ClassReferenceMemberVariable(
            name="userService",
            type="UserService",
            referenced_class_category=ClassCategory.SERVICE,
        )
        var3 = ClassReferenceMemberVariable(
            name="orderRepository",
            type="OrderRepository",
            referenced_class_category=ClassCategory.REPOSITORY,
        )

        controller = RestControllerClass(
            name="UserController",
            package="com.example.web",
            member_variables=[var1, var2, var3],
        )

        service_vars = controller.service_variables
        assert len(service_vars) == 1
        assert service_vars[0].name == "userService"
        assert service_vars[0].referenced_class_category == ClassCategory.SERVICE

    def test_endpoints(self):
        """Test getting endpoints from a controller."""
        method1 = JavaMethod(name="privateMethod", return_type="void")
        method2 = RestEndpoint(
            name="getUser",
            return_type="ResponseEntity<User>",
            path_mappings={"GET": "/users/{id}"},
        )
        method3 = RestEndpoint(
            name="createUser",
            return_type="ResponseEntity<User>",
            path_mappings={"POST": "/users"},
        )

        controller = RestControllerClass(
            name="UserController",
            package="com.example.web",
            methods=[method1, method2, method3],
        )

        endpoints = controller.endpoints
        assert len(endpoints) == 2
        assert {m.name for m in endpoints} == {"getUser", "createUser"}
        assert all(isinstance(m, RestEndpoint) for m in endpoints)

    def test_get_all_endpoints(self):
        """Test getting all endpoints from a controller."""
        method1 = RestEndpoint(
            name="getUser",
            return_type="ResponseEntity<User>",
            path_mappings={"GET": "/users/{id}"},
        )
        method2 = RestEndpoint(
            name="createUser",
            return_type="ResponseEntity<User>",
            path_mappings={"POST": "/users"},
        )
        method3 = RestEndpoint(
            name="handleUser",
            return_type="ResponseEntity<User>",
            path_mappings={"GET": "/users/search", "PUT": "/users/{id}"},
        )

        controller = RestControllerClass(
            name="UserController",
            package="com.example.web",
            class_annotations=[Annotation(name="RequestMapping", values={"value": "/api"})],
            methods=[method1, method2, method3],
        )

        endpoints = controller.get_all_endpoints()
        assert endpoints == {
            "GET": [
                ("/api/users/{id}", "getUser"),
                ("/api/users/search", "handleUser"),
            ],
            "POST": [("/api/users", "createUser")],
            "PUT": [("/api/users/{id}", "handleUser")],
        }


class TestServiceClass:
    """Test cases for the ServiceClass model."""

    def test_service_class_basic(self):
        """Test a basic service class."""
        service = ServiceClass(name="UserService", package="com.example.service")
        assert service.name == "UserService"
        assert service.package == "com.example.service"
        assert service.category == ClassCategory.SERVICE
        assert service.fully_qualified_name == "com.example.service.UserService"

    class TestMethodCallArgument:
        """Test cases for MethodCallArgument model."""

        def test_argument_basic_properties(self):
            """Test a basic MethodCallArgument."""
            arg = MethodCallArgument(
                position=2,
                raw_expression="foo",
                expression_type=ArgumentExpressionType.IDENTIFIER,
                inferred_type="String",
                source_start_offset=0,
                source_end_offset=3,
            )
            assert arg.position == 2
            assert arg.raw_expression == "foo"
            assert arg.expression_type == ArgumentExpressionType.IDENTIFIER
            assert arg.inferred_type == "String"

        def test_argument_expression_types(self):
            """Test classification of expression types."""
            # String literal
            literal = MethodCallArgument(
                position=0,
                raw_expression='"test"',
                expression_type=ArgumentExpressionType.LITERAL,
            )
            assert literal.expression_type == ArgumentExpressionType.LITERAL
            # Identifier
            identifier = MethodCallArgument(
                position=1,
                raw_expression="count",
                expression_type=ArgumentExpressionType.IDENTIFIER,
            )
            assert identifier.expression_type == ArgumentExpressionType.IDENTIFIER

        def test_argument_with_unresolved_reference(self):
            """Test unresolved_reference property can be set."""
            fake_ref = object()
            arg = MethodCallArgument(
                position=0,
                raw_expression="CONST",
                expression_type=ArgumentExpressionType.IDENTIFIER,
                unresolved_reference=fake_ref,
            )
            assert arg.unresolved_reference == fake_ref


# Add these test classes to test_models.py


class TestJavaConstructor:
    """Test cases for the JavaConstructor model."""

    def test_constructor_basic_properties(self):
        """Test a constructor with basic properties."""
        constructor = JavaConstructor(name="TestClass")
        assert constructor.name == "TestClass"
        assert constructor.parameters == []
        assert constructor.annotations == []
        assert constructor.exceptions == []
        assert constructor.modifiers == []

    def test_constructor_with_parameters(self):
        """Test a constructor with parameters."""
        param1 = Parameter(name="id", type="Long")
        param2 = Parameter(name="name", type="String")
        constructor = JavaConstructor(name="TestClass", parameters=[param1, param2])
        assert len(constructor.parameters) == 2
        assert "Long id" in str(constructor)
        assert "String name" in str(constructor)

    def test_constructor_with_annotations_and_modifiers(self):
        """Test a constructor with annotations and modifiers."""
        anno = Annotation(name="Autowired")
        constructor = JavaConstructor(
            name="TestClass",
            annotations=[anno],
            modifiers=["public"],
        )
        assert len(constructor.annotations) == 1
        assert constructor.modifiers == ["public"]
        assert "@Autowired" in str(constructor)
        assert "public" in str(constructor)

    def test_constructor_with_exceptions(self):
        """Test a constructor with exceptions."""
        constructor = JavaConstructor(
            name="TestClass",
            exceptions=["IOException", "RuntimeException"],
        )
        assert constructor.exceptions == ["IOException", "RuntimeException"]
        assert "throws IOException, RuntimeException" in str(constructor)

    def test_has_parameter_of_type(self):
        """Test checking if constructor has parameter of specific type."""
        param1 = Parameter(name="template", type="RestTemplate")
        param2 = Parameter(name="url", type="String")
        constructor = JavaConstructor(name="ApiClient", parameters=[param1, param2])

        assert constructor.has_parameter_of_type("RestTemplate")
        assert constructor.has_parameter_of_type("String")
        assert not constructor.has_parameter_of_type("HttpClient")

    def test_get_parameters_of_category(self):
        """Test getting parameters of specific category (placeholder for future enhancement)."""
        param1 = Parameter(name="template", type="RestTemplate")
        param2 = Parameter(name="id", type="Long")
        constructor = JavaConstructor(name="ApiClient", parameters=[param1, param2])

        # This returns empty list for now but tests the interface
        service_params = constructor.get_parameters_of_category(ClassCategory.SERVICE)
        assert service_params == []

    def test_constructor_string_representation(self):
        """Test string representation of constructor."""
        param = Parameter(name="id", type="Long")
        constructor = JavaConstructor(
            name="TestClass",
            parameters=[param],
            modifiers=["public"],
        )
        result = str(constructor)
        assert "public TestClass(Long id)" in result

    def test_constructor_injection_flag_default_and_set(self):
        """Test the is_injection flag on JavaConstructor."""
        ctor = JavaConstructor(name="TestClass")
        assert ctor.is_injection is False
        ctor2 = JavaConstructor(name="TestClass", is_injection=True)
        assert ctor2.is_injection is True


# Add these methods to the existing TestJavaClass
class TestJavaClassConstructorMethods:
    """Test constructor-related methods in JavaClass."""

    def test_has_default_constructor(self):
        """Test checking if class has default constructor."""
        # Class with default constructor
        default_constructor = JavaConstructor(name="TestClass")
        cls_with_default = JavaClass(
            name="TestClass",
            package="com.example.test",
            constructors=[default_constructor],
        )
        assert cls_with_default.has_default_constructor()

        # Class without default constructor
        param_constructor = JavaConstructor(
            name="TestClass", parameters=[Parameter(name="id", type="Long")]
        )
        cls_without_default = JavaClass(
            name="TestClass",
            package="com.example.test",
            constructors=[param_constructor],
        )
        assert not cls_without_default.has_default_constructor()

        # Class with no constructors at all
        cls_no_constructors = JavaClass(
            name="TestClass",
            package="com.example.test",
            constructors=[],
        )
        assert not cls_no_constructors.has_default_constructor()

    def test_get_constructors_with_annotation(self):
        """Test getting constructors with specific annotation."""
        autowired_constructor = JavaConstructor(
            name="TestClass",
            annotations=[Annotation(name="Autowired")],
            parameters=[Parameter(name="service", type="MyService")],
        )
        regular_constructor = JavaConstructor(name="TestClass")
        inject_constructor = JavaConstructor(
            name="TestClass",
            annotations=[Annotation(name="Inject")],
            parameters=[Parameter(name="repo", type="MyRepository")],
        )

        cls = JavaClass(
            name="TestClass",
            package="com.example.test",
            constructors=[
                autowired_constructor,
                regular_constructor,
                inject_constructor,
            ],
        )

        autowired_constructors = cls.get_constructors_with_annotation("Autowired")
        assert len(autowired_constructors) == 1
        assert autowired_constructors[0] == autowired_constructor

        inject_constructors = cls.get_constructors_with_annotation("Inject")
        assert len(inject_constructors) == 1
        assert inject_constructors[0] == inject_constructor

        nonexistent_constructors = cls.get_constructors_with_annotation("NonExistent")
        assert len(nonexistent_constructors) == 0


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
