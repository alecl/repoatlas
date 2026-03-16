# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Changed

- Moved prototype scripts (`codegroupanalyze.py`, `codemerge.py`) to `app/manual_tests/` with sanitized paths
- Moved MCP experimental code (`code_context_tools.py`, `debug_code_context.py`, `install_mcp_code_context.py`) to `experimental/`
- Removed hardcoded debug artifacts from `java_analyze.py` (`--dump` now dumps all controller methods)
- `app/src/app/` now contains only the production CLI (`java_analyze.py`)

## [0.1.0]

### [0.0.11]

#### Added

- GitHub Actions CI workflow with lint-and-test job (SCFW audit, ruff, pyright, pytest)
- Local SCFW supply-chain audit script (`scripts/scfw-audit.sh`)
- Security policy (SECURITY.md) for vulnerability reporting via GitHub private reporting
- Screen recording as a standard PR template section

#### Changed

- Upgraded to Python 3.12
- Refined AI contribution policy with clearer expectations

### [0.0.10]

#### Added

- Contributing guide, GitHub issue templates (bug, feature, question), and PR template with issues-first workflow
- Made demo `section_20` standalone-runnable with Maven wrapper, H2 in-memory DB, and Docker Compose

#### Changed

- Clarified config override behavior in documentation
- Updated contribution plan with rationale for AI-assisted workflow

### [0.0.9]

#### Added

- 7 retroactive ADRs documenting core architecture decisions (ADR-0001 through ADR-0007)
- Demo Spring Boot microservices project (`demo/section_20/`) showcasing all resolver features
- Unit tests for `CodeAnalyzerConfig`, `refresh_class_if_needed`, and visualizer/classification/autowire modules
- Integration tests for parser edge cases and resolver pipeline end-to-end flows
- Expanded property resolver and analyzer dependency tests

#### Changed

- Updated to latest Python and Bash conventions
- Upgraded pre-commit hooks and ruff configuration
- Updated tree-sitter and Java language pack dependencies
- Reorganized topics folder structure

### [0.0.8]

#### Changed

- General documentation adjustments and cleanup

### [0.0.7]

#### Added

- Implicit constructor injection support for Spring beans without `@Autowired`
- Multi-value annotation array support (e.g., `@GetMapping({"/path1", "/path2"})`)
- Array initializer parsing in annotations with normalized endpoint path lists
- Unit and integration tests for constructor injection and multi-value mappings

#### Fixed

- `get_full_path`, `get_all_endpoints`, and `find_classes_by_endpoint` now handle list-of-paths correctly
- Annotation value and qualifier parsing handles `str | List[str]` types correctly
- `get_base_endpoint_path` returns correct type for list or string inputs
- Constructor injection properly overrides existing member variables with resolved implementations

### [0.0.6]

#### Added

- Constructor parsing with overload support and comment offset tracking
- Enum constructor and method extraction via flattened enum body declarations
- Parser tests for `API_CLIENT` detection with explicit and wildcard imports
- Test for `RestTemplate` detection in API client constructors

#### Changed

- Migrated Pydantic validators to v2 `field_validator` style
- Unified API client detection using `LocalNameResolver` and config defaults
- Merged member and constructor indicator types into single config field
- API client detection now matches simple type names in addition to FQNs

#### Fixed

- Unique keys for constructor offsets to handle overloads correctly
- `default_factory` fields use lambdas for correct Pyright typing
- Missing `fqn_type` field on `Parameter` model
- Default config list merging in `ApiClientConfig` to preserve defaults
- Method parameter type updated to `Sequence[Any]` for type correctness

### [0.0.5]

#### Added

- Constructor parsing foundation
- API client detection config overrides

### [0.0.4]

#### Added

- API client detection with class category inference
- Prioritized substring matching for class category classification

#### Fixed

- `ValueError` message assertion in `test_infer_class_category`
- Ambiguous substring matches now raise `ValueError` across priority levels

### [0.0.3]

#### Added

- Detailed method call and argument tracking models (`MethodCallInfo`, `MethodCallArgument`)
- Method call extraction with argument parsing and target resolution
- Service method call filtering with `has_service_calls` / `get_service_calls` toggle
- Regex fallback for method call extraction

#### Changed

- Removed legacy class category style
- Removed backward compatibility properties in favor of `target_name` and `target_type`
- Method call formatting shows argument types and names

#### Fixed

- Loop variable in `code_visualizer.py` method call iteration
- Missing `referenced_class_category` attribute handling in `MemberVariable`
- Import block includes `MethodCallArgument` and `ArgumentExpressionType`
- Pyright typing issues resolved

### [0.0.2]

#### Added

- Initial project structure and bootstrap

### [0.0.1]

#### Added

- Core data models (`models.py`) for Java class representation
- `__hash__` method on `JavaClass` using key fields for hashability
- Test conftest with `sample_controllers` fixture for codeanalyzer unit tests

#### Fixed

- Missing `OrderController` in `sample_controllers` fixture for full test coverage
