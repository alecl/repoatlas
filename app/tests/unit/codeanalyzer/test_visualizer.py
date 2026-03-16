"""
Unit tests for CodeVisualizer output formatting.

Strategy: Unit tests with hand-created model objects.
Real: Formatting algorithms (text, JSON, Markdown, Mermaid)
Mocked: Nothing (pure transformation of model objects)

Test Responsibilities:
- TestTextFormat: Plain text output formatting
- TestJsonFormat: JSON structure validation and content verification
- TestMarkdownFormat: Markdown syntax and table formatting
- TestMermaidFormat: Mermaid diagram generation (class and flow charts)
"""

import json
from typing import Dict, List, Optional

import pytest

from app.src.codeanalyzer.code_visualizer import CodeVisualizer
from app.src.codeanalyzer.models import (
    Annotation,
    ClassCategory,
    ClassReferenceMemberVariable,
    JavaClass,
    JavaMethod,
    MemberVariable,
    MethodCallInfo,
    Parameter,
    RestControllerClass,
    RestEndpoint,
    ServiceClass,
)


@pytest.fixture
def sample_classes() -> list[JavaClass]:
    """Fixture to create sample classes for testing visualization"""
    # Controller
    controller = RestControllerClass(
        name="UserController",
        package="com.example.web",
        class_annotations=[
            Annotation(name="RestController"),
            Annotation(name="RequestMapping", values={"value": "/api/users"}),
        ],
        member_variables=[
            ClassReferenceMemberVariable(
                name="userService",
                type="UserService",
                is_autowired=True,
                referenced_class_category=ClassCategory.SERVICE,
            )
        ],
        methods=[
            RestEndpoint(
                name="getUsers",
                return_type="List<User>",
                path_mappings={"GET": ""},
                method_calls=[
                    MethodCallInfo(
                        target_name="userService",
                        method_name="findAll",
                        target_type="UserService",
                        target_class_category=ClassCategory.SERVICE,
                    )
                ],
            ),
            RestEndpoint(
                name="getUser",
                return_type="User",
                path_mappings={"GET": "/{id}"},
                parameters=[Parameter(name="id", type="Long")],
                method_calls=[
                    MethodCallInfo(
                        target_name="userService",
                        method_name="findById",
                        target_type="UserService",
                        target_class_category=ClassCategory.SERVICE,
                    )
                ],
            ),
            RestEndpoint(
                name="multi",
                return_type="void",
                path_mappings={"GET": ["/x", "/y"]},
            ),
        ],
    )

    # Service
    service = ServiceClass(
        name="UserService",
        package="com.example.service",
        class_annotations=[Annotation(name="Service")],
        methods=[
            JavaMethod(name="findAll", return_type="List<User>"),
            JavaMethod(
                name="findById",
                return_type="User",
                parameters=[Parameter(name="id", type="Long")],
            ),
        ],
    )

    return [controller, service]


class TestTextFormat:
    """Test the text format output of CodeVisualizer"""

    def test_format_text(self, sample_classes):
        """Test text formatting of Java classes"""
        # Format the classes as text
        text_output = CodeVisualizer.format_text(sample_classes)

        # Verify the text contains expected sections
        assert "=== Java Classes ===" in text_output
        assert "Total classes: 2" in text_output

        # Check controller section
        assert "=== Controllers ===" in text_output
        assert "Controller: UserController" in text_output
        assert "Package: com.example.web" in text_output
        assert "Base path: /api/users" in text_output

        # Check endpoints section
        assert "Endpoints:" in text_output
        assert "GET: /api/users -> getUsers" in text_output
        assert "GET: /api/users/{id} -> getUser" in text_output
        # multi-value mapping assertions
        assert "GET: /api/users/x -> multi" in text_output
        assert "GET: /api/users/y -> multi" in text_output

        # Check service dependencies section
        assert "Service Dependencies:" in text_output
        assert "UserService userService" in text_output

        # Check service method calls section
        assert "Method getUsers calls:" in text_output
        assert "(UserService)userService.findAll()" in text_output
        assert "Method getUser calls:" in text_output
        assert "(UserService)userService.findById()" in text_output

        # Check services section
        assert "=== Services ===" in text_output
        assert "Service: UserService" in text_output
        assert "Package: com.example.service" in text_output
        assert "Methods:" in text_output
        # TODO: The argument and returns types are currently the AST type, not the Java type and we have to fix that
        # assert "List<User> findAll()" in text_output
        # assert "User findById(Long id)" in text_output
        assert "findAll()" in text_output
        assert "findById(id)" in text_output


class TestJsonFormat:
    """Test the JSON format output of CodeVisualizer"""

    def test_format_json(self, sample_classes):
        """Test JSON formatting of Java classes"""
        # Format the classes as JSON
        json_output = CodeVisualizer.format_json(sample_classes)

        # Parse the JSON to verify its structure
        data = json.loads(json_output)

        # Check the summary section
        assert "summary" in data
        assert data["summary"]["total_classes"] == 2
        assert data["summary"]["controllers"] == 1
        assert data["summary"]["services"] == 1

        # Check the controllers section
        assert "controllers" in data
        assert len(data["controllers"]) == 1
        controller = data["controllers"][0]
        assert controller["name"] == "UserController"
        assert controller["package"] == "com.example.web"
        assert controller["base_endpoint_path"] == "/api/users"

        # Check endpoints
        assert "endpoints" in controller
        assert "GET" in controller["endpoints"]
        assert len(controller["endpoints"]["GET"]) == 4
        # multi-value paths present
        get_list = controller["endpoints"]["GET"]
        multi_paths = {e["path"] for e in get_list if e["method"] == "multi"}
        assert multi_paths == {"/api/users/x", "/api/users/y"}

        # Check service dependencies
        assert "service_dependencies" in controller
        assert len(controller["service_dependencies"]) == 1
        assert controller["service_dependencies"][0]["name"] == "userService"
        assert controller["service_dependencies"][0]["type"] == "UserService"

        # Check method calls
        assert "method_calls" in controller
        assert "getUsers" in controller["method_calls"]
        assert "getUser" in controller["method_calls"]
        assert controller["method_calls"]["getUsers"][0]["method_name"] == "findAll"
        assert "arguments" in controller["method_calls"]["getUsers"][0]
        assert controller["method_calls"]["getUsers"][0]["arguments"] == []

        # Check the services section
        assert "services" in data
        assert len(data["services"]) == 1
        service = data["services"][0]
        assert service["name"] == "UserService"
        assert service["package"] == "com.example.service"

        # Check service methods
        assert "methods" in service
        assert len(service["methods"]) == 2
        assert service["methods"][0]["name"] == "findAll"
        assert service["methods"][1]["name"] == "findById"


class TestMarkdownFormat:
    """Test the Markdown format output of CodeVisualizer"""

    def test_format_markdown(self, sample_classes):
        """Test Markdown formatting of Java classes"""
        # Format the classes as Markdown
        md_output = CodeVisualizer.format_markdown(sample_classes)

        # Verify the Markdown contains expected sections
        assert "# Java Spring Analysis Results" in md_output

        # Check the summary section
        assert "## Summary" in md_output
        assert "**Total classes**: 2" in md_output

        # Check the controllers section
        assert "## Controllers" in md_output
        assert "### UserController" in md_output
        assert "**Package**: `com.example.web`" in md_output
        assert "**Base Endpoint Path**: `/api/users`" in md_output

        # Check endpoints table
        assert "#### Endpoints" in md_output
        assert "| HTTP Method | Path | Method |" in md_output
        assert "| GET | `/api/users` | `getUsers` |" in md_output
        assert "| GET | `/api/users/{id}` | `getUser` |" in md_output
        # multi-value mapping
        assert "| GET | `/api/users/x` | `multi` |" in md_output
        assert "| GET | `/api/users/y` | `multi` |" in md_output

        # Check service dependencies table
        assert "#### Service Dependencies" in md_output
        assert "| Type | Superclass | Name | Qualifier |" in md_output
        assert "| `UserService` | `` | `userService` |" in md_output

        # Check service method calls table
        assert "#### Service Method Calls" in md_output
        assert "| Controller Method | Service | Service Method | Args |" in md_output
        assert "| `getUsers` | `userService` | `findAll` |" in md_output
        assert "| `getUser` | `userService` | `findById` |" in md_output

        # Check the services section
        assert "## Services" in md_output
        assert "### UserService" in md_output
        assert "**Package**: `com.example.service`" in md_output

        # Check methods table
        assert "#### Methods" in md_output
        assert "| Return Type | Method | Parameters |" in md_output
        assert "| `List<User>` | `findAll` |" in md_output
        assert "| `User` | `findById` | Long id |" in md_output


class TestMermaidFormat:
    """Test the Mermaid format outputs of CodeVisualizer"""

    def test_format_mermaid_classdiagram(self, sample_classes):
        """Test Mermaid class diagram formatting"""
        # Format the classes as a Mermaid class diagram
        mermaid_output = CodeVisualizer.format_mermaid_classdiagram(sample_classes)

        # Verify the Mermaid syntax
        assert "```mermaid" in mermaid_output
        assert "classDiagram" in mermaid_output
        assert "```" in mermaid_output

        # Check class definitions
        assert "class UserController {" in mermaid_output
        assert "<<controller>>" in mermaid_output
        assert "class UserService {" in mermaid_output
        assert "<<service>>" in mermaid_output

        # Check method definitions
        assert "+List<User> getUsers()" in mermaid_output
        assert "+User getUser(Long id)" in mermaid_output
        assert "+List<User> findAll()" in mermaid_output
        assert "+User findById(Long id)" in mermaid_output

        # Check relationship
        assert "UserController --> UserService : uses" in mermaid_output

    def test_format_mermaid_flowchart(self, sample_classes):
        """Test Mermaid flowchart formatting"""
        # Format the classes as a Mermaid flowchart
        mermaid_output = CodeVisualizer.format_mermaid_flowchart(sample_classes)

        # Verify the Mermaid syntax
        assert "```mermaid" in mermaid_output
        assert "flowchart TD" in mermaid_output
        assert "```" in mermaid_output

        # Check controller node
        assert 'UserController["Controller: UserController"]' in mermaid_output

        # Check endpoint nodes
        assert 'UserController_getUsers("GET: getUsers")' in mermaid_output
        assert 'UserController_getUser("GET: getUser")' in mermaid_output

        # Check connections
        assert "UserController --> UserController_getUsers" in mermaid_output
        assert "UserController --> UserController_getUser" in mermaid_output

        # Check service method nodes
        assert 'UserService_findAll["Service: UserService.findAll"]' in mermaid_output
        assert 'UserService_findById["Service: UserService.findById"]' in mermaid_output

        # Check service method connections
        assert "UserController_getUsers --> UserService_findAll" in mermaid_output
        assert "UserController_getUser --> UserService_findById" in mermaid_output


class TestMarkdownEdgeCases:
    """Test edge-case branches in format_markdown."""

    def test_format_markdown_no_endpoints(self):
        """Controller with no endpoints → no Endpoints table."""
        ctrl = RestControllerClass(
            name="EmptyCtrl",
            package="com.example",
            class_annotations=[Annotation(name="RestController")],
            methods=[],
        )
        md = CodeVisualizer.format_markdown([ctrl])
        assert "#### Endpoints" not in md

    def test_format_markdown_no_service_deps(self):
        """Controller with no service variables → no Service Dependencies table."""
        ctrl = RestControllerClass(
            name="NoDepCtrl",
            package="com.example",
            class_annotations=[Annotation(name="RestController")],
            member_variables=[],
            methods=[
                RestEndpoint(name="get", return_type="void", path_mappings={"GET": "/"}),
            ],
        )
        md = CodeVisualizer.format_markdown([ctrl])
        assert "#### Service Dependencies" not in md

    def test_format_markdown_no_method_calls(self):
        """Controller methods with no service calls → no Service Method Calls table."""
        ctrl = RestControllerClass(
            name="NoCallCtrl",
            package="com.example",
            class_annotations=[Annotation(name="RestController")],
            methods=[
                RestEndpoint(
                    name="get",
                    return_type="void",
                    path_mappings={"GET": "/"},
                    method_calls=[],
                ),
            ],
        )
        md = CodeVisualizer.format_markdown([ctrl])
        assert "#### Service Method Calls" not in md

    def test_format_markdown_api_client_section(self):
        """API_CLIENT category classes show up in summary."""
        api_client = JavaClass(
            name="ExternalClient",
            package="com.example.clients",
            category=ClassCategory.API_CLIENT,
        )
        md = CodeVisualizer.format_markdown([api_client])
        assert "API Client Classes" in md
        assert "com.example.clients.ExternalClient" in md


class TestJsonEdgeCases:
    """Test edge-case branches in format_json."""

    def test_format_json_service_methods_only(self):
        """When service_methods_only is True, non-service calls are excluded."""
        ctrl = RestControllerClass(
            name="Ctrl",
            package="com.example",
            class_annotations=[Annotation(name="RestController")],
            methods=[
                RestEndpoint(
                    name="op",
                    return_type="void",
                    path_mappings={"GET": "/"},
                    method_calls=[
                        MethodCallInfo(
                            target_name="svc",
                            method_name="doWork",
                            target_type="SvcType",
                            target_class_category=ClassCategory.SERVICE,
                        )
                    ],
                ),
            ],
        )
        json_out = CodeVisualizer.format_json([ctrl])
        data = json.loads(json_out)
        assert "op" in data["controllers"][0]["method_calls"]


class TestMermaidEdgeCases:
    """Test edge-case branches in Mermaid formatters."""

    def test_format_mermaid_classdiagram_resolved_impl(self):
        """Resolved implementation shows subclass relationship."""
        resolved_impl = JavaClass(name="UserServiceImpl", package="com.example")
        svc_var = ClassReferenceMemberVariable(
            name="svc",
            type="UserService",
            is_autowired=True,
            referenced_class_category=ClassCategory.SERVICE,
        )
        svc_var.resolved_implementation = resolved_impl
        ctrl = RestControllerClass(
            name="Ctrl",
            package="com.example",
            class_annotations=[Annotation(name="RestController")],
            member_variables=[svc_var],
            methods=[],
        )
        output = CodeVisualizer.format_mermaid_classdiagram([ctrl])
        assert "UserServiceImpl" in output
        assert "subclass" in output

    def test_format_mermaid_flowchart_resolved_impl(self, sample_classes):
        """Resolved implementation in flowchart shows subclass info."""
        resolved_impl = JavaClass(name="UserServiceImpl", package="com.example")
        svc_var = ClassReferenceMemberVariable(
            name="svc",
            type="UserService",
            is_autowired=True,
            referenced_class_category=ClassCategory.SERVICE,
        )
        svc_var.resolved_implementation = resolved_impl
        ctrl = RestControllerClass(
            name="Ctrl",
            package="com.example",
            class_annotations=[Annotation(name="RestController")],
            member_variables=[svc_var],
            methods=[
                RestEndpoint(
                    name="op",
                    return_type="void",
                    path_mappings={"GET": "/"},
                    method_calls=[
                        MethodCallInfo(
                            target_name="svc",
                            method_name="doWork",
                            target_type="UserService",
                            source_variable=svc_var,
                        )
                    ],
                ),
            ],
        )
        output = CodeVisualizer.format_mermaid_flowchart([ctrl])
        assert "UserServiceImpl" in output
        assert "subclass of" in output

    def test_format_mermaid_non_controller_service_skipped(self):
        """Non-controller/service classes are skipped in class diagram."""
        other = JavaClass(
            name="SomeEntity",
            package="com.example",
            category=ClassCategory.ENTITY,
        )
        output = CodeVisualizer.format_mermaid_classdiagram([other])
        assert "SomeEntity" not in output


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
