import tempfile
from pathlib import Path
from typing import Dict, List

import pytest

from app.src.codeanalyzer.analyzer import JavaAnalyzer
from app.src.codeanalyzer.models import (
    Annotation,
    ClassCategory,
    ClassReferenceMemberVariable,
    JavaClass,
    JavaMethod,
    MethodCallInfo,
    Parameter,
    RestControllerClass,
    RestEndpoint,
    ServiceClass,
)


@pytest.fixture
def constants_map() -> dict[str, str]:
    """Constants map for testing variable resolution"""
    return {
        "ApplicationConstants.AUTHORIZATION": "Authorization",
        "ApplicationConstants.CALLER_IDENTITY": "X-Caller-Ref",
        "ApplicationConstants.GROUP_ID": "X-Group-Ref",
        "OrganizationConstants.COMMA": ",",
        "ApiConstants.API_BASE_PATH": "/api/v2",
        "AppConstants.API_PREFIX": "/api/constants",
        "AppConstants.GET_DATA_PATH": "/data",
        "HeaderConstants.AUTH_HEADER": "X-Auth-Token",
        "HeaderConstants.TENANT_ID": "X-Tenant-ID",
        "ApiConstants.SEARCH_PATH": "/search",
    }


@pytest.fixture
def sample_controllers() -> list[RestControllerClass]:
    """Fixture to create sample controllers for testing"""
    # Controller 1
    controller1 = RestControllerClass(
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
                    )
                ],
            ),
        ],
        filename="UserController.java",
        relative_path="com/example/web/UserController.java",
        absolute_path="/path/to/com/example/web/UserController.java",
    )

    # Controller 2
    controller2 = RestControllerClass(
        name="ProductController",
        package="com.example.web",
        class_annotations=[
            Annotation(name="RestController"),
            Annotation(name="RequestMapping", values={"value": "/api/products"}),
        ],
        member_variables=[
            ClassReferenceMemberVariable(
                name="productService",
                type="ProductService",
                is_autowired=True,
                referenced_class_category=ClassCategory.SERVICE,
            )
        ],
        methods=[
            RestEndpoint(
                name="getProducts",
                return_type="List<Product>",
                path_mappings={"GET": ""},
                method_calls=[
                    MethodCallInfo(
                        target_name="productService",
                        method_name="findAll",
                        target_type="ProductService",
                    )
                ],
            )
        ],
        filename="ProductController.java",
        relative_path="com/example/web/ProductController.java",
        absolute_path="/path/to/com/example/web/ProductController.java",
    )

    # Controller 3: with a long/complex endpoint path for substring testing
    controller3 = RestControllerClass(
        name="OrderController",
        package="com.example.web",
        class_annotations=[
            Annotation(name="RestController"),
            Annotation(name="RequestMapping", values={"value": "/api/orders/v2/long/path"}),
        ],
        member_variables=[
            ClassReferenceMemberVariable(
                name="orderService",
                type="OrderService",
                is_autowired=True,
                referenced_class_category=ClassCategory.SERVICE,
            )
        ],
        methods=[
            RestEndpoint(
                name="getOrders",
                return_type="List<Order>",
                path_mappings={"GET": "/history"},
                method_calls=[
                    MethodCallInfo(
                        target_name="orderService",
                        method_name="findHistory",
                        target_type="OrderService",
                    )
                ],
            )
        ],
        filename="OrderController.java",
        relative_path="com/example/web/OrderController.java",
        absolute_path="/path/to/com/example/web/OrderController.java",
    )

    return [controller1, controller2, controller3]


@pytest.fixture
def sample_services() -> list[ServiceClass]:
    """Fixture to create sample services for testing"""
    # Service 1
    service1 = ServiceClass(
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
        filename="UserService.java",
        relative_path="com/example/service/UserService.java",
        absolute_path="/path/to/com/example/service/UserService.java",
    )

    # Service 2
    service2 = ServiceClass(
        name="ProductService",
        package="com.example.service",
        class_annotations=[Annotation(name="Service")],
        methods=[JavaMethod(name="findAll", return_type="List<Product>")],
        filename="ProductService.java",
        relative_path="com/example/service/ProductService.java",
        absolute_path="/path/to/com/example/service/ProductService.java",
    )

    return [service1, service2]


@pytest.fixture
def sample_analyzer(sample_controllers, sample_services):
    """Fixture to create a sample analyzer with controllers and services"""
    analyzer = JavaAnalyzer()

    # Add controllers and services to the analyzer
    for controller in sample_controllers:
        analyzer.classes[controller.fully_qualified_name] = controller

    for service in sample_services:
        analyzer.classes[service.fully_qualified_name] = service

    # Add a matching OrderService for the new controller
    order_service = ServiceClass(
        name="OrderService",
        package="com.example.service",
        class_annotations=[Annotation(name="Service")],
        methods=[JavaMethod(name="findHistory", return_type="List<Order>")],
        filename="OrderService.java",
        relative_path="com/example/service/OrderService.java",
        absolute_path="/path/to/com/example/service/OrderService.java",
    )
    analyzer.classes[order_service.fully_qualified_name] = order_service

    return analyzer


@pytest.fixture
def mock_analyzer():
    """Heavily mocked analyzer for unit tests"""
    analyzer = JavaAnalyzer()
    # Classes dictionary is empty by default, can be populated in tests
    return analyzer


@pytest.fixture
def temp_java_files():
    """Generator for temporary Java test files for integration tests"""
    temp_dir = tempfile.mkdtemp()
    temp_path = Path(temp_dir)

    def _create_file(filename: str, content: str) -> str:
        file_path = temp_path / filename
        file_path.write_text(content)
        return str(file_path)

    yield _create_file

    # Cleanup
    import shutil

    shutil.rmtree(temp_dir)


@pytest.fixture
def real_parsed_analyzer():
    """Clean analyzer instance for integration tests with real parsing"""
    return JavaAnalyzer()
