"""
Integration tests for JavaAnalyzer with real file parsing and component interactions.

Strategy: Real Java file parsing with minimal mocking for end-to-end workflows.
Real: Java file parsing, analyzer with real resolvers, temp file I/O,
      full resolution pipeline
Mocked: Minimal (only for error scenario testing and some file operations)

Test Responsibilities:
- TestAnalyzerFileOperations: File parsing, directory operations, error handling
- TestRealJavaFiles: End-to-end parsing of various Java constructs
  (controllers, services, interfaces, abstract classes, Spring annotations)
- TestResolverIntegration: Cross-resolver integration scenarios,
  chained constant resolution
"""

import os
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.src.codeanalyzer.analyzer import JavaAnalyzer
from app.src.codeanalyzer.autowire_resolver import AmbiguousBeanReferenceError
from app.src.codeanalyzer.models import (
    ClassCategory,
    ClassReferenceMemberVariable,
    JavaClass,
    RestControllerClass,
    ServiceClass,
)
from app.src.codeanalyzer.parser import JavaParser


class TestAnalyzerFileOperations:
    """Test file parsing operations in the JavaAnalyzer class - integration tests"""

    @patch.object(JavaParser, "parse_java_file")
    def test_parse_file(self, mock_parse_java_file):
        """Test parsing a single file"""
        # Setup mock
        mock_class = JavaClass(name="TestClass", package="com.test")
        mock_parse_java_file.return_value = mock_class

        # Create test instance
        analyzer = JavaAnalyzer()

        # Call the method
        result = analyzer.parse_file("test.java")

        # Verify correct behavior
        mock_parse_java_file.assert_called_once_with("test.java")
        assert result == mock_class
        assert analyzer.classes == {"com.test.TestClass": mock_class}

    def test_parse_directory(self, mocker, tmp_path):
        """Test parsing a directory"""
        # Create test directory with Java files
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        (test_dir / "Test1.java").touch()
        (test_dir / "Test2.java").touch()
        (test_dir / "subdir").mkdir()
        (test_dir / "subdir" / "Test3.java").touch()

        # Setup mock classes
        mock_class1 = JavaClass(name="Test1", package="com.test")
        mock_class2 = JavaClass(name="Test2", package="com.test")
        mock_class3 = JavaClass(name="Test3", package="com.test.subdir")

        # Create a custom side effect that adds classes to analyzer.classes
        def parse_file_side_effect(file_path):
            if "Test1.java" in file_path:
                return_class = mock_class1
            elif "Test2.java" in file_path:
                return_class = mock_class2
            elif "Test3.java" in file_path:
                return_class = mock_class3
            else:
                return None

            # This is what the real parse_file does - add to classes dictionary
            analyzer.classes[return_class.fully_qualified_name] = return_class
            return return_class

        # Create analyzer instance first
        analyzer = JavaAnalyzer()

        # Mock parse_file with our custom side effect AFTER creating the analyzer
        mock_parse_file = mocker.patch.object(
            JavaAnalyzer, "parse_file", side_effect=parse_file_side_effect
        )

        # Mock os.walk to return our test files
        mocker.patch(
            "os.walk",
            return_value=[
                (str(test_dir), ["subdir"], ["Test1.java", "Test2.java"]),
                (str(test_dir / "subdir"), [], ["Test3.java"]),
            ],
        )

        # Call the method with recursive=True
        results = analyzer.parse_directory(str(test_dir), recursive=True)

        # Verify parse_file was called for each Java file
        assert mock_parse_file.call_count == 3
        assert len(results) == 3

        # Verify the classes are in the analyzer's classes dictionary
        assert "com.test.Test1" in analyzer.classes
        assert "com.test.Test2" in analyzer.classes
        assert "com.test.subdir.Test3" in analyzer.classes

    @patch.object(JavaParser, "parse_java_file")
    def test_parse_file_error_handling(self, mock_parse):
        """Test error handling when parsing a file fails"""
        # Setup mock to raise an exception
        mock_parse.side_effect = ValueError("Invalid Java file")

        # Create analyzer
        analyzer = JavaAnalyzer()

        # Verify exception propagation
        with pytest.raises(ValueError, match="Invalid Java file"):
            analyzer.parse_file("invalid.java")

    @patch.object(JavaParser, "parse_java_file")
    def test_parse_directory_error_handling(self, mock_parse, tmp_path):
        """Test error handling when parsing a directory with some invalid files"""
        # Create test directory with Java files
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        (test_dir / "valid1.java").touch()
        (test_dir / "valid2.java").touch()
        (test_dir / "invalid.java").touch()

        # Setup mock to raise an exception for the invalid file
        def parse_side_effect(file_path):
            if "invalid.java" in file_path:
                raise ValueError("Invalid Java file")
            return JavaClass(name=f"Class_{os.path.basename(file_path)}", package="com.test")

        mock_parse.side_effect = parse_side_effect

        # Create analyzer
        analyzer = JavaAnalyzer()

        # Parse directory with mocked os functions
        with (
            patch(
                "os.walk",
                return_value=[(str(test_dir), [], ["valid1.java", "valid2.java", "invalid.java"])],
            ),
            patch(
                "os.listdir",
                return_value=["valid1.java", "valid2.java", "invalid.java"],
            ),
            patch("logging.Logger.error"),
        ):  # Suppress error logs
            classes = analyzer.parse_directory(str(test_dir))

        # Verify valid files were parsed
        assert len(classes) == 2
        assert any(cls.name == "Class_valid1.java" for cls in classes)
        assert any(cls.name == "Class_valid2.java" for cls in classes)


class TestRealJavaFiles:
    """Test parsing of real Java files with minimal mocking - integration tests"""

    def test_spring_controller_with_qualified_annotations(self, tmp_path):
        """Test parsing a Spring controller with fully qualified annotations"""
        # Sample Spring controller with fully qualified annotations
        controller_content = """
        package com.example.web;

        import java.util.List;
        import java.util.stream.Collectors;
        import org.springframework.beans.factory.annotation.Autowired;
        import org.springframework.http.ResponseEntity;

        @org.springframework.web.bind.annotation.RestController
        @org.springframework.web.bind.annotation.RequestMapping("/api/users")
        public class UserController {

            @org.springframework.beans.factory.annotation.Autowired
            private UserService userService;

            @org.springframework.web.bind.annotation.GetMapping("")
            public List<User> getAllUsers() {
                return userService.findAll();
            }

            @org.springframework.web.bind.annotation.GetMapping("/{id}")
            public ResponseEntity<User> getUser(
                @org.springframework.web.bind.annotation.PathVariable("id") Long id) {
                return ResponseEntity.ok(userService.findById(id));
            }

            @org.springframework.web.bind.annotation.PostMapping("")
            public User createUser(
                @org.springframework.web.bind.annotation.RequestBody User user) {
                return userService.save(user);
            }
        }
        """

        # Create a temporary file
        java_file = tmp_path / "UserController.java"
        dedented_content = textwrap.dedent(controller_content).strip()
        java_file.write_text(dedented_content)

        # Parse the file
        parser = JavaParser()
        java_class = parser.parse_java_file(str(java_file))

        # Verify correct class detection
        assert java_class.name == "UserController"
        assert java_class.package == "com.example.web"
        assert java_class.category == ClassCategory.CONTROLLER
        assert isinstance(java_class, RestControllerClass)

        # Verify base path
        assert java_class.base_endpoint_path == "/api/users"

        # Verify service dependencies
        assert len(java_class.service_variables) == 1
        assert java_class.service_variables[0].name == "userService"
        assert java_class.service_variables[0].type == "UserService"
        assert java_class.service_variables[0].is_autowired

        # Verify endpoints
        endpoints = java_class.get_all_endpoints()
        assert "GET" in endpoints
        assert "POST" in endpoints

        # Check GET endpoints
        get_paths = [path for path, _ in endpoints["GET"]]
        assert "/api/users" in get_paths
        assert "/api/users/{id}" in get_paths

        # Check POST endpoints
        post_paths = [path for path, _ in endpoints["POST"]]
        assert "/api/users" in post_paths

    def test_multi_value_getmapping(self, tmp_path):
        """Integration test for multi-value @GetMapping arrays"""
        controller_content = """
        package com.example.multi;

        import org.springframework.web.bind.annotation.RestController;
        import org.springframework.web.bind.annotation.GetMapping;

        @RestController
        public class MultiController {

            @GetMapping({"/x","/y"})
            public void multi() {}
        }
        """
        java_file = tmp_path / "MultiController.java"
        java_file.write_text(textwrap.dedent(controller_content).strip())
        parser = JavaParser()
        java_class = parser.parse_java_file(str(java_file))
        assert isinstance(java_class, RestControllerClass)
        endpoints = java_class.get_all_endpoints()
        assert "GET" in endpoints
        paths = [p for p, _ in endpoints["GET"]]
        assert "/x" in paths
        assert "/y" in paths

    def test_spring_service_parsing(self, tmp_path):
        """Test parsing a Spring service class"""
        # Sample Spring service
        service_content = """
        package com.example.service;

        import java.util.List;
        import org.springframework.stereotype.Service;
        import org.springframework.beans.factory.annotation.Autowired;
        import com.example.repository.UserRepository;

        @Service
        public class UserServiceImpl implements UserService {

            @Autowired
            private UserRepository userRepository;

            @Override
            public List<User> findAll() {
                return userRepository.findAll();
            }

            @Override
            public User findById(Long id) {
                return userRepository.findById(id)
                    .orElseThrow(() -> new RuntimeException("User not found"));
            }

            @Override
            public User save(User user) {
                return userRepository.save(user);
            }
        }
        """

        # Create a temporary file
        java_file = tmp_path / "UserServiceImpl.java"
        dedented_content = textwrap.dedent(service_content).strip()
        java_file.write_text(dedented_content)

        # Parse the file
        parser = JavaParser()
        java_class = parser.parse_java_file(str(java_file))

        # Verify correct class detection
        assert java_class.name == "UserServiceImpl"
        assert java_class.package == "com.example.service"
        assert java_class.category == ClassCategory.SERVICE
        assert isinstance(java_class, ServiceClass)

    def test_service_interface_parsing(self, tmp_path):
        """Test parsing a Java interface through parser"""
        code = "package com.example.service; public interface MyService {}"
        file_path = tmp_path / "MyService.java"
        file_path.write_text(code)
        parser = JavaParser()
        java_class = parser.parse_java_file(str(file_path))
        from app.src.codeanalyzer.models import AbstractionType

        assert java_class.name == "MyService"
        assert java_class.package == "com.example.service"
        assert java_class.abstraction_type == AbstractionType.INTERFACE
        assert java_class.category == ClassCategory.SERVICE

    def test_service_abstract_parsing(self, tmp_path):
        """Test parsing a Java abstract class through parser"""
        code = "package com.example.service; public abstract class MyAbstractService {}"
        file_path = tmp_path / "MyAbstractService.java"
        file_path.write_text(code)
        parser = JavaParser()
        java_class = parser.parse_java_file(str(file_path))
        from app.src.codeanalyzer.models import AbstractionType

        assert java_class.name == "MyAbstractService"
        assert java_class.package == "com.example.service"
        assert java_class.abstraction_type == AbstractionType.ABSTRACT
        assert java_class.category == ClassCategory.SERVICE

    def test_real_entity_controller(self, tmp_path):
        """Test parsing the actual EntityController"""
        # Content based on the real EntityController
        entity_controller_content = """
        package com.example.entity.web;

        import java.util.ArrayList;
        import java.util.List;
        import java.util.Map;
        import org.springframework.beans.factory.annotation.Autowired;
        import org.springframework.http.HttpStatus;
        import org.springframework.web.bind.annotation.GetMapping;
        import org.springframework.web.bind.annotation.PostMapping;
        import org.springframework.web.bind.annotation.RequestBody;
        import org.springframework.web.bind.annotation.RequestHeader;
        import org.springframework.web.bind.annotation.RequestMapping;
        import org.springframework.web.bind.annotation.ResponseStatus;
        import org.springframework.web.bind.annotation.RestController;
        import com.example.constants.AppConstants;
        import com.example.entity.service.IEntityService;
        import com.example.entity.utils.EntityConstants;

        @RestController
        @RequestMapping(value = "/api/v1/entities")
        public class EntityController {

            @Autowired
            private IEntityService entityService;

            @GetMapping(value = "/getChildren")
            public RestResponse getEntityList(
                    @RequestHeader(AppConstants.AUTHORIZATION) String ssoToken,
                    @RequestHeader(AppConstants.CALLER_IDENTITY) String callerRef) {
                // Implementation
                return null;
            }

            @GetMapping(value = EntityConstants.GET_ENTITY_FLAGS_URL)
            @ResponseStatus(HttpStatus.OK)
            public RestResponse getEntityFlags(
                    @RequestHeader(value = AppConstants.ENTITY_ID, required = true) String entityId) {
                // Implementation
                return null;
            }

            @PostMapping(value = EntityConstants.SET_ENTITY_FLAGS_URL)
            @ResponseStatus(HttpStatus.OK)
            public RestResponse setEntityFlags(
                    @RequestHeader(value = AppConstants.ENTITY_ID, required = true) String entityId,
                    @RequestBody Object entitySettings) {
                // Implementation
                return null;
            }
        }
        """

        # Constants map for resolving constants in annotations
        constants = {
            "AppConstants.AUTHORIZATION": "Authorization",
            "AppConstants.CALLER_IDENTITY": "X-Caller-Ref",
            "AppConstants.ENTITY_ID": "entity-id",
            "EntityConstants.GET_ENTITY_FLAGS_URL": "/flags",
            "EntityConstants.SET_ENTITY_FLAGS_URL": "/set-flags",
        }

        # Create a temporary file
        java_file = tmp_path / "EntityController.java"
        dedented_content = textwrap.dedent(entity_controller_content).strip()
        java_file.write_text(dedented_content)

        # Parse the file
        parser = JavaParser()
        java_class = parser.parse_java_file(str(java_file))

        # Create analyzer to resolve constants
        analyzer = JavaAnalyzer()
        analyzer.classes[java_class.fully_qualified_name] = java_class
        analyzer.add_constants(constants)

        # Verify correct class detection
        assert java_class.name == "EntityController"
        assert java_class.package == "com.example.entity.web"
        assert java_class.category == ClassCategory.CONTROLLER
        assert isinstance(java_class, RestControllerClass)

        # Verify base path
        assert java_class.base_endpoint_path == "/api/v1/entities"

        # Verify service dependencies
        assert len(java_class.service_variables) == 1
        assert java_class.service_variables[0].name == "entityService"
        assert java_class.service_variables[0].is_autowired

        # Verify endpoints
        endpoints = java_class.get_all_endpoints()
        assert "GET" in endpoints
        assert "POST" in endpoints

        # Check paths
        get_paths = [path for path, _ in endpoints["GET"]]
        assert "/api/v1/entities/getChildren" in get_paths
        assert "/api/v1/entities/flags" in get_paths

        post_paths = [path for path, _ in endpoints["POST"]]
        assert "/api/v1/entities/set-flags" in post_paths

    def test_autowire_single_implementation_resolution(self, tmp_path):
        """Test autowiring when only one implementation exists"""
        # Interface and its sole implementation
        interface_file = tmp_path / "MySvc.java"
        interface_file.write_text("package com.example; public interface MySvc {}")
        impl_file = tmp_path / "MySvcImpl.java"
        impl_file.write_text(
            "package com.example;\n"
            + "import org.springframework.stereotype.Service;\n"
            + "@Service\n"
            + "public class MySvcImpl implements MySvc {}"
        )

        analyzer = JavaAnalyzer()
        analyzer.parse_directory(str(tmp_path), recursive=False)
        analyzer._resolve_all_references()

        svc_class = analyzer.classes["com.example.MySvc"]
        svc_var = ClassReferenceMemberVariable(name="svc", type="MySvc", is_autowired=True)
        svc_var.unresolved_autowire = type(
            "UA",
            (),
            {"raw_value": "MySvc", "mark_fully_resolved": lambda *a, **k: None},
        )()
        svc_class.member_variables.append(svc_var)
        analyzer.autowire_resolver.resolve_all()
        assert svc_var.resolved_implementation.name == "MySvcImpl"

    def test_autowire_primary_resolution(self, tmp_path):
        """Test autowiring with @Primary among multiple implementations"""
        tmp_interface = tmp_path / "MySvc.java"
        tmp_interface.write_text("package com.example; public interface MySvc {}")
        tmp_impl1 = tmp_path / "MySvcImpl1.java"
        tmp_impl1.write_text(
            "package com.example;\n"
            + "import org.springframework.stereotype.Service;\n"
            + "public class MySvcImpl1 implements MySvc {}"
        )
        tmp_impl2 = tmp_path / "MySvcImpl2.java"
        tmp_impl2.write_text(
            "package com.example;\n"
            + "import org.springframework.context.annotation.Primary;\n"
            + "import org.springframework.stereotype.Service;\n"
            + "@Primary\n"
            + "@Service\n"
            + "public class MySvcImpl2 implements MySvc {}"
        )

        analyzer = JavaAnalyzer()
        analyzer.parse_directory(str(tmp_path), recursive=False)
        analyzer._resolve_all_references()

        svc_class = analyzer.classes["com.example.MySvc"]
        svc_var = ClassReferenceMemberVariable(name="svc", type="MySvc", is_autowired=True)
        svc_var.unresolved_autowire = type(
            "UA",
            (),
            {"raw_value": "MySvc", "mark_fully_resolved": lambda *a, **k: None},
        )()
        svc_class.member_variables.append(svc_var)
        analyzer.autowire_resolver.resolve_all()
        assert svc_var.resolved_implementation.name == "MySvcImpl2"

    def test_autowire_qualifier_resolution(self, tmp_path):
        """Test autowiring with @Qualifier to pick specific implementation"""
        tmp_interface = tmp_path / "MySvc.java"
        tmp_interface.write_text("package com.example; public interface MySvc {}")
        tmp_impl1 = tmp_path / "MySvcImpl1.java"
        tmp_impl1.write_text(
            "package com.example;\n"
            + "import org.springframework.stereotype.Service;\n"
            + "@Service\n"
            + '@Qualifier("impl1")\n'
            + "public class MySvcImpl1 implements MySvc {}"
        )
        tmp_impl2 = tmp_path / "MySvcImpl2.java"
        tmp_impl2.write_text(
            "package com.example;\n"
            + "import org.springframework.stereotype.Service;\n"
            + "@Service\n"
            + '@Qualifier("impl2")\n'
            + "public class MySvcImpl2 implements MySvc {}"
        )

        analyzer = JavaAnalyzer()
        analyzer.parse_directory(str(tmp_path), recursive=False)
        analyzer._resolve_all_references()

        svc_class = analyzer.classes["com.example.MySvc"]
        svc_var = ClassReferenceMemberVariable(
            name="svc", type="MySvc", is_autowired=True, qualifier="impl2"
        )
        svc_var.unresolved_autowire = type(
            "UA",
            (),
            {"raw_value": "MySvc", "mark_fully_resolved": lambda *a, **k: None},
        )()
        svc_class.member_variables.append(svc_var)
        analyzer.autowire_resolver.resolve_all()
        assert svc_var.resolved_implementation.name == "MySvcImpl2"

    @pytest.mark.skip(
        reason="AmbiguousBeanReferenceError is now caught in the chain and we have a unit test for before that spot."
    )
    def test_autowire_ambiguity_error(self, tmp_path):
        """Test autowiring raises error when multiple implementations without qualifier or @Primary"""
        tmp_interface = tmp_path / "MySvc.java"
        tmp_interface.write_text("package com.example; public interface MySvc {}")
        tmp_impl1 = tmp_path / "MySvcImpl1.java"
        tmp_impl1.write_text(
            "package com.example;\n"
            + "import org.springframework.stereotype.Service;\n"
            + "@Service\n"
            + "public class MySvcImpl1 implements MySvc {}"
        )
        tmp_impl2 = tmp_path / "MySvcImpl2.java"
        tmp_impl2.write_text(
            "package com.example;\n"
            + "import org.springframework.stereotype.Service;\n"
            + "@Service\n"
            + "public class MySvcImpl2 implements MySvc {}"
        )

        analyzer = JavaAnalyzer()
        analyzer.parse_directory(str(tmp_path), recursive=False)
        analyzer._resolve_all_references()

        svc_class = analyzer.classes["com.example.MySvc"]
        svc_var = ClassReferenceMemberVariable(name="svc", type="MySvc", is_autowired=True)
        svc_var.unresolved_autowire = type(
            "UA",
            (),
            {"raw_value": "MySvc", "mark_fully_resolved": lambda *a, **k: None},
        )()
        svc_class.member_variables.append(svc_var)
        with pytest.raises(AmbiguousBeanReferenceError):
            analyzer.autowire_resolver._resolve_autowired_dependency(svc_var, svc_class)


class TestResolverIntegration:
    """Test resolver integration with real components - integration tests"""

    def test_resolve_variable(self, sample_analyzer, constants_map):
        """Test variable resolution in classes (using peek_expression_value for direct inspection)"""
        from app.src.codeanalyzer.constant_resolver import ConstantResolver

        # Add a class with a constant
        test_class = JavaClass(
            name="ConstantClass",
            package="com.example.constants",
            constants={"LOCAL_CONSTANT": "local-value"},
        )
        sample_analyzer.classes[test_class.fully_qualified_name] = test_class

        # Add global constants
        sample_analyzer.add_constants(constants_map)

        resolver = ConstantResolver(sample_analyzer)

        # Resolve a local constant
        value = resolver.peek_expression_value("ConstantClass", "LOCAL_CONSTANT")
        assert value == "local-value"

        # Resolve a global constant
        value = resolver.peek_expression_value("ConstantClass", "ApiConstants.API_BASE_PATH")
        assert value == "/api/v2"

        # Resolve an unknown constant
        value = resolver.peek_expression_value("ConstantClass", "UNKNOWN_CONSTANT")
        assert value == "UNKNOWN_CONSTANT"

    def test_peek_expression_value_handles_chained_missing(self, sample_analyzer):
        """Test peek_expression_value returns expr for missing chained reference"""
        from app.src.codeanalyzer.constant_resolver import ConstantResolver

        classA = JavaClass(name="A", package="com.example", constants={"B": "B.D"})
        classB = JavaClass(name="B", package="com.example", constants={"C": "final-value"})
        sample_analyzer.classes[classA.fully_qualified_name] = classA
        sample_analyzer.classes[classB.fully_qualified_name] = classB
        resolver = ConstantResolver(sample_analyzer)
        val = resolver.peek_expression_value("A", "B")
        assert val == "B.D"


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
