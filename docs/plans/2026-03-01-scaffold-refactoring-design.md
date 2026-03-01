# Scaffold Refactoring — Design Document

**Date:** 2026-03-01
**Status:** Approved
**Purpose:** Align v0.1.0 scaffold with navi-fractal-design-v2 spec before implementation

---

## Problem

The current scaffold uses bare strings for refusal reasons, embeds quality gate logic in
`_sandbox.py`, and has parameter names that don't match the design spec. These structural
mismatches will compound during implementation. Fix them in one clean pass.

## Approach

Bottom-up refactoring. Create `_types.py` first (no internal deps), then migrate each module
in dependency order. Each step produces a green commit.

## Steps

### 1. Create `_types.py`

New module containing all shared types:

- `Reason` enum — 10 members: `ACCEPTED`, `EMPTY_GRAPH`, `TRIVIAL_GRAPH`,
  `GIANT_COMPONENT_TOO_SMALL`, `NO_VALID_RADII`, `NO_WINDOW_PASSES_R2`,
  `AICC_PREFERS_EXPONENTIAL`, `CURVATURE_GUARD`, `SLOPE_STABILITY_GUARD`, `NEGATIVE_SLOPE`
- `QualityGateReason` enum — 6 members: `PASSED`, `NOT_ACCEPTED`, `R2_TOO_LOW`,
  `STDERR_TOO_HIGH`, `RADIUS_RATIO_TOO_SMALL`, `AICC_MARGIN_TOO_SMALL`
- `DimensionSummary` frozen dataclass — 5 fields: `dimension`, `accepted`, `reason`, `r2`, `ci`
- `LinFit` frozen dataclass — moved from `_regression.py` (shared type, not regression-specific)

### 2. Update `_regression.py`

- Remove `LinFit` definition
- Import `LinFit` from `_types`
- No logic changes

### 3. Create `_helpers.py`

- Move `make_grid_graph` from `_graph.py`
- Add `make_path_graph(n: int) -> Graph`
- Both import `Graph` from `_graph`

### 4. Refactor `_sandbox.py`

**Type changes:**
- `SandboxResult.reason: str` → `SandboxResult.reason: Reason`
- Add `SandboxResult.reason_detail: str | None`
- Add `SandboxResult.summary() -> DimensionSummary`
- All hardcoded reason strings → `Reason` enum members
- Import `Reason`, `LinFit`, `DimensionSummary` from `_types`

**Parameter renames (with semantic changes noted):**

| Current | Spec | Change |
|---------|------|--------|
| `delta_aicc_min` | `delta_power_win` | Rename only |
| `min_window_points` | `min_points` | Rename only |
| `min_log_span` | `min_radius_ratio` | Semantic: ratio (default 3.0) → internally convert to ln-span |
| `saturation_fraction` | `max_saturation_frac` | Rename only |
| `slope_stability_max_cv` | `max_slope_range` | Semantic: range of sub-window slopes, not CV |
| `bootstrap_reps` default | 200 → 0 | Default change (opt-in) |
| (new) `min_delta_y` | 0.5 | New param — minimum response range in log-mass |
| (new) `require_positive_slope` | True | New param — reject slope ≤ 0 |
| (new) `rng` | None | New param — optional `random.Random` override |

**New refusal path:** `NEGATIVE_SLOPE` check (when `require_positive_slope=True` and best
window slope ≤ 0).

**Extract:** `sandbox_quality_gate` removed from this module → `_quality_gate.py`.

### 5. Create `_quality_gate.py`

- `sandbox_quality_gate(result, *, preset) -> (bool, QualityGateReason, str | None)`
- Return type changes from `tuple[bool, str]` to `tuple[bool, QualityGateReason, str | None]`
- Presets expanded per spec:

| Preset | R² min | stderr max | radius ratio min | ΔAICc min |
|--------|--------|------------|------------------|-----------|
| `"inclusive"` | 0.85 | 0.50 | 3.0 | 1.5 |
| `"strict"` | 0.95 | 0.20 | 4.0 | 3.0 |

- All thresholds overridable via keyword arguments

### 6. Update `__init__.py`

Target exports (14 symbols):
```
CompiledGraph, Graph, compile_to_undirected_metric_graph     # _graph
make_grid_graph, make_path_graph                              # _helpers
estimate_sandbox_dimension, SandboxResult                     # _sandbox
sandbox_quality_gate                                          # _quality_gate
degree_preserving_rewire_undirected                           # _null_model
Reason, QualityGateReason, DimensionSummary, LinFit          # _types
```

### 7. Update all tests

- `result.reason == "accepted"` → `result.reason == Reason.ACCEPTED`
- `"empty" in result.reason` → `result.reason == Reason.EMPTY_GRAPH`
- Quality gate returns → unpack 3-tuple, assert `QualityGateReason` enum
- Parameter names in test calls updated to match spec names
- Add imports for `Reason`, `QualityGateReason` from `navi_fractal`

## Explicitly deferred

These are implementation-phase work, not refactoring:

- `SandboxResult` full 25+ field expansion (additive, doesn't break existing code)
- Slope stability algorithm change (CV → sub-window range) — logic change, not structural
- `min_delta_y` filtering logic — new feature, not restructuring
- `model_preference`, `window_log_span`, `window_delta_y` fields — additive
- `n_nodes_original`, `n_nodes_measured`, `retained_fraction` audit fields — additive

## Commit strategy

One commit per step. Each commit is green (tests pass, lint/mypy clean). Conventional
commit messages: `refactor:` prefix.
