# Java Spring Analyzer Project

## Project Structure

```
app/src/app
│
├── java_analyze.py        # Example script demonstrating all features
│
app/src/codeanalyzer/
│
├── analyzer.py           # Orchestrates parsing and multi-pass resolution pipeline
├── import_resolver.py    # Lazily resolves import statements and determines scope
├── type_resolver.py      # Resolves type references using imports and package context
├── constant_resolver.py  # Resolves constant references with chaining support
├── path_resolver.py      # Resolves REST endpoint paths and combines base and method paths
├── autowire_resolver.py  # Resolves @Autowired dependencies to concrete implementations
├── property_resolver.py  # Resolves @Value property placeholders from configuration files
├── parser.py             # Low-level parsing using tree-sitter (JavaParser)
├── models.py             # Pydantic models with computed properties (JavaClass, RestEndpoint, etc.)
├── code_visualizer.py    # Output formatting and visualization (text, JSON, Markdown, Mermaid)
└── constants.json        # Example constants for resolution
│
app/tests/
├── integration/
│   └── codeanalyzer/
│       ├── test_abstraction_type.py
│       ├── test_analyzer_dump_classes.py
│       └── test_analyzer_integration.py
└── unit/
    ├── codeanalyzer/
    │   ├── test_analyzer_core.py
    │   ├── test_models.py
    │   ├── test_parser.py
    │   ├── test_visualizer.py
    │   └── ... (12 more test files)
    └── codetools/
        └── ... (3 test files)
```

## Artifact Descriptions

1. **`analyzer.py`** (Artifact: Analyzer Orchestrator)
   - Coordinates parsing and resolution across multiple classes
   - Manages specialized resolvers in a multi-pass pipeline
   - Maintains class registry and global constants injection
   - Provides search, reporting, and dependency graph capabilities

2. **`import_resolver.py`** (Artifact: Import Resolver)
   - Lazily resolves import statements to determine class/package locations
   - Determines reference scope (JDK, same jar, same repo/different jar, third-party)
   - Caches resolution results and tracks usage statistics

3. **`type_resolver.py`** (Artifact: Type Resolver)
   - Resolves type references via explicit and wildcard imports
   - Handles generics by extracting base types
   - Falls back to same-package or fully qualified names

4. **`constant_resolver.py`** (Artifact: Constant Resolver)
   - Resolves constant references within and across classes
   - Supports chained resolution for multi-level constant definitions
   - Integrates with the import resolver for cross-class lookups

5. **`path_resolver.py`** (Artifact: Path Resolver)
   - Resolves REST endpoint paths by combining base and method mappings
   - Handles constant placeholders in @RequestMapping and @Get/Post annotations

6. **`autowire_resolver.py`** (Artifact: Autowire Resolver)
   - Resolves Spring @Autowired dependencies to concrete implementations
   - Honors @Qualifier and @Primary annotations for disambiguation

7. **`property_resolver.py`** (Artifact: Property Resolver)
   - Parses configuration files and resolves ${property.name:default} placeholders
   - Supports default values and environment variable fallbacks

8. **`parser.py`** (Artifact: Java Parser)
   - Parses Java source using tree-sitter into Pydantic models
   - Extracts AST nodes, annotations, imports, and constants for later resolution

9. **`models.py`** (Artifact: Java Models)
   - Defines Pydantic models for Java elements with computed properties
   - Includes JavaClass, RestEndpoint, ImportDefinition, and reference tracking

10. **`code_visualizer.py`** (Artifact: Code Visualizer)
    - Formats analysis results as text, JSON, Markdown, and Mermaid diagrams

11. **`java_analyze.py`** (Artifact: Example Usage)
    - Demonstrates usage of JavaAnalyzer and resolvers via CLI

12. **`constants.json`** (Artifact: Example Constants)
    - Provides sample constant mappings for testing and documentation

## Key Improvements and New Features

1. **Separation of Concerns**
   - Distinct parser, data models, resolvers, and visualizer layers

2. **Semantic Resolution Pipeline**
   - Multi-pass orchestration by JavaAnalyzer with specialized resolvers for imports, types, constants, paths, autowire, and properties

3. **Lazy and Cached Resolution**
   - Lazy import matching and caching in ImportResolver for performance

4. **Advanced Constant Resolution**
   - ConstantResolver supports chained lookups and cross-class references for accurate values

5. **Robust Type Handling**
   - TypeResolver manages explicit and wildcard imports, generics, and same-package or fully qualified fallbacks

6. **REST Endpoint Path Composition**
   - PathResolver seamlessly merges controller and method-level paths and resolves constants within them

7. **Spring Dependency Injection Support**
   - AutowireResolver resolves @Autowired fields using @Qualifier and @Primary strategies

8. **Configurable Property Injection**
   - PropertyResolver parses config files and resolves @Value placeholders with defaults and environment fallbacks

9. **Rich Search and Graph Features**
   - JavaAnalyzer provides flexible search (by name, package, path) and dependency graph generation

10. **Extensible and Testable Architecture**
    - Modular resolvers with focused unit tests, clear design for future extensions
   
