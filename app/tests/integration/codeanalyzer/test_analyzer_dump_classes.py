"""
Integration tests for analyzer class dumping functionality.

Strategy: Real Java file parsing with method filtering and source manipulation.
Real: Java file parsing, class filtering, method comment handling
Mocked: Nothing

Test Responsibilities:
- TestAnalyzerDumpClasses: Various filtering scenarios, comment inclusion/exclusion,
  method selection, import/package preservation
"""

import os
import tempfile
from pathlib import Path

import pytest

from app.src.codeanalyzer.analyzer import JavaAnalyzer
from app.src.codeanalyzer.models import Annotation, ElementType, JavaMethod
from app.src.codeanalyzer.parser import JavaParser


class TestAnalyzerDumpClasses:
    """Test the dump_classes_to_string method with various filtering options using real parsed classes."""

    @pytest.fixture
    def temp_java_files(self):
        """Create temporary Java files for testing."""
        temp_dir = tempfile.mkdtemp()

        # Simple service class
        service_content = """package com.example.service;

import java.util.List;

/**
 * User service for managing users
 */
@Service
public class UserService {

    /**
     * Find all users in the system
     * @return list of all users
     */
    public List<User> findAll() {
        return userRepository.findAll();
    }

    /**
     * Save a user to the database
     * @param user the user to save
     * @return the saved user
     */
    public User save(User user) {
        return userRepository.save(user);
    }

    public User findById(Long id) {
        return userRepository.findById(id);
    }
}"""

        # Controller class with endpoints
        controller_content = """package com.example.controller;

import java.util.List;

/**
 * REST controller for user operations
 */
@RestController
@RequestMapping("/api/users")
public class UserController {

    /**
     * Get all users endpoint
     */
    @GetMapping
    public List<User> getAllUsers() {
        return userService.findAll();
    }

    /**
     * Create new user endpoint
     */
    @PostMapping
    public User createUser(@RequestBody User user) {
        return userService.save(user);
    }

    @GetMapping("/{id}")
    public User getUserById(@PathVariable Long id) {
        return userService.findById(id);
    }
}"""

        # Simple utility class
        util_content = """package com.example.util;

/**
 * String utilities
 */
public class StringUtils {

    /**
     * Check if string is empty
     */
    public static boolean isEmpty(String str) {
        return str == null || str.trim().isEmpty();
    }

    public static String capitalize(String str) {
        if (isEmpty(str)) {
            return str;
        }
        return str.substring(0, 1).toUpperCase() + str.substring(1);
    }
}"""

        # Class without comments
        no_comments_content = """package com.example.model;

public class SimpleClass {

    public void methodOne() {
        System.out.println("One");
    }

    public void methodTwo() {
        System.out.println("Two");
    }

    public void methodThree() {
        System.out.println("Three");
    }
}"""

        # Write files
        files = {
            "UserService.java": service_content,
            "UserController.java": controller_content,
            "StringUtils.java": util_content,
            "SimpleClass.java": no_comments_content,
        }

        file_paths = {}
        for filename, content in files.items():
            file_path = os.path.join(temp_dir, filename)
            with open(file_path, "w") as f:
                f.write(content)
            file_paths[filename] = file_path

        yield file_paths

        # Cleanup
        for file_path in file_paths.values():
            os.unlink(file_path)
        os.rmdir(temp_dir)

    @pytest.fixture
    def parsed_classes(self, temp_java_files):
        """Parse the temporary Java files and return JavaClass objects."""
        parser = JavaParser()
        classes = {}

        for filename, file_path in temp_java_files.items():
            java_class = parser.parse_java_file(file_path, store_source=True)
            classes[filename] = java_class

        return classes

    @pytest.fixture
    def analyzer(self):
        """Create a JavaAnalyzer instance."""
        return JavaAnalyzer()

    def test_dump_all_classes_no_filtering(self, analyzer, parsed_classes):
        """Test dumping all classes without any filtering."""
        classes = list(parsed_classes.values())

        result = analyzer.dump_classes_to_string(classes)

        assert len(result) == len(classes)

        # Verify each class source is returned unchanged
        for java_class in classes:
            assert java_class.fully_qualified_name in result
            assert result[java_class.fully_qualified_name] == java_class.source_code

    def test_dump_service_methods_filtering(self, analyzer, parsed_classes):
        """Test filtering methods in the service class."""
        service_class = parsed_classes["UserService.java"]

        # Include only findAll and save methods
        include_methods = {service_class.name: ["findAll", "save"]}

        result = analyzer.dump_classes_to_string([service_class], include_methods=include_methods)

        assert len(result) == 1
        dumped_source = result[service_class.fully_qualified_name]

        # Should contain included methods
        assert "findAll" in dumped_source
        assert "save" in dumped_source

        # Should not contain excluded method
        assert "findById" not in dumped_source

    def test_dump_controller_endpoints_filtering(self, analyzer, parsed_classes):
        """Test filtering REST endpoints in controller."""
        controller_class = parsed_classes["UserController.java"]

        # Include only the GET all users endpoint
        include_methods = {controller_class.name: ["getAllUsers"]}

        result = analyzer.dump_classes_to_string(
            [controller_class], include_methods=include_methods
        )

        assert len(result) == 1
        dumped_source = result[controller_class.fully_qualified_name]

        # Should contain included endpoint
        assert "getAllUsers" in dumped_source
        assert "@GetMapping" in dumped_source

        # Should not contain excluded endpoints
        assert "createUser" not in dumped_source
        assert "getUserById" not in dumped_source
        assert "@PostMapping" not in dumped_source

    def test_dump_exclude_all_method_comments(self, analyzer, parsed_classes):
        """Test excluding all method comments while keeping methods."""
        service_class = parsed_classes["UserService.java"]

        result = analyzer.dump_classes_to_string([service_class], include_method_comments=False)

        assert len(result) == 1
        dumped_source = result[service_class.fully_qualified_name]

        # Should contain all methods
        assert "findAll" in dumped_source
        assert "save" in dumped_source
        assert "findById" in dumped_source

        # Should not contain method comments
        assert "Find all users in the system" not in dumped_source

    @pytest.mark.parametrize(
        "resolve_constants,include_element_types,include_methods,include_method_comments",
        [
            (True, None, None, True),
            (True, [ElementType.CLASS_ANNOTATION], None, True),
            (True, None, {"UserService": ["save"]}, True),
            (True, None, None, False),
            (False, None, None, True),
            (False, [ElementType.CLASS_ANNOTATION], None, True),
        ],
    )
    def test_dump_with_constant_replacement_options(
        self,
        analyzer,
        parsed_classes,
        resolve_constants,
        include_element_types,
        include_methods,
        include_method_comments,
    ):
        """Test dump_classes_to_string accepts new parameters without error"""
        service_class = parsed_classes["UserService.java"]
        # calling with the new params should not raise
        result = analyzer.dump_classes_to_string(
            [service_class],
            include_methods=include_methods,
            include_method_comments=include_method_comments,
            include_element_types=include_element_types,
        )
        dumped = result[service_class.fully_qualified_name]
        # sanity: class declaration remains
        assert f"class {service_class.name}" in dumped
        # Should still contain class-level comment
        assert "User service for managing users" in dumped

    def test_dump_method_filtering_with_comments_included(self, analyzer, parsed_classes):
        """Test method filtering while keeping comments for included methods."""
        service_class = parsed_classes["UserService.java"]

        include_methods = {service_class.name: ["findAll"]}

        result = analyzer.dump_classes_to_string(
            [service_class],
            include_methods=include_methods,
            include_method_comments=True,
        )

        assert len(result) == 1
        dumped_source = result[service_class.fully_qualified_name]

        # Should contain included method and its full Javadoc
        # Should contain included method with its full Javadoc comment block and signature
        expected_comment_block = """    /**
     * Find all users in the system
     * @return list of all users
     */"""
        assert expected_comment_block in dumped_source
        assert "public List<User> findAll()" in dumped_source

        # Should not contain excluded methods or their comments
        assert "save" not in dumped_source
        assert "Save a user to the database" not in dumped_source
        assert "findById" not in dumped_source

    def test_dump_method_filtering_with_comments_excluded(self, analyzer, parsed_classes):
        """Test method filtering while excluding all method comments."""
        service_class = parsed_classes["UserService.java"]

        include_methods = {service_class.name: ["findAll", "save"]}

        result = analyzer.dump_classes_to_string(
            [service_class],
            include_methods=include_methods,
            include_method_comments=False,
        )

        assert len(result) == 1
        dumped_source = result[service_class.fully_qualified_name]

        # Should contain included methods
        assert "findAll" in dumped_source
        assert "save" in dumped_source

        # Should not contain any method comments
        assert "Find all users in the system" not in dumped_source
        assert "Save a user to the database" not in dumped_source

        # Should not contain excluded method
        assert "findById" not in dumped_source

    def test_dump_class_without_comments(self, analyzer, parsed_classes):
        """Test dumping a class that has no method comments."""
        simple_class = parsed_classes["SimpleClass.java"]

        include_methods = {simple_class.name: ["methodOne", "methodThree"]}

        result = analyzer.dump_classes_to_string(
            [simple_class],
            include_methods=include_methods,
            include_method_comments=False,
        )

        assert len(result) == 1
        dumped_source = result[simple_class.fully_qualified_name]

        # Should contain included methods
        assert "methodOne" in dumped_source
        assert "methodThree" in dumped_source

        # Should not contain excluded method
        assert "methodTwo" not in dumped_source

    def test_dump_multiple_classes_different_filters(self, analyzer, parsed_classes):
        """Test dumping multiple classes with different filtering rules."""
        service_class = parsed_classes["UserService.java"]
        controller_class = parsed_classes["UserController.java"]
        util_class = parsed_classes["StringUtils.java"]

        classes = [service_class, controller_class, util_class]
        include_methods = {
            service_class.name: ["findAll"],
            controller_class.name: ["getAllUsers", "createUser"],
            # No filter for util_class - should include all methods
        }

        result = analyzer.dump_classes_to_string(
            classes, include_methods=include_methods, include_method_comments=True
        )

        assert len(result) == 3

        # Check service class
        service_dump = result[service_class.fully_qualified_name]
        assert "findAll" in service_dump
        assert "save" not in service_dump
        assert "findById" not in service_dump

        # Check controller class
        controller_dump = result[controller_class.fully_qualified_name]
        assert "getAllUsers" in controller_dump
        assert "createUser" in controller_dump
        assert "getUserById" not in controller_dump

        # Check util class (no filtering)
        util_dump = result[util_class.fully_qualified_name]
        assert "isEmpty" in util_dump
        assert "capitalize" in util_dump
        assert util_dump == util_class.source_code

    def test_dump_using_fully_qualified_name_filter(self, analyzer, parsed_classes):
        """Test filtering using fully qualified class names."""
        service_class = parsed_classes["UserService.java"]

        include_methods = {service_class.fully_qualified_name: ["save"]}

        result = analyzer.dump_classes_to_string([service_class], include_methods=include_methods)

        assert len(result) == 1
        dumped_source = result[service_class.fully_qualified_name]

        # Should contain only the save method
        assert "save" in dumped_source
        assert "findAll" not in dumped_source
        assert "findById" not in dumped_source

    def test_dump_with_nonexistent_methods(self, analyzer, parsed_classes):
        """Test filtering with method names that don't exist."""
        service_class = parsed_classes["UserService.java"]

        include_methods = {service_class.name: ["nonexistentMethod", "anotherFakeMethod"]}

        result = analyzer.dump_classes_to_string([service_class], include_methods=include_methods)

        assert len(result) == 1
        dumped_source = result[service_class.fully_qualified_name]

        # All existing methods should be removed
        assert "findAll" not in dumped_source
        assert "save" not in dumped_source
        assert "findById" not in dumped_source

    def test_dump_empty_method_list(self, analyzer, parsed_classes):
        """Test filtering with an empty list of methods (exclude all)."""
        service_class = parsed_classes["UserService.java"]

        include_methods = {service_class.name: []}

        result = analyzer.dump_classes_to_string([service_class], include_methods=include_methods)

        assert len(result) == 1
        dumped_source = result[service_class.fully_qualified_name]

        # All methods should be removed
        assert "findAll" not in dumped_source
        assert "save" not in dumped_source
        assert "findById" not in dumped_source

        # Should have class declaration and imports
        assert "class UserService" in dumped_source
        assert "import java.util.List" in dumped_source

    def test_dump_preserves_imports_and_package(self, analyzer, parsed_classes):
        """Test that imports and package declarations are preserved."""
        controller_class = parsed_classes["UserController.java"]

        include_methods = {controller_class.name: ["getAllUsers"]}

        result = analyzer.dump_classes_to_string(
            [controller_class], include_methods=include_methods
        )

        assert len(result) == 1
        dumped_source = result[controller_class.fully_qualified_name]

        # Should preserve package and imports
        assert "package com.example.controller" in dumped_source
        assert "import java.util.List" in dumped_source

        # Should preserve class-level annotations
        assert "@RestController" in dumped_source
        assert '@RequestMapping("/api/users")' in dumped_source

    def test_dump_preserves_class_level_comments(self, analyzer, parsed_classes):
        """Test that class-level comments are always preserved."""
        service_class = parsed_classes["UserService.java"]

        # Remove all methods but keep comments excluded
        include_methods = {service_class.name: []}

        result = analyzer.dump_classes_to_string(
            [service_class],
            include_methods=include_methods,
            include_method_comments=False,
        )

        assert len(result) == 1
        dumped_source = result[service_class.fully_qualified_name]

        # Should preserve class-level comment
        assert "User service for managing users" in dumped_source

        # Should not have method comments
        assert "Find all users in the system" not in dumped_source

    def test_constant_replacement_behavior(self, analyzer, tmp_path):
        """Test constant replacement in class annotation with filtering."""
        # Create a temporary Java file with a constant in annotation
        code = """
            package com.test;

            import com.example.Constants;

            @RequestMapping(value = Constants.API_PATH)
            public class ConstController {}
            """
        java_file = tmp_path / "ConstController.java"
        java_file.write_text(code)

        # Parse and store source
        parser = JavaParser()
        java_class = parser.parse_java_file(str(java_file), store_source=True)
        analyzer.classes = {java_class.fully_qualified_name: java_class}

        # Inject constant value
        analyzer.add_constants({"Constants.API_PATH": "/test/path"})

        # Test with resolve_constants=True (default behavior)
        result_with_resolve = analyzer.dump_classes_to_string(
            [java_class],
            resolve_constants=True,
            include_element_types=[ElementType.CLASS_ANNOTATION],
        )
        dumped_with_resolve = result_with_resolve[java_class.fully_qualified_name]
        assert "Constants.API_PATH" not in dumped_with_resolve
        assert '"/test/path"' in dumped_with_resolve

        # Test with resolve_constants=False (constants should remain unchanged)
        result_no_resolve = analyzer.dump_classes_to_string(
            [java_class],
            resolve_constants=False,
            include_element_types=[ElementType.CLASS_ANNOTATION],  # This should be ignored
        )
        dumped_no_resolve = result_no_resolve[java_class.fully_qualified_name]
        assert "Constants.API_PATH" in dumped_no_resolve
        assert '"/test/path"' not in dumped_no_resolve

        # Test with resolve_constants=True but no element types (no replacement)
        result_no_types = analyzer.dump_classes_to_string(
            [java_class],
            resolve_constants=True,
            include_element_types=[ElementType.METHOD_ANNOTATION],  # Different type
        )
        dumped_no_types = result_no_types[java_class.fully_qualified_name]
        assert "Constants.API_PATH" in dumped_no_types
        assert '"/test/path"' not in dumped_no_types

    def test_comment_preservation_with_method_filtering_and_constants(self, analyzer, tmp_path):
        """
        Integration test that reproduces the bug where method comments were truncated
        when filtering methods and applying constant replacements simultaneously.

        This bug was caused by overlapping removal operations (for unwanted methods/comments)
        and replacement operations (for constants), resulting in comment text being cut off
        instead of being fully preserved.
        """
        # Create a real constants file
        constants_content = """/*
 * Copyright 2024, Test Company LLC
 *
 * ApiConstants.java
 */
package com.example.constants;

public class ApiConstants {
    public static final String FIRST_ENDPOINT = "/api/v1/first";
    public static final String SECOND_ENDPOINT = "/api/v1/second";
    public static final String THIRD_ENDPOINT = "/api/v1/third";
    public static final String FOURTH_ENDPOINT = "/api/v1/fourth";
}"""

        # Create the controller file that references the constants
        controller_content = """/*
 * Copyright 2024, Test Company LLC
 *
 * TestController.java
 */
package com.example.web;

import org.springframework.web.bind.annotation.*;
import com.example.constants.ApiConstants;

/**
 * Test REST controller for API endpoints.
 */
@RestController
@RequestMapping(value = "/api")
public class TestController {

    /**
     * First method that will be excluded
     *
     * @param param the input parameter
     * @return response message
     * @throws Exception if error occurs
     */
    @GetMapping(value = "/excluded")
    public String firstMethod(@RequestParam String param) throws Exception {
        return "first";
    }

    @GetMapping(value = ApiConstants.FIRST_ENDPOINT)
    public String secondMethod(@RequestParam String[] data) throws Exception {
        return "second";
    }

    @PostMapping(value = ApiConstants.SECOND_ENDPOINT)
    public String thirdMethod(@RequestBody String body) {
        return "third";
    }

    @PutMapping(value = ApiConstants.THIRD_ENDPOINT)
    public String fourthMethod(@RequestBody String settings) throws Exception {
        return "fourth";
    }

    /**
     * This method performs important business logic for data processing
     * operations in the system with advanced configuration capabilities
     *
     * @param id the unique identifier
     * @param config the configuration object
     * @return success message or error details
     */
    @PostMapping(value = ApiConstants.FOURTH_ENDPOINT)
    public String fifthMethod(@RequestParam String id) throws Exception {
        return "fifth";
    }
}"""

        # Write both files to temporary locations
        constants_file = tmp_path / "ApiConstants.java"
        constants_file.write_text(constants_content)

        controller_file = tmp_path / "TestController.java"
        controller_file.write_text(controller_content)

        # Parse both files using the normal flow
        from app.src.codeanalyzer.parser import JavaParser

        parser = JavaParser()

        # Parse the constants file first
        constants_class = parser.parse_java_file(str(constants_file), store_source=True)
        analyzer.classes[constants_class.fully_qualified_name] = constants_class

        # Parse the controller file
        controller_class = parser.parse_java_file(str(controller_file), store_source=True)
        analyzer.classes[controller_class.fully_qualified_name] = controller_class

        # Run the normal resolution process to resolve constants
        analyzer._resolve_all_references()

        # Apply method filtering - this is what triggered the original bug
        # We keep only secondMethod and fifthMethod (the one with the long comment)
        include_methods = {"TestController": ["secondMethod", "fifthMethod"]}

        # Apply constant replacement in method annotations - this combined with
        # method filtering caused the overlapping operations that truncated comments
        result = analyzer.dump_classes_to_string(
            [controller_class],
            resolve_constants=True,  # Explicitly test with True first
            include_methods=include_methods,
            include_method_comments=True,
            include_element_types=[ElementType.METHOD_ANNOTATION],
        )

        dumped_source = result[controller_class.fully_qualified_name]

        # Verify the critical bug is fixed - the complete comment should be preserved
        expected_comment_text = """/**
     * This method performs important business logic for data processing
     * operations in the system with advanced configuration capabilities
     *
     * @param id the unique identifier
     * @param config the configuration object
     * @return success message or error details
     */"""

        # Normalize both texts for comparison (handle indentation differences)
        import re

        def normalize_comment(text):
            # Remove extra whitespace but preserve structure
            lines = [line.strip() for line in text.strip().split("\n")]
            return "\n".join(lines)

        normalized_expected = normalize_comment(expected_comment_text)
        normalized_dumped = normalize_comment(dumped_source)

        # The key test: verify the complete comment is present
        assert normalized_expected in normalized_dumped, (
            f"Complete comment not found in dumped source.\nExpected:\n{normalized_expected}\n\nActual dumped source:\n{dumped_source}"
        )

        # Verify constants were properly replaced (not just that the comment was preserved)
        assert '"/api/v1/first"' in dumped_source, "Constant FIRST_ENDPOINT was not replaced"
        assert '"/api/v1/fourth"' in dumped_source, "Constant FOURTH_ENDPOINT was not replaced"

        # Verify original constant references are gone (replaced)
        assert "ApiConstants.FIRST_ENDPOINT" not in dumped_source, (
            "Original constant reference should be replaced"
        )
        assert "ApiConstants.FOURTH_ENDPOINT" not in dumped_source, (
            "Original constant reference should be replaced"
        )

        # Verify method filtering worked correctly
        assert "secondMethod" in dumped_source, "Included method should be present"
        assert "fifthMethod" in dumped_source, "Included method should be present"
        assert "firstMethod" not in dumped_source, "Excluded method should not be present"
        assert "thirdMethod" not in dumped_source, "Excluded method should not be present"
        assert "fourthMethod" not in dumped_source, "Excluded method should not be present"

        # NEW: Test with resolve_constants=False - constants should remain unchanged
        result_no_resolve = analyzer.dump_classes_to_string(
            [controller_class],
            resolve_constants=False,
            include_methods=include_methods,
            include_method_comments=True,
            include_element_types=[ElementType.METHOD_ANNOTATION],  # Should be ignored
        )

        dumped_no_resolve = result_no_resolve[controller_class.fully_qualified_name]

        # Comment should still be preserved (main bug test)
        normalized_dumped_no_resolve = normalize_comment(dumped_no_resolve)
        assert normalized_expected in normalized_dumped_no_resolve, (
            f"Complete comment not preserved with resolve_constants=False.\nActual: {dumped_no_resolve}"
        )

        # Constants should NOT be replaced (should remain as references)
        assert "ApiConstants.FIRST_ENDPOINT" in dumped_no_resolve, (
            "Original constant reference should remain when resolve_constants=False"
        )
        assert "ApiConstants.FOURTH_ENDPOINT" in dumped_no_resolve, (
            "Original constant reference should remain when resolve_constants=False"
        )

        # Replaced values should NOT be present
        assert '"/api/v1/first"' not in dumped_no_resolve, (
            "Constant should not be replaced when resolve_constants=False"
        )
        assert '"/api/v1/fourth"' not in dumped_no_resolve, (
            "Constant should not be replaced when resolve_constants=False"
        )

        # Method filtering should still work the same
        assert "secondMethod" in dumped_no_resolve, "Included method should be present"
        assert "fifthMethod" in dumped_no_resolve, "Included method should be present"
        assert "firstMethod" not in dumped_no_resolve, "Excluded method should not be present"
        assert "thirdMethod" not in dumped_no_resolve, "Excluded method should not be present"
        assert "fourthMethod" not in dumped_no_resolve, "Excluded method should not be present"

    def test_overlapping_ranges_edge_cases(self, analyzer, tmp_path):
        """
        Test edge cases for overlapping removal ranges that caused the comment truncation bug.

        This test verifies that the SourceReplacer correctly handles:
        1. Adjacent comment and method removal ranges
        2. Multiple overlapping ranges
        3. Constant replacements within removal ranges
        """
        # Create a simple class with tightly packed methods and comments
        java_content = """package com.test;

public class TestClass {
    /**
     * First method comment
     */
    @GetMapping("/first")
    public void firstMethod() {}

    /**
     * Second method comment
     */
    @PostMapping("/second")
    public void secondMethod() {}

    /**
     * Third method comment that should be preserved
     */
    @PutMapping("/third")
    public void thirdMethod() {}
}"""

        # Write to temporary file
        java_file = tmp_path / "TestClass.java"
        java_file.write_text(java_content)

        # Parse the file
        import re

        from app.src.codeanalyzer.parser import JavaParser

        parser = JavaParser()
        java_class = parser.parse_java_file(str(java_file), store_source=True)

        # Test filtering that keeps only the last method
        include_methods = {"TestClass": ["thirdMethod"]}

        result = analyzer.dump_classes_to_string(
            [java_class], include_methods=include_methods, include_method_comments=True
        )

        dumped_source = result[java_class.fully_qualified_name]

        # Verify the preserved method and its comment are intact
        assert "Third method comment that should be preserved" in dumped_source, (
            "Comment for preserved method should be complete"
        )
        assert "thirdMethod" in dumped_source, "Preserved method should be present"

        # Verify removed methods and comments are not present
        assert "First method comment" not in dumped_source, (
            "Comment for removed method should not be present"
        )
        assert "Second method comment" not in dumped_source, (
            "Comment for removed method should not be present"
        )
        assert "firstMethod" not in dumped_source, "Removed method should not be present"
        assert "secondMethod" not in dumped_source, "Removed method should not be present"
