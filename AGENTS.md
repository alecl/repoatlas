# Agent Workflow

This file is the cross-agent workflow contract for this repository. It is checked
into version control and read by both Claude Code and OpenAI Codex. It must live
in-repo because Codex has no global `~/.codex/AGENTS.md` discovery path — without
this file, Codex loses all workflow guidance. Claude Code's global `~/.claude/CLAUDE.md`
covers only generic cross-repo rules; the detailed workflow policy below is
repo-portable and must travel with the code.

Generic sections are fenced so you know what to copy verbatim to new repos.
Repo-specific sections follow and must be customized per project.

<!-- GENERIC WORKFLOW — copy this block verbatim to new repos ======================== -->

## Skills

This repository uses the following skills. Each agent discovers them by name from
its user-level skill directory. Both agents resolve skills by name — no repo-local
file paths are required. Typical install locations: `~/.claude/skills/` for Claude Code,
`~/.codex/skills/` for Codex.

### Available Skills

- `plan-change`: Create or update an agent plan for non-trivial work
- `review-change`: Review a meaningful change before declaring it complete
- `log-change`: Update durable change records when behavior, bug-fix, or architecture records change
- `commit-change`: Close a validated task boundary with one coherent commit or record why the commit is deferred
- `python-validate`: Apply Python conventions and run the required `uv`-based validation flow
- `bash-validate`: Apply Bash conventions and run the required `shellcheck`-based validation flow

### Skill Usage Rules

- If the user names a skill or the task clearly matches a skill description, use that skill for the turn.
- Read only enough of a skill to follow its workflow.
- Prefer the smallest number of skills that covers the task cleanly.
- Keep context small: do not load extra references unless the active skill requires them.

If skills are not found in your agent's user-level directory, you can copy them from
another team member's install or place them under `.agents/skills/` in this repo.

## When Planning Is Required

Create or update a plan in `docs/agent/plans/` before starting non-trivial work, including when:

- multiple files are likely to change
- behavior changes are expected
- architecture or interface changes are involved
- the task carries meaningful risk, ambiguity, or rollback concerns
- the initial implementation approach may need validation before broader edits

Plan files should include:

- objective
- constraints and assumptions
- affected files or subsystems
- validation plan
- ADR assessment
- commit expectation
- expected durable records to update
- course corrections
- reusable learnings
- follow-ups

## Quality Pass Before Validation Tools

Before running linting, formatting, type-checking, or tests, do a short design-quality pass for:

- repeated string literals and other magic strings
- duplicated logic that should be consolidated
- opportunities to introduce named constants
- opportunities to extract helpers or simplify branching
- consistency with existing module boundaries and project conventions

Do not stop at "the checks pass" if the code still has obvious repetition or avoidable complexity.

## Durable Records

### CHANGELOG.md

Use `CHANGELOG.md` for concise, externally relevant or operationally meaningful summaries.

- keep a Keep a Changelog structure
- maintain `## [Unreleased]` as a temporary staging area for not-yet-archived notes
- use `Added`, `Changed`, `Fixed`, and `Removed` (but don't include any sections with no content for an entry)
- when archiving shipped notes, create a new section in the format `## [version] - YYYY-MM-DD HH:MM`
- when an archived change maps cleanly to a ticketed change plan, add `Ticket: [COCO-123](docs/agent/plans/...)` immediately below the dated section header, with a blank line before and after the ticket line
- the project cuts semantic versions; each release gets its own `## [version] - YYYY-MM-DD` section — see `VERSIONING.md` for the release process and bump commands
- major bug fixes may be summarized here under `Fixed`
- treat strong-signal changes as changelog candidates even when the underlying code change is small. Strong signals include:
  - default command or CLI invocation changes
  - operator workflow changes documented in `README.md`, `ARCHITECTURE.md`, or `DEVOPS.md`
  - public interface, tool-surface, config-default, or environment-variable changes
- when a task closeout merits a changelog entry, stage it in `Unreleased` only until the changelog is updated, then move the shipped notes into a dated version section
- do not leave durable history only under `Unreleased`; once the changelog is updated, the archived entry belongs under a dated version header
- at ticket or milestone completion, make an explicit changelog decision:
  - `CHANGELOG required: yes` with the intended entry scope, related ticket if the task has one, and version/timestamp target if known
  - `CHANGELOG required: no` with a short rationale

Do not assume that a backlog or MVP completion can inherit earlier ticket-level `no changelog` decisions.
Reassess changelog candidacy against the final diff before commit; an earlier `no` does not survive automatically if the completed change carries a strong signal.

### Bug-fix changelog rule

When `BUG_FIXES.md` is updated, always add a corresponding terse `### Fixed` one-liner in `CHANGELOG.md` in the same pass.

### BUG_FIXES.md

Use `BUG_FIXES.md` for implementation-level bug-fix records.

Each entry should include:

- date and title
- summary
- impact
- root cause
- trigger or reproduction
- resolution
- tests added or updated
- follow-ups
- links

### ADRs

Create or update an ADR in `docs/agent/adr/` for changes that affect architecture, interfaces, long-term design direction, or important tradeoffs.

#### When to write an ADR

Write an ADR when the decision:

- Introduces or removes a major dependency
- Changes module boundaries or layer responsibilities
- Chooses between two or more viable strategies with different long-term tradeoffs
- Changes how data flows between components
- Establishes a pattern that future code is expected to follow

Skip the ADR when the change is:

- A bug fix that doesn't change architecture
- Adding a test, doc update, or config tweak
- Refactoring that preserves existing interfaces and behavior
- Choosing a utility function or small library for a contained purpose
- Implementing an approach already covered by an existing ADR

When in doubt, write the ADR — if future contributors would need the tradeoff record, it belongs in an ADR.

#### Two-phase timing

- **Planning phase:** Decide ADR candidacy (`ADR required: yes/no` with rationale). Identify which decisions are ADR-worthy.
- **Implementation phase:** Write or update the actual ADR file, in the same commit as the code it describes.

For every non-trivial planned task, make the ADR decision explicit in the plan:

- `ADR required: yes` and list the candidate decision or decisions
- `ADR required: no` with a short rationale

Do not leave ADR candidacy implicit.

#### New vs. update vs. supersede

- **New ADR:** When making a decision not covered by an existing ADR.
- **Update existing ADR:** When refining or extending a decision that already has an ADR (e.g., adding a new consequence discovered during implementation).
- **Superseding:** When replacing a previous decision, create a new ADR and add cross-references in both directions: the new ADR's Related ADRs says "supersedes ADR-NNNN" and the old ADR gets a Related ADRs entry saying "superseded by ADR-NNNN". This keeps supersession discoverable from either end without introducing a Status lifecycle.

#### ADR sections

- Context
- Decision
- Alternatives considered
- Consequences
- Related ADRs (optional)

Copy `docs/agent/adr/ADR-0000-template.md` and rename to the next monotonic `ADR-NNNN-short-title.md`.

Use the filename pattern `ADR-xxxx-short-title.md`, with zero-padded numbering that increases monotonically.

#### Sync guardrail

When the ADR section structure here changes, update `ADR-0000-template.md` to match.

## Course Corrections

If the initial implementation approach was abandoned or materially changed:

- record the original approach
- explain why it changed
- record the final chosen approach

Capture this in the relevant plan file under `Course corrections`. Reflect it in an ADR or bug-fix record as well when the change is architecturally significant or explains a production bug.

## Reusable Learnings

If a task reveals a lesson that should change future work, record it in the task plan under `Reusable learnings`.

Before declaring the work complete, reconcile each reusable learning into one of:

- `AGENTS.md` when it is repo policy
- the relevant skill when it is a repeatable procedure
- the task plan only, with a short reason, when it is context-specific and should not become general guidance

## Commit Granularity

Each commit should represent one coherent, reviewable, reversible unit of change.

When a ticket-sized task is completed and validated, create a commit unless the user explicitly asked for batching, deferral, or a no-commit turn. If a commit is deferred, record the reason in the task plan or closeout notes.

Preferred boundaries:

- one bug fix with its tests
- one feature slice with directly related tests and records
- one refactor with no behavior change
- one dependency update for a single purpose
- one mechanical rename, move, or formatting-only change

Avoid mixing:

- refactors with behavior changes unless inseparable
- unrelated cleanup with bug fixes or features
- dependency upgrades with unrelated code changes
- broad formatting changes with logic edits
- multiple unrelated bug fixes in one commit

When practical, include related `CHANGELOG.md`, `BUG_FIXES.md`, and ADR updates in the same commit as the code change they describe.

## Commit Message Format

Use Conventional Commits for all commit messages.

Examples:

- `feat(api): add tenant usage endpoint`
- `fix(auth): handle expired refresh token`
- `refactor(config): consolidate env parsing`
- `test(worker): cover retry backoff behavior`
- `docs(agent): add ADR for queue partitioning`

## When To Invoke Skills

- use `plan-change` before non-trivial work
- use `review-change` before declaring meaningful work complete
- use `log-change` when behavior, bug-fix, operational, architecture, or strong-signal user/operator-facing documentation records must be updated
- use `commit-change` after review and logging are complete for a task-sized change boundary
- use `python-validate` for Python changes
- use `bash-validate` for Bash changes

## Definition Of Done

Work is not complete until the following are satisfied as applicable:

- the relevant plan file is created or updated
- the quality pass has been done
- language-specific validations have been run
- required tests have been added or updated
- `CHANGELOG.md` has been updated for externally relevant changes
- changelog candidacy has been decided explicitly for the task or milestone being closed
- `BUG_FIXES.md` has been updated for bug fixes
- ADR candidacy has been decided explicitly in the task plan
- ADRs have been created or updated for significant design decisions
- course corrections have been recorded when the implementation direction changed
- reusable learnings have been reconciled into policy, a skill, or explicitly kept task-local with rationale
- a task-boundary commit has been created or intentionally deferred with a recorded reason
- commits are scoped as coherent reviewable units
- commit messages follow Conventional Commits

<!-- END GENERIC WORKFLOW ========================================================== -->

<!-- REPO-SPECIFIC — customize the sections below per project ======================= -->

## Authoritative Conventions

- Follow `conventions.python.md` for Python structure, package management, validation commands, and test conventions.
- Follow `conventions.bash.md` for Bash script structure, safety posture, idempotence, and validation expectations.
- If repository-local instructions conflict with a broader convention, follow the more specific repository-local instruction.

## Agent-Owned Artifact Locations

- Agent plans: `docs/agent/plans/`
- Architecture decision records: `docs/agent/adr/`
- Ideas (plans or other research documents not yet ready for implementation): `docs/agent/ideas/`
- Coco-Pilot topic workspaces (runtime topic state and review artifacts): `docs/agent/coco-pilot-topics/`

Use repository-root files for shared durable logs:

- `CHANGELOG.md`
- `BUG_FIXES.md`

## Python Workflow

For Python changes:

- treat `conventions.python.md` as authoritative
- use `uv` for dependency management, syncing, locking, and command execution
- treat the required flags for `uv lock`, `uv run`, and `uv sync` in `conventions.python.md` as mandatory
- compute the literal `--exclude-newer` date value and pass it directly where required
- preserve the current repository-standard validation posture from `conventions.python.md`, including the exact `ruff`, `pyright`, and `pytest` command expectations as written there
- choose the narrowest reasonable test scope first, then broaden when risk or impact warrants it
- follow the mocking and test-structure conventions in `conventions.python.md`

## Bash Workflow

For Bash changes:

- treat `conventions.bash.md` as authoritative
- prefer CI/CD-safe, non-interactive, fail-fast behavior by default
- use strict mode unless there is a documented reason not to
- route execution through `main "$@"`
- resolve relative paths from `SCRIPT_DIR`
- check prerequisites explicitly
- keep scripts idempotent and safe to re-run
- prefer cross-platform-compatible patterns that work on macOS and common Linux environments
- run `shellcheck` for Bash changes
- do not assume a shell formatter is required unless the repository standard is updated to say so

## Package Management

For Python package management:

- follow `conventions.python.md`
- use `uv`
- use `uv add --bounds major` when adding dependencies
- do not bypass the locked environment with ad hoc package installation or execution flows
- respect the repository extras model and dependency grouping conventions

## FastMCP Tool Metadata

For FastMCP tools in this repo:

- put tool-level LLM guidance in `@server.tool(description=...)`
- put parameter-level LLM guidance in `Annotated[..., Field(description=...)]`
- do not rely on docstring parameter sections to populate JSON Schema properties
- keep LLM-facing guidance out of docstring parameter blocks to avoid duplicated schema text

<!-- END REPO-SPECIFIC ============================================================= -->
