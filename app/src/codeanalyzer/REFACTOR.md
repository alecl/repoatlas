# Reference Resolution Design for Java Code Analyzer

## Architectural Overview

### Separation of Concerns

The system is divided into three main layers with clear responsibilities:

#### 1. Models (models.py)
**Purpose**: Pure data representation
- Pydantic models representing Java code structure
- Simple computed properties derived directly from data
- `__str__` methods for consistent string representation
- Basic data access methods (filtering, searching)
- Storage for unresolved references

**What doesn't belong**:
- Complex resolution logic
- Path manipulation
- Type inference
- State mutation beyond initialization

#### 2. Parser (parser.py)
**Purpose**: Syntactic analysis - single file scope
- Extract AST from Java source using tree-sitter
- Create Pydantic models from AST nodes
- Extract structural elements (classes, methods, fields, annotations)
- Parse import statements (but not resolve them)
- Extract constant declarations (but not resolve values)
- Mark unresolved references for later resolution

**What doesn't belong**:
- Cross-file resolution
- Semantic analysis
- Type resolution
- Constant value resolution

#### 3. Analyzer (analyzer.py)
**Purpose**: Semantic analysis - cross-file scope
- Orchestrate the parsing process
- Maintain registry of all parsed classes
- Coordinate specialized resolvers
- Perform multi-pass resolution
- Report on unresolved references

### Resolver Architecture

The analyzer delegates specific resolution tasks to specialized resolvers:

```python
# analyzer.py - Orchestrator
class JavaAnalyzer:
    """
    Main analyzer that orchestrates the parsing and resolution process.
    
    Responsibilities:
    - Coordinate file parsing across a codebase
    - Maintain registry of all parsed Java classes
    - Manage specialized resolvers for different resolution types
    - Execute multi-pass resolution pipeline
    - Report on unresolved references
    
    Usage:
        analyzer = JavaAnalyzer()
        analyzer.analyze_directory("/path/to/java/code")
        results = analyzer.get_resolution_report()
    """
    def __init__(self):
        self.parser = JavaParser()
        self.classes: Dict[str, JavaClass] = {}
        
        # Specialized resolvers
        self.import_resolver = ImportResolver(self)  # Foundation for other resolvers
        self.type_resolver = TypeResolver(self)
        self.constant_resolver = ConstantResolver(self)
        self.path_resolver = PathResolver(self)
        self.autowire_resolver = AutowireResolver(self)
        self.property_resolver = PropertyResolver(self)
    
    def analyze_directory(self, path: str) -> None:
        """Parse all files, then resolve references"""
        # Phase 1: Parse all files (order doesn't matter)
        self._parse_all_files(path)
        
        # Phase 2: Build indices for lookup
        self._build_resolution_indices()
        
        # Phase 3: Multi-pass resolution
        self._resolve_all_references()
    
    def _resolve_all_references(self):
        """Orchestrate resolution using specialized resolvers"""
        resolution_pipeline = [
            ("import_resolution", self.import_resolver.resolve_used_imports),
            ("type_resolution", self.type_resolver.resolve_all),
            ("constant_resolution", self.constant_resolver.resolve_all),
            ("path_resolution", self.path_resolver.resolve_all),
            ("autowire_resolution", self.autowire_resolver.resolve_all),
            ("property_resolution", self.property_resolver.resolve_all),
        ]
        
        for pass_num in range(5):  # Multiple passes for complex dependencies
            changes_made = False
            for stage_name, resolver_method in resolution_pipeline:
                changes_made |= resolver_method()
            
            if not changes_made:
                break
        
        self._report_unresolved_references()
```

## Design Philosophy

The reference resolution system is designed to handle the reality of analyzing Java codebases where:
1. Files are parsed in arbitrary order (not dependency order)
2. References may cross multiple boundaries (JARs, repositories, companies)
3. Some references may never be fully resolvable
4. Resolution happens in multiple passes after initial parsing

### Core Principles
- **Separation of Concerns**: Parsing extracts syntax; resolution handles semantics
- **Progressive Resolution**: Start with what we know, incrementally resolve more
- **Explicit Tracking**: Know what's unresolved, partially resolved, and fully resolved
- **Self-Contained Models**: Each model tracks its own unresolved references

## Requirements

1. Support resolution of various reference types:
   - Constants (e.g., `Constants.BASE_PATH`)
   - Type references (e.g., interface → implementation)
   - Autowired dependencies
   - Property values from properties files

2. Handle references across different scopes:
   - Same JAR
   - Same repository, different JAR
   - Different repository within company
   - Third-party dependencies
   - JDK standard library

3. Track resolution attempts and provide visibility into:
   - What couldn't be resolved
   - Why resolution failed
   - What scope the reference likely belongs to

4. Support multiple resolution passes:
   - There may be dependency chains where one file has variables that lead to another file that also has variables needeing resolution

## Data Model

### Core Types

```python
from enum import Enum
from typing import Optional, Dict, List
from pydantic import BaseModel, Field
from datetime import datetime

class ElementType(str, Enum):
    """Types of code elements where references can appear"""
    CLASS_ANNOTATION = "class_annotation"
    METHOD_ANNOTATION = "method_annotation"
    FIELD_ANNOTATION = "field_annotation"
    PARAMETER_ANNOTATION = "parameter_annotation"
    METHOD_BODY = "method_body"
    FIELD_DECLARATION = "field_declaration"
    CONSTANT_VALUE = "constant_value"
    IMPORT = "import"

class ReferenceLocation(BaseModel):
    """Location of an unresolved reference in the code structure"""
    class_name: str
    element_type: ElementType
    element_name: str
    detail: Optional[str] = None  # Additional context like annotation key
    
    def __str__(self) -> str:
        """Human-readable path representation"""
        parts = [self.class_name, self.element_type.value, self.element_name]
        if self.detail:
            parts.append(self.detail)
        return ".".join(parts)

class ReferenceScope(str, Enum):
    """Scope of where a reference points to"""
    SAME_JAR = "same_jar"
    SAME_REPO_DIFFERENT_JAR = "same_repo_different_jar"  
    COMPANY_DIFFERENT_REPO = "company_different_repo"
    THIRD_PARTY = "third_party"
    JDK = "jdk"
    UNKNOWN = "unknown"

class ReferenceResolutionStatus(str, Enum):
    """Status of reference resolution"""
    UNRESOLVED = "unresolved"
    PARTIALLY_RESOLVED = "partially_resolved"  # Know the scope but not exact location
    FULLY_RESOLVED = "fully_resolved"
    UNRESOLVABLE = "unresolvable"  # Tried but failed

class ResolutionAttempt(BaseModel):
    """Record of an attempt to resolve a reference"""
    timestamp: datetime
    strategy: str  # e.g., "local_constants", "import_chain", "maven_lookup"
    success: bool
    error_message: Optional[str] = None
    partial_result: Optional[Dict[str, Any]] = None

class ResolvedLocation(BaseModel):
    """Where a reference was resolved to"""
    scope: ReferenceScope
    repository: Optional[str] = None  # Git repo URL or identifier
    jar_name: Optional[str] = None
    package_name: Optional[str] = None
    class_name: Optional[str] = None
    # Maven coordinates for third-party deps
    maven_group_id: Optional[str] = None
    maven_artifact_id: Optional[str] = None
    maven_version: Optional[str] = None

class UnresolvedReference(BaseModel):
    """Base class for unresolved references"""
    raw_value: str  # e.g., "Constants.BASE_PATH"
    location: ReferenceLocation
    resolution_status: ReferenceResolutionStatus = ReferenceResolutionStatus.UNRESOLVED
    resolved_location: Optional[ResolvedLocation] = None
    resolved_value: Optional[str] = None  # For constants
    resolution_attempts: List[ResolutionAttempt] = Field(default_factory=list)
    
    def add_resolution_attempt(self, strategy: str, success: bool, 
                             error_message: Optional[str] = None,
                             partial_result: Optional[Dict[str, Any]] = None):
        """Record a resolution attempt"""
        self.resolution_attempts.append(ResolutionAttempt(
            timestamp=datetime.now(),
            strategy=strategy,
            success=success,
            error_message=error_message,
            partial_result=partial_result
        ))
    
    def mark_partially_resolved(self, scope: ReferenceScope, **kwargs):
        """Mark as partially resolved with known scope"""
        self.resolution_status = ReferenceResolutionStatus.PARTIALLY_RESOLVED
        self.resolved_location = ResolvedLocation(scope=scope, **kwargs)
    
    def mark_fully_resolved(self, value: str, resolved_location: ResolvedLocation):
        """Mark as fully resolved"""
        self.resolution_status = ReferenceResolutionStatus.FULLY_RESOLVED
        self.resolved_value = value
        self.resolved_location = resolved_location
    
    def mark_unresolvable(self, reason: str):
        """Mark as unresolvable"""
        self.resolution_status = ReferenceResolutionStatus.UNRESOLVABLE
        self.add_resolution_attempt("final_attempt", False, error_message=reason)
```

### Specific Reference Types

```python
class UnresolvedConstant(UnresolvedReference):
    """Reference to a constant that needs resolution"""
    pass

class UnresolvedType(UnresolvedReference):
    """Reference to a type that needs resolution"""
    is_interface: bool = False
    is_generic: bool = False

class UnresolvedAutowire(UnresolvedReference):
    """Reference to an autowired dependency"""
    interface_type: str
    qualifier: Optional[str] = None
```

## Integration with Existing Models

```python
class Annotation(BaseModel):
    name: str
    values: Dict[str, str] = Field(default_factory=dict)
    unresolved_values: Dict[str, UnresolvedConstant] = Field(default_factory=dict)
    
    @property
    def has_unresolved_references(self) -> bool:
        return len(self.unresolved_values) > 0

class ClassReferenceMemberVariable(MemberVariable):
    type: str
    unresolved_type: Optional[UnresolvedType] = None
    unresolved_autowire: Optional[UnresolvedAutowire] = None
    
    # After resolution, these get populated:
    resolved_class: Optional['JavaClass'] = None
    resolved_implementation: Optional['JavaClass'] = None  # For interfaces
```

## Specialized Resolvers

Each resolver handles a specific aspect of resolution:

### Import Resolver

```python
# import_resolver.py
class ImportResolver:
    """
    Lazily resolves import statements to determine their location and scope.
    
    Responsibilities:
    - Resolve imports only when needed by other resolvers
    - Cache resolved import locations for performance
    - Track which imports are actually used vs unused
    - Determine scope (JDK, same JAR, different JAR, third-party)
    
    Usage:
        import_resolver = ImportResolver(analyzer)
        location = import_resolver.resolve_import_for_type("UserService", context_class)
        stats = import_resolver.get_import_statistics()
    """
    def __init__(self, analyzer: JavaAnalyzer):
        self.analyzer = analyzer
        # Cache: import FQN -> resolved location
        self._import_cache: Dict[str, Optional[ResolvedLocation]] = {}
        # Track which imports are actually used
        self._used_imports: Set[str] = set()
    
    def resolve_import_for_type(self, type_name: str, context_class: JavaClass) -> Optional[ResolvedLocation]:
        """Resolve an import only when needed for type resolution"""
        for import_def in context_class.imports:
            if self._import_matches_type(import_def, type_name):
                return self._resolve_import_lazy(import_def, context_class)
        return None
    
    def resolve_used_imports(self) -> bool:
        """Post-processing pass to resolve all imports that were actually used"""
        # This is called as part of the resolution pipeline
        # It doesn't resolve anything eagerly, just returns False
        # The actual resolution happens lazily via resolve_import_for_type
        return False
    
    def _resolve_import_lazy(self, import_def: ImportDefinition, 
                           context_class: JavaClass) -> Optional[ResolvedLocation]:
        """Resolve import only when needed, cache result"""
        fqn = import_def.fully_qualified_name
        
        # Check cache first
        if fqn in self._import_cache:
            return self._import_cache[fqn]
        
        # Mark as used
        self._used_imports.add(fqn)
        
        # Determine scope and location
        location = self._determine_import_location(fqn, context_class)
        
        # Cache the result (even if None)
        self._import_cache[fqn] = location
        return location
    
    def _determine_import_location(self, fqn: str, 
                                 context_class: JavaClass) -> Optional[ResolvedLocation]:
        """Determine where an import points to"""
        # Quick checks for common cases
        if fqn.startswith("java.") or fqn.startswith("javax."):
            return ResolvedLocation(scope=ReferenceScope.JDK, package_name=fqn)
        
        # Check if it's in our parsed classes
        for class_fqn, java_class in self.analyzer.classes.items():
            if class_fqn == fqn or (fqn.endswith(".*") and class_fqn.startswith(fqn[:-2])):
                return ResolvedLocation(
                    scope=self._determine_scope_from_path(java_class, context_class),
                    class_name=java_class.name,
                    package_name=java_class.package,
                    jar_name=self._extract_jar_name(java_class)
                )
        
        # External dependency
        return ResolvedLocation(
            scope=ReferenceScope.THIRD_PARTY,
            package_name=fqn
        )
    
    def _determine_scope_from_path(self, target_class: JavaClass, 
                                  context_class: JavaClass) -> ReferenceScope:
        """Determine scope based on file paths"""
        # Simple heuristic based on paths
        context_jar = self._extract_jar_name(context_class)
        target_jar = self._extract_jar_name(target_class)
        
        if context_jar == target_jar:
            return ReferenceScope.SAME_JAR
        elif self._is_same_repository(context_class, target_class):
            return ReferenceScope.SAME_REPO_DIFFERENT_JAR
        else:
            return ReferenceScope.COMPANY_DIFFERENT_REPO
    
    def get_import_statistics(self) -> Dict[str, Any]:
        """Report on import usage"""
        return {
            "total_imports": len(self._import_cache),
            "used_imports": len(self._used_imports),
            "unused_imports": len(self._import_cache) - len(self._used_imports),
            "by_scope": self._count_by_scope()
        }
```

```python
# type_resolver.py
class TypeResolver:
    def __init__(self, analyzer: JavaAnalyzer):
        self.analyzer = analyzer
    
    def resolve_all(self) -> bool:
        """Resolve all unresolved type references"""
        changes_made = False
        
        for java_class in self.analyzer.classes.values():
            # Resolve member variable types
            for member in java_class.member_variables:
                if isinstance(member, ClassReferenceMemberVariable) and member.unresolved_type:
                    resolved_class = self.resolve_type(member.type, java_class)
                    if resolved_class:
                        member.resolved_class = resolved_class
                        member.unresolved_type.mark_fully_resolved(...)
                        changes_made = True
            
            # Resolve method parameter and return types
            for method in java_class.methods:
                changes_made |= self._resolve_method_types(method, java_class)
        
        return changes_made
    
    def resolve_type(self, type_name: str, context_class: JavaClass) -> Optional[JavaClass]:
        """Resolve a type name to its JavaClass"""
        # Handle generics
        base_type = type_name.split("<")[0].strip()
        
        # Check imports
        for import_def in context_class.imports:
            if self._import_matches_type(import_def, base_type):
                return self._find_class_by_fqn(import_def.fully_qualified_name)
        
        # Check same package
        potential_fqn = f"{context_class.package}.{base_type}"
        return self._find_class_by_fqn(potential_fqn)
```

### Constant Resolver

```python
# constant_resolver.py
class ConstantResolver:
    """
    Resolves constant references to their actual values.
    
    Responsibilities:
    - Resolve constant references like Constants.BASE_PATH
    - Handle constant chains (constants referencing other constants)
    - Resolve constants used in annotations, field values, etc.
    - Track resolution attempts for debugging
    
    Usage:
        constant_resolver = ConstantResolver(analyzer)
        success = constant_resolver.resolve_all()
        value = constant_resolver.resolve_constant("Constants.API_PATH", context_class)
    """
    def __init__(self, analyzer: JavaAnalyzer):
        self.analyzer = analyzer
        self.import_resolver = analyzer.import_resolver
    
    def resolve_all(self) -> bool:
        """Resolve all unresolved constants"""
        changes_made = False
        
        for java_class in self.analyzer.classes.values():
            changes_made |= self._resolve_class_constants(java_class)
        
        return changes_made
    
    def _resolve_class_constants(self, java_class: JavaClass) -> bool:
        """Resolve constants in a single class"""
        changes_made = False
        
        # Resolve in annotations
        for annotation in self._get_all_annotations(java_class):
            for key, unresolved in list(annotation.unresolved_values.items()):
                resolved_value = self._resolve_constant_chain(unresolved, java_class)
                if resolved_value:
                    annotation.values[key] = resolved_value
                    unresolved.mark_fully_resolved(
                        resolved_value,
                        ResolvedLocation(
                            scope=self._determine_scope(unresolved),
                            class_name=java_class.name
                        )
                    )
                    del annotation.unresolved_values[key]
                    changes_made = True
        
        return changes_made
    
    def _resolve_constant_chain(self, unresolved: UnresolvedConstant, 
                               context_class: JavaClass) -> Optional[str]:
        """Handle complex constant resolution chains"""
        unresolved.add_resolution_attempt("constant_chain", False)
        
        resolution_chain = []
        current_ref = unresolved.raw_value
        max_depth = 10
        
        for depth in range(max_depth):
            if '.' not in current_ref:
                # Local constant
                value = context_class.constants.get(current_ref)
            else:
                # Cross-class constant
                class_ref, field_name = current_ref.rsplit('.', 1)
                target_class = self._resolve_class_reference(class_ref, context_class)
                if not target_class:
                    unresolved.add_resolution_attempt(
                        "constant_chain", False,
                        error_message=f"Cannot resolve class: {class_ref}",
                        partial_result={"resolution_chain": resolution_chain}
                    )
                    return None
                value = target_class.constants.get(field_name)
            
            if not value:
                return None
            
            resolution_chain.append((current_ref, value))
            
            # Check if value is another constant reference
            if self._looks_like_constant_reference(value):
                current_ref = value
                continue
            else:
                # Found final value
                unresolved.add_resolution_attempt("constant_chain", True)
                return self._evaluate_constant_chain(resolution_chain)
        
        return None
    
    def _resolve_class_reference(self, class_ref: str, context_class: JavaClass) -> Optional[JavaClass]:
        """Use import resolver to find where a class reference points"""
        import_location = self.import_resolver.resolve_import_for_type(class_ref, context_class)
        
        if import_location and import_location.scope != ReferenceScope.THIRD_PARTY:
            # Try to find the class in our parsed classes
            for fqn, java_class in self.analyzer.classes.items():
                if java_class.name == class_ref and java_class.package == import_location.package_name:
                    return java_class
        
        # Try same package
        potential_fqn = f"{context_class.package}.{class_ref}"
        return self.analyzer.classes.get(potential_fqn)
```

### Path Resolver

```python
# path_resolver.py
class PathResolver:
    """
    Resolves REST endpoint paths, including constant references.
    
    Responsibilities:
    - Resolve base paths from controller annotations
    - Resolve endpoint-specific paths with constants
    - Combine base and endpoint paths correctly
    - Handle path parameter syntax
    
    Usage:
        path_resolver = PathResolver(analyzer)
        success = path_resolver.resolve_all()
        full_paths = path_resolver.get_full_paths(endpoint, base_path)
    """
    def __init__(self, analyzer: JavaAnalyzer):
        self.analyzer = analyzer
        self.constant_resolver = analyzer.constant_resolver
    
    def resolve_all(self) -> bool:
        """Resolve all paths in REST endpoints"""
        changes_made = False
        
        for controller in self._get_all_controllers():
            # Resolve base path
            base_path = self._resolve_base_path(controller)
            
            # Resolve endpoint paths
            for endpoint in controller.endpoints:
                for method, path in endpoint.path_mappings.items():
                    if self._is_unresolved_path(path):
                        resolved_path = self._resolve_endpoint_path(path, controller)
                        if resolved_path != path:
                            endpoint.path_mappings[method] = resolved_path
                            changes_made = True
        
        return changes_made
    
    def get_full_paths(self, endpoint: RestEndpoint, base_path: str) -> Dict[str, str]:
        """Get fully resolved paths for an endpoint"""
        result = {}
        for method, path in endpoint.path_mappings.items():
            resolved_path = self._resolve_endpoint_path(path, endpoint._parent_class)
            result[method] = self._combine_paths(base_path, resolved_path)
        return result
    
    def _resolve_endpoint_path(self, path: str, controller: RestControllerClass) -> str:
        """Resolve constants in endpoint path"""
        if not path or not self._looks_like_constant_reference(path):
            return path
        
        # Create an unresolved constant for the path
        unresolved = UnresolvedConstant(
            raw_value=path,
            location=ReferenceLocation(
                class_name=controller.name,
                element_type=ElementType.METHOD_ANNOTATION,
                element_name="path"
            )
        )
        
        resolved = self.constant_resolver._resolve_constant_chain(unresolved, controller)
        return resolved if resolved else path
    
    def _combine_paths(self, base_path: str, endpoint_path: str) -> str:
        """Combine base and endpoint paths with proper formatting"""
        # Ensure paths start with / and combine correctly
        if not base_path:
            return endpoint_path if endpoint_path.startswith('/') else f"/{endpoint_path}"
        
        if not endpoint_path:
            return base_path
        
        # Remove trailing slash from base, ensure endpoint starts with slash
        base = base_path.rstrip('/')
        endpoint = endpoint_path if endpoint_path.startswith('/') else f"/{endpoint_path}"
        
        return f"{base}{endpoint}"
```

### Autowire Resolver

```python
# autowire_resolver.py
class AutowireResolver:
    """
    Resolves Spring autowired dependencies to their implementations.
    
    Responsibilities:
    - Match interfaces to their implementations
    - Handle @Qualifier annotations for disambiguation
    - Resolve @Primary beans when multiple candidates exist
    - Support constructor and field injection
    
    Usage:
        autowire_resolver = AutowireResolver(analyzer)
        success = autowire_resolver.resolve_all()
        impl = autowire_resolver.resolve_autowired_field(field, context_class)
    """
    def __init__(self, analyzer: JavaAnalyzer):
        self.analyzer = analyzer
        self.type_resolver = analyzer.type_resolver
    
    def resolve_all(self) -> bool:
        """Resolve all autowired dependencies"""
        changes_made = False
        
        for java_class in self.analyzer.classes.values():
            for member in java_class.get_class_references():
                if member.is_autowired and member.unresolved_autowire:
                    resolved = self._resolve_autowired_dependency(member, java_class)
                    if resolved:
                        member.resolved_implementation = resolved
                        member.unresolved_autowire.mark_fully_resolved(
                            resolved.fully_qualified_name,
                            ResolvedLocation(
                                scope=ReferenceScope.SAME_JAR,
                                class_name=resolved.name
                            )
                        )
                        changes_made = True
        
        return changes_made
    
    def _resolve_autowired_dependency(self, member: ClassReferenceMemberVariable,
                                    context_class: JavaClass) -> Optional[JavaClass]:
        """Resolve interface to implementation based on Spring rules"""
        # First resolve the interface type
        interface_class = self.type_resolver.resolve_type(member.type, context_class)
        if not interface_class:
            return None
        
        # Find implementations
        implementations = self._find_implementations(interface_class)
        
        # Apply Spring resolution rules
        if member.qualifier:
            # Match by qualifier
            return self._find_by_qualifier(implementations, member.qualifier)
        elif len(implementations) == 1:
            # Single implementation
            return implementations[0]
        else:
            # Multiple implementations - check for @Primary
            return self._find_primary_bean(implementations)
    
    def _find_implementations(self, interface_class: JavaClass) -> List[JavaClass]:
        """Find all classes that implement the given interface"""
        implementations = []
        
        for java_class in self.analyzer.classes.values():
            if self._implements_interface(java_class, interface_class):
                implementations.append(java_class)
        
        return implementations
    
    def _find_by_qualifier(self, implementations: List[JavaClass], 
                          qualifier: str) -> Optional[JavaClass]:
        """Find implementation with matching @Qualifier"""
        for impl in implementations:
            for annotation in impl.class_annotations:
                if annotation.name == "Qualifier" and annotation.value == qualifier:
                    return impl
                # Also check Component with value
                if annotation.name in ["Component", "Service", "Repository"] and annotation.value == qualifier:
                    return impl
        return None
    
    def _find_primary_bean(self, implementations: List[JavaClass]) -> Optional[JavaClass]:
        """Find implementation marked as @Primary"""
        for impl in implementations:
            if any(anno.name == "Primary" for anno in impl.class_annotations):
                return impl
        return None
```

### Property Resolver

```python
# property_resolver.py
class PropertyResolver:
    """
    Resolves Spring property references in @Value annotations.
    
    Responsibilities:
    - Parse property files (application.properties, application.yml)
    - Resolve ${property.name} references
    - Handle default values in ${property.name:default}
    - Support property placeholders and environment variables
    
    Usage:
        property_resolver = PropertyResolver(analyzer)
        property_resolver.load_properties_file("application.properties")
        success = property_resolver.resolve_all()
    """
    def __init__(self, analyzer: JavaAnalyzer):
        self.analyzer = analyzer
        self.properties: Dict[str, Dict[str, str]] = {}  # file -> key -> value
    
    def load_properties_file(self, file_path: str):
        """Load a properties file"""
        properties = self._parse_properties_file(file_path)
        self.properties[file_path] = properties
    
    def resolve_all(self) -> bool:
        """Resolve all @Value annotations"""
        changes_made = False
        
        for java_class in self.analyzer.classes.values():
            # Check member variables
            for member in java_class.member_variables:
                changes_made |= self._resolve_member_value(member)
            
            # Check method parameters
            for method in java_class.methods:
                for param in method.parameters:
                    changes_made |= self._resolve_parameter_value(param)
        
        return changes_made
    
    def _resolve_member_value(self, member: MemberVariable) -> bool:
        """Resolve @Value annotation on a member"""
        for annotation in member.annotations:
            if annotation.name == "Value" and annotation.value:
                # Parse ${property.name:default}
                property_ref = self._parse_property_reference(annotation.value)
                if property_ref:
                    resolved_value = self._lookup_property(property_ref)
                    if resolved_value:
                        # Add resolved value to member
                        if not hasattr(member, 'resolved_properties'):
                            member.resolved_properties = {}
                        member.resolved_properties[property_ref.name] = resolved_value
                        return True
        return False
    
    def _parse_property_reference(self, value: str) -> Optional[PropertyReference]:
        """Parse ${property.name:default} syntax"""
        if not value.startswith("${") or not value.endswith("}"):
            return None
        
        # Extract content between ${ and }
        content = value[2:-1]
        
        # Split on : for default value
        parts = content.split(":", 1)
        property_name = parts[0]
        default_value = parts[1] if len(parts) > 1 else None
        
        return PropertyReference(
            name=property_name,
            default_value=default_value
        )
    
    def _lookup_property(self, property_ref: PropertyReference) -> str:
        """Look up property value across all loaded property files"""
        # Search in order of precedence
        for file_path in sorted(self.properties.keys(), reverse=True):
            if property_ref.name in self.properties[file_path]:
                return self.properties[file_path][property_ref.name]
        
        # Return default if specified
        return property_ref.default_value
```

## Resolution Workflow

### 1. During Parsing

```python
def _extract_annotation_from_node(self, annotation_node) -> Annotation:
    annotation = Annotation(name="RequestMapping")
    
    # When we encounter Constants.BASE_PATH
    raw_value = "Constants.BASE_PATH"
    
    if self._looks_like_constant_reference(raw_value):
        annotation.values["value"] = raw_value
        annotation.unresolved_values["value"] = UnresolvedConstant(
            raw_value=raw_value,
            location=ReferenceLocation(
                class_name=self.current_class_name,  # "UserController"
                element_type=ElementType.CLASS_ANNOTATION,
                element_name="RequestMapping",
                detail="value"
            )
        )
    
    return annotation
```

### 2. Multi-Pass Resolution

```python
class JavaAnalyzer:
    def _resolve_all_references(self):
        """Resolve all unresolved references in multiple passes"""
        max_passes = 5
        resolution_strategies = [
            ("local_constants", self._resolve_local_constants),
            ("import_chain", self._resolve_through_imports),
            ("cross_jar", self._resolve_cross_jar),
            ("maven_lookup", self._resolve_from_maven),
        ]
        
        for pass_num in range(max_passes):
            changes_made = False
            
            for strategy_name, strategy_func in resolution_strategies:
                changes_made |= strategy_func(strategy_name)
            
            if not changes_made:
                break
        
        self._finalize_unresolved_references()
    
    def _resolve_local_constants(self, strategy_name: str) -> bool:
        """First pass: resolve constants within same JAR"""
        changes_made = False
        
        for java_class in self.classes.values():
            for unresolved in self._get_unresolved_constants(java_class):
                if unresolved.resolution_status != ReferenceResolutionStatus.UNRESOLVED:
                    continue
                
                resolved_value = self._try_resolve_constant_same_jar(
                    unresolved, java_class
                )
                
                if resolved_value:
                    unresolved.mark_fully_resolved(
                        value=resolved_value,
                        resolved_location=ResolvedLocation(
                            scope=ReferenceScope.SAME_JAR,
                            jar_name=self._get_jar_name(java_class),
                            class_name=java_class.name
                        )
                    )
                    unresolved.add_resolution_attempt(strategy_name, True)
                    changes_made = True
                else:
                    unresolved.add_resolution_attempt(
                        strategy_name, False, 
                        error_message="Not found in same JAR"
                    )
        
        return changes_made
```

### 3. Complex Resolution Example

```python
def _resolve_constant_chain(self, unresolved: UnresolvedConstant, 
                          context_class: JavaClass) -> Optional[str]:
    """
    Resolve a chain of constant references
    e.g., UserConstants.PATH depends on Constants.BASE_PATH
    """
    resolution_chain = []
    current_ref = unresolved.raw_value
    max_depth = 10  # Prevent infinite loops
    
    for depth in range(max_depth):
        # Try to resolve current reference
        if '.' not in current_ref:
            # Local constant
            value = context_class.constants.get(current_ref)
        else:
            # Cross-class constant
            class_ref, field_name = current_ref.rsplit('.', 1)
            target_class = self._resolve_class_through_imports(
                class_ref, context_class
            )
            if not target_class:
                unresolved.add_resolution_attempt(
                    "constant_chain",
                    False,
                    error_message=f"Cannot resolve class: {class_ref}",
                    partial_result={"resolution_chain": resolution_chain}
                )
                return None
            
            value = target_class.constants.get(field_name)
        
        if not value:
            return None
        
        resolution_chain.append((current_ref, value))
        
        # Check if value is another constant reference
        if self._looks_like_constant_reference(value):
            current_ref = value
            continue
        else:
            # Found final value, now resolve the chain
            final_value = value
            for ref, val in reversed(resolution_chain[:-1]):
                final_value = val.replace(ref, final_value)
            
            return final_value
    
    unresolved.add_resolution_attempt(
        "constant_chain",
        False,
        error_message=f"Resolution chain too deep (>{max_depth})",
        partial_result={"resolution_chain": resolution_chain}
    )
    return None
```

## Use Cases

### 1. Constant Resolution with Complex Dependencies

```java
// Constants.java
public class Constants {
    public static final String BASE_PATH = "/api/v1";
    public static final String USERS_PATH = BASE_PATH + "/users";
}

// UserConstants.java
public class UserConstants {
    public static final String GET_USER_PATH = Constants.USERS_PATH + "/{id}";
}

// UserController.java
@RestController
@RequestMapping(Constants.BASE_PATH)
public class UserController {
    @GetMapping(value = UserConstants.GET_USER_PATH)
    public User getUser(@PathVariable String id) { ... }
}
```

Resolution flow:
1. Parse all files (order doesn't matter)
2. First pass: Resolve `Constants.BASE_PATH` → `"/api/v1"`
3. Second pass: Resolve `Constants.USERS_PATH` → `"/api/v1/users"`
4. Third pass: Resolve `UserConstants.GET_USER_PATH` → `"/api/v1/users/{id}"`

### 2. Cross-JAR Resolution

```java
// In common-lib.jar
package com.company.common;
public class CommonPaths {
    public static final String API_PREFIX = "/api/v2";
}

// In user-service.jar
package com.company.users;
import com.company.common.CommonPaths;

@RestController
@RequestMapping(CommonPaths.API_PREFIX + "/users")
public class UserController { ... }
```

Resolution attempts:
1. Try same JAR - fails
2. Check imports, find reference to different package
3. Mark as `PARTIALLY_RESOLVED` with scope `SAME_REPO_DIFFERENT_JAR`
4. If common-lib.jar is available, fully resolve

### 3. Autowire Resolution

```java
// UserService.java
public interface UserService {
    User findById(Long id);
}

// UserServiceImpl.java
@Service
@Qualifier("primary")
public class UserServiceImpl implements UserService { ... }

// UserController.java
@RestController
public class UserController {
    @Autowired
    @Qualifier("primary")
    private UserService userService;
}
```

Resolution:
1. Identify autowired field with interface type
2. Search for implementations in same JAR
3. Match qualifier if present
4. Create `UnresolvedAutowire` tracking the resolution

## Benefits

### Architecture Benefits

1. **Separation of Concerns**: Each component has a single, clear responsibility
2. **Testability**: Resolvers can be unit tested independently
3. **Maintainability**: Changes to resolution logic don't affect parsing or models
4. **Extensibility**: New resolvers can be added without modifying existing code
5. **Reusability**: Resolvers can leverage each other's functionality

### Resolution Benefits

1. **Comprehensive Tracking**: Know exactly what's unresolved and why
2. **Progressive Resolution**: Handle complex dependency chains
3. **Cross-Boundary Support**: Designed for multi-JAR/repo analysis
4. **Debugging Support**: Resolution attempts provide audit trail
5. **Flexible Pipeline**: Resolution order can be adjusted based on needs

## Implementation Guidelines

### Model Design

```python
# Good - Simple computed property
@computed_field
@property
def fully_qualified_name(self) -> str:
    return f"{self.package}.{self.name}"

# Bad - Complex logic in model
def resolve_type(self, type_name: str) -> Tuple[str, str]:
    # Complex resolution logic doesn't belong here
    pass
```

### Parser Design

```python
# Good - Mark for later resolution
def _extract_annotation_value(self, node) -> str:
    value = node.text.decode('utf-8')
    if self._looks_like_constant_reference(value):
        # Just mark as unresolved, don't try to resolve
        return UnresolvedConstant(raw_value=value, ...)
    return value

# Bad - Try to resolve during parsing
def _extract_annotation_value(self, node) -> str:
    value = node.text.decode('utf-8')
    if self._looks_like_constant_reference(value):
        # Don't do resolution in parser!
        return self._resolve_constant(value)
    return value
```

### Resolver Design

```python
# Good - Focused resolver with clear responsibility
class ConstantResolver:
    def resolve_all(self) -> bool:
        # Only handles constant resolution
        pass

# Bad - Resolver doing too many things
class GeneralResolver:
    def resolve_everything(self) -> bool:
        # Handles constants, types, paths, etc.
        pass
```

## Future Extensions

1. **Properties File Integration**: Resolve `@Value("${property.name}")` annotations
2. **Maven Integration**: Resolve third-party dependencies via Maven metadata
3. **Build System Integration**: Use build files to understand JAR relationships
4. **Caching**: Cache resolved references for incremental analysis
