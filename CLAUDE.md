# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

RepoAtlas is a Python-based analyzer for Java Spring applications using tree-sitter for robust parsing. It extracts REST controllers, endpoints, service dependencies, and code relationships to create LLM codebase context — all without runtime instrumentation.

## Essential Commands

All `uv` commands **must** include `--frozen --exclude-newer <date>` where `<date>` is 3 days before today (YYYY-MM-DD format). Compute the literal date — do NOT use `$(date ...)` shell substitution.

```bash
# Install dependencies
uv sync --frozen --exclude-newer <date> --all-extras

# Run all tests
uv run --frozen --exclude-newer <date> pytest app/tests/

# Run a single test file
uv run --frozen --exclude-newer <date> pytest app/tests/unit/codeanalyzer/test_parser.py -v

# Lint and format
uv run --frozen --exclude-newer <date> ruff check --fix app/
uv run --frozen --exclude-newer <date> ruff format app/

# Type check
uv run --frozen --exclude-newer <date> pyright app/

# Run the analyzer
uv run --frozen --exclude-newer <date> python app/src/app/java_analyze.py <path> --format markdown
```

## Architecture

### Three-Layer Design (ADR-0003)

1. **Parser** (`app/src/codeanalyzer/parser.py`): Tree-sitter Java parsing → Pydantic models
2. **Models** (`app/src/codeanalyzer/models.py`): Pure data containers with computed fields. No resolution logic.
3. **Resolver Pipeline** (multi-pass, orchestrated by `analyzer.py`):
   - `ImportResolver` → `TypeResolver` → `ConstantResolver` → `PathResolver` → `AutowireResolver` → `PropertyResolver`

The `JavaAnalyzer` (`app/src/codeanalyzer/analyzer.py`) is the orchestrator: it parses files, maintains a class registry, runs the resolver pipeline, and provides search/visualization.

### Key Design Decisions

- Syntax-first analysis with tree-sitter, no runtime instrumentation (ADR-0001)
- Tree-walking over query parsing for AST robustness (ADR-0002)
- Models are pure data; resolvers are separate passes (ADR-0003, ADR-0004)
- FQN-based matching over substring matching (ADR-0007)
- ADRs live in `docs/agent/adr/` — see `AGENTS.md § ADRs` for when and how to create them; copy `ADR-0000-template.md` to start

### Source Layout

- `app/src/codeanalyzer/` — Core analysis engine (parser, models, resolvers, visualizer)
- `app/src/app/` — Production CLI (`java_analyze.py`)
- `app/src/codetools/` — Utility modules (gitignore handling, code merging)
- `app/manual_tests/` — Reference scripts for codetools usage (not runnable as-is)
- `experimental/` — MCP and code-context prototypes (not production code)
- `app/tests/unit/` — Unit tests (mocked dependencies, mirrors src structure)
- `app/tests/integration/` — Integration tests (real tree-sitter parsing)

## Conventions

### Authoritative References

- `conventions.python.md` — Python standards (uv flags, imports, testing, linting)
- `conventions.bash.md` — Bash script standards (strict mode, idempotence, cross-OS)
- `AGENTS.md` — Agent workflow, skills, planning requirements, definition of done

When conflicts exist: repository-local instructions > broader conventions.

### Python

- **Imports**: Absolute from project root (`from app.src.codeanalyzer.models import JavaClass`)
- **Line length**: 99 (ruff configured in pyproject.toml)
- **Ruff rules**: E, F, B, I, UP, SIM, C4
- **Pre-commit hooks** run ruff check/format automatically on commit (excludes tests)
- **Pyright** excludes: `codetools`, `tests`, `.venv`
- **Adding deps**: `uv add --bounds major <pkg>` (use `--optional dev` or `--optional test` for non-production)

### Testing

- Unit tests use hand-crafted Pydantic models and mocks (`spec=` on MagicMock, mock where imported)
- Integration tests parse real Java files via tree-sitter
- Coverage: `--cov=app.src` is in pytest addopts by default
