# SPDX-License-Identifier: MIT
# Regular package rather than PEP 420 namespace because tests/fixtures/india.py
# is consumed by test_patterns.py via `from tests.fixtures import india`. With
# `pythonpath = ["packages/python-core", ...]` in the repo-root pyproject.toml,
# `import tests` resolves to THIS package's regular __init__.py before any
# PEP 420 namespace discovery, which means `tests.fixtures` is reachable under
# repo-root pytest (`pytest -q` from `/`). python-server's tests/ is kept as a
# PEP 420 namespace (no __init__.py) -- pytest's `--import-mode=importlib`
# loads its test files anonymously, so the absence of a regular-package
# `__init__.py` does not affect collection. See BILTIQ-002 reflect.html
# § test-harness for the diagnosis trail.
