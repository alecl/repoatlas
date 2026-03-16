# RepoAtlas

A Python-based analyzer for Java Spring applications using tree-sitter for robust parsing. This tool extracts detailed information about Spring controllers, including endpoints, HTTP methods, service dependencies, and more.

## Why RepoAtlas?

Spring's layered indirection — dependency injection, route mappings, constant resolution, cross-package type references — defeats both million-token context windows and agentic discovery harnesses. Without RepoAtlas, every agent question triggers a slow, expensive, non-deterministic chain-walk: grep or RAG retrieves fragments, the agent burns tokens tracing imports and wiring across files, and the result is a best-effort partial answer that may miss critical paths. RepoAtlas replaces this with a persistent artifact — a fully resolved structural map computed once by a deterministic parser pipeline. Every agent reads the same correct answer in a single file read instead of spending dozens of tool calls hoping to reconstruct it. The speed-up is massive and compounds with every question, every developer, and every CI check that needs architectural context. As a bonus, the artifact is effectively an OpenAPI/Swagger-style endpoint catalog — extracted directly from source code, no runtime scaffolding required — giving teams a resolved API surface even for codebases that were never wired with OpenAPI tooling. See the [full rationale](RATIONALE.md) for why this matters for agentic workflows, blast-radius analysis, and code search.

## Features

- Parse Java source files with tree-sitter for accurate syntax analysis
- Extract detailed information from Spring REST controllers:
  - Controller class names and packages
  - Base request paths
  - HTTP endpoints with methods (GET, POST, PUT, etc.)
  - Service dependencies with @Autowired and @Qualifier annotations
  - Method parameters and their annotations
- Resolve constant variables to their literal values
- Support for file path tracking (relative and absolute paths)
- Modular architecture with well-defined class hierarchy
- Comprehensive unit tests and type annotations

## Project Structure

```
repoatlas/
├── app/
│   ├── src/
│   │   ├── codeanalyzer/   # Core analysis engine — parser, models, resolver pipeline, visualizer
│   │   ├── codetools/      # Utility modules — gitignore handling, code merging
│   │   └── app/            # Production CLI (java_analyze.py)
│   ├── manual_tests/       # Reference scripts for codetools usage (not runnable as-is)
│   └── tests/
│       ├── unit/           # Unit tests (mocked deps, mirrors src structure)
│       └── integration/    # Integration tests (real tree-sitter parsing)
├── experimental/           # MCP and code-context prototypes (not production code)
├── .env.sample             # Template for environment variables
├── pyproject.toml          # Project metadata and dependencies
└── .vscode/
    └── launch.json         # VSCode debugging configuration
```

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Git (for GitHub repository access)

> **Note**: Tree-sitter grammars are installed automatically via `tree-sitter-language-pack`. No manual grammar building is required.

### Installation

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/repoatlas.git
   cd repoatlas
   ```

2. Install uv and set up the project
```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies (dev + test)
uv sync --frozen --exclude-newer $EXCLUDE_NEWER --extra dev --extra test
```

**Why `--exclude-newer`?** This flag tells uv to ignore packages published after the given date. It gives the community a window to discover and yank compromised releases before they reach your lockfile — a simple defense against fast-moving supply-chain attacks. Set the date ~3 days behind today.

Cross-OS one-liner (Python is already a prerequisite):
```bash
export EXCLUDE_NEWER=$(python3 -c "import datetime;print((datetime.date.today()-datetime.timedelta(days=3)).isoformat())")
```
Then use `uv sync --frozen --exclude-newer $EXCLUDE_NEWER --extra dev --extra test` and similar for all `uv run` commands.

Alternatively, using pip:
```bash
python -m venv .venv
source .venv/bin/activate
# On Windows: .venv\Scripts\activate
pip install -e ".[dev,test]"
```

3. Configure environment variables
```bash
cp .env.sample .env
# Edit .env file with your specifics
```

### Running the Application

```bash
uv run --frozen --exclude-newer $EXCLUDE_NEWER python app/src/app/java_analyze.py app/tests/unit/codeanalyzer/test_samples/QualifiedController.java
```

Or activate the virtualenv first and run directly:
```bash
source .venv/bin/activate
python app/src/app/java_analyze.py app/tests/unit/codeanalyzer/test_samples/QualifiedController.java
```

### CLI Options

| Argument | Short | Description |
|----------|-------|-------------|
| `path` | | Java file(s) or directory to analyze |
| `--recursive` | `-r` | Recursively analyze directories |
| `--format` | `-f` | Output: text, json, markdown, mermaid-class, mermaid-flow |
| `--output` | `-o` | Write results to file (default: stdout) |
| `--config` | | Path to configuration file (JSON5, see below) |
| `--constants` | `-c` | Path to JSON file with constant mappings |
| `--resolve-constants` | `-rc` | Resolve constant variables in class dump |
| `--dump` | `-d` | Dump class source |
| `--search` | `-s` | Search for classes/endpoints by criteria |
| `--search-type` | | Search type: name, path, package, endpoint |
| `--base-path` | | Base path(s) to strip from endpoint prefixes |

### Configuration

The `--config` flag accepts a JSON5 file (comments supported). See [`codeanalyzer_sample_config.json`](app/src/codeanalyzer/codeanalyzer_sample_config.json) for all available options with documentation.

| Section | Purpose |
|---------|---------|
| `logging.level` | Set log verbosity |
| `classification.class_name_overrides` | Override automatic class categorization by class name |
| `classification.api_client` | Additional annotations and types for API client detection (merged with built-in defaults) |

## Development

### Running Tests

```bash
# Run all tests
uv run --frozen --exclude-newer $EXCLUDE_NEWER pytest app/tests/

# Run with coverage report
uv run --frozen --exclude-newer $EXCLUDE_NEWER pytest --cov=app.src app/tests/

# Run specific test category
uv run --frozen --exclude-newer $EXCLUDE_NEWER pytest app/tests/unit/
uv run --frozen --exclude-newer $EXCLUDE_NEWER pytest app/tests/integration/
```

### Linting and Code Quality

```bash
# Run ruff linter (with auto-fix)
uv run --frozen --exclude-newer $EXCLUDE_NEWER ruff check --fix app/

# Run ruff formatter
uv run --frozen --exclude-newer $EXCLUDE_NEWER ruff format app/

# Run pyright (type checking)
uv run --frozen --exclude-newer $EXCLUDE_NEWER pyright app/
```

### Debugging

You can use the VSCode configuration provided in `.vscode/launch.json` or run the module directly with debugging enabled:

```bash
# Debug main application with a sample repository
python -m debugpy --listen 5678 --wait-for-client -m app.src.app.main --repo https://github.com/username/repository

# Debug main application with a local folder
python -m debugpy --listen 5678 --wait-for-client -m app.src.app.main --dir /path/to/your/project

# Debug specific tests
python -m debugpy --listen 5678 --wait-for-client -m pytest app/tests/unit/test_specific.py
```

### Adding Dependencies

Always use `--bounds major` to constrain dependency ranges:

```bash
# Optional dependencies (dev, test, etc.)
uv add --optional dev --bounds major ruff
uv add --optional test --bounds major pytest

# Main dependencies
uv add --bounds major aiohttp
```

Note: Use `--bounds major` instead of `^` syntax (uv doesn't support PEP 440 caret notation).

### Locking / Updating

```bash
# Lock dependencies (within constraints)
uv lock --exclude-newer $EXCLUDE_NEWER

# Bump within constraints
uv lock --exclude-newer $EXCLUDE_NEWER --upgrade
```

### Safe Major Bumps

Use `dependency_checker.py` to analyze major version upgrades, review output, then apply with `--apply-changes`.

## Contributing

This project is early stage. We welcome thoughtful contributions but ask that you
read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR. The short version:
open an issue first, keep changes small, and explain your work in your own words.

