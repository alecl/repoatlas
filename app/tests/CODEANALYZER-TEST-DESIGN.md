# Test Organization Philosophy & Strategy Guide

## General Philosophy

### Decision Framework: Real vs Hand-Created vs Mocked

Our test strategy follows a clear hierarchy based on what we're testing and the level of integration required:

#### 1. **Pure Unit Tests** → Hand-Created Objects
- **When**: Testing individual class methods, algorithms, or business logic
- **Objects**: Hand-created model instances (JavaClass, Annotation, etc.)
- **Mocking**: Minimal or none - focus on the unit being tested
- **Example**: Testing `Annotation.value` property or `JavaClass.find_member_variable_by_name()`

#### 2. **Component Unit Tests** → Hand-Created + Mocked Dependencies  
- **When**: Testing a component that depends on other components
- **Objects**: Hand-created model instances for inputs
- **Mocking**: Mock external dependencies (analyzer, resolvers)
- **Example**: Testing `ConstantResolver` with mocked analyzer and hand-created JavaClass

#### 3. **Integration Tests** → Real Parsing + Minimal Mocking
- **When**: Testing component interactions or end-to-end workflows
- **Objects**: Real parsed Java files using tree-sitter
- **Mocking**: Only external I/O or complex setup
- **Example**: Parsing real Java files and testing the full resolution pipeline

### Key Decision Criteria

**Use Integration Tests When:**
- Testing involves parsing actual Java source code
- Multiple components work together (parser + analyzer + resolvers)
- End-to-end workflows from source to results
- Real file I/O is meaningful to the test

**Use Unit Tests When:**
- Testing specific algorithms or business logic
- Component behavior can be verified in isolation
- Hand-created objects provide sufficient test coverage
- Fast execution is important

**Use Mocks When:**
- External dependencies are complex to set up
- Testing error scenarios that are hard to reproduce
- Isolating the component under test
- Dependencies are slow or have side effects

## File-by-File Strategy

### Core Model Tests
**`test_models.py`** - Pure Unit Tests
- **Strategy**: Test model behavior with hand-created objects
- **Real**: Pydantic model validation, computed properties
- **Mocked**: Nothing (no dependencies)
- **Rationale**: Models should work independently of parsing or external state

**`test_reference_models.py`** - Pure Unit Tests  
- **Strategy**: Test reference tracking model behavior
- **Real**: Model state transitions, resolution status tracking
- **Mocked**: Nothing (no dependencies)
- **Rationale**: Reference models are pure data structures

### Classification & Utility Tests
**`test_classification.py`** - Pure Unit Tests
- **Strategy**: Test classification logic with hand-created annotations
- **Real**: Classification algorithms
- **Mocked**: Nothing (pure functions)
- **Rationale**: Classification is algorithmic, no external dependencies

**`test_blank_line_collapse.py`** - Pure Unit Tests
- **Strategy**: Test string processing utility
- **Real**: String manipulation algorithms
- **Mocked**: Nothing (pure functions)
- **Rationale**: Utility functions with string inputs/outputs

### Parser Tests  
**`test_parser.py`** - Mixed Unit/Integration
- **Strategy**: Test parsing logic with both mocked and real tree-sitter
- **Real**: Some Java file parsing for integration scenarios
- **Mocked**: Tree-sitter components for unit testing parsing logic
- **Rationale**: Parser needs both isolated algorithm testing and real integration validation

**`test_abstraction_type.py`** - Integration (in Unit folder)
- **Strategy**: Test specific abstraction detection with real files
- **Real**: Java file parsing, tree-sitter integration
- **Mocked**: Nothing
- **Rationale**: Abstraction detection requires real parsing to be meaningful

### Analyzer Tests
**`test_analyzer_core.py`** - Unit Tests
- **Strategy**: Test analyzer logic with hand-created classes
- **Real**: Core analyzer algorithms (search, getters, basic operations)
- **Mocked**: Resolution pipeline (_resolve_all_references)
- **Rationale**: Core functionality can be tested without complex resolution setup

**`test_analyzer_integration.py`** - Integration Tests
- **Strategy**: Test file operations and real parsing workflows  
- **Real**: Java file parsing, analyzer with real resolvers, temp file I/O
- **Mocked**: Minimal (only for error scenario testing)
- **Rationale**: File operations and resolution pipelines require real component interaction

**`test_analyzer_dump_classes.py`** - Integration (in Unit folder)
- **Strategy**: Test class dumping with real parsed content
- **Real**: Java file parsing, method filtering, source code manipulation
- **Mocked**: Nothing
- **Rationale**: Dumping functionality requires real parsing to test accurately

### Resolver Tests
**All Resolver Tests** (`test_*_resolver.py`) - Unit Tests
- **Strategy**: Test resolver algorithms with hand-created classes
- **Real**: Resolution logic, algorithm correctness
- **Mocked**: Analyzer (with controlled classes dictionary)
- **Rationale**: Resolvers have clear inputs/outputs that can be unit tested

**`test_constant_resolver.py`** - Unit Tests
- **Real**: Constant resolution algorithms, chaining logic
- **Mocked**: Analyzer with controlled classes and global_constants

**`test_import_resolver.py`** - Unit Tests  
- **Real**: Import matching, scope determination algorithms
- **Mocked**: Analyzer with controlled classes dictionary

**`test_autowire_resolver.py`** - Unit Tests
- **Real**: Autowire resolution logic, @Primary/@Qualifier handling
- **Mocked**: Analyzer and TypeResolver

**`test_type_resolver.py`** - Unit Tests
- **Real**: Type resolution algorithms, import matching
- **Mocked**: Analyzer with controlled classes

**`test_path_resolver.py`** - Unit Tests
- **Real**: Path composition algorithms
- **Mocked**: Analyzer and ConstantResolver

**`test_property_resolver.py`** - Unit Tests with Real Files
- **Real**: Property file parsing, placeholder resolution
- **Mocked**: Analyzer
- **Rationale**: Property resolution requires real file parsing but controlled analyzer state

### Output Tests
**`test_visualizer.py`** - Unit Tests
- **Strategy**: Test output formatting with hand-created model objects
- **Real**: Formatting algorithms (text, JSON, Markdown, Mermaid)
- **Mocked**: Nothing
- **Rationale**: Output formatting is pure transformation of model objects

### Specialized Tests
**`test_interface_autowire.py`** - Unit Tests
- **Strategy**: Test specific autowire disambiguation scenarios
- **Real**: Autowire resolution logic
- **Mocked**: Analyzer and TypeResolver
- **Rationale**: Tests specific edge cases that need controlled setup

## Benefits of This Organization

### Fast Development Cycle
- Unit tests run in milliseconds
- Quick feedback on algorithm changes
- Easy debugging with controlled inputs

### Comprehensive Coverage  
- Unit tests verify algorithm correctness
- Integration tests verify component interaction
- Real scenarios validate end-to-end workflows

### Maintainable Test Suite
- Clear separation of concerns
- Predictable test behavior
- Easy to add new test cases

### Reliable CI/CD
- Unit tests catch regressions quickly
- Integration tests validate real-world scenarios
- Minimal test flakiness due to controlled inputs

## Anti-Patterns to Avoid

### Over-Mocking
- Don't mock simple data structures
- Don't mock the component being tested
- Avoid mocking when hand-created objects suffice

### Under-Integration Testing
- Don't rely only on unit tests for parsing components
- Don't skip file I/O testing for file-dependent features
- Don't rely on unit tests for dump classes and file output testing that relies on matching up line numbers in real source code
- Test real component interactions for critical paths

### Mixed Concerns in Single Tests
- Don't mix unit and integration testing approaches
- Keep test files focused on one testing strategy
- Separate fast unit tests from slower integration tests

This philosophy ensures our test suite is both comprehensive and maintainable, providing fast feedback during development while validating real-world scenarios.

## Test Strategy Headers

Test strategy headers provide clear documentation of testing approach directly in each test file, ensuring developers understand what's being tested, how tests are structured, and which components are real versus mocked.

When modifying test strategy for a file:
1. Update the strategy description
2. Adjust Real/Mocked sections
3. Update test class descriptions if classes change
4. Maintain consistency with the overall philosophy

### Template for Test Files
```python
"""
[Unit/Integration] tests for [Component] functionality.

Strategy: [Brief description of testing approach]
Real: [What uses real implementations/objects]
Mocked: [What is mocked and why]
Note: [Any special considerations]

Test Responsibilities:
- TestClassName: Description of what this class tests
- TestAnotherClass: Description of what this class tests
"""
```
