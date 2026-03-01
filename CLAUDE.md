# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

navi-fractal is a standalone, zero-dependency Python library for audit-grade fractal dimension estimation on graphs. It provides sandbox (mass-radius) dimension estimation with quality gates that refuse to emit a dimension unless positive evidence of power-law scaling exists. Python 3.12+, stdlib only.

## Commands

```bash
# Install dev dependencies
uv sync

# Run tests (disable benchmarks for speed)
uv run pytest tests/ -v --benchmark-disable

# Run a single test file
uv run pytest tests/test_sandbox.py -v --benchmark-disable

# Run a single test
uv run pytest tests/test_sandbox.py::test_name -v --benchmark-disable

# Run benchmarks
uv run pytest tests/test_benchmark.py -v

# Lint and format
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Type check
uv run mypy --strict src/navi_fractal/

# Security scan
uv run bandit -r src/ -c pyproject.toml

# Build wheel
uv build

# Pre-commit setup (one-time)
pre-commit install

# Run all pre-commit hooks
pre-commit run --all-files
```

## CI

GitHub Actions runs on push to `main` and all PRs. Five parallel jobs:

- **lint** — `ruff check` + `ruff format --check`
- **typecheck** — `mypy --strict src/navi_fractal/`
- **test** — pytest across Python 3.12 + 3.13, `--benchmark-disable`
- **security** — `pip-audit` + `bandit`
- **build** — gates on all four above; builds wheel, smoke-tests public API, uploads artifact

Benchmarks run via manual dispatch only.

## Architecture

Uses `src/` layout (`src/navi_fractal/`). Internal modules prefixed with `_`.

### Public API (`__init__.py`)

Core exports (v0.1.0):
- `Graph` — input container with set-based adjacency
- `CompiledGraph` — frozen, deterministic adjacency for reproducible traversal
- `compile_to_undirected_metric_graph()` — compilation step
- `make_grid_graph()` — helper constructor
- `estimate_sandbox_dimension()` → `SandboxResult`
- `sandbox_quality_gate()` — post-hoc acceptance policy
- `LinFit` — linear fit result dataclass
- `degree_preserving_rewire_undirected()` — null model

### Module Layout

- `_graph.py` — `Graph`, `CompiledGraph`, compiler, helper constructors
- `_bfs.py` — BFS layer counts, mass computation, diameter estimation
- `_regression.py` — `LinFit`, OLS, WLS, AICc, quadratic fit
- `_sandbox.py` — `estimate_sandbox_dimension()`, `SandboxResult`, quality gates
- `_null_model.py` — degree-preserving Maslov-Sneppen rewiring
- `_radii.py` — automatic radius selection (dense prefix + log-spaced tail)

### Pipeline

1. **Compile** input graph to deterministic undirected metric graph
2. **Component selection** — optionally restrict to giant connected component
3. **Diameter estimation** — two-sweep BFS heuristic
4. **Radii selection** — dense prefix + log-spaced tail, capped at 30% of diameter
5. **BFS mass collection** — seeded random centers, ball sizes M(r) at each radius
6. **Moment aggregation** — geometric or arithmetic mean across centers
7. **Window search** — exhaustive over contiguous radius windows with quality gates
8. **Bootstrap** — resample centers for confidence intervals
9. **Return** full diagnostic dataclass or refusal with reason

### Refusal reasons (dimension=None)

- Empty or trivial graph
- Insufficient non-degenerate, non-saturated radii
- No window passes R² threshold
- Power-law not preferred over exponential by AICc margin
- Curvature guard triggered
- Slope stability guard triggered

Every refusal includes a machine-readable `reason` string.

## Conventions

- **Conventional commits:** `feat:`, `fix:`, `test:`, `chore:`, `docs:`
- **Line length:** 100 (ruff + mypy strict)
- **TDD:** write failing test -> implement -> verify -> commit
- **`NullHandler` on library logger** — app configures handlers, not the library
- **All estimation functions return frozen dataclasses** with full audit trail
- **Deterministic given same seed and Python version** — compiled graph guarantees traversal order
- **No remote push** without explicit approval — local only until told otherwise

## Gotchas

- **`random` module used for center selection** — `S311` (ruff) and `B311` (bandit) are suppressed; this is not security-sensitive randomness
- **pytest-benchmark `pedantic()`** required for large graphs — standard mode runs too many iterations
- **No CLI, no config files, no framework dependencies** — this is a library only
- **Float precision** — regression results are deterministic for a given Python version but not guaranteed bit-identical across platforms
