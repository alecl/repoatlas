# =============================================================================
# MODEL RESPONSIBILITY DOCUMENTATION
# =============================================================================
#
# This section documents which methods/properties in this file are:
#   - Pure data access or computed fields (OK for models)
#
# Pure data access/computed fields (OK in models):
#   - All @computed_field properties (e.g., fully_qualified_name, value, base_endpoint_path, etc.)
#   - __str__ methods for string representation
#   - Data container methods (e.g., get_class_references, find_member_variable_by_name)
#
# Resolution or cross-file logic (NOT OK in models and should be moved to resolvers/analyzer or similar)
# =============================================================================


from datetime import datetime
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, Field, computed_field


class ElementType(StrEnum):
    """Types of code elements where references can appear"""

    CLASS_ANNOTATION = "class_annotation"
    METHOD_ANNOTATION = "method_annotation"
    FIELD_ANNOTATION = "field_annotation"
    PARAMETER_ANNOTATION = "parameter_annotation"
    METHOD_BODY = "method_body"
    FIELD_DECLARATION = "field_declaration"
    CONSTANT_VALUE = "constant_value"
    IMPORT = "import"
    ENUM_CONSTANT = "enum_constant"


class ReferenceLocation(BaseModel):
    """Location of an unresolved reference in the code structure"""

    class_name: str
    element_type: ElementType
    element_name: str
    detail: str | None = None  # Additional context like annotation key

    # Source code offsets for the reference
    source_start_offset: int | None = None
    source_end_offset: int | None = None

    def __str__(self) -> str:
        """Human-readable path representation"""
        parts = [self.class_name, self.element_type.value, self.element_name]
        if self.detail:
            parts.append(self.detail)
        return ".".join(parts)


class ReferenceScope(StrEnum):
    """Scope of where a reference points to"""

    SAME_JAR = "same_jar"
    SAME_REPO_DIFFERENT_JAR = "same_repo_different_jar"
    COMPANY_DIFFERENT_REPO = "company_different_repo"
    THIRD_PARTY = "third_party"
    JDK = "jdk"
    UNKNOWN = "unknown"


class ReferenceResolutionStatus(StrEnum):
    """Status of reference resolution"""

    UNRESOLVED = "unresolved"
    PARTIALLY_RESOLVED = "partially_resolved"
    FULLY_RESOLVED = "fully_resolved"
    UNRESOLVABLE = "unresolvable"


class ResolutionAttempt(BaseModel):
    """Record of an attempt to resolve a reference"""

    timestamp: datetime
    strategy: str  # e.g., "local_constants", "import_chain", "maven_lookup"
    success: bool
    error_message: str | None = None
    partial_result: dict[str, Any] | None = None


class ResolvedLocation(BaseModel):
    """Where a reference was resolved to"""

    scope: ReferenceScope
    repository: str | None = None
    jar_name: str | None = None
    package_name: str | None = None
    class_name: str | None = None
    maven_group_id: str | None = None
    maven_artifact_id: str | None = None
    maven_version: str | None = None


class UnresolvedReference(BaseModel):
    """Base class for unresolved references"""

    raw_value: str  # e.g., "Constants.BASE_PATH"
    location: ReferenceLocation
    resolution_status: ReferenceResolutionStatus = ReferenceResolutionStatus.UNRESOLVED
    resolved_location: ResolvedLocation | None = None
    resolved_value: str | None = None  # For constants
    resolution_attempts: list[ResolutionAttempt] = Field(default_factory=list)

    def add_resolution_attempt(
        self,
        strategy: str,
        success: bool,
        error_message: str | None = None,
        partial_result: dict[str, Any] | None = None,
    ):
        """Record a resolution attempt"""
        self.resolution_attempts.append(
            ResolutionAttempt(
                timestamp=datetime.now(),
                strategy=strategy,
                success=success,
                error_message=error_message,
                partial_result=partial_result,
            )
        )

    def mark_partially_resolved(self, scope: ReferenceScope, **kwargs):
        """Mark as partially resolved with known scope"""
        self.resolution_status = ReferenceResolutionStatus.PARTIALLY_RESOLVED
        self.resolved_location = ResolvedLocation(scope=scope, **kwargs)

    def mark_fully_resolved(self, value: str, resolved_location: ResolvedLocation | None):
        """Mark as fully resolved"""
        self.resolution_status = ReferenceResolutionStatus.FULLY_RESOLVED
        self.resolved_value = value
        self.resolved_location = resolved_location

    def mark_unresolvable(self, reason: str):
        """Mark as unresolvable"""
        self.resolution_status = ReferenceResolutionStatus.UNRESOLVABLE
        self.add_resolution_attempt("final_attempt", False, error_message=reason)


class UnresolvedConstant(UnresolvedReference):
    """Reference to a constant that needs resolution"""

    pass


# TODO: Should this be based class of UnresolvedConstant?
class UnresolvedEnumConstant(UnresolvedReference):
    """Reference to an enum constant that needs resolution."""

    enum_type: str
    constant_name: str


class UnresolvedType(UnresolvedReference):
    """Reference to a type that needs resolution"""

    is_interface: bool = False
    is_generic: bool = False


class UnresolvedAutowire(UnresolvedReference):
    """Reference to an autowired dependency"""

    interface_type: str
    qualifier: str | None = None


class Annotation(BaseModel):
    """Represents a Java annotation with its name and values."""

    name: str
    values: dict[str, str | list[str]] = Field(default_factory=dict)
    unresolved_values: dict[str, "UnresolvedConstant"] = Field(default_factory=dict)

    def __str__(self) -> str:
        """String representation of the annotation."""
        if not self.values:
            return f"@{self.name}"
        values_str = ", ".join([f"{k}='{v}'" for k, v in self.values.items()])
        return f"@{self.name}({values_str})"

    @computed_field
    @property
    def value(self) -> str | list[str] | None:
        """
        Get the 'value' parameter of the annotation if it exists.
        Returns a single string if only one value, or list of strings if multiple.
        """
        v = None
        if "value" in self.values:
            v = self.values["value"]
        elif "" in self.values:
            v = self.values[""]
        if isinstance(v, list):
            return v if len(v) > 1 else v[0]
        return v

    @property
    def has_unresolved_references(self) -> bool:
        """Return True if this annotation has unresolved references."""
        return len(self.unresolved_values) > 0


class EnumConstant(BaseModel):
    """Model for a Java enum constant."""

    name: str
    constructor_arguments: list[str] = Field(default_factory=list)
    annotations: list[Annotation] = Field(default_factory=list)
    fqn_type: str | None = Field(default=None, description="Fully qualified type name")
    source_start_offset: int | None = None
    source_end_offset: int | None = None


class AbstractionType(StrEnum):
    """Type of abstraction for a class (interface or abstract)."""

    INTERFACE = "interface"
    ABSTRACT = "abstract"


class ClassCategory(StrEnum):
    """Enum for different types of Java classes."""

    CONTROLLER = "controller"
    SERVICE = "service"
    ENUM = "enum"
    REPOSITORY = "repository"
    DTO = "dto"
    DAO = "dao"
    ENTITY = "entity"
    CONFIGURATION = "configuration"
    MAPPER = "mapper"
    ASPECT = "aspect"
    COMPONENT = "component"
    UTILITY = "utility"
    CLIENT = "client"
    API_CLIENT = "api_client"
    EXCEPTION = "exception"
    TEST = "test"
    OTHER = "other"
    UNKNOWN = "unknown"


class MemberVariableCategory(StrEnum):
    """Enum for different types of class member variables."""

    CLASS_REFERENCE = "class_reference"
    PRIMITIVE = "primitive"
    COLLECTION = "collection"
    MAP = "map"
    ENUM = "enum"
    OTHER = "other"


class ArgumentExpressionType(StrEnum):
    """Types of expressions that can appear as method arguments"""

    LITERAL = "literal"  # String, number, boolean literals
    IDENTIFIER = "identifier"  # Variable names, constants
    FIELD_ACCESS = "field_access"  # this.field, object.field
    METHOD_CALL = "method_call"  # Nested method invocations
    BINARY_EXPRESSION = "binary_expression"  # a + b, etc.
    TERNARY_EXPRESSION = "ternary_expression"  # condition ? a : b
    ARRAY_ACCESS = "array_access"  # array[index]
    OBJECT_CREATION = "object_creation"  # new Object()
    CAST_EXPRESSION = "cast_expression"  # (Type) value
    OTHER = "other"  # Other complex expressions


class MethodCallArgument(BaseModel):
    """Represents an argument passed to a method call"""

    position: int  # 0-based position in argument list
    raw_expression: str  # The actual text of the argument expression
    expression_type: ArgumentExpressionType = (
        ArgumentExpressionType.OTHER
    )  # This is the AST type of the expression NOT the language specific type
    inferred_type: str | None = None  # Best guess at the argument's type

    # For resolution workflow
    unresolved_reference: Any | None = None

    # Source location information
    source_start_offset: int | None = None
    source_end_offset: int | None = None

    def __str__(self) -> str:
        return self.raw_expression


class MethodCallInfo(BaseModel):
    """Information about a method call (generalized, not just services)"""

    # Target information (renamed from service_* for generality)
    target_name: str  # Variable name of the target being called (e.g., 'userService')
    target_type: str  # Type of the target (e.g., 'UserService')
    target_class_category: ClassCategory = ClassCategory.UNKNOWN  # Category of target class

    # Method information
    method_name: str  # Name of the method being called
    package_name: str | None = None  # Resolved package name if available

    # Arguments
    arguments: list[MethodCallArgument] = Field(default_factory=list)

    # Reference back to the member variable on which this call was made (if applicable)
    source_variable: Optional["ClassReferenceMemberVariable"] = None

    @computed_field
    @property
    def arg_count(self) -> int:
        """Number of arguments in the call"""
        return len(self.arguments)

    def __str__(self) -> str:
        """String representation of the method call."""
        args_str = ", ".join(str(arg) for arg in self.arguments)
        package_info = f" ({self.package_name})" if self.package_name else ""
        return f"{self.target_name}.{self.method_name}({args_str}){package_info}"

    def is_target_category(self, category: ClassCategory) -> bool:
        """Check if the target is of a specific category"""
        return self.target_class_category == category


class Parameter(BaseModel):
    """Represents a method parameter with annotations."""

    name: str
    type: str
    annotations: list[Annotation] = Field(default_factory=list)
    fqn_type: str | None = Field(default=None, description="Fully qualified type name")

    def __str__(self) -> str:
        """String representation of the parameter."""
        annotations_str = " ".join([str(a) for a in self.annotations])
        if annotations_str:
            return f"{annotations_str} {self.type} {self.name}"
        return f"{self.type} {self.name}"


class JavaMethod(BaseModel):
    """Base model for a Java method with enhanced method call support."""

    name: str
    return_type: str
    parameters: list[Parameter] = Field(default_factory=list)
    annotations: list[Annotation] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    modifiers: list[str] = Field(default_factory=list)
    method_calls: list[MethodCallInfo] = Field(default_factory=list)

    def __str__(self) -> str:
        """String representation of the method."""
        annotations_str = " ".join([str(a) for a in self.annotations])
        modifiers_str = " ".join(self.modifiers)
        params_str = ", ".join([str(p) for p in self.parameters])
        exceptions_str = ", ".join(self.exceptions)

        result = f"{self.return_type} {self.name}({params_str})"

        if annotations_str:
            result = f"{annotations_str}\n{result}"
        if modifiers_str:
            result = f"{modifiers_str} {result}"
        if exceptions_str:
            result = f"{result} throws {exceptions_str}"

        return result

    # Enhanced method call filtering methods
    def get_method_calls_by_category(self, category: ClassCategory) -> list[MethodCallInfo]:
        """
        Get method calls filtered by target class category.

        Args:
            category: The ClassCategory to filter by

        Returns:
            List of MethodCallInfo objects where target matches the category
        """
        return [call for call in self.method_calls if call.is_target_category(category)]

    def get_service_calls(self) -> list[MethodCallInfo]:
        """
        Get all method calls to service classes.

        Returns:
            List of MethodCallInfo objects targeting services
        """
        return self.get_method_calls_by_category(ClassCategory.SERVICE)

    def has_calls_to_category(self, category: ClassCategory) -> bool:
        """
        Check if this method makes any calls to the specified category.

        Args:
            category: The ClassCategory to check for

        Returns:
            True if method makes calls to the category, False otherwise
        """
        return any(call.is_target_category(category) for call in self.method_calls)

    def has_service_calls(self) -> bool:
        """Check if this method makes any calls to service classes."""
        return self.has_calls_to_category(ClassCategory.SERVICE)

    def add_method_call(
        self,
        target_name: str,
        method_name: str,
        target_type: str,
        target_class_category: ClassCategory = ClassCategory.UNKNOWN,
        package_name: str | None = None,
        arguments: list[MethodCallArgument] | None = None,
        source_variable: Optional["ClassReferenceMemberVariable"] = None,
    ) -> None:
        """
        Add a method call to this method.

        Args:
            target_name: The variable name of the target being called
            method_name: The name of the method being called
            target_type: The type of the target
            target_class_category: The category of the target class
            package_name: Optional package name of the target
            arguments: List of method call arguments
            source_variable: Reference to the source variable if applicable
        """
        self.method_calls.append(
            MethodCallInfo(
                target_name=target_name,
                method_name=method_name,
                target_type=target_type,
                target_class_category=target_class_category,
                package_name=package_name,
                arguments=arguments or [],
                source_variable=source_variable,
            )
        )

    def get_calls_with_arguments_containing(self, pattern: str) -> list[MethodCallInfo]:
        """
        Get method calls that have arguments containing a specific pattern.

        Args:
            pattern: String pattern to search for in argument expressions

        Returns:
            List of MethodCallInfo objects with matching arguments
        """
        matching_calls = []
        for call in self.method_calls:
            if any(pattern in arg.raw_expression for arg in call.arguments):
                matching_calls.append(call)
        return matching_calls

    def get_calls_with_unresolved_arguments(self) -> list[MethodCallInfo]:
        """
        Get method calls that have arguments with unresolved references.

        Returns:
            List of MethodCallInfo objects with unresolved argument references
        """
        matching_calls = []
        for call in self.method_calls:
            if any(arg.unresolved_reference is not None for arg in call.arguments):
                matching_calls.append(call)
        return matching_calls


class RestEndpoint(JavaMethod):
    """Model for a REST endpoint method with HTTP mappings."""

    path_mappings: dict[str, str | list[str]] = Field(
        default_factory=dict
    )  # HTTP method -> path(s)

    # Add a reference to the parent class for constants resolution
    _parent_class: Optional["JavaClass"] = None

    def get_full_path(self, base_path: str) -> dict[str, str | list[str]]:
        """
        Get the full paths for this endpoint by combining the base path
        with endpoint-specific paths.

        Args:
            base_path: The base path from the controller's RequestMapping

        Returns:
            A dictionary mapping HTTP methods to full paths (string) or lists of full paths
        """
        paths_map: dict[str, list[str]] = {}
        for method, path in self.path_mappings.items():
            items = path if isinstance(path, list) else [path]
            for p in items:
                resolved = self._resolve_path(p)
                if resolved and not resolved.startswith("/"):
                    resolved = f"/{resolved}"
                if not base_path:
                    full = resolved
                else:
                    base = base_path.rstrip("/")
                    full = f"{base}{resolved}" if resolved else base
                paths_map.setdefault(method, []).append(full)
        # Convert single-item lists to single values for backward compatibility
        final: dict[str, str | list[str]] = {}
        for method, pl in paths_map.items():
            final[method] = pl[0] if len(pl) == 1 else pl
        return final

    # New method to resolve constant references in paths
    def _resolve_path(self, path: str) -> str:
        """
        Resolve a path that might be a constant reference.

        Args:
            path: The path which might be a constant reference

        Returns:
            The resolved path string
        """
        if not path:
            return path

        # If the path looks like a constant reference (contains dots)
        if "." in path and not path.startswith("/"):
            # Try to resolve it from the parent class constants
            if self._parent_class and hasattr(self._parent_class, "constants"):
                # Check if it's in the constants map
                if path in self._parent_class.constants:
                    return self._parent_class.constants[path]

        return path

    # Post-init hook for parent class reference
    def model_post_init(self, __context: Any) -> None:
        """Initialize parent class reference from context if available."""
        super().model_post_init(__context)


class MemberVariable(BaseModel):
    """Base model for a Java class member variable."""

    name: str
    type: str
    category: MemberVariableCategory = MemberVariableCategory.OTHER
    annotations: list[Annotation] = Field(default_factory=list)
    modifiers: list[str] = Field(default_factory=list)
    resolved_properties: dict[str, str] = Field(default_factory=dict)
    fqn_type: str | None = Field(default=None, description="Fully qualified type name")

    def __str__(self) -> str:
        """String representation of the member variable."""
        annotations_str = " ".join([str(a) for a in self.annotations])
        modifiers_str = " ".join(self.modifiers)
        result = f"{self.type} {self.name}"

        if annotations_str:
            result = f"{annotations_str} {result}"
        if modifiers_str:
            result = f"{modifiers_str} {result}"

        return result


class ClassReferenceMemberVariable(MemberVariable):
    """Model for a member variable that references another class."""

    category: MemberVariableCategory = MemberVariableCategory.CLASS_REFERENCE
    is_autowired: bool = False
    qualifier: str | None = None
    referenced_class_category: ClassCategory = ClassCategory.UNKNOWN

    unresolved_type: Optional["UnresolvedType"] = None
    unresolved_autowire: Optional["UnresolvedAutowire"] = None

    resolved_class: Optional["JavaClass"] = None
    resolved_implementation: Optional["JavaClass"] = None

    def __str__(self) -> str:
        """String representation of the class reference member variable."""
        result = super().__str__()

        # Add autowired and qualifier information if not already in annotations
        autowired_in_annotations = any(a.name == "Autowired" for a in self.annotations)
        qualifier_in_annotations = any(a.name == "Qualifier" for a in self.annotations)

        # Always put @Autowired before @Qualifier for consistent test output
        if self.is_autowired and not autowired_in_annotations:
            result = f"@Autowired {result}"
        if self.qualifier and not qualifier_in_annotations:
            result = (
                f'@Autowired @Qualifier("{self.qualifier}") {super().__str__()}'
                if self.is_autowired
                else f'@Qualifier("{self.qualifier}") {result}'
            )

        return result


class ImportDefinition(BaseModel):
    """Represents a Java import statement."""

    fully_qualified_name: str
    is_static: bool = False
    is_wildcard: bool = False

    @computed_field
    @property
    def package_name(self) -> str:
        """Get the package name part of the import."""
        if not self.fully_qualified_name:
            return ""

        if self.is_wildcard:
            return self.fully_qualified_name  # Already just the package name

        # For normal imports, get everything before the last dot
        parts = self.fully_qualified_name.split(".")
        return ".".join(parts[:-1])

    @computed_field
    @property
    def class_name(self) -> str:
        """Get the class name part of the import."""
        if not self.fully_qualified_name:
            return ""

        if self.is_wildcard:
            return ""  # No specific class for wildcard imports

        # For normal imports, get everything after the last dot
        parts = self.fully_qualified_name.split(".")
        return parts[-1]


class JavaConstructor(BaseModel):
    """Model for a Java constructor."""

    name: str  # Constructor name (same as class name)
    parameters: list[Parameter] = Field(default_factory=list)
    annotations: list[Annotation] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    modifiers: list[str] = Field(default_factory=list)
    is_injection: bool = Field(
        default=False,
        description="True if Spring should inject this constructor (implicit or @Autowired)",
    )

    def __str__(self) -> str:
        """String representation of the constructor."""
        annotations_str = " ".join([str(a) for a in self.annotations])
        modifiers_str = " ".join(self.modifiers)
        params_str = ", ".join([str(p) for p in self.parameters])
        exceptions_str = ", ".join(self.exceptions)

        result = f"{self.name}({params_str})"

        if annotations_str:
            result = f"{annotations_str}\n{result}"
        if modifiers_str:
            result = f"{modifiers_str} {result}"
        if exceptions_str:
            result = f"{result} throws {exceptions_str}"

        return result

    def has_parameter_of_type(self, type_name: str) -> bool:
        """
        Check if constructor has a parameter of the specified type.

        Args:
            type_name: The type name to check for

        Returns:
            True if constructor has parameter of this type, False otherwise
        """
        return any(param.type == type_name for param in self.parameters)

    def get_parameters_of_category(self, category: ClassCategory) -> list[Parameter]:
        """
        Get parameters that match a specific class category.
        Note: This would require type resolution to work properly.

        Args:
            category: The ClassCategory to filter by

        Returns:
            List of parameters matching the category
        """
        # This would need the analyzer to resolve parameter types to categories
        # For now, return empty list - could be enhanced later
        return []


class JavaClass(BaseModel):
    """Base model for a Java class."""

    name: str
    package: str
    class_annotations: list[Annotation] = Field(default_factory=list)
    member_variables: list[MemberVariable] = Field(default_factory=list)
    constructors: list[JavaConstructor] = Field(default_factory=list)
    methods: list[JavaMethod] = Field(default_factory=list)
    imports: list[ImportDefinition] = Field(default_factory=list)
    import_statements: list[str] = Field(default_factory=list)  # Original import statements
    constants: dict[str, str] = Field(default_factory=dict)
    category: ClassCategory = ClassCategory.UNKNOWN
    implements: list[str] = Field(default_factory=list)
    abstraction_type: AbstractionType | None = None
    extends: str | None = None
    resolved_location: ResolvedLocation | None = None

    # File location information
    filename: str = ""
    relative_path: str = ""
    absolute_path: str = ""

    # File metadata fields
    last_modified: float | None = None
    file_size: int | None = None
    crc32_hash: int | None = None
    md5_hash: str | None = None
    source_code: str | None = None

    # Method offset tracking
    method_offsets: dict[str, tuple[int, int]] = Field(
        default_factory=dict
    )  # name -> (start, end)
    method_comment_offsets: dict[str, list[tuple[int, int]]] = Field(
        default_factory=dict
    )  # name -> (start, end)

    # Constructor offset tracking
    constructor_offsets: dict[str, tuple[int, int]] = Field(
        default_factory=dict
    )  # name -> (start, end)
    constructor_comment_offsets: dict[str, list[tuple[int, int]]] = Field(
        default_factory=dict
    )  # name -> (start, end)

    # Hold references that were fully resolved (for source replacements)
    resolved_references: list[UnresolvedReference] = Field(default_factory=list)

    def __hash__(self) -> int:
        return hash((self.name, self.package, self.relative_path, self.filename))

    @computed_field
    @property
    def fully_qualified_name(self) -> str:
        """Get the fully qualified class name including package."""
        return f"{self.package}.{self.name}"

    def get_class_references(self) -> list[ClassReferenceMemberVariable]:
        """
        Get all member variables that reference other classes.

        Returns:
            List of class reference member variables
        """
        return [
            var for var in self.member_variables if isinstance(var, ClassReferenceMemberVariable)
        ]

    def find_member_variable_by_name(self, name: str) -> MemberVariable | None:
        """
        Find a member variable by name.

        Args:
            name: The name of the member variable to find

        Returns:
            The MemberVariable if found, None otherwise
        """
        for var in self.member_variables:
            if var.name == name:
                return var
        return None

    def has_default_constructor(self) -> bool:
        """
        Check if the class has a default (no-argument) constructor.

        Returns:
            True if class has a default constructor, False otherwise
        """
        return any(len(constructor.parameters) == 0 for constructor in self.constructors)

    def get_default_constructor(self) -> JavaConstructor | None:
        """
        Get the default (no-argument) constructor if it exists.

        Returns:
            The default constructor if found, None otherwise
        """
        for constructor in self.constructors:
            if len(constructor.parameters) == 0:
                return constructor
        return None

    def get_constructors(self) -> list[JavaConstructor]:
        """
        Get all constructors

        Returns:
            List of constructors
        """
        return self.constructors

    def get_constructors_with_annotation(self, annotation_name: str) -> list[JavaConstructor]:
        """
        Get all constructors that have a specific annotation.

        Args:
            annotation_name: The name of the annotation to search for

        Returns:
            List of constructors with the specified annotation
        """
        return [
            constructor
            for constructor in self.constructors
            if any(anno.name == annotation_name for anno in constructor.annotations)
        ]


class EnumClass(JavaClass):
    """Model for a Java enum."""

    category: ClassCategory = ClassCategory.ENUM  # New category
    enum_constants: list[EnumConstant] = Field(default_factory=list)


class RestControllerClass(JavaClass):
    """Model for a Spring Web REST controller class."""

    category: ClassCategory = ClassCategory.CONTROLLER

    @computed_field
    @property
    def base_endpoint_path(self) -> str:
        """
        Extract the base path from the controller's RequestMapping annotation.

        Returns:
            The base path as a string, or empty string if not found
        """
        return self.get_base_endpoint_path()

    def get_base_endpoint_path(self) -> str:
        """
        Extract the base endpoint path from the controller's RequestMapping annotation.

        Returns:
            The base path as a string, or empty string if not found
        """
        for annotation in self.class_annotations:
            if annotation.name == "RequestMapping":
                # Handle possible list or single string on 'value'
                val = annotation.value
                if isinstance(val, list):
                    if val:
                        return val[0]
                elif val:
                    return val
                # Also check for 'path' parameter as an alternative
                p = annotation.values.get("path")
                if isinstance(p, list):
                    if p:
                        return p[0]
                elif p:
                    return p
        return ""

    @computed_field
    @property
    def service_variables(self) -> list[ClassReferenceMemberVariable]:
        """
        Get all member variables that reference service classes.

        Returns:
            List of service member variables
        """
        service_vars = []
        for var in self.member_variables:
            if isinstance(var, ClassReferenceMemberVariable) and (
                var.referenced_class_category == ClassCategory.SERVICE
            ):
                service_vars.append(var)
        # Merge in constructor‐injected services: mark existing fields or add new
        for name, impl in getattr(self, "_constructor_injections", {}).items():
            existing_var = next((v for v in service_vars if v.name == name), None)
            if existing_var:
                existing_var.is_autowired = True
                existing_var.resolved_implementation = impl
            else:
                service_vars.append(
                    ClassReferenceMemberVariable(
                        name=name,
                        type=name,
                        is_autowired=True,
                        referenced_class_category=ClassCategory.SERVICE,
                        resolved_implementation=impl,
                    )
                )
        return service_vars

    @computed_field
    @property
    def endpoints(self) -> list[RestEndpoint]:
        """
        Get all REST endpoint methods.

        Returns:
            List of REST endpoint methods
        """
        endpoints = []
        for method in self.methods:
            if isinstance(method, RestEndpoint):
                # Set parent class reference for constants resolution
                method._parent_class = self
                endpoints.append(method)
        return endpoints

    def get_all_endpoints(self) -> dict[str, list[tuple[str, str]]]:
        """
        Get all HTTP endpoints defined in this controller.

        Returns:
            Dictionary mapping HTTP methods to lists of (path, method_name) tuples
        """
        endpoints_dict: dict[str, list[tuple[str, str]]] = {}

        for endpoint in self.endpoints:
            full_paths = endpoint.get_full_path(self.base_endpoint_path)
            for http_method, path_or_paths in full_paths.items():
                if http_method not in endpoints_dict:
                    endpoints_dict[http_method] = []
                paths = path_or_paths if isinstance(path_or_paths, list) else [path_or_paths]
                for path in paths:
                    endpoints_dict[http_method].append((path, endpoint.name))

        return endpoints_dict


class ServiceClass(JavaClass):
    """Model for a Spring service class."""

    category: ClassCategory = ClassCategory.SERVICE


class DependencyOptions(BaseModel):
    """Options for controlling dependency loading."""

    # Dependency direction
    upstream: bool = True
    downstream: bool = False

    # Depth control
    max_depth: int = 999

    # Scope filtering
    include_scopes: list[ReferenceScope] = Field(
        default_factory=lambda: [
            ReferenceScope.SAME_JAR,
            ReferenceScope.SAME_REPO_DIFFERENT_JAR,
            ReferenceScope.COMPANY_DIFFERENT_REPO,
        ]
    )
    exclude_scopes: list[ReferenceScope] = Field(
        default_factory=lambda: [
            ReferenceScope.JDK,
            ReferenceScope.THIRD_PARTY,
            ReferenceScope.UNKNOWN,
        ]
    )

    # Category filtering
    include_categories: list[ClassCategory] = Field(
        default_factory=list
    )  # Empty means include all
    exclude_categories: list[ClassCategory] = Field(
        default_factory=list
    )  # Empty means exclude none

    # Package filtering
    exclude_packages: list[str] = Field(default_factory=list)  # Empty means exclude none

    class Config:
        use_enum_values = True  # Use string values for enums
