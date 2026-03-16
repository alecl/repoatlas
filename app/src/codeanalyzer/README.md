# RepoAtlas Code Analyzer

The codeanalyzer module provides Java Spring application analysis using tree-sitter for robust parsing. It maps the complete architecture of Spring applications by extracting REST endpoints, tracing service dependencies, resolving property values, constants and types across packages, and building a navigable graph of how your controllers, services, and repositories connect.

## Installation

See the [main README](../../../README.md) for installation instructions. The tree-sitter Java grammar is installed automatically via `tree-sitter-language-pack`.

## Usage

### Basic Usage

```python
from app.src.codeanalyzer.analyzer import JavaAnalyzer

# Initialize the analyzer
analyzer = JavaAnalyzer()

# Parse a single file
java_class = analyzer.parse_file("path/to/UserController.java")

# Or parse a directory (recursively)
classes = analyzer.parse_directory("path/to/src", recursive=True)

# Get all controllers
controllers = analyzer.get_controllers()

# For a specific controller, get endpoints
for controller in controllers:
    print(f"Controller: {controller.name}")
    print(f"Base path: {controller.base_endpoint_path}")
    
    # Get endpoints
    endpoints = controller.get_all_endpoints()
    for http_method, paths in endpoints.items():
        for path, method_name in paths:
            print(f"  {http_method}: {path} -> {method_name}")
    
    # Get service dependencies
    for service in controller.service_variables:
        print(f"  Service: {service.type} {service.name}")
```

### Using Constant Resolution

```python
# Define constants mapping
constants = {
    "ApplicationConstants.AUTHORIZATION": "Authorization",
    "ApiConstants.API_BASE_PATH": "/api/v2",
    "HeaderConstants.AUTH_HEADER": "X-Auth-Token"
}

# Add constants to the analyzer
analyzer.add_constants(constants)

# Parse files - constants will be resolved automatically
java_class = analyzer.parse_file("path/to/UserController.java")

# Now paths and annotations using these constants will show their resolved values
```

### Command Line Interface

The package includes a command-line tool:

```bash
python app/src/app/java_analyze.py path/to/src --recursive --format markdown --output analysis.md
```

For more options:

```bash
python app/src/app/java_analyze.py --help
```

## Architecture

The package is organized into several components:

### Models (`models.py`)

- **Base Models**:
  - `JavaClass`: Base class for all Java classes
  - `JavaMethod`: Base class for all Java methods
  - `MemberVariable`: Base class for class member variables

- **Specialized Models**:
  - `RestControllerClass`: Spring REST controller model with endpoint extraction
  - `RestEndpoint`: Method with HTTP mappings
  - `ClassReferenceMemberVariable`: Member variable representing a service dependency

- **Supporting Models**:
  - `Annotation`: Java annotation with name and values
  - `Parameter`: Method parameter with type and annotations
  - `ClassCategory`: Enum for different Java class types
  - `MemberVariableCategory`: Enum for different member variable types

### Parser (`parser.py`)

- **JavaParser**: Low-level parser that uses tree-sitter to analyze Java source files
- **JavaAnalyzer**: High-level analyzer that manages parsing and analysis workflow

## Example Output

Here's a sample of the Markdown output for a controller analysis:

```markdown
### UserController

- **Package**: `com.example.web`
- **Base Path**: `/api/users`

#### Endpoints

| HTTP Method | Path | Method |
|------------|------|--------|
| GET | `/api/users` | `getAllUsers` |
| GET | `/api/users/{id}` | `getUserById` |
| POST | `/api/users` | `createUser` |
| PUT | `/api/users/{id}` | `updateUser` |
| DELETE | `/api/users/{id}` | `deleteUser` |

#### Service Dependencies

| Type | Name | Qualifier |
|------|------|-----------|
| `UserService` | `userService` | userServiceImpl |
```

## Running Tests

To run the tests:

```bash
# Run all tests
pytest app/tests/ -v

# Run unit tests only
pytest app/tests/unit/ -v

# Run integration tests only
pytest app/tests/integration/ -v
```
