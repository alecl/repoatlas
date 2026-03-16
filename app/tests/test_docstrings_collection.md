# Test File Docstring Headers Collection

## Unit Test Files

### test_models.py
```python
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
```

### test_reference_models.py
```python
"""
Unit tests for reference tracking model classes.

Strategy: Pure unit tests with hand-created reference objects.
Real: Reference state transitions, resolution status tracking
Mocked: Nothing (reference models are pure data structures)

Test Responsibilities:
- TestReferenceLocation: Reference location string representation
- TestResolutionAttempt: Resolution attempt tracking and status updates
- TestUnresolvedReference: Base unresolved reference behavior
- TestUnresolvedType: Type-specific unresolved reference behavior
- TestUnresolvedAutowire: Autowire-specific unresolved reference behavior
"""
```

### test_classification.py
```python
"""
Unit tests for class classification logic.

Strategy: Pure unit tests with hand-created annotations and class names.
Real: Classification algorithms (annotation-driven and name-driven)
Mocked: Nothing (pure classification functions)

Test Responsibilities:
- Single function tests: Each test validates one classification scenario
  (annotation-driven vs name-driven patterns)
"""
```

### test_blank_line_collapse.py
```python
"""
Unit tests for blank line collapse utility function.

Strategy: Pure unit tests with string inputs.
Real: String manipulation algorithms
Mocked: Nothing (pure string processing function)

Test Responsibilities:
- Parameterized tests: Various collapse scenarios with different line endings
- Edge case tests: Indentation preservation, whitespace handling
"""
```

### test_abstraction_type.py
```python
"""
Integration tests for abstraction type detection.

Strategy: Real file parsing to test abstraction detection.
Real: Java file parsing, tree-sitter integration, abstraction type detection
Mocked: Nothing
Note: Located in unit/ folder but uses integration test approach

Test Responsibilities:
- Single function tests: Interface and abstract class detection through parsing
"""
```

### test_analyzer_core.py
```python
"""
Unit tests for core JavaAnalyzer functionality.

Strategy: Unit tests with hand-created model objects and mocked dependencies.
Real: Core analyzer algorithms (search, getters, basic operations)
Mocked: Resolution pipeline (_resolve_all_references), file operations

Test Responsibilities:
- TestJavaAnalyzerBasics: Initialization, pipeline triggering, empty state handling
- TestJavaAnalyzerSearch: Class search by name, path, package
- TestJavaAnalyzerGetters: Controllers, services, endpoints, dependencies retrieval
- TestJavaAnalyzerConstants: Constant handling and resolution integration
"""
```

### test_analyzer_dump_classes.py
```python
"""
Integration tests for analyzer class dumping functionality.

Strategy: Real Java file parsing with method filtering and source manipulation.
Real: Java file parsing, class filtering, method comment handling
Mocked: Nothing
Note: Located in unit/ folder but uses integration test approach

Test Responsibilities:
- TestAnalyzerDumpClasses: Various filtering scenarios, comment inclusion/exclusion,
  method selection, import/package preservation
"""
```

### test_constant_resolver.py
```python
"""
Unit tests for ConstantResolver functionality.

Strategy: Unit tests with hand-created JavaClass objects and mocked analyzer.
Real: Constant resolution algorithms, chaining logic, global constant handling
Mocked: Analyzer (with controlled classes and global_constants dictionaries)

Test Responsibilities:
- Single function tests: Simple, cross-class, chained, and global constant resolution
- Additional tests from analyzer split: resolve_all, annotations, class references
"""
```

### test_import_resolver.py
```python
"""
Unit tests for ImportResolver functionality.

Strategy: Unit tests with hand-created JavaClass/ImportDefinition objects and mocked analyzer.
Real: Import matching algorithms, scope determination, caching logic
Mocked: Analyzer (with controlled classes dictionary)

Test Responsibilities:
- Single function tests: Basic resolution, JDK scope detection, statistics tracking
- Additional tests from analyzer split: Cache behavior, type matching, location determination
"""
```

### test_autowire_resolver.py
```python
"""
Unit tests for AutowireResolver functionality.

Strategy: Unit tests with hand-created JavaClass objects and mocked dependencies.
Real: Autowire resolution logic, @Primary/@Qualifier handling, ambiguity detection
Mocked: Analyzer and TypeResolver (controlled resolution behavior)

Test Responsibilities:
- Single function tests: Disambiguation scenarios, implementation resolution
- Additional tests from analyzer split: resolve_all, qualifier/primary finding
"""
```

### test_type_resolver.py
```python
"""
Unit tests for TypeResolver functionality.

Strategy: Unit tests with hand-created JavaClass/ImportDefinition objects and mocked analyzer.
Real: Type resolution algorithms, import matching, wildcard imports
Mocked: Analyzer (with controlled classes dictionary)

Test Responsibilities:
- Single function tests: Import resolution, wildcard imports, same-package resolution,
  resolved class population
"""
```

### test_path_resolver.py
```python
"""
Unit tests for PathResolver functionality.

Strategy: Unit tests with hand-created controller objects and mocked dependencies.
Real: Path composition algorithms, constant placeholder resolution
Mocked: Analyzer and ConstantResolver (controlled path resolution)

Test Responsibilities:
- Single function tests: Constant path resolution in REST endpoint mappings
"""
```

### test_property_resolver.py
```python
"""
Unit tests for PropertyResolver functionality.

Strategy: Unit tests with mocked analyzer and real property file parsing.
Real: Property file parsing, @Value placeholder resolution with defaults
Mocked: Analyzer (with controlled classes), member variables

Test Responsibilities:
- Single function tests: Property value resolution from real .properties files
"""
```

### test_parser.py
```python
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
```

### test_visualizer.py
```python
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
```

### test_interface_autowire.py
```python
"""
Unit tests for interface autowire disambiguation.

Strategy: Unit tests with hand-created JavaClass objects and mocked dependencies.
Real: Autowire resolution logic for interface implementations
Mocked: Analyzer and TypeResolver

Test Responsibilities:
- Single function tests: Interface implementation disambiguation with multiple candidates
"""
```

## Integration Test Files

### test_analyzer_integration.py
```python
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
```
