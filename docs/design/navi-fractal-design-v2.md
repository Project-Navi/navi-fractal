# navi-fractal — Design Document

**Date:** 2026-03-01
**Status:** Draft
**Author:** Nelson Spence + Claude

---

## Overview

Extract the sandbox fractal dimension estimator from the Project Navi research codebase into a standalone Python library. The library provides audit-grade fractal dimension estimation for graphs — it will **refuse** to emit a dimension unless positive evidence of power-law scaling exists over a nontrivial scale range.

**Repo:** `~/GitHub/navi-fractal` (local only until validated)
**Remote:** `Project-Navi/navi-fractal` (after confidence in value and stability)

## Problem

Fractal dimension estimation on graphs is widely used in network science, neuroscience, and complexity research, but existing tools are either:

1. **Embedded in monolithic packages** (NetworkX plugins, MATLAB scripts) with heavy dependency trees
2. **Overconfident** — they emit dimension estimates without validating scaling regime quality, model discrimination, or curvature artifacts
3. **Non-reproducible** — nondeterministic center selection, no seeded RNG, no audit trail

navi-fractal takes the approach of a conservative instrument: it measures carefully, reports its uncertainty, and refuses to produce a number when the evidence doesn't support one.

## Positioning

This is not a utility library. It contains original methodology: the audit-grade quality gate framework, the "refuse to emit" philosophy, and the multi-guard approach to scaling regime validation. It exists to make that methodology verifiable by strangers via `pip install`.

## Scope: v0.1.0 vs v0.2.0

### v0.1.0 — "Sandbox Dimension Auditor"

Ship one estimator done perfectly:

- Graph construction and deterministic compilation
- BFS mass collection and diameter estimation
- Sandbox dimension estimation with full refusal chain
- Quality gates (inclusive and strict presets)
- Regression utilities (OLS, WLS, AICc, quadratic curvature)
- Bootstrap confidence intervals on chosen window
- Degree-preserving null model rewiring
- Helper constructors (grid, path)

### v0.2.0 — "Multifractal + Creative Determinant"

Each deserves its own test cycle and its own narrative:

- Multifractal spectrum D(q) estimation (Song et al. 2015 inspired, with audit modifications)
- Creative Determinant condition checking (CD theory as docs artifact, not embedded string)
- Multi-trajectory evaluation with alpha stability checks
- SymPy/LaTeX symbolic subpackage (optional dependency)
- `CITATION.cff` for academic citation

### Why this split

Sandbox dimension + refusal gates is a complete, defensible product. CD and multifractal each introduce their own correctness debates. Shipping the "refuses without evidence" narrative with one estimator done perfectly is stronger than three done 80%.

## Architecture (v0.1.0)

Single-concern Python library. Zero runtime dependencies — stdlib only.

```
navi-fractal/
  src/navi_fractal/
    __init__.py          # public API re-exports
    _types.py            # Reason enum, QualityGateReason enum, DimensionSummary, LinFit
    _graph.py            # Graph, CompiledGraph, compile_to_undirected_metric_graph
    _bfs.py              # BFS layer counts, mass computation, diameter estimation
    _regression.py       # LinFit, OLS, WLS, AICc, quadratic fit
    _sandbox.py          # estimate_sandbox_dimension, SandboxResult
    _quality_gate.py     # sandbox_quality_gate with inclusive/strict presets
    _null_model.py       # degree_preserving_rewire_undirected
    _radii.py            # auto_radii selection
    _helpers.py          # make_grid_graph, make_path_graph
    py.typed             # PEP 561 marker
  tests/
    test_graph.py            # construction, compilation, determinism
    test_bfs.py              # BFS correctness, mass accumulation
    test_regression.py       # OLS, WLS, AICc against known values
    test_sandbox.py          # estimation, refusal cases, known geometries
    test_quality_gates.py    # inclusive vs strict presets, parameter override
    test_null_model.py       # rewiring preserves degree sequence
    test_known_dimensions.py # grid (D≈2), path (D≈1), complete graph (refused)
    test_determinism.py      # identical results across runs with same seed
    test_benchmark.py        # performance on large graphs
  pyproject.toml
  LICENSE                    # Apache 2.0
  README.md
```

**Design principles:**

- Logic separated by concern: graph → BFS → regression → estimation → quality gate
- Internal modules prefixed with `_` — implementation details hidden
- Every estimation function returns a frozen dataclass with full audit trail
- `src/` layout prevents accidental imports of unbuilt code

## License

**Apache 2.0.**

This library contains original methodological contributions. Apache 2.0 is permissive and enterprise-friendly, but requires preservation of copyright notices and includes an explicit patent grant. Companies can use it freely; they cannot strip attribution.

## Public API (v0.1.0)

```python
from navi_fractal import (
    # Graph construction
    Graph,
    CompiledGraph,
    compile_to_undirected_metric_graph,
    make_grid_graph,
    make_path_graph,

    # Sandbox dimension
    estimate_sandbox_dimension,
    SandboxResult,
    DimensionSummary,
    Reason,
    LinFit,

    # Quality gates
    sandbox_quality_gate,
    QualityGateReason,

    # Null model
    degree_preserving_rewire_undirected,
)
```

### estimate_sandbox_dimension(g, *, seed, rng, n_centers, ...) → SandboxResult

Estimate the sandbox (mass–radius) fractal dimension D from ⟨M(r)⟩ ~ r^D. Returns a frozen dataclass containing the dimension estimate (or None if refused), the full diagnostic chain, and all intermediate data needed to reproduce or challenge the result.

**Key parameters (all named, all documented, all with good defaults):**

| Parameter | Default | What it controls |
|-----------|---------|------------------|
| `seed` | `0` | Deterministic RNG for center selection |
| `rng` | `None` | Optional `random.Random` instance; if provided, overrides `seed` (for Monte Carlo pipelines that manage their own RNG streams) |
| `n_centers` | `256` | Number of random BFS origins |
| `component_policy` | `"giant"` | Restrict to largest connected component, or `"all"` |
| `mean_mode` | `"geometric"` | How to aggregate mass across centers |
| `min_points` | `6` | Minimum number of radii in a scaling window |
| `min_radius_ratio` | `3.0` | Minimum ratio r_max/r_min in scaling window (internally converted to ln-span) |
| `r2_min` | `0.85` | Minimum R² to accept a scaling window |
| `min_delta_y` | `0.5` | Minimum response range in log-mass |
| `max_saturation_frac` | `0.2` | Mass saturation cutoff (fraction of N) |
| `delta_power_win` | `1.5` | Minimum ΔAICc for power-law over exponential |
| `require_positive_slope` | `True` | Reject negative dimension estimates |
| `use_wls` | `True` | Weighted least squares |
| `curvature_guard` | `True` | Reject windows where quadratic log-log fits better |
| `slope_stability_guard` | `False` | Reject windows with high local slope dispersion (see below) |
| `slope_stability_sub_len` | `None` (= `min_points`) | Sub-window length for local slope computation |
| `max_slope_range` | `0.5` | Maximum allowed range of local slopes within a window |
| `bootstrap_reps` | `0` | Bootstrap replicates for confidence intervals |

**Slope stability guard definition:** For a candidate window of length L, compute OLS (or WLS) slope on every contiguous sub-window of length `slope_stability_sub_len`. Collect all local slopes. `window_slope_range = max(local_slopes) - min(local_slopes)`. Refuse if `window_slope_range > max_slope_range`. This detects windows where dimension appears stable overall but is locally inconsistent — a sign of coincidental rather than genuine scaling.

These parameters are the answer to "what counts as evidence?" Every threshold is explicit, named, and overridable.

**What is a "nontrivial scale range"?** Operationally: the scaling window must span at least `min_radius_ratio` (default 3×) in radius. A 3× range means the power-law fit is tested over nearly half an order of magnitude — enough to distinguish genuine scaling from local coincidence.

**Refusal reasons (dimension=None):**

`Reason` is a Python `enum.Enum`. Match on it programmatically. `reason_detail: str | None` carries human-readable context (e.g., `"R²=0.82 < 0.85 on best window [3, 12]"`). Downstream code matches on `reason`, never on `reason_detail`.

| `reason` code | When |
|---------------|------|
| `ACCEPTED` | Credible scaling window found |
| `EMPTY_GRAPH` | Graph has 0 nodes |
| `TRIVIAL_GRAPH` | Selected graph has < 2 nodes after applying `component_policy` |
| `GIANT_COMPONENT_TOO_SMALL` | `component_policy="giant"` and giant component has < 2 nodes while total ≥ 2 (detail includes `giant=N, total=M`) |
| `NO_VALID_RADII` | Insufficient non-degenerate, non-saturated radii |
| `NO_WINDOW_PASSES_R2` | No contiguous window meets R² threshold |
| `AICC_PREFERS_EXPONENTIAL` | ΔAICc < `delta_power_win`, i.e., power-law not preferred by sufficient margin |
| `CURVATURE_GUARD` | Quadratic log-log fits significantly better |
| `SLOPE_STABILITY_GUARD` | Local slope dispersion exceeds threshold |
| `NEGATIVE_SLOPE` | `require_positive_slope=True` and best window has slope ≤ 0 (includes zero) |

`reason_detail: str | None` carries human-readable context (e.g., `"R²=0.82 < 0.85 on best window [3, 12]"`). Downstream code matches on `reason`, never on `reason_detail`.

Every refusal includes a machine-readable reason code and optional detail string.

**Acceptance contract is binary:** `dimension is not None` means accepted; `dimension is None` means refused. There is no third state. The estimator never returns a dimension it doesn't stand behind. If a future need arises for "computed but questionable," that lives in `SandboxResult` internals (e.g., `_candidate_dimension`), never in the public contract.

**Strict mode** is achieved by tightening parameters:

```python
result = estimate_sandbox_dimension(
    g, seed=42,
    r2_min=0.95,
    delta_power_win=2.0,
    slope_stability_guard=True,
    max_slope_range=0.2,
    bootstrap_reps=200,
)
```

### sandbox_quality_gate(res, *, preset) → (bool, QualityGateReason, str | None)

Post-hoc acceptance **policy**, separate from the estimator's acceptance decision.

**Two-level contract:**

- **Estimator acceptance** (`dimension is not None`): A credible scaling regime exists under the estimator's configured thresholds. This is a measurement statement: "the data supports a power-law fit in this window." Uses `Reason` enum.
- **Quality gate acceptance**: A policy decision about whether the estimate is strong enough for a given use case. The quality gate can reject an estimate that the estimator accepted. It never accepts an estimate the estimator refused. Uses its own `QualityGateReason` enum — never reuses `Reason`.

This separation matters because the same measurement might be good enough for exploratory analysis but not for a publication figure. Keeping the enums distinct prevents users from confusing "the instrument couldn't measure" with "the measurement wasn't good enough for your policy."

**QualityGateReason codes:**

| Code | When |
|------|------|
| `PASSED` | Estimate meets all policy thresholds |
| `NOT_ACCEPTED` | Estimator refused (dimension is None) — gate doesn't override |
| `R2_TOO_LOW` | R² below preset minimum |
| `STDERR_TOO_HIGH` | Slope stderr above preset maximum |
| `RADIUS_RATIO_TOO_SMALL` | Scaling window too narrow |
| `AICC_MARGIN_TOO_SMALL` | ΔAICc below preset minimum |

Returns `(passed: bool, reason: QualityGateReason, detail: str | None)`.

**Presets:**

| Preset | R² min | Slope stderr max | Radius ratio min | ΔAICc min |
|--------|--------|------------------|------------------|-----------|
| `"inclusive"` | 0.85 | 0.50 | 3.0 | 1.5 |
| `"strict"` | 0.95 | 0.20 | 4.0 | 3.0 |

All thresholds overridable via keyword arguments.

### SandboxResult (frozen dataclass) — two-tier access

The result type is designed for two audiences: researchers who want the full audit trail, and application developers who want a quick answer.

**Tier 1 — Quick access:**

```python
# Convenience method for applications that just need the answer
result.summary()  # → DimensionSummary(dimension, accepted, reason, r2, ci)
```

`DimensionSummary` is a lightweight frozen dataclass with exactly five fields:

| Field | Type | Description |
|-------|------|-------------|
| `dimension` | `float \| None` | The estimate, or None if refused |
| `accepted` | `bool` | True iff dimension is not None |
| `reason` | `Reason` | Enum code (ACCEPTED or refusal reason) |
| `r2` | `float \| None` | R² of power-law fit (None if refused) |
| `ci` | `tuple[float, float] \| None` | 95% bootstrap CI (None if not computed) |

This is the stable public contract for downstream code. It will not grow. Notably, `reason_detail` is excluded — it lives only in the full `SandboxResult` to prevent downstream code from depending on human-readable prose.

**Tier 2 — Full audit trail:**

The `SandboxResult` itself carries everything needed to reproduce or challenge the conclusion:

- `dimension: Optional[float]` — the estimate, or None if refused
- `reason: Reason` — enum code (see Refusal reasons table)
- `reason_detail: str | None` — human-readable context for the decision
- `model_preference: Literal["powerlaw", "none"]` — which model was selected (typed as `Literal` in `_types.py`, not bare `str`)
- `delta_aicc: Optional[float]` — power-law vs exponential evidence margin
- `powerlaw_fit: Optional[LinFit]` — full regression diagnostics
- `exponential_fit: Optional[LinFit]` — alternative model fit
- `window_r_min, window_r_max` — scaling window bounds
- `window_log_span, window_delta_y` — window quality metrics (log-span in ln units; divide by ln(r_max/r_min) to recover ratio)
- `window_slope_range` — slope stability diagnostic (if guard enabled)
- `window_aicc_quad_minus_lin` — curvature diagnostic
- `dimension_ci: Optional[Tuple[float, float]]` — 95% bootstrap CI
- `radii_eval, mean_mass_eval, y_eval` — raw data for plotting
- `n_nodes_original, n_nodes_measured, retained_fraction` — component selection audit
- `n_centers, seed, notes` — reproducibility metadata

Every field is documented. Nothing is hidden.

### degree_preserving_rewire_undirected(g, *, n_swaps, seed, rng) → Graph

Maslov-Sneppen rewiring that preserves exact degree sequence while destroying higher-order structure. Essential for validating that measured fractal properties reflect genuine structure, not degree distribution artifacts.

- Deterministic (seeded RNG)
- Optional degree verification post-rewiring
- Returns a new Graph (input unchanged)

## Pipeline: How Estimation Works

1. **Compile** input Graph to deterministic undirected metric graph (insertion-order node IDs, sorted integer adjacency)
2. **Component selection** — optionally restrict to giant connected component
3. **Diameter estimation** — two-sweep BFS heuristic
4. **Radii selection** — dense prefix + log-spaced tail, capped at configurable fraction of diameter
5. **BFS mass collection** — for each seeded random center, compute cumulative ball sizes M(r) at each radius
6. **Moment aggregation** — geometric or arithmetic mean across centers, with per-radius variance for WLS weights
7. **Window search** — exhaustive search over contiguous radius windows, applying all filters and guards:
   - Degeneracy filter (M ≤ 1)
   - Saturation filter (M ≥ fraction of N)
   - Minimum radius ratio and response range
   - R² threshold
   - Power-law vs exponential model discrimination via ΔAICc
   - Curvature guard: reject if quadratic log-log fits significantly better
   - Slope stability guard: reject if local slope dispersion exceeds threshold
   - Score surviving windows by (span, R², -stderr) — prefer widest credible window
8. **Bootstrap** — resample centers on the chosen window for 95% confidence intervals
9. **Return** full diagnostic dataclass, or refusal with reason

## Graph Implementation

The library includes its own lightweight graph container rather than depending on NetworkX:

- `Graph` — input container with set-based adjacency for convenient construction
- `CompiledGraph` — frozen dataclass with sorted integer adjacency tuples for deterministic traversal
- `compile_to_undirected_metric_graph()` — the compilation step that guarantees reproducibility

**Why not NetworkX?** Zero dependencies is the priority. The graph operations needed (BFS, component detection, diameter estimation, rewiring) are straightforward in stdlib Python. The compiled graph representation guarantees deterministic results.

## Regression and Model Selection

All regression is implemented from scratch (stdlib only):

- **OLS** — ordinary least squares with R², slope stderr, SSE
- **WLS** — weighted least squares with delta-method variance propagation
- **AICc** — corrected Akaike information criterion for small samples
- **Quadratic fit** — for curvature guard (3×3 Gaussian elimination)

The power-law vs exponential discrimination via ΔAICc on the same window is the key differentiator. Most tools fit power-law and report R² without asking whether an exponential fits just as well.

**Competing model forms (both fitted on the same window of radii):**

- Power law: `log M(r) = a + D · log r` — linear in log-log space, slope = dimension
- Exponential: `log M(r) = a + b · r` — linear in semi-log space (i.e., M grows as exp(br))

ΔAICc = AICc_exponential − AICc_powerlaw. Positive values favor power-law. The estimator requires ΔAICc ≥ `delta_power_win` to accept.

## Determinism

The library is designed for reproducibility:

- Graph compilation produces sorted integer adjacency from insertion order
- BFS traversal is deterministic on compiled graphs
- Center selection uses seeded `random.Random` (not global state)
- Float accumulation follows consistent ordering within each function

**Claim — two tiers:**

1. **Field-level determinism (guaranteed):** Given the same Python version and seed, the library produces identical structural fields: same `window_i`/`window_j`, same `radii_eval`, same `model_preference`, same `reason` enum value, same `n_centers`. Integer, boolean, and enum fields are exact.
2. **Float-level determinism (best effort):** Floating-point fields (`dimension`, `r2`, `slope_stderr`, etc.) are deterministic on the same platform. Cross-platform, they may differ at the ULP level due to float summation order and FPU behavior. Not guaranteed bit-identical.

**CI strategy:** Define two tolerance constants:

- `FLOAT_ATOL_SAME_PLATFORM = 1e-12` — for same-OS, same-Python tests
- `FLOAT_ATOL_CROSS_PLATFORM = 1e-9` — for CI matrix across Linux/macOS/Windows

Assert structural field equality exactly. Assert float fields within the appropriate tolerance. Validate across Python 3.12+ on Linux, macOS, Windows.

## Test Strategy

### 1. Known geometry tests (test_known_dimensions.py)

| Graph | Expected D | Acceptance |
|-------|-----------|------------|
| Grid 30×30 | ≈ 2.0 | D ∈ [1.8, 2.2], R² > 0.95, reason=`ACCEPTED` |
| Path 100 | ≈ 1.0 | D ∈ [0.8, 1.2], reason=`ACCEPTED` |
| Complete K₅₀ | refused | dimension is None, reason ∈ {`NO_VALID_RADII`, `NO_WINDOW_PASSES_R2`} |
| Star S₅₀ | refused | dimension is None |
| Rewired grid (50×50) | changed | D differs, OR reason changes, OR ΔAICc collapses |

### 2. Refusal path coverage (test_sandbox.py)

Every reason code must be exercised by at least one test:

- `EMPTY_GRAPH` — empty graph input
- `TRIVIAL_GRAPH` — single-node graph with `component_policy="all"`
- `GIANT_COMPONENT_TOO_SMALL` — dust cloud graph with `component_policy="giant"` (many tiny components, giant < 2 nodes, total ≥ 2)
- `NO_VALID_RADII` — all radii degenerate or saturated
- `NO_WINDOW_PASSES_R2` — graph with noisy scaling
- `AICC_PREFERS_EXPONENTIAL` — exponential growth graph
- `CURVATURE_GUARD` — graph with log-log curvature
- `SLOPE_STABILITY_GUARD` — graph with unstable local slopes
- `NEGATIVE_SLOPE` — contrived graph with decreasing mass

Each test asserts `dimension is None`, correct `reason` code, and that `reason_detail` contains relevant diagnostics.

### 3. Determinism tests (test_determinism.py)

Run `estimate_sandbox_dimension()` twice with identical parameters:

- Structural fields must be exactly equal: `window_i`, `window_j`, `radii_eval`, `model_preference`, `reason`, `n_centers`
- Float fields must match within `FLOAT_ATOL_SAME_PLATFORM` (1e-12) on same platform; `FLOAT_ATOL_CROSS_PLATFORM` (1e-9) in CI matrix: `dimension`, `powerlaw_fit.r2`, `powerlaw_fit.slope_stderr`

### 4. Quality gate tests (test_quality_gates.py)

- Inclusive preset accepts known good results (`QualityGateReason.PASSED`)
- Strict preset rejects marginal results that inclusive accepts (correct `QualityGateReason` code)
- Estimate refused by estimator → gate returns `QualityGateReason.NOT_ACCEPTED`
- Parameter overrides work as documented
- Detail strings contain relevant threshold values

### 5. Null model tests (test_null_model.py)

- Degree sequence preserved exactly after rewiring (hard invariant)
- On a sufficiently large graph (grid ≥ 50×50), rewiring produces measurable degradation in at least one of:
  - Dimension estimate differs by > tolerance
  - Reason code changes (e.g., `ACCEPTED` → `NO_WINDOW_PASSES_R2`)
  - ΔAICc drops below `delta_power_win`
  - Window log-span shrinks (scaling regime contracts)
  - R² drops below `r2_min` on the same window
- Deterministic with same seed
- Small graph caveat: rewiring a path or small grid may not produce meaningful structural change — tests acknowledge this and use large enough graphs

### 6. Regression tests (test_regression.py)

- OLS against hand-computed values
- WLS with known weights against hand-computed values
- AICc ordering matches known model preferences
- Quadratic fit SSE against known values

### 7. Benchmarks (test_benchmark.py)

| Graph | Nodes | Target |
|-------|-------|--------|
| Grid 30×30 | 900 | < 1s |
| Grid 100×100 | 10,000 | < 10s |
| Grid 300×300 | 90,000 | < 60s (stretch) |

pytest-benchmark with `benchmark.pedantic()` for reproducible timing.

## Known Limitations (v0.1.0)

1. **Sandbox dimension only.** Multifractal spectrum and Creative Determinant are deferred to v0.2.0. This is intentional — one estimator done perfectly.

2. **Stdlib-only BFS is slower than compiled alternatives.** For graphs above ~100K nodes, performance may be a concern. A future Cython/Rust extension path is possible without changing the API.

3. **Graph container is minimal.** No weighted edges, no directed dimension estimation, no hypergraph support. Covers the core use case (unweighted undirected graphs) cleanly.

4. **WLS variance uses delta method approximation.** For arithmetic mean mode, variance of mean mass is propagated via delta method. Includes a configurable variance floor to prevent zero-weight pathologies.

5. **No symbolic/LaTeX export in v0.1.0.** Deferred to v0.2.0 with optional SymPy dependency.

## Packaging

- **Version:** 0.1.0
- **Python:** >= 3.12 (policy: modern typing and performance features, keeps codebase small)
- **Runtime dependencies:** none
- **Dev dependencies:** pytest, pytest-benchmark, ruff, mypy
- **Build system:** hatchling
- **Type checking:** py.typed marker (PEP 561), mypy strict mode
- **License:** Apache 2.0

## README Strategy

Code first, explanation second. Same pattern as navi-sanitize:

```python
from navi_fractal import estimate_sandbox_dimension, make_grid_graph

grid = make_grid_graph(30, 30)
result = estimate_sandbox_dimension(grid, seed=42, n_centers=256)

if result.dimension:
    print(f"D = {result.dimension:.3f}")
    print(f"R² = {result.powerlaw_fit.r2:.4f}")
    print(f"Window: r ∈ [{result.window_r_min}, {result.window_r_max}]")
    if result.dimension_ci:
        print(f"95% CI: {result.dimension_ci}")
else:
    print(f"Refused: {result.reason.name}")
    if result.reason_detail:
        print(f"  Detail: {result.reason_detail}")
```

Then: Why (the problem with overconfident tools), How it decides (pipeline summary), Quality gates table, Null model example, Known limitations, Benchmarks, License.

## Post-Publication Narrative

> "Most fractal analysis tools will always give you a number. Mine won't. If the evidence doesn't support a dimension estimate, navi-fractal says 'refused' and shows you exactly why."

The body of work:

1. **navi-sanitize** — "this person understands input boundaries"
2. **navi-fractal** — "this person understands measurement, and is honest about what it can't prove"
3. (v0.2.0) **navi-fractal + CD** — "here's the theory connecting structure to navigability"
4. (future) **navi-dsc** — "here's the full framework those pieces fit into"

## v0.2.0 Roadmap (Not Designed Yet)

Deferred for separate design review:

- Multifractal spectrum D(q) — "Inspired by Song et al. (2015), with modifications for audit gates and determinism"
- Creative Determinant condition — CD theory as `docs/` artifact, not embedded string; `get_cd_theorem_text()` accessor
- Multi-trajectory evaluation with alpha stability
- SymPy/LaTeX symbolic subpackage (optional `navi-fractal[symbolic]` extra)
- `CITATION.cff` for machine-readable academic citation
