## Pytest Configuration

You might want to add markers to pytest.ini:
```
markers =
    core: Basic functionality tests
    integration: Integration tests with real files  
    slow: Slow-running tests
    resolver: Resolver-specific tests
```
Then mark tests accordingly:

```python
python@pytest.mark.integration
class TestRealJavaFiles:
    # ...
```

And run with:
```bash
pytest -m "not slow"  # Skip slow tests
pytest -m integration  # Run only integration tests

# only codeanalyzer tests
pytest app/tests/integration/codeanalyzer/ app/tests/unit/codeanalyzer

# add -vv before or after path names for more verbose output (no truncating on assert values and including assert value prints at end summary too)

# to see missing line coverage in test output add --cov-report term-missing 
# to see missing line coverage in an HTML report add --cov-report html ; open htmlcov/index.html
```
