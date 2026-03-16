# Contributing to RepoAtlas

## Before You Contribute

RepoAtlas is an early-stage project. We're actively shaping the architecture, scope,
and direction, which means we maintain tight control over what gets merged. Contributions
are welcome, but not every PR will be accepted — and that's okay. If you're interested in
helping, reading this guide first will save both of us time.

## Issues First

All non-trivial changes start as a GitHub issue. Describe the problem or idea, then wait
for a maintainer response before writing code. This lets us align on whether the change
fits the project's direction before you invest effort.

PRs without a linked issue may be closed without review.

The **Question** template is for questions only — change proposals belong in bug or
feature request issues.

## What We're Likely to Accept

- Small, focused bug fixes
- Documentation improvements
- Test coverage improvements
- Issues labeled `help wanted` or `good first issue`

## What We're Unlikely to Accept

- Large PRs or unsolicited feature work
- Opinionated refactors or "cleanup" PRs
- Anything that expands scope without prior discussion

If you're unsure, open an issue and ask. We'd rather have a short conversation than
see effort go to waste.

## AI-Assisted Contributions

AI coding tools (Claude Code, Copilot, Cursor, etc.) WITH their humans are welcome.
The bar is deep human involvement at every stage, not just prompting and pasting.

**What we expect:**

- **Planning**: You drove the design, not just accepted whatever the tool suggested.
- **Code review**: You read every line the tool produced and understand why it's there.
- **Test review**: You verified the tests exercise the right behavior, not just that they pass.
- **Manual testing**: You ran the code yourself and observed the output.
- **You must be able to explain what your code does and why, in your own words.** If asked
  during review, "the AI wrote it" is not an answer.
- PR descriptions and issue reports should reflect genuine understanding, not generated
  walls of text. Keep them concise and specific.
- Show that you've read the relevant code. For example, explain how your change interacts
  with the analyzer pipeline, or why a specific resolver is affected.

**Screen recording requirement:** Include a screen recording of the code running and the
output being reviewed as proof of human involvement. Link it in your PR (the template has
a section for this). A short Loom, asciinema, or unlisted YouTube video is fine.

**What will get your PR closed:**

- Purely AI-generated drive-by PRs with no evidence of human review.
- Repeated low-quality or clearly AI-generated submissions may result in being blocked.

## Pull Request Expectations

- Keep PRs small and focused — one logical change per PR.
- Reference the issue: `Fixes #N` or `Closes #N`.
- Explain what changed and why.
- Explain how you tested it: what command you ran, what output you observed.
- Include before/after CLI output where relevant.
- PR titles follow conventional commits: `feat:`, `fix:`, `docs:`, etc.
- Don't mix unrelated changes.

## Test Coverage

**Every code change must include tests.** PRs that change behavior without corresponding
test coverage will not be merged.

- **Bug fixes** require a test that fails before the fix and passes after.
- **New features** require unit tests covering the core logic and at least one integration
  test demonstrating end-to-end behavior through the parser or resolver pipeline.
- **Refactors** must not reduce existing coverage — run `pytest --cov` and verify.

If a change is genuinely untestable, explain why in the PR description. "I didn't have
time to write tests" is not a valid reason.

## Validating Code Changes

For code PRs, run tests, lint, format, and type-check before submitting:

- **pytest** — run the test suite
- **ruff check** — lint
- **ruff format** — format
- **pyright** — type-check
- `scripts/scfw-audit.sh` — run the Datadog SCFW supply-chain audit locally

See the README's [Development](README.md#development) section for exact invocations
and required flags.

## Setting Expectations

Opening a PR doesn't create an obligation on either side. We may close it, defer it,
ask you to shrink it, or reimplement the idea ourselves. If that's okay with you,
we'd love your help.
