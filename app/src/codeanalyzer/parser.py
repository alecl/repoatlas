import logging
import os
import re
import zlib
from hashlib import md5
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Type, Union

from tree_sitter import Language, Parser
from tree_sitter_language_pack import get_language, get_parser

from app.src.codeanalyzer.code_analyzer_config import CodeAnalyzerConfig
from app.src.codeanalyzer.util import node_to_dict
from app.src.logging import logger

from .ast_constants import FieldName, NodeType
from .classification import (
    infer_api_client_category,
    infer_class_category,
    infer_member_variable_category,
)

# Import the models
from .models import (
    AbstractionType,
    Annotation,
    ArgumentExpressionType,
    ClassCategory,
    ClassReferenceMemberVariable,
    DependencyOptions,
    ElementType,
    EnumClass,
    EnumConstant,
    ImportDefinition,
    JavaClass,
    JavaConstructor,
    JavaMethod,
    MemberVariable,
    MemberVariableCategory,
    MethodCallArgument,
    MethodCallInfo,
    Parameter,
    ReferenceLocation,
    RestControllerClass,
    RestEndpoint,
    ServiceClass,
    UnresolvedConstant,
    UnresolvedReference,
)
from .type_resolver import JDK_TYPES


class LocalNameResolver:
    """
    Resolve simple Java type names to fully-qualified names using only package and imports.
    """

    def __init__(self, package: str, imports: list[ImportDefinition]):
        self.package = package
        self.imports = imports

    def to_fqn(self, name: str) -> str:
        # Handle generics by stripping after '<'
        simple = name.split("<", 1)[0].strip()
        # 1) explicit imports
        for imp in self.imports:
            if not imp.is_wildcard and imp.class_name == simple:
                return imp.fully_qualified_name
        # 2) wildcard imports (skip java.lang types)
        for imp in self.imports:
            if imp.is_wildcard and simple not in JDK_TYPES:
                return f"{imp.fully_qualified_name}.{simple}"
        # 3) java.lang fallback
        if simple in JDK_TYPES:
            return f"java.lang.{simple}"
        # 4) no import match; return simple name
        return simple


class MissingDeclarationException(Exception):
    """Raised when no class or interface declaration is found in the Java file."""


class JavaParser:
    """
    Parser for Java files using tree-sitter.
    Extracts Java class information with special handling for Spring components.
    """

    def __init__(
        self,
        config: CodeAnalyzerConfig | None = None,
        language_path: str | None = None,
    ):
        """
        Initialize the Java parser.

        Args:
            config: Configuration object, uses default if None
            language_path: Ignored. The grammar is always loaded from tree_sitter_languages.
        """
        self.config = config or CodeAnalyzerConfig()
        self.parser = get_parser("java")
        self.java_language = get_language("java")

    def _looks_like_constant_reference(self, value: str) -> bool:
        """
        Determine if a value looks like a constant reference (e.g., Constants.BASE_PATH).
        """
        # Heuristic: contains a dot, does not start with a quote or slash, and is not a boolean literal
        if not isinstance(value, str):
            return False
        value = value.strip()
        return bool(
            "." in value
            and not value.startswith(("/", '"', "'"))
            and value.lower() not in ("true", "false")
        )

    def _extract_annotation_from_node(
        self, annotation_node, element_type: ElementType, element_name: str
    ) -> Annotation | None:
        """
        Extract annotation from a single annotation node.

        Args:
            annotation_node: The tree-sitter node representing an annotation
            element_type: The type of element this annotation is attached to
            element_name: The name of the element (class name, method name, etc.)

        Returns:
            Annotation object or None if extraction fails
        """
        name_node = annotation_node.child_by_field_name(FieldName.NAME)
        if not name_node:
            return None

        # Extract simple name without package prefix
        full_name = name_node.text.decode("utf-8")
        simple_name = full_name.split(".")[-1] if "." in full_name else full_name
        values = {}
        unresolved_values = {}

        # Get annotation arguments
        argument_list = annotation_node.child_by_field_name(FieldName.ARGUMENTS)
        if argument_list:
            for arg in argument_list.children:
                if arg.type == "," or arg.type == "(" or arg.type == ")":
                    continue

                if arg.type == NodeType.ELEMENT_VALUE_PAIR:
                    # Handle key=value pairs like value="/api/v1/organizations"
                    key = None
                    value = None
                    value_node = None

                    for child in arg.children:
                        if child.type == NodeType.IDENTIFIER:
                            key = child.text.decode("utf-8")
                        elif child.type in [
                            NodeType.STRING_LITERAL,
                            NodeType.FIELD_ACCESS,
                            NodeType.TRUE,
                            NodeType.FALSE,
                            NodeType.IDENTIFIER,
                        ]:
                            value, value_node = self._extract_annotation_value(child)
                        elif child.type == "=":
                            continue

                    if key and value is not None:
                        self._process_annotation_value(
                            key,
                            value,
                            value_node,
                            values,
                            unresolved_values,
                            element_type,
                            element_name,
                            simple_name,
                        )

                elif arg.type == NodeType.STRING_LITERAL:
                    # Handle single unnamed string argument
                    val = arg.text.decode("utf-8")[1:-1]  # Remove quotes
                    values["value"] = val

                elif arg.type == NodeType.ELEMENT_VALUE_ARRAY_INITIALIZER:
                    # Handle array initializer for annotations like @GetMapping({"/a","/b"})
                    array_vals = []
                    for elem in arg.children:
                        if elem.type == NodeType.STRING_LITERAL:
                            array_vals.append(elem.text.decode("utf-8")[1:-1])
                        elif elem.type == NodeType.FIELD_ACCESS:
                            array_vals.append(elem.text.decode("utf-8"))
                    values["value"] = array_vals

                elif arg.type == NodeType.FIELD_ACCESS:
                    # Handle constant references
                    val = arg.text.decode("utf-8")
                    values["value"] = val
                    unresolved_values["value"] = UnresolvedConstant(
                        raw_value=val,
                        location=ReferenceLocation(
                            class_name=getattr(self, "current_class_name", "UnknownClass"),
                            element_type=element_type,
                            element_name=simple_name,
                            detail="value",
                            source_start_offset=arg.start_byte,
                            source_end_offset=arg.end_byte,
                        ),
                    )
                else:
                    # Try to extract value directly
                    value, value_node = self._extract_annotation_value(arg)
                    if value is not None:
                        self._process_annotation_value(
                            "value",
                            value,
                            value_node,
                            values,
                            unresolved_values,
                            element_type,
                            element_name,
                            simple_name,
                        )

        return Annotation(name=simple_name, values=values, unresolved_values=unresolved_values)

    def _process_annotation_value(
        self,
        key: str,
        value: str,
        value_node: Any,
        values: dict[str, str],
        unresolved_values: dict[str, UnresolvedConstant],
        element_type: ElementType,
        element_name: str,
        annotation_name: str,
    ):
        """
        Process an annotation value and create unresolved constant if needed.

        Args:
            key: The annotation parameter key
            value: The extracted string value
            value_node: The tree-sitter node containing the value
            values: Dictionary to store resolved values
            unresolved_values: Dictionary to store unresolved constants
            element_type: Type of element the annotation is on
            element_name: Name of the element
            annotation_name: Name of the annotation
        """
        from .models import ReferenceLocation, UnresolvedConstant

        if self._looks_like_constant_reference(value):
            values[key] = value
            unresolved_values[key] = UnresolvedConstant(
                raw_value=value,
                location=ReferenceLocation(
                    class_name=getattr(self, "current_class_name", "UnknownClass"),
                    element_type=element_type,
                    element_name=annotation_name,
                    detail=key,
                    source_start_offset=value_node.start_byte if value_node else None,
                    source_end_offset=value_node.end_byte if value_node else None,
                ),
            )
        else:
            values[key] = value

    def _extract_annotation_value(self, value_node) -> tuple[str, Any]:
        """
        Extract the value from an annotation value node.

        Args:
            value_node: The tree-sitter node representing the value

        Returns:
            Tuple of (extracted value as string, original node)
        """
        if value_node.type == NodeType.STRING_LITERAL:
            return value_node.text.decode("utf-8")[1:-1], value_node  # Remove quotes
        elif (
            value_node.type == NodeType.FIELD_ACCESS
            or value_node.type == NodeType.IDENTIFIER
            or value_node.type == NodeType.TRUE
            or value_node.type == NodeType.FALSE
        ):
            return value_node.text.decode("utf-8"), value_node
        else:
            # For other types, return the raw text
            return value_node.text.decode("utf-8"), value_node

    def _extract_annotations(
        self, node, element_type: ElementType, element_name: str
    ) -> list[Annotation]:
        """
        Extract annotations from a tree-sitter node.

        Args:
            node: The tree-sitter node to extract annotations from
            element_type: The type of element these annotations are attached to
            element_name: The name of the element (class, method, field name)

        Returns:
            List of Annotation objects
        """
        annotations = []

        # Check for modifiers node which contains annotations
        modifiers_node = None
        for child in node.children:
            if child.type == NodeType.MODIFIERS:
                modifiers_node = child
                break

        if modifiers_node:
            for child in modifiers_node.children:
                if child.type == NodeType.MARKER_ANNOTATION:
                    # Simple annotation without arguments like @Override
                    name_node = child.child_by_field_name(FieldName.NAME)
                    if name_node:
                        simple_name = name_node.text.decode("utf-8").split(".")[-1]
                        annotations.append(Annotation(name=simple_name))
                elif child.type == NodeType.ANNOTATION:
                    # Annotation with arguments
                    annotation = self._extract_annotation_from_node(
                        child, element_type, element_name
                    )
                    if annotation:
                        annotations.append(annotation)

        # Also check for annotations before the current node (siblings)
        current = node
        while current.prev_sibling:
            current = current.prev_sibling
            if current.type == NodeType.MARKER_ANNOTATION:
                name_node = current.child_by_field_name(FieldName.NAME)
                if name_node:
                    simple_name = name_node.text.decode("utf-8").split(".")[-1]
                    annotations.append(Annotation(name=simple_name))
            elif current.type == NodeType.ANNOTATION:
                annotation = self._extract_annotation_from_node(
                    current, element_type, element_name
                )
                if annotation:
                    annotations.append(annotation)

        return annotations

    def _extract_modifiers(self, node) -> list[str]:
        """
        Extract modifiers (public, private, static, etc.) from a node.

        Args:
            node: The tree-sitter node to extract modifiers from

        Returns:
            List of modifier strings
        """
        modifiers = []

        # Check for modifiers on the node itself
        modifiers_node = None
        for child in node.children:
            if child.type == NodeType.MODIFIERS:
                modifiers_node = child
                break

        if modifiers_node:
            for modifier in modifiers_node.children:
                if modifier.type not in [
                    NodeType.MARKER_ANNOTATION,
                    NodeType.ANNOTATION,
                ]:
                    modifiers.append(modifier.text.decode("utf-8"))

        return modifiers

    def _extract_imports(self, root_node) -> tuple[list[ImportDefinition], list[str]]:
        """
        Extract import statements from the Java file.

        Args:
            root_node: The tree-sitter root node

        Returns:
            Tuple of (List of ImportDefinition objects, List of import strings)
        """
        imports = []
        import_statements = []

        for child in root_node.children:
            if child.type == NodeType.IMPORT_DECLARATION:
                is_static = False
                is_wildcard = False

                # Check if this is a static import
                for grandchild in child.children:
                    if grandchild.type == "static" or grandchild.text.decode("utf-8") == "static":
                        is_static = True
                        break

                # Get the import name
                import_text = child.text.decode("utf-8")
                import_name = ""

                for grandchild in child.children:
                    if (
                        grandchild.type == NodeType.SCOPED_IDENTIFIER
                        or grandchild.type == NodeType.IDENTIFIER
                    ):
                        import_name = grandchild.text.decode("utf-8")
                    elif grandchild.type == NodeType.ASTERISK:
                        is_wildcard = True

                if not import_name and "import" in import_text:
                    # Extract from raw text
                    parts = import_text.split()
                    if "static" in parts:
                        # Static import
                        import_name = parts[2].rstrip(";")
                    else:
                        import_name = parts[1].rstrip(";")

                if import_name.endswith(".*"):
                    is_wildcard = True
                    import_name = import_name[:-2]

                imports.append(
                    ImportDefinition(
                        fully_qualified_name=import_name,
                        is_static=is_static,
                        is_wildcard=is_wildcard,
                    )
                )

                # Also store the original import statement
                import_statements.append(import_name)

        return imports, import_statements

    def _extract_package(self, root_node) -> str:
        """
        Extract the package name from the Java file.

        Args:
            root_node: The tree-sitter root node

        Returns:
            The package name as a string
        """
        for child in root_node.children:
            if child.type == NodeType.PACKAGE_DECLARATION:
                for grandchild in child.children:
                    if grandchild.type == NodeType.SCOPED_IDENTIFIER:
                        return grandchild.text.decode("utf-8")

        return ""

    def _extract_constants(self, class_node) -> dict[str, str]:
        """
        Extract constant field definitions from the class.

        Args:
            class_node: The tree-sitter node representing the class

        Returns:
            Dictionary mapping constant names to their values
        """
        constants = {}

        class_body = None
        for child in class_node.children:
            if child.type == NodeType.CLASS_BODY:
                class_body = child
                break

        if class_body:
            for child in class_body.children:
                if child.type == NodeType.FIELD_DECLARATION:
                    modifiers = self._extract_modifiers(child)

                    # If this is a static final field (constant)
                    if "static" in modifiers and "final" in modifiers:
                        declarator_node = None
                        for grandchild in child.children:
                            if grandchild.type == NodeType.VARIABLE_DECLARATOR:
                                declarator_node = grandchild
                                break

                        if declarator_node:
                            name_node = declarator_node.child_by_field_name(FieldName.NAME)
                            value_node = declarator_node.child_by_field_name(FieldName.VALUE)

                            if name_node and value_node:
                                name = name_node.text.decode("utf-8")
                                if value_node.type == NodeType.STRING_LITERAL:
                                    value = value_node.text.decode("utf-8")[1:-1]  # Remove quotes
                                    constants[name] = value

        return constants

    def _extract_enum_constants(self, enum_node) -> list[EnumConstant]:
        """
        Extract enum constants from an enum declaration.

        Args:
            enum_node: The tree-sitter node representing the enum declaration

        Returns:
            List of EnumConstant objects
        """
        enum_constants = []

        # Find the enum_body node
        enum_body = None
        for child in enum_node.children:
            if child.type == NodeType.ENUM_BODY:
                enum_body = child
                break

        if not enum_body:
            return enum_constants

        # Process each enum_constant node in the enum_body
        for child in enum_body.children:
            if child.type == NodeType.ENUM_CONSTANT:
                # Extract the constant name
                name_node = child.child_by_field_name(FieldName.NAME)
                if not name_node:
                    continue

                name = name_node.text.decode("utf-8")

                # Extract constructor arguments if any
                args = []
                args_node = child.child_by_field_name(FieldName.ARGUMENTS)
                if args_node:
                    for arg_child in args_node.children:
                        # Skip parentheses
                        if arg_child.type in ["(", ")"]:
                            continue

                        # Process string literals and other argument types
                        if arg_child.type == NodeType.STRING_LITERAL:
                            # Remove surrounding quotes
                            arg_value = arg_child.text.decode("utf-8")[1:-1]
                            args.append(arg_value)
                        elif arg_child.type not in [",", ";"]:
                            # Add other argument types as raw text
                            args.append(arg_child.text.decode("utf-8"))

                # Extract annotations (though enums typically have few annotations)
                annotations = self._extract_annotations(child, ElementType.ENUM_CONSTANT, name)

                # Create the EnumConstant object with source offsets
                enum_constants.append(
                    EnumConstant(
                        name=name,
                        constructor_arguments=args,
                        annotations=annotations,
                        source_start_offset=child.start_byte,
                        source_end_offset=child.end_byte,
                    )
                )

            # Stop when we hit the semicolon or enum_body_declarations
            if child.type == ";" or child.type == NodeType.ENUM_BODY_DECLARATIONS:
                break

        return enum_constants

    def _extract_member_variables(self, class_node) -> list[MemberVariable]:
        """
        Extract member variables from a class node.

        Args:
            class_node: The tree-sitter node representing the class

        Returns:
            List of MemberVariable objects
        """
        from .models import (
            ElementType,
            ReferenceLocation,
            UnresolvedAutowire,
            UnresolvedType,
        )

        member_variables = []

        class_body = None
        for child in class_node.children:
            if child.type == NodeType.CLASS_BODY:
                class_body = child
                break

        if class_body:
            for child in class_body.children:
                if child.type == NodeType.FIELD_DECLARATION:
                    # Get the type
                    type_node = child.child_by_field_name(FieldName.TYPE)
                    if not type_node:
                        continue
                    type_text = type_node.text.decode("utf-8")

                    # Get the variable name(s) - could be multiple in one declaration
                    for declarator_node in child.children:
                        if declarator_node.type == NodeType.VARIABLE_DECLARATOR:
                            name_node = declarator_node.child_by_field_name(FieldName.NAME)
                            if name_node:
                                name = name_node.text.decode("utf-8")

                                # Get modifiers and annotations
                                modifiers = self._extract_modifiers(child)
                                annotations = self._extract_annotations(
                                    child, ElementType.FIELD_ANNOTATION, name
                                )

                                # Determine if it's autowired or has qualifier
                                is_autowired = any(
                                    anno.name == "Autowired" for anno in annotations
                                )
                                qualifier = None

                                for anno in annotations:
                                    if anno.name == "Qualifier":
                                        raw_qual = anno.values.get(
                                            "value", anno.values.get("", None)
                                        )
                                        if isinstance(raw_qual, list):
                                            qualifier = raw_qual[0] if raw_qual else None
                                        elif isinstance(raw_qual, str):
                                            qualifier = raw_qual
                                        else:
                                            qualifier = None

                                # Determine the variable category
                                category = infer_member_variable_category(type_text)

                                # Mark unresolved type if not primitive/collection/map
                                unresolved_type = None
                                if category == MemberVariableCategory.CLASS_REFERENCE:
                                    unresolved_type = UnresolvedType(
                                        raw_value=type_text,
                                        location=ReferenceLocation(
                                            class_name=getattr(
                                                self,
                                                "current_class_name",
                                                "UnknownClass",
                                            ),
                                            element_type=ElementType.FIELD_DECLARATION,
                                            element_name=name,
                                        ),
                                        is_interface=False,  # Could be improved with interface detection
                                        is_generic="<" in type_text and ">" in type_text,
                                    )

                                # Mark unresolved autowire if autowired
                                unresolved_autowire = None
                                if (
                                    is_autowired
                                    and category == MemberVariableCategory.CLASS_REFERENCE
                                ):
                                    unresolved_autowire = UnresolvedAutowire(
                                        raw_value=type_text,
                                        location=ReferenceLocation(
                                            class_name=getattr(
                                                self,
                                                "current_class_name",
                                                "UnknownClass",
                                            ),
                                            element_type=ElementType.FIELD_DECLARATION,
                                            element_name=name,
                                        ),
                                        interface_type=type_text,
                                        qualifier=qualifier,
                                    )

                                if category == MemberVariableCategory.CLASS_REFERENCE:
                                    # Determine the referenced class category
                                    # TODO - needs fully qualified name for accurate inference
                                    referenced_category = infer_class_category(
                                        type_text, [], config=self.config
                                    )

                                    member_variables.append(
                                        ClassReferenceMemberVariable(
                                            name=name,
                                            type=type_text,
                                            category=category,
                                            annotations=annotations,
                                            modifiers=modifiers,
                                            is_autowired=is_autowired,
                                            qualifier=qualifier,
                                            referenced_class_category=referenced_category,
                                            unresolved_type=unresolved_type,
                                            unresolved_autowire=unresolved_autowire,
                                        )
                                    )
                                else:
                                    member_variables.append(
                                        MemberVariable(
                                            name=name,
                                            type=type_text,
                                            category=category,
                                            annotations=annotations,
                                            modifiers=modifiers,
                                        )
                                    )

        return member_variables

    def _extract_method_parameters(self, method_node) -> list[Parameter]:
        """
        Extract parameters from a method.

        Args:
            method_node: The tree-sitter node representing the method

        Returns:
            List of Parameter objects
        """
        parameters = []

        parameters_node = method_node.child_by_field_name(FieldName.PARAMETERS)
        if not parameters_node:
            return parameters

        for param_node in parameters_node.children:
            if param_node.type == NodeType.FORMAL_PARAMETER:
                type_node = param_node.child_by_field_name(FieldName.TYPE)
                name_node = param_node.child_by_field_name(FieldName.NAME)

                if type_node and name_node:
                    type_text = type_node.text.decode("utf-8")
                    name = name_node.text.decode("utf-8")

                    # Extract annotations for this parameter
                    annotations = self._extract_annotations(
                        param_node, ElementType.METHOD_ANNOTATION, name
                    )

                    parameters.append(
                        Parameter(name=name, type=type_text, annotations=annotations)
                    )

        return parameters

    def _extract_method_exceptions(self, method_node) -> list[str]:
        """
        Extract exceptions thrown by a method.

        Args:
            method_node: The tree-sitter node representing the method

        Returns:
            List of exception names
        """
        exceptions = []

        # Find throws clause
        for child in method_node.children:
            if child.type == NodeType.THROWS:
                for exception_node in child.children:
                    if (
                        exception_node.type == NodeType.TYPE_IDENTIFIER
                        or exception_node.type == NodeType.SCOPED_TYPE_IDENTIFIER
                    ):
                        exceptions.append(exception_node.text.decode("utf-8"))

        return exceptions

    def _find_all_method_invocations(self, node) -> list:
        """
        Recursively find all method_invocation nodes in the given AST node.

        Args:
            node: The tree-sitter node to search in

        Returns:
            List of method_invocation nodes
        """
        invocations = []

        # Check if current node is a method invocation
        if node.type == NodeType.METHOD_INVOCATION:
            invocations.append(node)

        # Recursively search children
        for child in node.children:
            invocations.extend(self._find_all_method_invocations(child))

        return invocations

    def _extract_method_calls(
        self, method_node, member_variables: list[MemberVariable], source_code: str
    ) -> list[MethodCallInfo]:
        """
        Extract ALL method calls from a method body using tree-sitter AST traversal.

        Args:
            method_node: The tree-sitter node representing the method
            member_variables: List of member variables to match against
            source_code: The source code string

        Returns:
            List of MethodCallInfo objects for all method calls
        """
        method_calls = []
        body_node = method_node.child_by_field_name(FieldName.BODY)

        if not body_node:
            return method_calls

        # Create lookup for member variables by name
        member_var_lookup = {var.name: var for var in member_variables}

        # Find all method invocation nodes in the method body
        method_invocations = self._find_all_method_invocations(body_node)

        # Process each method invocation
        for invocation_node in method_invocations:
            method_call_info = self._extract_method_call_info_enhanced(
                invocation_node, member_var_lookup, source_code
            )
            if method_call_info:
                method_calls.append(method_call_info)

        # Fallback for mocked or missing AST: regex-based extraction of var.method(...)
        # Anything that falls into here we should fix so AST can handle it instead
        # This code is NOT smart about ignoring commented code while AST is
        # I don't think we need this any longer
        # if not method_calls:
        #     body_node_str = body_node.text.decode("utf-8")
        #     for var_name, var in member_var_lookup.items():
        #         pattern = rf"\b{re.escape(var_name)}\.(\w+)\("
        #         for match in re.finditer(pattern, body_node_str):
        #             mci = MethodCallInfo(
        #                 target_name=var_name,
        #                 method_name=match.group(1),
        #                 target_type=var.type,
        #                 target_class_category=getattr(
        #                     var, "referenced_class_category", ClassCategory.UNKNOWN
        #                 ),
        #             )
        #             logger.warning(
        #                 f"Fallback regex method call extraction: {mci} in source (likely missed by tree-sitter AST)"
        #             )
        #             method_calls.append(mci)
        return method_calls

    def _find_matching_paren(self, text: str, open_pos: int) -> int:
        """
        Find the matching closing parenthesis.

        Args:
            text: The text to search in
            open_pos: Position of the opening parenthesis

        Returns:
            Position of the matching closing parenthesis or -1 if not found
        """
        depth = 1
        for i in range(open_pos + 1, len(text)):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    return i
        return -1

    def _extract_method_call_info_enhanced(
        self,
        invocation_node,
        member_var_lookup: dict[str, MemberVariable],
        source_code: str,
    ) -> MethodCallInfo | None:
        """
        Extract comprehensive method call information from a method_invocation node.

        Args:
            invocation_node: The method_invocation tree-sitter node
            member_var_lookup: Dictionary mapping variable names to MemberVariable objects
            source_code: The source code string

        Returns:
            MethodCallInfo with full argument details, or None if extraction fails
        """
        # Get the object being called on (left side of the dot)
        object_node = invocation_node.child_by_field_name(FieldName.OBJECT)

        # Get the method name being called
        name_node = invocation_node.child_by_field_name(FieldName.NAME)
        if not name_node:
            return None

        method_name = name_node.text.decode("utf-8")

        # Determine target information
        target_info = self._determine_target_info(object_node, member_var_lookup)
        if not target_info:
            return None

        target_name, target_type, target_class_category, source_variable = target_info

        # Extract arguments
        arguments = self._extract_method_arguments(invocation_node, source_code)

        return MethodCallInfo(
            target_name=target_name,
            target_type=target_type,
            target_class_category=target_class_category,
            method_name=method_name,
            arguments=arguments,
            source_variable=source_variable,
        )

    def _determine_target_info(
        self, object_node, member_var_lookup: dict[str, MemberVariable]
    ) -> tuple[str, str, ClassCategory, ClassReferenceMemberVariable | None] | None:
        """
        Determine target information from an object node.

        Args:
            object_node: The object node from a method_invocation
            member_var_lookup: Dictionary mapping variable names to MemberVariable objects

        Returns:
            Tuple of (target_name, target_type, target_class_category, source_variable) or None
        """
        if not object_node:
            # Static method call or method on 'this' - use current class
            return None  # Skip for now, could be enhanced later

        root_object_name = self._get_root_object_name(object_node)
        if not root_object_name:
            return None

        # Check if it's a member variable we know about
        if root_object_name in member_var_lookup:
            var = member_var_lookup[root_object_name]
            if isinstance(var, ClassReferenceMemberVariable):
                return (root_object_name, var.type, var.referenced_class_category, var)
            else:
                # Non-class reference variable (primitive, collection, etc.)
                return (root_object_name, var.type, ClassCategory.OTHER, None)

        # Unknown variable - could be parameter, local variable, or static reference
        return (
            root_object_name,
            "Unknown",  # Type unknown
            ClassCategory.UNKNOWN,
            None,
        )

    def _extract_method_arguments(
        self, invocation_node, source_code: str
    ) -> list[MethodCallArgument]:
        """
        Extract detailed argument information from a method invocation.

        Args:
            invocation_node: The method_invocation tree-sitter node
            source_code: The source code string

        Returns:
            List of MethodCallArgument objects
        """
        arguments = []
        arguments_node = invocation_node.child_by_field_name(FieldName.ARGUMENTS)

        if not arguments_node:
            return arguments

        position = 0
        for child in arguments_node.children:
            # Skip parentheses and commas, process actual argument expressions
            if child.type not in [
                NodeType.OPEN_PAREN,
                NodeType.CLOSE_PAREN,
                NodeType.COMMA,
            ]:
                arg = self._create_method_call_argument(child, position, source_code)
                arguments.append(arg)
                position += 1

        return arguments

    def _get_root_object_name(self, object_node) -> str | None:
        if object_node.type == NodeType.IDENTIFIER:
            return object_node.text.decode("utf-8")

        elif object_node.type == NodeType.METHOD_INVOCATION:
            nested_object = object_node.child_by_field_name(FieldName.OBJECT)
            if nested_object:
                return self._get_root_object_name(nested_object)

        elif object_node.type == NodeType.FIELD_ACCESS:  # ✅ Uses enum
            field_object = object_node.child_by_field_name(FieldName.OBJECT)
            if field_object and field_object.type == NodeType.THIS:
                field_name = object_node.child_by_field_name(FieldName.FIELD)
                if field_name:
                    return field_name.text.decode("utf-8")
            else:
                return self._get_root_object_name(field_object)

        return None

    def _check_for_unresolved_reference(self, arg_node) -> UnresolvedReference | None:
        """
        Check if an argument contains references that need resolution.

        Args:
            arg_node: The tree-sitter node representing the argument

        Returns:
            UnresolvedReference if resolution needed, None otherwise
        """
        node_type = arg_node.type
        raw_value = arg_node.text.decode("utf-8")

        # Check for constant references (e.g., Constants.VALUE, SomeClass.STATIC_FIELD)
        if node_type == NodeType.FIELD_ACCESS:
            if self._looks_like_constant_reference(raw_value):
                return UnresolvedConstant(
                    raw_value=raw_value,
                    location=ReferenceLocation(
                        class_name=getattr(self, "current_class_name", "UnknownClass"),
                        element_type=ElementType.METHOD_BODY,
                        element_name="method_argument",
                        source_start_offset=arg_node.start_byte,
                        source_end_offset=arg_node.end_byte,
                    ),
                )

        # Check for identifier that might be a constant
        elif node_type == NodeType.IDENTIFIER:
            # Check if it looks like a constant (all caps, etc.)
            if raw_value.isupper() and "_" in raw_value:
                return UnresolvedConstant(
                    raw_value=raw_value,
                    location=ReferenceLocation(
                        class_name=getattr(self, "current_class_name", "UnknownClass"),
                        element_type=ElementType.METHOD_BODY,
                        element_name="method_argument",
                        source_start_offset=arg_node.start_byte,
                        source_end_offset=arg_node.end_byte,
                    ),
                )

        return None

    def _create_method_call_argument(
        self, arg_node, position: int, source_code: str
    ) -> MethodCallArgument:
        """
        Create a MethodCallArgument from a tree-sitter argument node.

        Args:
            arg_node: The tree-sitter node representing the argument
            position: 0-based position in argument list
            source_code: The source code string

        Returns:
            MethodCallArgument object
        """
        raw_expression = arg_node.text.decode("utf-8")
        expression_type = self._classify_argument_expression(arg_node)
        inferred_type = self._infer_argument_type(arg_node)
        unresolved_reference = self._check_for_unresolved_reference(arg_node)

        return MethodCallArgument(
            position=position,
            raw_expression=raw_expression,
            expression_type=expression_type,
            inferred_type=inferred_type,
            unresolved_reference=unresolved_reference,
            source_start_offset=arg_node.start_byte,
            source_end_offset=arg_node.end_byte,
        )

    def _classify_argument_expression(self, arg_node) -> ArgumentExpressionType:
        """
        Classify the type of expression used as a method argument.

        Args:
            arg_node: The tree-sitter node representing the argument

        Returns:
            ArgumentExpressionType enum value
        """
        node_type = arg_node.type

        if node_type in [
            NodeType.STRING_LITERAL,
            NodeType.CHARACTER_LITERAL,
            NodeType.DECIMAL_INTEGER_LITERAL,
            NodeType.HEX_INTEGER_LITERAL,
            NodeType.OCTAL_INTEGER_LITERAL,
            NodeType.BINARY_INTEGER_LITERAL,
            NodeType.DECIMAL_FLOATING_POINT_LITERAL,
            NodeType.HEX_FLOATING_POINT_LITERAL,
            NodeType.TRUE,
            NodeType.FALSE,
            NodeType.NULL_LITERAL,
        ]:
            return ArgumentExpressionType.LITERAL

        elif node_type == NodeType.IDENTIFIER:
            return ArgumentExpressionType.IDENTIFIER

        elif node_type == NodeType.FIELD_ACCESS:
            return ArgumentExpressionType.FIELD_ACCESS

        elif node_type == NodeType.METHOD_INVOCATION:
            return ArgumentExpressionType.METHOD_CALL

        elif node_type == NodeType.BINARY_EXPRESSION:
            return ArgumentExpressionType.BINARY_EXPRESSION

        elif node_type == NodeType.TERNARY_EXPRESSION:
            return ArgumentExpressionType.TERNARY_EXPRESSION

        elif node_type == NodeType.ARRAY_ACCESS:
            return ArgumentExpressionType.ARRAY_ACCESS

        elif node_type == NodeType.OBJECT_CREATION_EXPRESSION:
            return ArgumentExpressionType.OBJECT_CREATION

        elif node_type == NodeType.CAST_EXPRESSION:
            return ArgumentExpressionType.CAST_EXPRESSION

        else:
            return ArgumentExpressionType.OTHER

    def _infer_argument_type(self, arg_node) -> str | None:
        """
        Infer the type of a method argument from its tree-sitter node.

        Args:
            arg_node: The tree-sitter node representing the argument

        Returns:
            Inferred type as string, or None if cannot be determined
        """
        node_type = arg_node.type

        if node_type == NodeType.STRING_LITERAL:
            return "String"
        elif node_type in [
            NodeType.DECIMAL_INTEGER_LITERAL,
            NodeType.HEX_INTEGER_LITERAL,
            NodeType.OCTAL_INTEGER_LITERAL,
            NodeType.BINARY_INTEGER_LITERAL,
        ]:
            return "int"
        elif node_type in [
            NodeType.DECIMAL_FLOATING_POINT_LITERAL,
            NodeType.HEX_FLOATING_POINT_LITERAL,
        ]:
            return "double"
        elif node_type in [NodeType.TRUE, NodeType.FALSE]:
            return "boolean"
        elif node_type == NodeType.CHARACTER_LITERAL:
            return "char"
        elif node_type == NodeType.NULL_LITERAL:
            return "null"
        elif node_type == NodeType.OBJECT_CREATION_EXPRESSION:
            # Try to extract type from 'new TypeName(...)'
            type_node = arg_node.child_by_field_name(FieldName.TYPE)
            if type_node:
                return type_node.text.decode("utf-8")

        # For more complex expressions, type inference would be more involved
        return None

    def _extract_methods(
        self, class_node, member_variables: list[MemberVariable], source_code: str
    ) -> tuple[
        list[JavaMethod | RestEndpoint],
        dict[str, tuple[int, int]],
        dict[str, list[tuple[int, int]]],
    ]:
        """
        Extract methods from a class node and track their byte offsets, including associated comments.

        Args:
            class_node: The tree-sitter node representing the class
            member_variables: List of member variables for service call detection
            source_code: The source code string

        Returns:
            Tuple of (List of methods, Dict of method name to (start, end) offset,
            Dict of method name to list of comment (start, end) offsets)
        """
        methods = []
        method_offsets = {}  # Maps method names to (start, end) offsets
        method_comment_offsets = {}  # Maps method names to list of comment (start, end) offsets

        class_body = None
        for child in class_node.children:
            if child.type in (
                NodeType.CLASS_BODY,
                NodeType.INTERFACE_BODY,
                NodeType.ENUM_BODY,
            ):
                class_body = child
                break

        if not class_body:
            return methods, method_offsets, method_comment_offsets

        # First pass: identify all comments in the class body
        all_comments = []
        for child in class_body.children:
            if child.type in (
                NodeType.COMMENT,
                NodeType.LINE_COMMENT,
                NodeType.BLOCK_COMMENT,
                NodeType.JAVADOC_COMMENT,
            ):
                all_comments.append((child.start_byte, child.end_byte))

        # Process methods
        last_method_end = 0
        for child in class_body.children:
            node_type = getattr(child, "type", None)
            if node_type == NodeType.METHOD_DECLARATION:
                name_node = child.child_by_field_name(FieldName.NAME)
                type_node = child.child_by_field_name(FieldName.TYPE)

                if name_node and type_node:
                    name = name_node.text.decode("utf-8")
                    return_type = type_node.text.decode("utf-8")

                    # Track method offsets
                    method_offsets[name] = (child.start_byte, child.end_byte)
                    method_comment_offsets[name] = []

                    # Find comments that belong to this method (between the last method and this one)
                    for comment_start, comment_end in all_comments:
                        # Only attach comments whose end is before the method starts
                        if last_method_end <= comment_end <= child.start_byte:
                            method_comment_offsets[name].append((comment_start, comment_end))

                    # Update last_method_end for the next iteration
                    last_method_end = child.end_byte

                    # Get modifiers
                    modifiers = self._extract_modifiers(child)

                    # Get parameters
                    parameters = self._extract_method_parameters(child)

                    # Get exceptions
                    exceptions = self._extract_method_exceptions(child)

                    # Get annotations
                    annotations = self._extract_annotations(
                        child, ElementType.METHOD_ANNOTATION, name
                    )

                    # Determine if this is a REST endpoint
                    path_mappings = {}

                    mapping_annotations = {
                        "GetMapping": "GET",
                        "PostMapping": "POST",
                        "PutMapping": "PUT",
                        "DeleteMapping": "DELETE",
                        "PatchMapping": "PATCH",
                        "RequestMapping": "GET",  # Default method for RequestMapping
                    }

                    for annotation in annotations:
                        if annotation.name in mapping_annotations:
                            http_method = mapping_annotations[annotation.name]

                            # For RequestMapping, check method attribute
                            if (
                                annotation.name == "RequestMapping"
                                and "method" in annotation.values
                            ):
                                method_value = annotation.values["method"]
                                # Extract HTTP method from RequestMethod enum constants
                                method_mapping = {
                                    "RequestMethod.GET": "GET",
                                    "RequestMethod.POST": "POST",
                                    "RequestMethod.PUT": "PUT",
                                    "RequestMethod.DELETE": "DELETE",
                                    "RequestMethod.PATCH": "PATCH",
                                }
                                for method_const, method_name in method_mapping.items():
                                    if method_const in method_value:
                                        http_method = method_name
                                        break

                            # Get the path from the annotation
                            path = annotation.value or ""
                            path_mappings[http_method] = path

                    if node_type == NodeType.METHOD_DECLARATION:
                        method_calls = self._extract_method_calls(
                            child, member_variables, source_code
                        )
                    else:
                        method_calls = []

                    # Create appropriate method object
                    if path_mappings:
                        endpoint = RestEndpoint(
                            name=name,
                            return_type=return_type,
                            parameters=parameters,
                            annotations=annotations,
                            exceptions=exceptions,
                            modifiers=modifiers,
                            method_calls=method_calls,
                            path_mappings=path_mappings,
                        )
                        methods.append(endpoint)
                    else:
                        methods.append(
                            JavaMethod(
                                name=name,
                                return_type=return_type,
                                parameters=parameters,
                                annotations=annotations,
                                exceptions=exceptions,
                                modifiers=modifiers,
                                method_calls=method_calls,
                            )
                        )

        return methods, method_offsets, method_comment_offsets

    def _extract_constructors(
        self, class_node, source_code: str
    ) -> tuple[
        list[JavaConstructor],
        dict[str, tuple[int, int]],
        dict[str, list[tuple[int, int]]],
    ]:
        """
        Extract constructors from a class node and track their byte offsets, including associated comments.

        Args:
            class_node: The tree-sitter node representing the class
            source_code: The source code string

        Returns:
            Tuple of (List of constructors, Dict of constructor name to (start, end) offset,
            Dict of constructor name to list of comment (start, end) offsets)
        """
        constructors = []
        constructor_offsets = {}  # Maps constructor names to (start, end) offsets
        constructor_comment_offsets = {}  # Maps constructor names to list of comment (start, end) offsets

        class_body = None
        for child in class_node.children:
            if child.type in (
                NodeType.CLASS_BODY,
                NodeType.INTERFACE_BODY,
                NodeType.ENUM_BODY,
            ):
                class_body = child
                break

        if not class_body:
            return constructors, constructor_offsets, constructor_comment_offsets

        # First pass: identify all comments in the class body (including enum declarations)
        all_comments = []
        # Flatten enum body declarations if present
        body_nodes = []
        for n in class_body.children:
            if n.type == NodeType.ENUM_BODY_DECLARATIONS:
                body_nodes.extend(n.children)
            else:
                body_nodes.append(n)
        for child in body_nodes:
            if child.type in (
                NodeType.COMMENT,
                NodeType.LINE_COMMENT,
                NodeType.BLOCK_COMMENT,
                NodeType.JAVADOC_COMMENT,
            ):
                all_comments.append((child.start_byte, child.end_byte))

        # Process constructors
        last_constructor_end = 0
        for child in body_nodes:
            node_type = getattr(child, "type", None)
            if node_type == NodeType.CONSTRUCTOR_DECLARATION:
                name_node = child.child_by_field_name(FieldName.NAME)

                if name_node:
                    name = name_node.text.decode("utf-8")

                    # Track constructor offsets with a unique key per overload
                    key = f"{name}#{len(constructors)}"
                    constructor_offsets[key] = (child.start_byte, child.end_byte)
                    constructor_comment_offsets[key] = []

                    # Find comments that belong to this constructor (between the last constructor and this one)
                    for comment_start, comment_end in all_comments:
                        # Only attach comments whose end is before the constructor starts
                        if last_constructor_end <= comment_end <= child.start_byte:
                            constructor_comment_offsets[key].append((comment_start, comment_end))

                    # Update last_constructor_end for the next iteration
                    last_constructor_end = child.end_byte

                    # Get modifiers
                    modifiers = self._extract_modifiers(child)

                    # Get parameters
                    parameters = self._extract_method_parameters(
                        child
                    )  # Reuse method parameter extraction

                    # Get exceptions
                    exceptions = self._extract_method_exceptions(
                        child
                    )  # Reuse method exception extraction

                    # Get annotations
                    annotations = self._extract_annotations(
                        child, ElementType.METHOD_ANNOTATION, name
                    )

                    # Create constructor object
                    constructor = JavaConstructor(
                        name=name,
                        parameters=parameters,
                        annotations=annotations,
                        exceptions=exceptions,
                        modifiers=modifiers,
                    )
                    constructors.append(constructor)

        return constructors, constructor_offsets, constructor_comment_offsets

    def _create_class_model(
        self,
        class_name: str,
        package: str,
        class_annotations: list[Annotation],
        category: ClassCategory,
        **kwargs,
    ) -> JavaClass | RestControllerClass | ServiceClass:
        """
        Create the appropriate class model based on the class category.

        Args:
            class_name: The name of the class
            package: The package of the class
            class_annotations: List of class annotations
            category: The class category
            **kwargs: Additional keyword arguments for the class model

        Returns:
            A JavaClass or subclass instance
        """
        if category == ClassCategory.CONTROLLER:
            return RestControllerClass(
                name=class_name,
                package=package,
                class_annotations=class_annotations,
                category=category,
                **kwargs,
            )
        elif category == ClassCategory.SERVICE:
            return ServiceClass(
                name=class_name,
                package=package,
                class_annotations=class_annotations,
                category=category,
                **kwargs,
            )
        elif category == ClassCategory.ENUM:
            return EnumClass(
                name=class_name,
                package=package,
                class_annotations=class_annotations,
                category=category,
                **kwargs,
            )
        else:
            return JavaClass(
                name=class_name,
                package=package,
                class_annotations=class_annotations,
                category=category,
                **kwargs,
            )

    def parse_java_file(
        self, file_path: str, store_source: bool = False
    ) -> JavaClass | RestControllerClass | ServiceClass:
        """
        Parse a Java file and extract class information.

        Args:
            file_path: Path to the Java file

        Returns:
            A JavaClass or subclass instance representing the parsed Java file
        """
        with open(file_path, "rb") as f:
            source_code_bytes = f.read()
            source_code = source_code_bytes.decode("utf-8")

        # Calculate file metadata
        file_stats = os.stat(file_path)
        last_modified = file_stats.st_mtime
        file_size = file_stats.st_size
        crc32_hash = zlib.crc32(source_code_bytes)
        md5_hash = md5(source_code_bytes).hexdigest()

        tree = self.parser.parse(source_code_bytes)
        root_node = tree.root_node

        logger.trace(
            f"Parsing Java file: {file_path}, size: {file_size} bytes, last modified: {last_modified}, File CRC32: {crc32_hash}, MD5: {md5_hash}"
        )
        logger.trace(f"Source code:\n{source_code}")
        logger.trace(f"Tree structure:\n{node_to_dict(root_node)}")
        # Check if the root node is a compilation unit

        # Extract package name
        package = self._extract_package(root_node)

        # Extract imports
        imports, import_statements = self._extract_imports(root_node)

        # Find the class or interface declaration
        decl_node = None
        decl_type = None
        class_name = ""
        for child in root_node.children:
            if child.type in (
                NodeType.CLASS_DECLARATION,
                NodeType.INTERFACE_DECLARATION,
                NodeType.ENUM_DECLARATION,
            ):
                if child.type == NodeType.CLASS_DECLARATION:
                    decl_type = "class"
                elif child.type == NodeType.INTERFACE_DECLARATION:
                    decl_type = "interface"
                elif child.type == NodeType.ENUM_DECLARATION:
                    decl_type = "enum"
                decl_node = child
                name_node = child.child_by_field_name(FieldName.NAME)
                if name_node and name_node.text:
                    class_name = name_node.text.decode("utf-8")
                break

        if not decl_node:
            raise MissingDeclarationException(
                f"No class or interface declaration found in {file_path}"
            )

        # Extract class annotations
        class_annotations = self._extract_annotations(
            decl_node, ElementType.CLASS_ANNOTATION, class_name
        )

        # Determine abstraction type and class category
        abstraction_type = None
        category = ClassCategory.UNKNOWN
        decl_modifiers = self._extract_modifiers(decl_node)
        if decl_type == "interface":
            abstraction_type = AbstractionType.INTERFACE
        elif decl_type == "enum":
            category = ClassCategory.ENUM
        else:
            if "abstract" in decl_modifiers:
                abstraction_type = AbstractionType.ABSTRACT

        if decl_type != "enum":
            category = infer_class_category(class_name, class_annotations, config=self.config)

        # logger.info(
        #     f"Inferring {category} for class {class_name} in {file_path}"
        # )

        # Extract member variables
        member_variables = self._extract_member_variables(decl_node)
        # Extract interface implementations if any
        implements: list[str] = []
        if decl_type == "class":
            impl_node = decl_node.child_by_field_name(FieldName.INTERFACES)
            if impl_node:
                for id_node in impl_node.children:
                    if (
                        id_node.type
                        in (
                            NodeType.IDENTIFIER,
                            NodeType.SCOPED_TYPE_IDENTIFIER,
                            NodeType.TYPE_LIST,
                        )
                        and id_node.text
                    ):
                        implements.append(id_node.text.decode("utf-8"))

        # Extract constants
        constants = self._extract_constants(decl_node)

        # Extract methods with offsets
        methods, method_offsets, method_comment_offsets = self._extract_methods(
            decl_node, member_variables, source_code
        )

        constructors, constructor_offsets, constructor_comment_offsets = (
            self._extract_constructors(decl_node, source_code)
        )

        # Local FQN resolution for API-client detection
        resolver = LocalNameResolver(package, imports)
        for var in member_variables:
            # annotate fully-qualified type for member
            if hasattr(var, "type"):
                var.fqn_type = resolver.to_fqn(var.type)
        for ctor in constructors:
            for param in ctor.parameters:
                # annotate fully-qualified type for constructor parameter
                param.fqn_type = resolver.to_fqn(param.type)
        # Mark injection constructors (explicit @Autowired or implicit for bean stereotypes)
        for ctor in constructors:
            autowired_anno = any(a.name == "Autowired" for a in ctor.annotations)
            implicit = False
            if not autowired_anno and len(constructors) == 1 and len(ctor.parameters) > 0:
                bean_annos = {
                    "RestController",
                    "Controller",
                    "Service",
                    "Component",
                    "Repository",
                    "Configuration",
                }
                implicit = any(a.name in bean_annos for a in class_annotations)
            ctor.is_injection = autowired_anno or implicit

        # Additional check for API CLIENT class category
        if category in [
            ClassCategory.SERVICE,
            ClassCategory.CLIENT,
            ClassCategory.OTHER,
            ClassCategory.UNKNOWN,
        ]:
            # logger.info(
            #     f"Inferring API client category for class {class_name} in {file_path}"
            # )
            api_client_category = infer_api_client_category(
                class_name,
                class_annotations,
                member_variables,
                methods + constructors,
                config=self.config,
            )
            if api_client_category == ClassCategory.API_CLIENT:
                category = ClassCategory.API_CLIENT

        # File location info
        path = Path(file_path)
        filename = path.name
        absolute_path = str(path.absolute())

        try:
            relative_path = filename
            common_roots = ["src", "java", "main"]
            parts = path.parts
            for root in common_roots:
                if root in parts:
                    idx = parts.index(root)
                    relative_path = str(Path(*parts[idx + 1 :]))
                    break
        except Exception:
            relative_path = filename

        # Create the appropriate class model
        java_class = self._create_class_model(
            class_name=class_name,
            package=package,
            class_annotations=class_annotations,
            category=category,
            abstraction_type=abstraction_type,
            member_variables=member_variables,
            methods=methods,
            constructors=constructors,
            method_offsets=method_offsets,
            method_comment_offsets=method_comment_offsets,
            constructor_offsets=constructor_offsets,
            constructor_comment_offsets=constructor_comment_offsets,
            imports=imports,
            import_statements=import_statements,
            constants=constants,
            filename=filename,
            relative_path=relative_path,
            absolute_path=absolute_path,
            implements=implements,
            last_modified=last_modified,
            file_size=file_size,
            crc32_hash=crc32_hash,
            md5_hash=md5_hash,
        )

        if store_source:
            java_class.source_code = source_code

        # Set parent references for methods that need them
        for method in java_class.methods:
            if isinstance(method, RestEndpoint):
                method._parent_class = java_class

        return java_class
