# Contributing to navi-fractal

## Setup

```bash
git clone https://github.com/Project-Navi/navi-fractal.git
cd navi-fractal
uv sync --group dev
```

## Development commands

```bash
uv run pytest                # tests
uv run ruff check            # lint
uv run ruff format --check   # format check
uv run mypy src/             # type check (strict)
uv run bandit -r src/        # security scan
```

All five must pass before merging.

## Pull request expectations

- Tests pass, no new warnings
- ruff clean (lint + format)
- mypy strict clean
- If you changed estimation logic, re-run `uv run python scripts/calibrate.py` and verify the calibration baseline hasn't regressed unexpectedly

## Code style

- ruff enforces formatting and lint rules (see `pyproject.toml`)
- mypy strict mode — all public functions need type annotations
- 100-character line limit

## Calibration baseline

The file `scripts/calibration-report.json` is the structured calibration baseline. If your changes affect dimension estimates, regenerate it:

```bash
uv run python scripts/calibrate.py
```

Compare the new report against the previous version. Document any changes in your PR description.
