# Python Project Conventions

This document defines our company's governance standards for Python projects to promote maintainability, consistency, and clear separation of concerns. It covers folder structure, packaging strategy, code quality tools, and debugging practices.

## Overview

- **Modular Design:** Separate core application logic into modules within the src directory, with dedicated test directories for each module.
- **Consistency & Maintainability:** Use standard configuration files (e.g. `pyproject.toml`) to ensure consistent code formatting, linting, and dependency management across projects.
- **Test-Driven Development:** Keep unit and integration tests under the dedicated `app/tests/` folder structure and run them using `pytest` (with optional code coverage reports).

## uv Mandatory Flags

The following `uv` subcommands have **mandatory flags** — no exceptions:

| Command    | Required flags                                      | Why                                                        |
|------------|-----------------------------------------------------|------------------------------------------------------------|
| `uv lock`  | `--exclude-newer <3-days-ago>`                      | Supply-chain protection during resolution                  |
| `uv run`   | `--frozen --exclude-newer <3-days-ago>`             | `--frozen` prevents re-resolution; `--exclude-newer` is defense-in-depth |
| `uv sync`  | `--frozen --exclude-newer <3-days-ago>`             | Same as above                                              |

**Date computation**: The `--exclude-newer` value is **3 calendar days before today** in `YYYY-MM-DD` format, computed via `$(date -v-3d +%Y-%m-%d)` on macOS. (This flag syntax may differ on Ubuntu/Linux — use `$(date -d '-3 days' +%Y-%m-%d)` there, but no action needed for now.) Claude must **compute the literal date value** and pass it directly — do NOT use `$(date ...)` shell substitution in commands, as it breaks Claude Code's permission auto-allow glob matching. Example: if today is 2026-02-15, use `--exclude-newer 2026-02-12`.

In the examples throughout this document, `<3-days-ago>` is a placeholder for this computed literal date.

Both flags together on `uv run`/`uv sync` provide layered protection: `--frozen` should prevent resolution, and `--exclude-newer` ensures that if resolution somehow occurs anyway, newly published packages are still excluded.

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
uv lock --exclude-newer <3-days-ago>

# Bump within constraints
uv lock --exclude-newer <3-days-ago> --upgrade
```

### Safe Major Bumps

Use `dependency_checker.py` to analyze major version upgrades, review output, then apply with `--apply-changes`.

## Project Structure

*Note: module1 and module2 are example module folders, not folders and files to be created verbatim.*

```
project-root/
├── app/
│   ├── src/
│   │   ├── __init__.py          # Makes src a module
│   │   ├── module1/
│   │   │   ├── __init__.py
│   │   │   └── core.py
│   │   ├── module2/
│   │   │   ├── __init__.py
│   │   │   └── core.py
│   │   └── app/
│   │       ├── __init__.py      # Makes app a module too
│   │       └── main.py
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── module1/
│   │   │   ├── module2/
│   │   │   └── app/
│   │   └── integration/
│   └── __init__.py              # Makes the entire app directory a module
├── utils/
│   ├── __init__.py
│   └── helpers.py
├── .editorconfig
├── .pre-commit-config.yaml      # Pre-commit hooks configuration
├── pyproject.toml
└── .vscode/
    └── launch.json
```

### Rationale

- **app/src/**: Houses all production code in a modular structure. Each module is self-contained with its own `__init__.py`.
- **app/tests/**: Contains unit and integration tests, organized to mirror the src directory structure.
- **utils/**: Common utilities shared across modules.
- **Configuration Files:** Third-party tooling configuration files remain in the project root.

## Import Style Guide

We use absolute imports for clarity and consistency. Examples:

```python
# In app/src/module1/core.py
from app.src.module2 import some_function
from app.src.core.main import main_function
from utils.helpers import utility_function

# In app/src/core/main.py
from app.src.module1.core import core_function
from app.src.module2.core import another_function
```

## Installation

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/your_project_name.git
   cd your_project_name
   ```

2. Install uv (fast Python package manager)
   ```bash
   # macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

3. Create virtual environment and install dependencies with uv
   ```bash
   # Install base dependencies
   uv sync --frozen --exclude-newer <3-days-ago>

   # Install with development and test dependencies
   uv sync --frozen --exclude-newer <3-days-ago> --extra dev --extra test

   # Or install all extras
   uv sync --frozen --exclude-newer <3-days-ago> --all-extras
   ```

   For projects with multiple components, organize optional dependencies by concern (e.g., `cli`, `test`, `dev`, `web`, `api`). Install only what you need:

   ```bash
   uv sync --frozen --exclude-newer <3-days-ago> --extra cli --extra dev --extra test
   ```

4. Configure environment variables
   ```bash
   cp .env.sample .env
   # Edit .env file with your specific values
   ```

## Running the Application

Always run the application as a module rather than a script to ensure consistent import resolution.

```bash
# Using uv run (no activation needed)
uv run --frozen --exclude-newer <3-days-ago> --package your-package-name python -m app.src.app.main

# Or activate the virtual environment first
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows

# Then run directly
python -m app.src.app.main
```

## Testing

### Running Tests

```bash
# Run all tests for specific package
uv run --frozen --exclude-newer <3-days-ago> --package your-package-name pytest app/tests/

# Run with coverage report
uv run --frozen --exclude-newer <3-days-ago> --package your-package-name pytest --cov=app.src app/tests/

# Run specific test category
uv run --frozen --exclude-newer <3-days-ago> --package your-package-name pytest app/tests/unit/
uv run --frozen --exclude-newer <3-days-ago> --package your-package-name pytest app/tests/integration/
```

### Example Test Structure

```python
# app/tests/unit/module1/test_core.py
from app.src.module1.core import core_function

def test_core_function():
    result = core_function()
    assert result == expected_value
```

### Test Markers (Selective Runs)

Use pytest markers to partition the test suite by component. Auto-apply markers in `conftest.py` based on test file path:

```python
# conftest.py
def pytest_collection_modifyitems(items):
    for item in items:
        if "/api/" in str(item.fspath):
            item.add_marker(pytest.mark.api)
        elif "/cli/" in str(item.fspath):
            item.add_marker(pytest.mark.cli)
```

Run selectively:

```bash
uv run --frozen --exclude-newer <3-days-ago> pytest app/tests/ -m "api"
uv run --frozen --exclude-newer <3-days-ago> pytest app/tests/ -m "not api"
```

### Mock Conventions

- **Always use `spec=`** on MagicMock to catch attribute typos at test time: `MagicMock(spec=MyClass)`
- **Mock where imported**, not where defined: `@patch('app.src.module1.core.requests')` not `@patch('requests')`

## Linting and Code Quality

```bash
# Run ruff for linting (includes flake8-compatible checks)
uv run --frozen --exclude-newer <3-days-ago> ruff check app/ --fix

# Run ruff for formatting (replaces black)
uv run --frozen --exclude-newer <3-days-ago> ruff format app/

# Run pyright for type checking
uv run --frozen --exclude-newer <3-days-ago> pyright app/
```

Note: Ruff is a fast, all-in-one Python linter and formatter that replaces flake8, black, isort, and many other tools. It's 10-100x faster and provides consistent formatting and linting in a single tool.

## Pre-commit Hooks

We use pre-commit hooks to automatically run code quality checks before commits. This ensures consistent code quality across the team.

### Setup

1. Install pre-commit (included in dev dependencies):
   ```bash
   uv sync --frozen --exclude-newer <3-days-ago> --extra dev
   ```

2. Install the git hooks:
   ```bash
   pre-commit install
   ```

3. (Optional) Run against all files:
   ```bash
   pre-commit run --all-files
   ```

### Configuration

Create a `.pre-commit-config.yaml` file in your project root:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.12.9  # Use the latest version
    hooks:
      - id: ruff
        exclude: ^app/tests/
        args: [--fix]
        pass_filenames: true
      - id: ruff-format
        exclude: ^app/tests/
        pass_filenames: true
```

This configuration:
- Runs ruff linting with automatic fixes on staged files
- Runs ruff formatting on staged files
- Excludes test files from linting (adjust as needed)

The hooks will run automatically on `git commit`. If any issues are found:
- Ruff will attempt to fix them automatically
- If fixes are made, you'll need to stage the changes and commit again
- If there are issues that can't be auto-fixed, the commit will be blocked until resolved

## VSCode Configuration

### launch.json

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Debug Main",
      "type": "python",
      "request": "launch",
      "module": "app.src.app.main",
      "console": "integratedTerminal",
      "justMyCode": false
    },
    {
      "name": "Python: Debug Tests",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": [
        "app/tests/unit/module1/test_core.py",
        "-v"
      ],
      "console": "integratedTerminal",
      "justMyCode": false
    },
    {
      "name": "Python: Debug Current Test File",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": [
        "${file}",
        "-v"
      ],
      "console": "integratedTerminal",
      "justMyCode": false
    }
  ]
}
```

## Package Configuration

### pyproject.toml

Use PEP 621 format with setuptools build system and `project.optional-dependencies`. The `uv` tool manages resolution and the lockfile (`uv.lock`); the build-system section is retained for compatibility with standard Python tooling.

NOTE: Once PEP 735 (dependency-groups) is widely adopted, we can migrate from `[project.optional-dependencies]` to `[dependency-groups]` to use uv's `--group` flag. For now, we use the `--extra` flag which works with the standard optional-dependencies.

```toml
[build-system]
requires = ["setuptools>=42", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "your_project_name"
version = "0.1.0"
authors = [
    { name = "Your Name", email = "your.email@example.com" }
]
description = "A brief description of your project."
readme = "README.md"
requires-python = ">=3.12, <3.14"
dependencies = [
    "some_package>=1.0.0",
    "another_package>=2.0.0"
]

[project.optional-dependencies]
test = [
    "pytest>=7.2.0",
    "pytest-cov>=4.0.0"
]
dev = [
    "ruff>=0.4.0",
    "pyright>=1.1.300",
    "pre-commit>=3.7.0"
]

[tool.setuptools.packages.find]
include = ["app*"]
exclude = ["app.tests*"]

[tool.pytest.ini_options]
testpaths = ["app/tests"]
python_files = ["test_*.py"]
addopts = "-v --cov=app.src --import-mode=importlib"

[tool.ruff]
line-length = 99
target-version = "py311"
extend-exclude = [
    ".venv",
    "venv",
    "__pycache__",
    "*.egg-info",
    "build",
    "dist",
    ".env"
]

# Enable rules that map to flake8, isort, and more
lint.select = ["E", "F", "B", "I", "UP", "SIM", "C4"]

# Ignore specific rules (from your flake8 config)
lint.ignore = ["E203", "E501", "F401"]

    # Configure import sorting
    [tool.ruff.lint.isort]
    combine-as-imports = true
    known-first-party = []  # optionally add your own modules here

[tool.ruff.format]
# Use consistent quote style
quote-style = "preserve"
indent-style = "space"

[tool.pyright]
exclude = ["app/tests", ".venv", "venv"]
```

## Configuration

### Pydantic BaseModel (Structured App Config)

For complex application configuration with nested structure, use Pydantic `BaseModel`. This is for **structured config files** (YAML, TOML) — not secrets.

- **Root config** composed of **nested sub-configs** (each a BaseModel)
- **YAML file** as base config, overridden by **CLI arguments** or **environment variables**
- Config is **pure data** — no side effects in `__init__`
- Generate JSON schema for IDE autocompletion: `uv run --frozen --exclude-newer <3-days-ago> python -m your_app config schema --output config-schema.json`

```python
from pydantic import BaseModel, Field

class DatabaseConfig(BaseModel):
    url: str | None = None
    sqlite_path: str = "./data/app.db"

class AppConfig(BaseModel):
    organization: str = ""
    database: DatabaseConfig = DatabaseConfig()
    # ... more nested configs
```

### python-dotenv (Secrets & Environment Variables)

For secrets, API keys, and values that should **not** be checked into git, use `python-dotenv` with a `.env` file:

```python
from dotenv import load_dotenv
load_dotenv(override=True)  # override=True ensures .env values take precedence over existing env vars
```

- `.env` file is gitignored — never committed
- Provide a `.env.sample` with placeholder values for documentation
- `override=True` is mandatory to ensure `.env` values properly overwrite any previously set environment variables

### When to Use Which

| Approach | Use for | Checked into git? |
|----------|---------|-------------------|
| Pydantic BaseModel | Complex structured config (YAML/TOML), nested settings, validated types | Yes |
| python-dotenv | Secrets, API keys, database URLs, credentials | No (`.env` gitignored) |
| Both together | App config in YAML + secrets in `.env`, Pydantic reads env vars via `Field(default=...)` | Config yes, secrets no |
