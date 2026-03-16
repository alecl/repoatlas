import contextlib
import logging
import os
import zlib
from collections.abc import Callable
from hashlib import md5
from typing import Any, Dict, List, Optional, Set, Tuple

from app.src.codeanalyzer.code_analyzer_config import CodeAnalyzerConfig
from app.src.logging import logger

from .autowire_resolver import AutowireResolver
from .constant_resolver import ConstantResolver
from .import_resolver import ImportResolver
from .models import (
    ClassCategory,
    ClassReferenceMemberVariable,
    DependencyOptions,
    ElementType,
    ImportDefinition,
    JavaClass,
    MethodCallInfo,
    ReferenceResolutionStatus,
    RestControllerClass,
    ServiceClass,
)
from .parser import JavaParser, MissingDeclarationException
from .path_resolver import PathResolver
from .property_resolver import PropertyResolver
from .source_replacer import SourceReplacer
from .type_resolver import TypeResolver
from .util import collapse_blank_lines


class MultipleJavaClassMatchError(Exception):
    """Raised when multiple Java classes match a unique lookup."""


class JavaAnalyzer:
    """
    Analyzer for Java files.
    Provides functionality to parse Java files and analyze their structure.
    """

    def __init__(
        self,
        config: CodeAnalyzerConfig | None = None,
        language_path: str | None = None,
    ):
        """
        Initialize the analyzer.

        Args:
            config: Configuration object, uses default if None
            language_path: Optional path to the tree-sitter Java grammar
        """
        self.config = config or CodeAnalyzerConfig()
        self.parser = JavaParser(config=config, language_path=language_path)
        self.classes: dict[str, JavaClass] = {}
        self.global_constants: dict[str, str] = {}

        # --- Specialized resolvers ---
        self.import_resolver = ImportResolver(self)
        self.type_resolver = TypeResolver(self)
        self.constant_resolver = ConstantResolver(self)
        self.path_resolver = PathResolver(self)
        self.autowire_resolver = AutowireResolver(self)
        self.property_resolver = PropertyResolver(self)

    def parse_file(self, file_path: str) -> JavaClass:
        """
        Parse a Java file and store the resulting JavaClass.

        Args:
            file_path: Path to the Java file

        Returns:
            The parsed JavaClass
        """
        java_class = self.parser.parse_java_file(file_path)
        self.classes[java_class.fully_qualified_name] = java_class
        return java_class

    def parse_directory(self, directory_path: str, recursive: bool = True) -> list[JavaClass]:
        """
        Parse all Java files in a directory.

        Args:
            directory_path: Path to the directory
            recursive: Whether to search recursively

        Returns:
            List of parsed JavaClass objects
        """
        classes = []

        if recursive:
            for root, _, files in os.walk(directory_path):
                for file in files:
                    if file.endswith(".java"):
                        file_path = os.path.join(root, file)
                        try:
                            java_class = self.parse_file(file_path)
                            classes.append(java_class)
                        except MissingDeclarationException as e:
                            logger.warning("SKIPPING - Missing declaration in %s %s", file_path, e)
                        except Exception as e:
                            logger.error("SKIPPING - Error parsing %s %s", file_path, e)
        else:
            for file in os.listdir(directory_path):
                if file.endswith(".java"):
                    file_path = os.path.join(directory_path, file)
                    try:
                        java_class = self.parse_file(file_path)
                        classes.append(java_class)
                    except MissingDeclarationException as e:
                        logger.warning("SKIPPING - Missing declaration in %s %s", file_path, e)
                    except Exception as e:
                        logger.error("SKIPPING - Error parsing %s %s", file_path, e)

        return classes

    def find_class_by_name(self, class_name: str) -> list[JavaClass]:
        """
        Find all classes matching the given name or fully qualified name.

        If class_name contains a dot ('.'), it is treated as a fully qualified or partially qualified name,
        and matches any class whose fully qualified name ends with that string.
        If class_name does not contain a dot, matches by simple class name.

        Args:
            class_name: The name or qualified name of the class to find

        Returns:
            List of JavaClass objects matching the given name or qualified name
        """
        if "." in class_name:
            # Treat as qualified name, match any class whose FQN ends with this string
            return [
                cls
                for cls in self.classes.values()
                if cls.fully_qualified_name.endswith(class_name)
            ]
        else:
            # Match by simple class name
            return [cls for cls in self.classes.values() if cls.name == class_name]

    def load_source_for_all_classes(self) -> None:
        """Load source code for all classes if not already loaded."""
        for class_name in list(self.classes.keys()):
            self.refresh_class_if_needed(class_name, load_source=True)

    def refresh_class_if_needed(
        self,
        class_name: str,
        load_source: bool = False,
        refresh_dependent_classes: bool = False,
        dependency_options: DependencyOptions | None = None,
        visited_classes: set[str] | None = None,
    ) -> tuple[bool, list[str]]:
        """
        Check if a class needs refreshing and refresh if needed.

        Args:
            class_name: Fully qualified name of the class to refresh
            load_source: Whether to load source code if not present
            refresh_dependent_classes: Whether to refresh dependent classes
            dependency_options: Options for dependency refreshing
            visited_classes: Set of already visited classes (for recursion)

        Returns:
            Tuple of (was_refreshed, refreshed_dependent_classes)
        """
        # Initialize visited_classes to prevent cycles
        visited_classes = visited_classes or set()
        if class_name in visited_classes:
            return False, []

        visited_classes.add(class_name)

        # Use provided options or create default DependencyOptions
        options = dependency_options or DependencyOptions(max_depth=1)  # Shallow depth by default

        # Get the class
        java_class = self.classes.get(class_name)
        if not java_class or not java_class.absolute_path:
            return False, []

        file_path = java_class.absolute_path

        # Check if file exists
        if not os.path.exists(file_path):
            return False, []

        # Initialize flags
        was_refreshed = False
        file_changed = False

        # Get current file metadata
        file_stats = os.stat(file_path)
        current_size = file_stats.st_size
        current_mtime = file_stats.st_mtime

        # Quick check: if size and modification time are unchanged, file is likely the same
        if hasattr(java_class, "file_size") and hasattr(java_class, "last_modified"):
            if java_class.file_size != current_size or java_class.last_modified != current_mtime:
                # Size or time changed, perform more detailed checks
                with open(file_path, "rb") as f:
                    content = f.read()

                current_crc32 = zlib.crc32(content)
                if not hasattr(java_class, "crc32_hash") or java_class.crc32_hash != current_crc32:
                    # CRC32 changed, final check with MD5
                    current_md5 = md5(content).hexdigest()
                    if not hasattr(java_class, "md5_hash") or java_class.md5_hash != current_md5:
                        file_changed = True
        else:
            # No metadata, assume file has changed
            file_changed = True

        # If file has changed or we need to load source
        if file_changed:
            # Do a complete reparse of the file
            refreshed_class = self.parser.parse_java_file(
                file_path,
                store_source=load_source
                or (hasattr(java_class, "source_code") and bool(java_class.source_code)),
            )

            # Replace in class dictionary
            self.classes[class_name] = refreshed_class
            was_refreshed = True
        elif load_source and (
            not hasattr(java_class, "source_code") or not java_class.source_code
        ):
            # Only load source if requested and not already present
            with open(file_path, encoding="utf-8") as f:
                java_class.source_code = f.read()

            # Update metadata for consistency
            java_class.file_size = current_size
            java_class.last_modified = current_mtime

        # If we're not refreshing dependencies or max_depth is 0, stop here
        if not refresh_dependent_classes or options.max_depth <= 0:
            return was_refreshed, []

        # Process dependency refreshing
        # Reduce max_depth for next level
        next_options = DependencyOptions(**options.dict())
        next_options.max_depth = options.max_depth - 1
        refreshed_dependencies = []

        # Get the current Java class again (might have been refreshed)
        java_class = self.classes.get(class_name)
        if not java_class or not java_class.absolute_path:
            return False, []

        # Process upstream dependencies (classes this class depends on)
        if options.upstream:
            upstream_dependencies = set()

            # Member variable types
            for var in java_class.get_class_references():
                resolved_class = self.resolve_type_to_class(var.type, java_class)
                if resolved_class:
                    upstream_dependencies.add(resolved_class.fully_qualified_name)

            # Superclass if any
            if hasattr(java_class, "extends") and java_class.extends:
                superclass = self.resolve_type_to_class(java_class.extends, java_class)
                if superclass:
                    upstream_dependencies.add(superclass.fully_qualified_name)

            # Classes referenced in method calls
            for method in java_class.methods:
                for call in getattr(method, "method_calls", []):
                    if call.service_type:
                        service_class = self.resolve_type_to_class(call.service_type, java_class)
                        if service_class:
                            upstream_dependencies.add(service_class.fully_qualified_name)

            # Process each dependency
            for dep_class_name in upstream_dependencies:
                # Get the dependency class
                dep_class = self.classes.get(dep_class_name)
                if not dep_class:
                    continue

                # Apply scope filtering
                if hasattr(dep_class, "resolved_location") and dep_class.resolved_location:
                    # Check if scope is excluded
                    if dep_class.resolved_location.scope in options.exclude_scopes:
                        continue

                    # Check if scope is included
                    if (
                        options.include_scopes
                        and dep_class.resolved_location.scope not in options.include_scopes
                    ):
                        continue

                # Apply category filtering
                if (
                    options.include_categories
                    and dep_class.category not in options.include_categories
                ):
                    continue

                if options.exclude_categories and dep_class.category in options.exclude_categories:
                    continue

                # Apply package filtering (secondary)
                if any(dep_class_name.startswith(pkg) for pkg in options.exclude_packages):
                    continue

                # Recursively refresh this dependency
                dep_refreshed, dep_chain = self.refresh_class_if_needed(
                    dep_class_name,
                    load_source=load_source,
                    refresh_dependent_classes=True,
                    dependency_options=next_options,
                    visited_classes=visited_classes,
                )

                if dep_refreshed:
                    refreshed_dependencies.append(dep_class_name)
                refreshed_dependencies.extend(dep_chain)

        # Process downstream dependencies (classes that depend on this class)
        if options.downstream:
            downstream_dependencies = set()

            # Find all classes that reference this class
            for other_name, other_class in self.classes.items():
                if other_name == class_name:
                    continue

                is_dependent = False

                # Check if other_class depends on this class through member variables
                for var in other_class.get_class_references():
                    resolved_class = self.resolve_type_to_class(var.type, other_class)
                    if resolved_class and resolved_class.fully_qualified_name == class_name:
                        downstream_dependencies.add(other_name)
                        is_dependent = True
                        break

                if is_dependent:
                    continue

                # Check superclass
                if hasattr(other_class, "extends") and other_class.extends:
                    superclass = self.resolve_type_to_class(other_class.extends, other_class)
                    if superclass and superclass.fully_qualified_name == class_name:
                        downstream_dependencies.add(other_name)
                        continue

                # Check method calls
                for method in other_class.methods:
                    found = False
                    for call in getattr(method, "method_calls", []):
                        if call.service_type:
                            service_class = self.resolve_type_to_class(
                                call.service_type, other_class
                            )
                            if service_class and service_class.fully_qualified_name == class_name:
                                downstream_dependencies.add(other_name)
                                found = True
                                break
                    if found:
                        break

            # Process each downstream dependency
            for dep_class_name in downstream_dependencies:
                # Apply the same filtering as for upstream
                dep_class = self.classes.get(dep_class_name)
                if not dep_class:
                    continue

                # Apply scope filtering
                if hasattr(dep_class, "resolved_location") and dep_class.resolved_location:
                    # Check if scope is excluded
                    if dep_class.resolved_location.scope in options.exclude_scopes:
                        continue

                    # Check if scope is included
                    if (
                        options.include_scopes
                        and dep_class.resolved_location.scope not in options.include_scopes
                    ):
                        continue

                # Apply category filtering
                if (
                    options.include_categories
                    and dep_class.category not in options.include_categories
                ):
                    continue

                if options.exclude_categories and dep_class.category in options.exclude_categories:
                    continue

                # Apply package filtering (secondary)
                if any(dep_class_name.startswith(pkg) for pkg in options.exclude_packages):
                    continue

                # Recursively refresh this dependency
                dep_refreshed, dep_chain = self.refresh_class_if_needed(
                    dep_class_name,
                    load_source=load_source,
                    refresh_dependent_classes=True,
                    dependency_options=next_options,
                    visited_classes=visited_classes,
                )

                if dep_refreshed:
                    refreshed_dependencies.append(dep_class_name)
                refreshed_dependencies.extend(dep_chain)

        return was_refreshed, list(set(refreshed_dependencies))  # Deduplicate

    def find_unique_class_by_name(self, class_name: str) -> JavaClass:
        """
        Find a unique class by name or qualified name.

        If multiple classes match, raises MultipleJavaClassMatchError.
        If no class matches, raises KeyError.

        Args:
            class_name: The name or qualified name of the class to find

        Returns:
            The unique JavaClass object matching the name

        Raises:
            MultipleJavaClassMatchError: If more than one class matches
            KeyError: If no class matches
        """
        matches = self.find_class_by_name(class_name)
        if not matches:
            raise KeyError(f"No class found for name: {class_name}")
        if len(matches) > 1:
            raise MultipleJavaClassMatchError(
                f"Multiple classes found for name '{class_name}': {[cls.fully_qualified_name for cls in matches]}"
            )
        return matches[0]

    def find_class_by_path(self, path: str, is_relative: bool = False) -> JavaClass | None:
        """
        Find a class by its file path.

        Args:
            path: The path to search for
            is_relative: Whether the path is relative

        Returns:
            The JavaClass if found, None otherwise
        """
        path = path.replace("\\", "/")  # Normalize path separators

        for cls in self.classes.values():
            if is_relative:
                if cls.relative_path.replace("\\", "/") == path:
                    return cls
            else:
                if cls.absolute_path.replace("\\", "/") == path:
                    return cls

        return None

    def find_class_by_package(self, package_name: str) -> list[JavaClass]:
        """
        Find classes in a specific package.

        Args:
            package_name: The package name to search for

        Returns:
            List of JavaClass objects in the package
        """
        return [cls for cls in self.classes.values() if cls.package == package_name]

    def resolve_type_to_class(self, type_name: str, from_class: JavaClass) -> JavaClass | None:
        """
        Resolve a type name to a JavaClass using imports.

        Args:
            type_name: The type name to resolve
            from_class: The class containing the import statements

        Returns:
            The resolved JavaClass if found, None otherwise
        """
        # Extract base type if generics are present
        base_type = type_name.split("<")[0].strip()

        # If already qualified, search directly
        if "." in base_type:
            if base_type in self.classes:
                return self.classes[base_type]
            return None

        # Try to resolve using imports
        for import_def in from_class.imports:
            if not import_def.is_wildcard and import_def.class_name == base_type:
                fqn = import_def.fully_qualified_name
                if fqn in self.classes:
                    return self.classes[fqn]

            # Check wildcard imports
            if import_def.is_wildcard:
                potential_fqn = f"{import_def.package_name}.{base_type}"
                if potential_fqn in self.classes:
                    return self.classes[potential_fqn]

        # Try in the same package
        potential_fqn = f"{from_class.package}.{base_type}"
        if potential_fqn in self.classes:
            return self.classes[potential_fqn]

        # Try java.lang package for common classes
        if base_type in ["String", "Integer", "Boolean", "Object", "Exception"]:
            potential_fqn = f"java.lang.{base_type}"
            if potential_fqn in self.classes:
                return self.classes[potential_fqn]

        # Not found
        return None

    def add_constants(self, constants_map: dict[str, str]) -> None:
        """
        Add global constants to the analyzer and propagate to all classes.

        This constant injection method is intended for testing or ad-hoc scenarios.
        Normally, constants are discovered from parsed Java class definitions.
        """
        self.global_constants = constants_map
        for cls in self.classes.values():
            for key, value in constants_map.items():
                cls.constants.setdefault(key, value)

        self._resolve_all_references()

    def _resolve_all_references(self, max_passes: int = 5) -> None:
        """
        Orchestrate multi-pass resolution using specialized resolvers.
        """
        resolution_pipeline = [
            ("import_resolution", self.import_resolver.resolve_used_imports),
            ("type_resolution", self.type_resolver.resolve_all),
            ("constant_resolution", self.constant_resolver.resolve_all),
            ("path_resolution", self.path_resolver.resolve_all),
            ("autowire_resolution", self.autowire_resolver.resolve_all),
            ("property_resolution", self.property_resolver.resolve_all),
        ]
        for _pass_num in range(max_passes):
            changes_made = False
            for _stage_name, resolver_method in resolution_pipeline:
                changes_made |= resolver_method()
            if not changes_made:
                break

    def report_unresolved_references(self) -> dict[str, Any]:
        """
        Report unresolved references for all classes.
        Returns a dictionary keyed by class name.
        """
        unresolved = {}
        for class_fqn, java_class in self.classes.items():
            class_unresolved = []
            # Annotations
            for annotation in getattr(java_class, "class_annotations", []):
                if getattr(annotation, "has_unresolved_references", False):
                    class_unresolved.append(
                        {
                            "type": "annotation",
                            "name": annotation.name,
                            "unresolved": list(annotation.unresolved_values.keys()),
                        }
                    )
            # Member variables
            for var in getattr(java_class, "member_variables", []):
                if hasattr(var, "unresolved_type") and var.unresolved_type:
                    class_unresolved.append(
                        {
                            "type": "member_variable_type",
                            "name": var.name,
                            "unresolved": var.unresolved_type.raw_value,
                        }
                    )
                if hasattr(var, "unresolved_autowire") and var.unresolved_autowire:
                    class_unresolved.append(
                        {
                            "type": "autowire",
                            "name": var.name,
                            "unresolved": var.unresolved_autowire.raw_value,
                        }
                    )
            if class_unresolved:
                unresolved[class_fqn] = class_unresolved
        return unresolved

    def get_controllers(self) -> list[RestControllerClass]:
        """
        Get all controller classes.

        Returns:
            List of RestControllerClass objects
        """
        return [
            cls
            for cls in self.classes.values()
            if cls.category == ClassCategory.CONTROLLER and isinstance(cls, RestControllerClass)
        ]

    def get_services(self) -> list[ServiceClass]:
        """
        Get all service classes.

        Returns:
            List of ServiceClass objects
        """
        return [
            cls
            for cls in self.classes.values()
            if cls.category == ClassCategory.SERVICE and isinstance(cls, ServiceClass)
        ]

    def get_all_endpoints(self) -> dict[str, dict[str, list[tuple[str, str]]]]:
        """
        Get all endpoints from all controllers.

        Returns:
            A dictionary mapping controller names to their HTTP methods and paths
        """
        endpoints = {}

        for controller in self.get_controllers():
            controller_endpoints = controller.get_all_endpoints()
            if controller_endpoints:
                endpoints[controller.name] = controller_endpoints

        return endpoints

    def get_all_service_dependencies(
        self,
    ) -> dict[str, list[ClassReferenceMemberVariable]]:
        """
        Get all service dependencies from all controllers.

        Returns:
            A dictionary mapping controller names to their service dependencies
        """
        dependencies = {}

        for controller in self.get_controllers():
            if controller.service_variables:
                dependencies[controller.name] = controller.service_variables

        return dependencies

    def get_service_method_calls(self) -> dict[str, dict[str, list[MethodCallInfo]]]:
        """
        Get all service method calls from controller methods.

        Returns:
            A dictionary mapping controller names to dictionaries of method names and their service calls
        """
        method_calls = {}

        for controller in self.get_controllers():
            # service calls within the current controller
            controller_calls = {}

            for method in controller.methods:
                if method.method_calls:
                    controller_calls[method.name] = method.method_calls

            if controller_calls:
                method_calls[controller.name] = controller_calls

        return method_calls

    def get_dependencies_graph(self) -> dict[str, list[str]]:
        """
        Create a dependency graph between classes.
        TODO - This is never actually used though it has a test??

        Returns:
            Dictionary mapping class names to lists of dependency class names
        """
        graph = {}

        for class_name, cls in self.classes.items():
            dependencies = []

            # Add dependencies from class reference member variables
            for var in cls.get_class_references():
                if var is None:
                    continue

                # Try to resolve the type to a fully qualified name
                resolved_class = self.resolve_type_to_class(var.type, cls)
                if resolved_class:
                    dependencies.append(resolved_class.fully_qualified_name)
                else:
                    # If can't resolve, just use the type name
                    dependencies.append(var.type)

            if dependencies:
                graph[class_name] = dependencies

        return graph

    # # More robust dependency detection with proper null checks
    # def get_dependencies_graph(self) -> Dict[str, List[str]]:
    #     """
    #     Create a dependency graph between classes with proper null checking.
    #     """
    #     graph = {}

    #     for class_name, cls in self.classes.items():
    #         if cls is None:
    #             continue

    #         dependencies = []

    #         # Add dependencies from class reference member variables
    #         for var in cls.get_class_references():
    #             if var is None:
    #                 continue

    #             # Try to resolve the type to a fully qualified name
    #             resolved_class = self.resolve_type_to_class(var.type, cls)
    #             if resolved_class:
    #                 dependencies.append(resolved_class.fully_qualified_name)
    #             else:
    #                 # If can't resolve, just use the type name
    #                 dependencies.append(var.type)

    #         # Add superclass dependency if it exists
    #         if hasattr(cls, "extends") and cls.extends:
    #             superclass = self.resolve_type_to_class(cls.extends, cls)
    #             if superclass:
    #                 dependencies.append(superclass.fully_qualified_name)

    #         # Add method call dependencies
    #         for method in cls.methods:
    #             if method is None:
    #                 continue

    #             for call in getattr(method, "method_calls", []):
    #                 if call is None or not hasattr(call, "service_type") or not call.service_type:
    #                     continue

    #                 service_class = self.resolve_type_to_class(call.service_type, cls)
    #                 if service_class:
    #                     dependencies.append(service_class.fully_qualified_name)

    #         if dependencies:
    #             graph[class_name] = list(set(dependencies))  # Deduplicate

    #     return graph

    def load_class_with_dependencies(
        self, class_name: str, dependency_options: DependencyOptions | None = None
    ) -> list[JavaClass]:
        """
        Load a class and its dependency chain with source code.

        Args:
            class_name: Name or fully qualified name of the class to analyze
            dependency_options: Options for controlling dependency loading

        Returns:
            List of JavaClass objects for the class and its dependencies
        """
        # Find the class
        classes = self.find_class_by_name(class_name)
        if not classes:
            raise ValueError(f"Class '{class_name}' not found")

        target_class = classes[0]

        # Ensure source is loaded for the target class
        self.refresh_class_if_needed(target_class.fully_qualified_name, load_source=True)

        # Use default dependency options if none provided
        options = dependency_options or DependencyOptions()

        # Load all dependencies
        _, loaded_deps = self.refresh_class_if_needed(
            target_class.fully_qualified_name,
            load_source=True,
            refresh_dependent_classes=True,
            dependency_options=options,
        )

        # Get loaded classes
        result = [target_class]
        for dep_name in loaded_deps:
            dep_class = self.classes.get(dep_name)
            if dep_class and hasattr(dep_class, "source_code") and dep_class.source_code:
                result.append(dep_class)

        return result

    def get_classes_by_category_with_dependencies(
        self,
        category: ClassCategory,
        load_dependencies: bool = True,
        dependency_options: DependencyOptions | None = None,
    ) -> list[JavaClass]:
        """
        Get all classes of a specific category and optionally load their dependencies.

        Args:
            category: The ClassCategory to filter by
            load_dependencies: Whether to load dependencies
            dependency_options: Options for controlling dependency loading

        Returns:
            List of JavaClass objects in the specified category with dependencies loaded
        """
        # Filter for the specified category
        classes = self.filter_java_classes(lambda cls: cls.category == category)

        # If no dependency loading requested, just return the filtered classes
        if not load_dependencies:
            return classes

        # Load dependencies for each class
        result = []
        for cls in classes:
            # Use the existing method to load dependencies
            self.load_class_with_dependencies(
                cls.fully_qualified_name, dependency_options=dependency_options
            )
            result.append(cls)

        return result

    def filter_java_classes(
        self, class_filter: Callable[[JavaClass], bool] | None = None
    ) -> list[JavaClass]:
        """
        Filter Java classes based on a predicate.

        Args:
            class_filter: Function that takes a JavaClass and returns True if it should be included

        Returns:
            List of JavaClass objects that pass the filter
        """
        if class_filter is None:
            return list(self.classes.values())

        return [cls for cls in self.classes.values() if class_filter(cls)]

    def dump_classes_to_string(
        self,
        classes: list[JavaClass],
        resolve_constants: bool = False,
        include_methods: dict[str, list[str]] | None = None,
        include_method_comments: bool = True,
        include_element_types: list[ElementType] | None = None,
    ) -> dict[str, str]:
        """
        Dump source code for a list of JavaClass objects, with optional method and comment filtering.

        Args:
            classes: List of JavaClass objects to dump
            resolve_constants: Whether to resolve constants in the source code - if False ignores include_element_types
            include_methods: Optional dict mapping class name or FQN to list of method names to include
                If not provided for a class, all methods are included
            include_method_comments: Whether to include method and constructor comments in the output

        Returns:
            Dict mapping class names to their source code
        """
        result = {}

        for java_class in classes:
            logger.debug(
                "dump_classes_to_string: class=%s, include_methods=%s, include_method_comments=%s, include_element_types=%s",
                java_class.name,
                include_methods,
                include_method_comments,
                include_element_types,
            )
            class_name = java_class.name
            class_fqn = java_class.fully_qualified_name

            # Skip classes without source
            if not hasattr(java_class, "source_code") or not java_class.source_code:
                continue

            # Combine method/constructor/comment removals with constant replacements in one pass
            src = java_class.source_code
            removal_ops: list[tuple[int, int]] = []

            # Determine if we are filtering methods
            method_key = None
            if include_methods and (class_name in include_methods or class_fqn in include_methods):
                method_key = class_name if class_name in include_methods else class_fqn
            included_methods = (include_methods or {}).get(method_key, []) if method_key else []

            # Collect ranges to remove for methods
            if hasattr(java_class, "method_offsets"):
                for m in java_class.methods:
                    if m.name not in java_class.method_offsets:
                        continue
                    m_start, m_end = java_class.method_offsets[m.name]
                    # exclude entire method if not in included list
                    if method_key and m.name not in included_methods:
                        removal_ops.append((m_start, m_end))
                        # also drop its comments
                        for c_start, c_end in java_class.method_comment_offsets.get(m.name, []):
                            removal_ops.append((c_start, c_end))
                    # drop comments for included methods if requested
                    elif not include_method_comments:
                        for c_start, c_end in java_class.method_comment_offsets.get(m.name, []):
                            removal_ops.append((c_start, c_end))

            # Handle constructor comments (always include constructors, but handle comments based on include_method_comments)
            if hasattr(java_class, "constructor_comment_offsets") and not include_method_comments:
                for c in java_class.constructors:
                    for (
                        comment_start,
                        comment_end,
                    ) in java_class.constructor_comment_offsets.get(c.name, []):
                        removal_ops.append((comment_start, comment_end))

            logger.trace("Collected removal_ops for %s: %s", java_class.name, removal_ops)

            final = src

            # Apply removals + constant replacements together to
            # avoid creating offset changes if done separately
            with contextlib.suppress(Exception):
                final = SourceReplacer.apply_resolutions(
                    src,
                    resolve_constants,
                    removal_ops,
                    getattr(java_class, "resolved_references", []),
                    include_element_types=include_element_types,
                    include_methods=include_methods,
                )

            logger.trace("Original source for %s:\n%s", class_name, java_class.source_code)
            logger.debug("Final dumped source for %s:\n%s", class_name, final)
            result[class_fqn] = collapse_blank_lines(final)

        return result

    def find_classes_by_endpoint(
        self, endpoint_terms: list[str], optional_base_paths: list[str] | None = None
    ) -> list[JavaClass]:
        """
        Find controller classes that contain endpoints starting with any of the given terms,
        optionally prefixed by any of the provided base paths.

        The search matches against the beginning of the endpoint's full path. If base paths are provided,
        the method searches for both the original terms and terms prefixed with each base path.

        Args:
            endpoint_terms: List of endpoint path prefixes to search for
            optional_base_paths: Optional list of base paths to prepend to endpoint terms

        Returns:
            List of RestControllerClass objects containing matching endpoints
        """
        matches = []
        seen_fqns = set()  # Track fully qualified names to avoid duplicates
        search_terms = list(endpoint_terms)  # Start with original terms

        # Add terms with optional base paths prefixed
        if optional_base_paths:
            for base_path in optional_base_paths:
                for term in endpoint_terms:
                    # Make sure both base_path and term are properly formatted with slashes
                    if base_path:
                        # Normalize base path - ensure it starts with / and ends with /
                        formatted_base = base_path
                        if not formatted_base.startswith("/"):
                            formatted_base = f"/{formatted_base}"
                        if not formatted_base.endswith("/"):
                            formatted_base = f"{formatted_base}/"

                        # Normalize term - ensure it doesn't start with /
                        formatted_term = term
                        if formatted_term.startswith("/"):
                            formatted_term = formatted_term[1:]

                        # Combine them
                        combined = f"{formatted_base}{formatted_term}"

                        # Normalize: remove any double slashes and ensure it starts with /
                        while "//" in combined:
                            combined = combined.replace("//", "/")
                        if not combined.startswith("/"):
                            combined = f"/{combined}"

                        search_terms.append(combined)

        # Log and debug info
        controllers = self.get_controllers()

        for controller in controllers:
            # Skip if already added
            if controller.fully_qualified_name in seen_fqns:
                continue

            found = False
            for endpoint in controller.endpoints:
                full_paths = endpoint.get_full_path(controller.base_endpoint_path)
                for _http_method, path_or_paths in full_paths.items():
                    paths = path_or_paths if isinstance(path_or_paths, list) else [path_or_paths]
                    for path in paths:
                        for term in search_terms:
                            # Check if path starts with the search term
                            if path.startswith(term):
                                matches.append(controller)
                                seen_fqns.add(controller.fully_qualified_name)
                                found = True
                                break
                        if found:
                            break
                    if found:
                        break
                if found:
                    break

        return matches  # Guaranteed to have no duplicates
