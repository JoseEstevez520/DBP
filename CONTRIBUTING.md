# Contributing to DBP

## Dev environment

```bash
git clone <repo>
cd DBP
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -e ".[test]"
```

## Running tests

```bash
pytest tests/ -v
```

## Code style

- **PEP 8** for all Python code.
- **Type hints** everywhere — every function signature must be annotated. Use `from __future__ import annotations` in every module.
- Line length: 88 characters (soft), 99 (hard).
- Use `black` and `ruff` if available, but consistency matters more than tooling.

## Pull request process

1. **Spec change first** — if the change affects the protocol, update the spec before touching code.
2. **Implementation** — write the code in `src/dbp/`.
3. **Tests** — every new feature must have tests in `tests/`. Run `pytest tests/ -v` and confirm all pass.
4. **Demo** — if the change is user-visible, add or update a scenario in `demo/`.
5. Open a PR with a clear description linking back to a GitHub issue.

## How to add a new policy

1. Add the policy value to the `Policy` enum in `src/dbp/primitives.py` (e.g. `Policy.MAJORITY`).
2. Add the matching branch in `Boundary.check()` in `src/dbp/boundary.py`.
3. Add tests in `tests/test_boundary.py` covering PASS and BLOCK cases.
4. Update the spec at `spec/`.

## How to add a new transport

1. Create `src/dbp/transport/<name>.py`.
2. Subclass `Transport` from `src/dbp/transport/base.py`.
3. Implement `send()` and `receive()` — both must call `self.boundary.check()` before delivery.
4. Export the new class from `src/dbp/transport/__init__.py`.
5. Add tests in `tests/test_transport_<name>.py`.
6. If the transport uses a wire format (headers, file layout, etc.), document it in the spec at `spec/transport-<name>.md`.
