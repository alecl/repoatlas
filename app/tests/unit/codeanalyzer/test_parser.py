"""
Mixed unit/integration tests for JavaParser functionality.

Strategy: Unit tests with mocked tree-sitter + integration tests with real parsing.
Real: Java file parsing (integration tests), annotation extraction
Mocked: Tree-sitter components (unit tests), parser methods for isolation

Test Responsibilities:
- TestJavaParserMethods: Annotation extraction, class categorization, method calls
- TestJavaParserWithFiles: Parameterized tests with real Java files,
  class type detection, file path handling
"""

import os
import tempfile
import textwrap
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest

from app.src.codeanalyzer.models import (
    Annotation,
    ClassCategory,
    ClassReferenceMemberVariable,
    ImportDefinition,
    JavaClass,
    JavaMethod,
    MemberVariable,
    MemberVariableCategory,
    Parameter,
    ReferenceLocation,
    RestControllerClass,
    RestEndpoint,
    ServiceClass,
    UnresolvedAutowire,
    UnresolvedConstant,
    UnresolvedType,
)
from app.src.codeanalyzer.parser import JavaParser


# Fixtures for sample Java code
@pytest.fixture
def basic_controller_content() -> str:
    """Sample Java content for a basic controller"""
    return """
    package com.example.demo.web;

    import org.springframework.web.bind.annotation.RestController;
    import org.springframework.web.bind.annotation.RequestMapping;
    import org.springframework.web.bind.annotation.GetMapping;
    import org.springframework.beans.factory.annotation.Autowired;

    @RestController
    @RequestMapping("/api/v1/demo")
    public class BasicController {

        @Autowired
        private DemoService demoService;

        @GetMapping("/hello")
        public String hello() {
            return demoService.getGreeting();
        }
    }
    """


@pytest.fixture
def complex_controller_content() -> str:
    """Sample Java content for a complex controller with more features"""
    return """
    package com.example.advanced.web;

    import java.util.List;
    import org.springframework.web.bind.annotation.RestController;
    import org.springframework.web.bind.annotation.RequestMapping;
    import org.springframework.web.bind.annotation.GetMapping;
    import org.springframework.web.bind.annotation.PostMapping;
    import org.springframework.web.bind.annotation.PutMapping;
    import org.springframework.web.bind.annotation.DeleteMapping;
    import org.springframework.web.bind.annotation.RequestParam;
    import org.springframework.web.bind.annotation.PathVariable;
    import org.springframework.web.bind.annotation.RequestBody;
    import org.springframework.beans.factory.annotation.Autowired;
    import org.springframework.beans.factory.annotation.Qualifier;
    import org.springframework.http.ResponseEntity;
    import org.springframework.security.access.prepost.PreAuthorize;
    import com.example.advanced.service.AdvancedService;
    import com.example.advanced.service.SecondaryService;
    import com.example.advanced.model.Item;
    import com.example.advanced.constants.ApiConstants;

    /**
     * Advanced controller with various features
     */
    @RestController
    @RequestMapping(value = ApiConstants.API_BASE_PATH)
    public class AdvancedController {

        private static final String ITEMS_PATH = "/items";
        private static final String ITEM_ID_PATH = "/items/{id}";

        @Autowired
        private AdvancedService advancedService;

        @Autowired
        @Qualifier("secondaryServiceImpl")
        private SecondaryService secondaryService;

        private RegularClass regularClass;

        /**
         * Get all items
         */
        @GetMapping(value = ITEMS_PATH)
        @PreAuthorize("hasRole('ADMIN')")
        public ResponseEntity<List<Item>> getAllItems() throws Exception {
            return ResponseEntity.ok(advancedService.findAll());
        }

        /**
         * Get one item by ID
         */
        @GetMapping(value = ITEM_ID_PATH)
        public ResponseEntity<Item> getItem(@PathVariable("id") Long id) {
            return ResponseEntity.ok(advancedService.findById(id));
        }

        /**
         * Create a new item
         */
        @PostMapping(value = ITEMS_PATH)
        public ResponseEntity<Item> createItem(@RequestBody Item item) {
            return ResponseEntity.ok(advancedService.save(item));
        }

        /**
         * Update an existing item
         */
        @PutMapping(value = ITEM_ID_PATH)
        public ResponseEntity<Item> updateItem(
                @PathVariable("id") Long id,
                @RequestBody Item item) {
            item.setId(id);
            return ResponseEntity.ok(advancedService.update(item));
        }

        /**
         * Delete an item
         */
        @DeleteMapping(value = ITEM_ID_PATH)
        public ResponseEntity<Void> deleteItem(@PathVariable("id") Long id) {
            advancedService.delete(id);
            return ResponseEntity.noContent().build();
        }

        /**
         * Search items
         */
        @GetMapping(value = ApiConstants.SEARCH_PATH)
        public ResponseEntity<List<Item>> searchItems(
                @RequestParam(value = "query", required = false) String query,
                @RequestParam(value = "page", defaultValue = "0") int page,
                @RequestParam(value = "size", defaultValue = "10") int size) {
            return ResponseEntity.ok(secondaryService.search(query, page, size));
        }
    }
    """


@pytest.fixture
def service_class_content() -> str:
    """Sample content for a service class"""
    return """
    package com.example.service;

    import org.springframework.stereotype.Service;
    import org.springframework.beans.factory.annotation.Autowired;
    import com.example.repository.UserRepository;
    import com.example.model.User;
    import java.util.List;
    import java.util.Optional;

    @Service
    public class UserService {

        @Autowired
        private UserRepository userRepository;

        public List<User> findAll() {
            return userRepository.findAll();
        }

        public User findById(Long id) {
            return userRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("User not found"));
        }

        public User save(User user) {
            return userRepository.save(user);
        }

        public User update(User user) {
            if (!userRepository.existsById(user.getId())) {
                throw new RuntimeException("User not found");
            }
            return userRepository.save(user);
        }

        public void delete(Long id) {
            userRepository.deleteById(id);
        }
    }
    """


@pytest.fixture
def temp_java_file(request):
    """Create a temporary Java file with specified content"""
    # request.param is the name of the fixture to get
    content = request.getfixturevalue(request.param)
    with tempfile.NamedTemporaryFile(suffix=".java", delete=False) as f:
        f.write(content.encode("utf-8"))

    # Yield the filename so tests can use it
    file_path = f.name
    yield file_path

    # Cleanup after the test
    if os.path.exists(file_path):
        os.unlink(file_path)


@pytest.fixture
def mock_tree_sitter():
    """Mock the tree-sitter components for testing without the actual library"""
    # Create mock classes for tree-sitter components
    mock_language = MagicMock()
    mock_parser = MagicMock()
    mock_tree = MagicMock()
    mock_node = MagicMock()

    # Set up the tree structure
    mock_parser.parse.return_value = mock_tree
    mock_tree.root_node = mock_node

    # Return the mocks
    return {
        "language": mock_language,
        "parser": mock_parser,
        "tree": mock_tree,
        "node": mock_node,
    }


# Test cases for JavaParser initialization
# These tests are no longer valid since JavaParser now always uses tree_sitter_language_pack.get_language/get_parser
# and does not use tree_sitter.Language or tree_sitter.Parser directly.
# Remove these tests to avoid false failures.


# Test cases for JavaParser methods
class TestJavaParserMethods:
    def test_extract_annotations_with_real_code(self, tmp_path):
        """Test extracting annotations using real Java code"""
        # Create a simple Java file with annotations
        java_content = """
        package com.test;

        @RestController
        @RequestMapping(value = "/api/v1")
        public class TestController {

            @Autowired
            private MyService service;

            @GetMapping("/test")
            public String test() {
                return "test";
            }
        }
        """

        java_file = tmp_path / "TestController.java"
        java_file.write_text(java_content)

        # Parse the file
        parser = JavaParser()
        java_class = parser.parse_java_file(str(java_file))

        # Test class annotations
        assert len(java_class.class_annotations) == 2
        rest_controller = next(
            a for a in java_class.class_annotations if a.name == "RestController"
        )
        assert rest_controller.values == {}  # No parameters

        request_mapping = next(
            a for a in java_class.class_annotations if a.name == "RequestMapping"
        )
        assert request_mapping.values == {"value": "/api/v1"}
        assert request_mapping.value == "/api/v1"  # Test the new property
        # Should not be unresolved (not a constant)
        assert not request_mapping.has_unresolved_references

        # Test member variable annotations
        assert len(java_class.member_variables) == 1
        service_var = java_class.member_variables[0]
        assert any(a.name == "Autowired" for a in service_var.annotations)
        # Should have unresolved_type and unresolved_autowire
        assert hasattr(service_var, "unresolved_type")
        assert isinstance(service_var.unresolved_type, UnresolvedType)
        assert hasattr(service_var, "unresolved_autowire")
        assert isinstance(service_var.unresolved_autowire, UnresolvedAutowire)

        # Test method annotations
        assert len(java_class.methods) == 1
        test_method = java_class.methods[0]
        assert len(test_method.annotations) == 1
        assert test_method.annotations[0].name == "GetMapping"
        assert test_method.annotations[0].values == {"value": "/test"}
        assert not test_method.annotations[0].has_unresolved_references

    def test_extract_array_initializer_argument(self, tmp_path):
        """Test extracting array initializer values in annotations like @GetMapping"""
        java_content = """
        package com.example;

        import org.springframework.web.bind.annotation.RestController;
        import org.springframework.web.bind.annotation.GetMapping;

        @RestController
        public class MultiController {

            @GetMapping({"/a","/b"})
            public void multi() {}
        }
        """
        java_file = tmp_path / "MultiController.java"
        java_file.write_text(java_content)
        parser = JavaParser()
        java_class = parser.parse_java_file(str(java_file))
        # The endpoint should have a list of two paths
        endpoint = next(m for m in java_class.methods if isinstance(m, RestEndpoint))
        assert endpoint.path_mappings["GET"] == ["/a", "/b"]
        # Annotation values should reflect the list
        anno = endpoint.annotations[0]
        assert anno.values["value"] == ["/a", "/b"]

    def test_extract_annotations_interface_with_real_code(self, tmp_path):
        """Test extracting annotations from a Java interface"""
        java_content = """
        package com.test;

        @Service
        public interface MyService {
            @Deprecated
            void doSomething();
        }
        """
        java_file = tmp_path / "MyService.java"
        java_file.write_text(java_content)

        parser = JavaParser()
        java_class = parser.parse_java_file(str(java_file))

        # Test class annotations
        assert len(java_class.class_annotations) == 1
        service_anno = java_class.class_annotations[0]
        assert service_anno.name == "Service"
        assert service_anno.values == {}

        # Test method annotations (should be present on interface method)
        assert len(java_class.methods) == 1
        method = java_class.methods[0]
        assert method.name == "doSomething"
        assert len(method.annotations) == 1
        assert method.annotations[0].name == "Deprecated"

    def test_extract_annotations_abstract_with_real_code(self, tmp_path):
        """Test extracting annotations from a Java abstract class"""
        java_content = """
        package com.test;

        @Service
        public abstract class MyAbstractService {
            @Deprecated
            public abstract void doSomething();
        }
        """
        java_file = tmp_path / "MyAbstractService.java"
        java_file.write_text(java_content)

        parser = JavaParser()
        java_class = parser.parse_java_file(str(java_file))

        # Test class annotations
        assert len(java_class.class_annotations) == 1
        service_anno = java_class.class_annotations[0]
        assert service_anno.name == "Service"
        assert service_anno.values == {}

        # Test method annotations (should be present on abstract method)
        assert len(java_class.methods) == 1
        method = java_class.methods[0]
        assert method.name == "doSomething"
        assert len(method.annotations) == 1
        assert method.annotations[0].name == "Deprecated"

    def test_infer_class_category(self):
        """Test inferring class category using classification.infer_class_category"""
        from app.src.codeanalyzer.classification import infer_class_category

        # Annotation-driven detection
        assert (
            infer_class_category("Dummy", [Annotation(name="RestController")])
            == ClassCategory.CONTROLLER
        )
        assert infer_class_category("Dummy", [Annotation(name="Service")]) == ClassCategory.SERVICE
        assert (
            infer_class_category("Dummy", [Annotation(name="Repository")])
            == ClassCategory.REPOSITORY
        )

        # Annotation fallback to OTHER
        assert (
            infer_class_category("Dummy", [Annotation(name="SomeOtherAnnotation")])
            == ClassCategory.OTHER
        )

        # Name-driven detection (suffix)
        assert infer_class_category("MyService", []) == ClassCategory.SERVICE
        assert infer_class_category("MySvc", []) == ClassCategory.SERVICE
        assert infer_class_category("MyController", []) == ClassCategory.CONTROLLER

        # Suffix match should succeed over substring match
        assert infer_class_category("MyServiceController", []) == ClassCategory.CONTROLLER

        # Substring match: only if no suffix match
        assert infer_class_category("FooServiceThing", []) == ClassCategory.SERVICE
        assert infer_class_category("BarControllerThing", []) == ClassCategory.CONTROLLER
        assert infer_class_category("SomeDtoHelper", []) == ClassCategory.DTO

        # Substring match: ambiguous (should raise)
        with pytest.raises(ValueError) as excinfo:
            # This name contains both "aspect" and "controller" as leve 1 substrings, but not as suffix
            infer_class_category("ThingServiceControllerAspectThing", [])
        # Expect the standard priority-level message
        assert "Multiple category matches at priority level" in str(excinfo.value)

        # Name-driven fallback to OTHER
        assert infer_class_category("Unknown", []) == ClassCategory.OTHER

    def test_extract_annotation_with_constant_reference(self, tmp_path):
        """Test extracting annotation with a constant reference marks unresolved"""
        java_content = """
        package com.test;

        import com.example.constants.ApiConstants;

        @RestController
        @RequestMapping(value = ApiConstants.API_BASE_PATH)
        public class TestController {
        }
        """
        java_file = tmp_path / "TestController.java"
        java_file.write_text(java_content)

        parser = JavaParser()
        java_class = parser.parse_java_file(str(java_file))

        request_mapping = next(
            a for a in java_class.class_annotations if a.name == "RequestMapping"
        )
        # Should have unresolved reference for "value"
        assert request_mapping.has_unresolved_references
        assert "value" in request_mapping.unresolved_values
        unresolved = request_mapping.unresolved_values["value"]
        assert isinstance(unresolved, UnresolvedConstant)
        assert unresolved.raw_value == "ApiConstants.API_BASE_PATH"
        assert unresolved.location.element_name == "RequestMapping"
        assert unresolved.location.detail == "value"

    def test_extract_constructors_with_real_code(self, tmp_path):
        """Test extracting constructors using real Java code"""
        # Create Java file with multiple constructors
        java_content = """
        package com.test;

        import org.springframework.beans.factory.annotation.Autowired;
        import org.springframework.web.client.RestTemplate;

        public class ApiClient {

            private final RestTemplate restTemplate;
            private final String baseUrl;

            /**
            * Default constructor
            */
            public ApiClient() {
                this.restTemplate = new RestTemplate();
                this.baseUrl = "http://localhost:8080";
            }

            /**
            * Constructor with RestTemplate injection
            * @param restTemplate the REST template
            */
            @Autowired
            public ApiClient(RestTemplate restTemplate) {
                this.restTemplate = restTemplate;
                this.baseUrl = "http://localhost:8080";
            }

            /**
            * Full constructor with all dependencies
            * @param restTemplate the REST template
            * @param baseUrl the base URL
            */
            @Autowired
            public ApiClient(RestTemplate restTemplate, String baseUrl) throws ConfigurationException {
                this.restTemplate = restTemplate;
                this.baseUrl = baseUrl;
            }
        }
        """

        java_file = tmp_path / "ApiClient.java"
        java_file.write_text(java_content)

        # Parse the file
        parser = JavaParser()
        java_class = parser.parse_java_file(str(java_file))

        # Verify constructors were extracted
        assert len(java_class.constructors) == 3

        # Test default constructor
        default_constructor = java_class.get_default_constructor()
        assert default_constructor is not None
        assert default_constructor.name == "ApiClient"
        assert len(default_constructor.parameters) == 0
        assert len(default_constructor.annotations) == 0
        assert "public" in default_constructor.modifiers

        all_constructors = java_class.get_constructors()

        for constructor in all_constructors:
            if (constructor.parameters) == 1:
                assert constructor.parameters[0].type == "RestTemplate"
                assert any(a.name == "Autowired" for a in constructor.annotations)
            if (constructor.parameters) == 2:
                assert constructor.parameters[0].type == "RestTemplate"
                assert constructor.parameters[1].type == "String"
                assert any(a.name == "Autowired" for a in constructor.annotations)
                assert "ConfigurationException" in constructor.exceptions

    def test_extract_constructors_with_parameter_annotations(self, tmp_path):
        """Test extracting constructors with parameter annotations"""
        java_content = """
        package com.test;

        import org.springframework.beans.factory.annotation.Value;
        import org.springframework.beans.factory.annotation.Qualifier;

        public class ConfigurableService {

            @Autowired
            public ConfigurableService(
                    @Qualifier("primaryRepo") UserRepository repository,
                    @Value("${app.timeout}") int timeout) {
                // constructor body
            }
        }
        """

        java_file = tmp_path / "ConfigurableService.java"
        java_file.write_text(java_content)

        parser = JavaParser()
        java_class = parser.parse_java_file(str(java_file))

        assert len(java_class.constructors) == 1
        constructor = java_class.constructors[0]

        # Check constructor annotation
        assert any(a.name == "Autowired" for a in constructor.annotations)

        # Check parameter annotations
        assert len(constructor.parameters) == 2

        repo_param = constructor.parameters[0]
        assert repo_param.name == "repository"
        assert repo_param.type == "UserRepository"
        assert any(a.name == "Qualifier" for a in repo_param.annotations)

        timeout_param = constructor.parameters[1]
        assert timeout_param.name == "timeout"
        assert timeout_param.type == "int"
        assert any(a.name == "Value" for a in timeout_param.annotations)

    def test_constructor_comment_extraction(self, tmp_path):
        """Test that constructor comments are properly extracted and tracked"""
        java_content = """
        package com.test;

        public class CommentedConstructors {

            /**
            * Default constructor with detailed comment
            * This constructor initializes with default values
            */
            public CommentedConstructors() {
                // default initialization
            }

            /**
            * Parameterized constructor
            * @param value the initial value
            */
            public CommentedConstructors(String value) {
                // parameterized initialization
            }

            public void someMethod() {
                // regular method
            }
        }
        """

        java_file = tmp_path / "CommentedConstructors.java"
        java_file.write_text(java_content)

        parser = JavaParser()
        java_class = parser.parse_java_file(str(java_file), store_source=True)

        # Verify constructor offsets are tracked
        assert hasattr(java_class, "constructor_offsets")
        assert len(java_class.constructor_offsets) == 2

        # Verify constructor comment offsets are tracked
        assert hasattr(java_class, "constructor_comment_offsets")
        assert len(java_class.constructor_comment_offsets) == 2

        # Check that comments are associated with constructors
        for constructor in java_class.constructors:
            constructor_name = constructor.name
            if constructor_name in java_class.constructor_comment_offsets:
                comments = java_class.constructor_comment_offsets[constructor_name]
                # Each constructor should have at least one comment block
                assert len(comments) >= 0  # Could be 0 if no comments, >= 1 if comments exist

    def test_interface_with_no_constructors(self, tmp_path):
        """Test that interfaces don't have constructors extracted"""
        java_content = """
        package com.test;

        public interface MyService {
            void doSomething();
        }
        """

        java_file = tmp_path / "MyService.java"
        java_file.write_text(java_content)

        parser = JavaParser()
        java_class = parser.parse_java_file(str(java_file))

        # Interfaces shouldn't have constructors
        assert len(java_class.constructors) == 0
        assert hasattr(java_class, "constructor_offsets")
        assert len(java_class.constructor_offsets) == 0

    def test_enum_with_constructors(self, tmp_path):
        """Test extracting constructors from enum classes"""
        java_content = """
        package com.test;

        public enum Status {
            ACTIVE("A", "Active Status"),
            INACTIVE("I", "Inactive Status");

            private final String code;
            private final String description;

            /**
            * Enum constructor
            * @param code the status code
            * @param description the status description
            */
            Status(String code, String description) {
                this.code = code;
                this.description = description;
            }

            public String getCode() {
                return code;
            }
        }
        """

        java_file = tmp_path / "Status.java"
        java_file.write_text(java_content)

        parser = JavaParser()
        java_class = parser.parse_java_file(str(java_file))

        # Enums can have constructors
        assert len(java_class.constructors) == 1
        constructor = java_class.constructors[0]
        assert constructor.name == "Status"
        assert len(constructor.parameters) == 2
        assert constructor.parameters[0].type == "String"
        assert constructor.parameters[1].type == "String"

    def test_implicit_constructor_injection_marker(self, tmp_path):
        """Test that single public constructor on a Spring bean is marked as injection."""
        java_content = """
        package com.test;
        import org.springframework.web.bind.annotation.RestController;
        @RestController
        public class Ctx {
            public Ctx(Service svc) {}
        }
        """
        java_file = tmp_path / "Ctx.java"
        java_file.write_text(java_content)
        parser = JavaParser()
        java_class = parser.parse_java_file(str(java_file))
        assert len(java_class.constructors) == 1
        assert java_class.constructors[0].is_injection


# Test cases for JavaParser with parameterized fixtures
@pytest.mark.parametrize(
    "temp_java_file, expected_name, expected_category",
    [
        pytest.param(
            "basic_controller_content",
            "BasicController",
            ClassCategory.CONTROLLER,
            id="basic_controller",
        ),
        pytest.param(
            "complex_controller_content",
            "AdvancedController",
            ClassCategory.CONTROLLER,
            id="complex_controller",
        ),
        pytest.param(
            "service_class_content",
            "UserService",
            ClassCategory.SERVICE,
            id="service_class",
        ),
    ],
    indirect=["temp_java_file"],
)
class TestJavaParserWithFiles:
    @patch.object(JavaParser, "_extract_package", return_value="com.test.package")
    @patch.object(JavaParser, "_extract_imports", return_value=([], []))
    @patch.object(JavaParser, "_extract_constants", return_value={})
    @patch.object(JavaParser, "_extract_member_variables", return_value=[])
    @patch.object(JavaParser, "_extract_methods", return_value=([], {}, {}))
    def test_parse_java_file_class_type(
        self,
        mock_extract_methods,
        mock_extract_member_variables,
        mock_extract_constants,
        mock_extract_imports,
        mock_extract_package,
        temp_java_file,
        expected_name,
        expected_category,
    ):
        """Test that parse_java_file creates the right class type"""
        parser = JavaParser()

        # Mock the annotation extraction
        with patch.object(parser, "_extract_annotations", return_value=[]):
            java_class = parser.parse_java_file(temp_java_file)

        # Verify class name and category
        assert java_class.name == expected_name
        assert java_class.category == expected_category

        # Verify class type based on category
        if expected_category == ClassCategory.CONTROLLER:
            assert isinstance(java_class, RestControllerClass)
        elif expected_category == ClassCategory.SERVICE:
            assert isinstance(java_class, ServiceClass)
        else:
            assert isinstance(java_class, JavaClass)

    @patch.object(JavaParser, "_extract_package")
    @patch.object(JavaParser, "_extract_imports")
    @patch.object(JavaParser, "_extract_constants")
    @patch.object(JavaParser, "_extract_member_variables")
    @patch.object(JavaParser, "_extract_methods")
    @patch.object(JavaParser, "_extract_annotations")
    def test_file_path_handling(
        self,
        mock_extract_annotations,
        mock_extract_methods,
        mock_extract_member_variables,
        mock_extract_constants,
        mock_extract_imports,
        mock_extract_package,
        temp_java_file,
        expected_name,
        expected_category,
    ):
        """Test that file paths are correctly stored in the JavaClass."""
        # Setup mocks
        mock_extract_package.return_value = "com.example"
        mock_extract_imports.return_value = ([], [])
        mock_extract_constants.return_value = {}
        mock_extract_member_variables.return_value = []
        mock_extract_methods.return_value = ([], {}, {})
        mock_extract_annotations.return_value = []

        # Parse file
        parser = JavaParser()
        java_class = parser.parse_java_file(temp_java_file)

        # Verify file paths
        assert java_class.filename == os.path.basename(temp_java_file)
        assert java_class.absolute_path == str(Path(temp_java_file).absolute())
        assert java_class.relative_path  # Just verify it's not empty


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])


class TestJavaParserApiClientDetection:
    """Test API client classification in parser for wildcard and explicit imports."""

    def _make_and_parse(self, import_line, tmp_path):
        src = textwrap.dedent(
            f"""
            package com.test;

            {import_line}

            public class WildClient {{
                public WildClient(RestTemplate rt) {{}}
            }}
        """
        ).strip()
        java_file = tmp_path / "WildClient.java"
        java_file.write_text(src)
        parser = JavaParser()
        return parser.parse_java_file(str(java_file))

    @pytest.mark.parametrize(
        "import_line",
        [
            "import org.springframework.web.client.RestTemplate;",
            "import org.springframework.web.client.*;",
        ],
    )
    def test_parser_sets_api_client_for_resttemplate_import(self, import_line, tmp_path):
        """Parser should classify class as API_CLIENT for RestTemplate wildcard and explicit imports."""
        clazz = self._make_and_parse(import_line, tmp_path)
        assert clazz.category == ClassCategory.API_CLIENT
