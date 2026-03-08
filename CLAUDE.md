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

# Run calibration (quick mode skips 3 slow flower generations)
uv run python scripts/calibrate.py --quick

# Run full calibration (all 19 graphs, ~14s)
uv run python scripts/calibrate.py
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
- `_bfs.py` — BFS layer counts + prefix-sum mass computation, diameter estimation
- `_regression.py` — `LinFit`, OLS, WLS, AICc, quadratic fit
- `_sandbox.py` — `estimate_sandbox_dimension()`, `SandboxResult`, quality gates
- `_null_model.py` — degree-preserving Maslov-Sneppen rewiring
- `_radii.py` — automatic radius selection (dense prefix + log-spaced tail)
- `_types.py` — shared types: `Reason`, `LinFit`, `DimensionSummary`, `ModelPreference`

### Pipeline

1. **Compile** input graph to deterministic undirected metric graph
2. **Component selection** — optionally restrict to giant connected component
3. **Diameter estimation** — two-sweep BFS heuristic
4. **Radii selection** — dense prefix + log-spaced tail, capped at 30% of diameter
5. **BFS mass collection** — seeded random centers, layer counts + prefix sums for M(r)
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

## Operational Standards

### Before every commit

1. **Tests pass**: `uv run pytest tests/ -v --benchmark-disable` — all green, no skips
2. **Lint clean**: `uv run ruff check src/ tests/` — zero warnings
3. **Format clean**: `uv run ruff format --check src/ tests/` — zero diffs
4. **Types clean**: `uv run mypy --strict src/navi_fractal/` — zero errors
5. **Calibration holds**: `uv run python scripts/calibrate.py --quick` — all v4-nf deltas within ±0.005

If any gate fails, fix before committing. Do not use `--no-verify` or skip hooks.

### Before any numerical change

Any change to BFS, regression, window search, or quality gate logic must be validated against the calibration instrument. The calibration table is the ground truth for "did I break the math." Run `scripts/calibrate.py --quick` (16 graphs, ~2s) at minimum, full run (19 graphs, ~14s) for anything touching BFS or radii.

### Test discipline

- **TDD**: write failing test → implement → verify → commit
- **Unit tests**: one behavior per test, descriptive name, no setup sharing between tests
- **Integration tests**: v4_smoke/ validates against the reference implementation
- **Calibration**: scripts/calibrate.py is the numerical validation instrument — it is not a test suite, it is a measurement audit
- **Never weaken a test to make it pass** — if a test fails, either the code is wrong or the test expectation needs updating with justification

### Code hygiene

- **No dead code** — delete it, don't comment it out
- **No TODO/FIXME without an issue** — if it's worth noting, it's worth tracking
- **Internal modules prefixed with `_`** — the public API is `__init__.py`, everything else is private
- **Frozen dataclasses for all results** — immutability is a correctness guarantee
- **Deterministic outputs** — given the same seed and Python version, every function produces identical results
- **No silent fallbacks** — if something fails, refuse explicitly with a reason code

### Git discipline

- **Conventional commits**: `feat:`, `fix:`, `test:`, `perf:`, `chore:`, `docs:`, `build:`
- **Atomic commits**: one logical change per commit, never mix refactors with features
- **No force push to main** — ever
- **No remote push without explicit approval** — local only until told otherwise
- **Co-author line**: `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`
- **Branch naming**: `feat/`, `fix/`, `perf/`, `docs/` prefixes

### Documentation

- **Docs site**: Zensical-powered, GitHub Pages deployment
- **Brand**: Project Navi brand guide (see `Project-Navi/brand` repo)
- **CSS**: `docs/stylesheets/navi.css` — shared brand stylesheet, do not edit per-page
- **MathJax**: enabled via arithmatex + `docs/javascripts/mathjax.js` — use `\( \)` for inline, `\[ \]` for display math
- **Diataxis**: tutorials (getting-started/), how-to (how-to/), explanation (explanation/), reference (reference/)

## Conventions

- **Line length:** 100 (ruff + mypy strict)
- **`NullHandler` on library logger** — app configures handlers, not the library
- **All estimation functions return frozen dataclasses** with full audit trail
- **Deterministic given same seed and Python version** — compiled graph guarantees traversal order
- **Copyright headers**: `# Copyright 2024-2026 Nelson Spence` + `# SPDX-License-Identifier: Apache-2.0` on every .py file

## Gotchas

- **`random` module used for center selection** — `S311` (ruff) and `B311` (bandit) are suppressed; this is not security-sensitive randomness
- **pytest-benchmark `pedantic()`** required for large graphs — standard mode runs too many iterations
- **No CLI, no config files, no framework dependencies** — this is a library only
- **Float precision** — regression results are deterministic for a given Python version but not guaranteed bit-identical across platforms
- **BFS performance** — pure Python BFS is the bottleneck on large graphs (>10K nodes). The layer-count algorithm is correct; the interpreter overhead is the constraint. Rust extension planned for v0.2.0.

## Calibration Instrument

The calibration script (`scripts/calibrate.py`) is the primary validation tool for numerical correctness. It runs navi-fractal side-by-side with the v4 reference implementation on (u,v)-flower networks with analytically known dimensions.

- **Quick mode** (`--quick`): 16 graphs, ~2s — sufficient for most changes
- **Full mode**: 19 graphs including gen 7+8 for (2,2)-flower and gen 6 for (2,3)-flower, ~14s
- **Output**: `scripts/calibration-report.json` — committed baseline, diffable across changes
- **Tolerance**: v4-nf delta within ±0.005 across all emit cases
- **Known characteristic**: (2,2)-flower gen 7→8 shows non-monotonic convergence (gap reversal from -6.0% to -9.5%). This is a measurement characteristic, not a bug — different window selections at different scales.
