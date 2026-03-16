# Versioning

RepoAtlas follows [Semantic Versioning](https://semver.org/) (SemVer).

## Version Scheme

| Bump  | When to use                                       | Example          |
|-------|---------------------------------------------------|------------------|
| Patch | Bug fixes, documentation corrections              | 0.1.0 → 0.1.1   |
| Minor | New features, non-breaking enhancements           | 0.1.0 → 0.2.0   |
| Major | Breaking changes to public interfaces or behavior | 0.2.0 → 1.0.0   |

### Pre-1.0 Note

While the project is pre-1.0, minor bumps may include small breaking changes. After 1.0, any breaking change requires a major bump.

## Git Tags

Every release is tagged `v{version}` (e.g., `v0.2.0`). Tags are created automatically by `bump-my-version`.

## Release Process

1. Ensure a clean working tree (`git status` shows no uncommitted changes).
2. Update `CHANGELOG.md`: move items from `[Unreleased]` into a new `## [X.Y.Z] - YYYY-MM-DD` section.
3. Commit the changelog: `git commit -m "docs: prepare changelog for vX.Y.Z"`
4. Run the version bump:
   ```bash
   uv run --frozen --exclude-newer <date> bump-my-version bump {patch|minor|major}
   ```
5. Push with tags: `git push origin main --follow-tags`
6. Verify the tag on the remote: `git ls-remote --tags origin`

## Dry Run

Preview what a bump would do without making changes:

```bash
uv run --frozen --exclude-newer <date> bump-my-version bump --dry-run --verbose patch
```

## Configuration

The `bump-my-version` configuration lives in `[tool.bumpversion]` in `pyproject.toml`. It targets only the `version = "..."` line in `pyproject.toml` to avoid false matches on other version-like strings (e.g., `target-version`, `requires-python`, dependency bounds).

## Future: PyPI Publishing

When the project is ready for PyPI distribution, the planned approach is:

- GitHub Actions workflow triggered on tag push (`v*`)
- Build with `uv build`
- Publish via trusted publisher OIDC (no stored API tokens)
