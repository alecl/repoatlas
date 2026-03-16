# Manual Tests

Reference implementations showing how to use `codetools` file-discovery and merge functionality.

## Important

These scripts are **not runnable as-is** — edit the placeholder paths in each script to point at a real project before running.

They are not part of the automated test suite or production package. There is no `__init__.py` by design.

## Running

From the repo root:

```bash
uv run --frozen --exclude-newer <date> python app/manual_tests/codegroupanalyze.py
uv run --frozen --exclude-newer <date> python app/manual_tests/codemerge.py
```

These scripts use absolute imports (`from app.src.codetools...`) that resolve via uv's project-aware `sys.path`.
