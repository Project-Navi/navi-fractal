# v4 Smoke Test Suite — Design Document

**Date:** 2026-03-02
**Status:** Approved
**Scope:** Validate fractal_analysis_v4_mfa.py against analytical ground truths before extraction

## Goal

Before extracting v4's core logic into navi-fractal, verify that v4 itself produces
correct results by testing against analytically known dimensions from the research
literature. This prevents baking in bugs from the start.

## Ground Truth Canon

Six papers provide the validation framework:

1. **Song et al. 2005** (Nature 433:392) — fractal/non-fractal dichotomy; BA model is non-fractal
2. **Rozenfeld et al. 2007** (NJP 9:175) — (u,v)-flower family: d_B = ln(u+v)/ln(u)
3. **Liu et al. 2015** (Chaos 25:023103) — sandbox algorithm methodology
4. **Song et al. 2015** (Sci. Rep. 5:17628) — weighted sandbox benchmarks
5. **Fronczak et al. 2024** (Sci. Rep. 14:9079) — scaling theory, (2,2)-flower d_B=2.0
6. **Lepek et al. 2025** (Chaos Solitons Fractals 199:116908) — FNB benchmarks

The (u,v)-flower family is the centerpiece: deterministic construction, exact analytical
dimension, no external data needed, CI-friendly.

## Architecture

```
tests/v4_smoke/
├── conftest.py                 # v4 import, flower/BA/ER constructors, fixtures
├── test_math_primitives.py     # Layer 1: regression, AICc, percentile
├── test_flower_integration.py  # Layer 2: (u,v)-flower pipeline
└── test_plausibility.py        # Layer 3: grids, paths, BA/ER rejection
```

### Import Strategy

`conftest.py` adds `docs/reference/` to sys.path so tests import v4 directly:
```python
from fractal_analysis_v4_mfa import estimate_sandbox_dimension, ...
```

### (u,v)-Flower Constructor

`make_uv_flower(u: int, v: int, gen: int) -> Graph`

- Generation 0: single edge (2 nodes)
- Each generation: replace every edge with two parallel paths of lengths u and v
- Self-contained, no external data
- Constructor assertions before pipeline tests:
  - Node count matches formula or known value (43,692 for (2,2) gen 8)
  - Diameter = u^gen (shortest path between original hubs)
  - Hub degree = 2^gen

### BA Model Constructor

`make_ba_graph(n: int, m: int, seed: int) -> Graph`

Barabasi-Albert preferential attachment. Non-fractal — should be rejected.

### ER Random Constructor

`make_er_graph(n: int, p: float, seed: int) -> Graph`

Erdos-Renyi random graph. Non-fractal — should be rejected or show poor R2.

## Layer 1 — Math Primitives (~15 tests)

No graph construction. Pure formula validation against hand-calculated values.

| Function | Test | Ground Truth |
|----------|------|-------------|
| linear_fit_ols | Perfect line y=2x+1 | slope=2.0, R2=1.0, intercept=1.0 |
| linear_fit_ols | Known residuals | Hand-computed SSE, slope_stderr |
| linear_fit_wls | Uniform weights | Must match OLS exactly |
| linear_fit_wls | Downweight outlier | Slope shifts toward clean data |
| aicc_for_ols | n=10, k=2, known SSE | n*log(SSE/n) + 2k + 2k(k+1)/(n-k-1) |
| aicc_for_ols | n <= k+1 | Returns inf |
| aicc_for_wls | Known chi2 | chi2 + 2k + 2k(k+1)/(n-k-1) |
| _percentile | [1,2,3,4,5] at p=50 | 3.0 (median) |
| _percentile | Interpolation at p=25 | 2.0 (linear interp) |
| quadratic_fit_sse_ols | Perfect parabola | SSE ~ 0.0 |
| quadratic_fit_sse_ols | Linear data | Quadratic coeff ~ 0 |
| _solve_3x3 | Known 3x3 system | Verified against Cramer's rule |
| _moments_from_center_masses | 3-center hand-crafted | Mean/var match manual |
| slope_range_over_subwindows | Constant slope | Range = 0.0 |
| slope_range_over_subwindows | Known curvature | Range matches hand-calc |

## Layer 2 — (u,v)-Flower Integration (~12 tests)

Research-grounded pipeline tests.

| Test | Graph | Expected | Tolerance | Source |
|------|-------|----------|-----------|--------|
| (2,2)-flower gen 8 dimension | 43,692 nodes | d_B = 2.000 | +/- 0.10 | Rozenfeld 2007 |
| (3,3)-flower gen 5 dimension | ~5K nodes | d_B = 1.631 | +/- 0.15 | Rozenfeld 2007 |
| (4,4)-flower gen 4 dimension | ~2K nodes | d_B = 1.500 | +/- 0.15 | Rozenfeld 2007 |
| (2,3)-flower gen 6 dimension | ~12K nodes | d_B = 2.322 | +/- 0.15 | Rozenfeld 2007 |
| (1,2)-flower transfractal | gen 8 | Gate rejects | — | See note below |
| (2,2)-flower R2 | gen 8 | R2 > 0.95 | — | Liu 2015 |
| (2,2)-flower reason | gen 8 | ACCEPTED | — | Pipeline check |
| (2,2)-flower quality gate | gen 8 | Passes "inclusive" | — | Gate check |
| Constructor: node count | (2,2) gen 8 | 43,692 | exact | Fronczak 2024 |
| Constructor: diameter | (2,2) gen 8 | 256 | exact | Analytical |
| Constructor: determinism | Same seed | Identical results | exact | Reproducibility |

### Note on (1,2)-flower transfractal test

The (1,2)-flower is transfractal (infinite d_B). v4 might return a dimension value
with terrible R2 rather than refusing outright. The assertion must check the quality
gate verdict specifically — `sandbox_quality_gate(result, preset="inclusive")` should
return `(False, ...)` — not just check `dimension is None`. If v4 does return
`dimension=None`, that's fine too; the test passes either way as long as the gate
rejects.

## Layer 3 — Cross-Algorithm Plausibility (~5 tests)

| Test | Graph | Expected | Source |
|------|-------|----------|--------|
| 30x30 grid | 900 nodes | 1.55 <= D <= 1.75 | Existing navi-fractal bounds |
| Path 100 | 100 nodes | 0.8 <= D <= 1.2 | Analytical d=1 |
| BA model (m=3, n=1000) | ~1000 nodes | Rejected or poor R2 | Song 2005 |
| ER random (p=0.01, n=500) | ~500 nodes | Rejected or poor R2 | Liu 2015 |
| Complete K50 | 50 nodes | dimension=None | Trivial diameter |

For BA and ER: assert either `dimension is None` OR `quality_gate fails`.

## Scope Boundary

**In scope:** Sandbox dimension (monofractal, q=0), quality gates, refusal paths.

**Out of scope (v0.2.0):** Multifractal D(q), Creative Determinant, weighted networks,
Sierpinski WFN (requires weighted sandbox).

## Tolerances Rationale

- **+/- 0.10 for large flowers (gen 8, 40K+ nodes):** Lepek 2025 reports d_B=1.98
  for (2,2)-flower via FNB vs 2.0 exact. Sandbox should be at least as accurate.
- **+/- 0.15 for smaller flowers (gen 4-5, 2-5K nodes):** Finite-size effects worsen
  with fewer nodes. Wider tolerance accounts for boundary effects.
- **Grid bounds [1.55, 1.75]:** Already validated in navi-fractal v0.1.0 (D=1.6197).
