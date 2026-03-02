# Calibration Instrument — Design Document

**Date:** 2026-03-02
**Status:** Approved
**Scope:** Scientific calibration instrument comparing navi-fractal against validated v4 reference

## Goal

Before extracting v4 logic into navi-fractal, build a proper scientific instrument that
runs both implementations on identical graphs and produces structured, diffable output.
The instrument measures dimension estimates, quality gate behavior, window selection,
and timing — providing the numerical evidence needed to validate extraction correctness
and characterize finite-size scaling behavior.

## Architecture: Graph Registry + Comparison Engine

### Graph Registry

A declarative list of `GraphSpec` entries. Each describes one graph instance:

```python
@dataclass
class GraphSpec:
    family: str          # "flower", "grid", "path", "ba", "er", "complete"
    label: str           # "flower_22_gen8", "grid_30x30"
    params: dict         # constructor args: {"u": 2, "v": 2, "gen": 8}
    analytical_d: float | None  # exact d_B if known, None for non-fractal
    expect: str          # "emit" or "refuse"
    group: str | None    # convergence group key: "flower_22" for multi-gen
```

Not frozen — this is a script registry, not a hashable key.

### Test Corpus (~20 instances)

**Flower convergence series** (4 families, multi-generation):

| Family | Generations | d_B | Group | Rationale |
|--------|------------|-----|-------|-----------|
| (2,2) | 4, 5, 6, 7, 8 | 2.000 | flower_22 | Largest convergence curve, canonical benchmark |
| (3,3) | 3, 4, 5 | 1.631 | flower_33 | Mid-range dimension, different path length |
| (4,4) | 3, 4 | 1.500 | flower_44 | Boundary case near d=1.5 |
| (2,3) | 4, 5, 6 | 2.322 | flower_23 | Asymmetric — tests heterogeneous local structure |

**Transfractal:**
- (1,2) gen 8 — expect refuse, no convergence group

**Standard geometries:**
- 30×30 grid — analytical d=2.0 for infinite lattice, expect emit
- 100-path — analytical d=1.0, expect emit

**Non-fractal controls (seeded):**
- BA (n=1000, m=3, seed=42) — expect refuse
- ER (n=500, p=0.01, seed=42) — expect refuse
- K50 — expect refuse

Seed flows into BA/ER constructors for reproducibility across runs.

### Comparison Engine

```python
@dataclass
class RunResult:
    backend: str              # "v4" or "navi-fractal"
    dimension: float | None
    reason: str               # normalized to string for both
    r2: float | None
    slope: float | None
    slope_stderr: float | None
    window_r_min: int | None
    window_r_max: int | None
    window_log_span: float | None
    window_delta_y: float | None
    delta_aicc: float | None
    elapsed_s: float
    n_nodes: int

@dataclass
class Comparison:
    spec: GraphSpec
    v4: RunResult
    nf: RunResult
    dimension_delta: float | None   # nf - v4
    r2_delta: float | None
    analytical_gap_v4: float | None # v4 - analytical
    analytical_gap_nf: float | None # nf - analytical
```

API normalization handled internally:
- v4 string `reason` kept as-is
- navi-fractal `Reason` enum → `.value`
- v4 `LinFit.n` vs navi-fractal `LinFit.n_points` → extracted into RunResult fields
- Timing via `time.perf_counter()`

Graph constructors build both V4Graph and NFGraph from the same edge set simultaneously.

## Output

### Stdout: Three Tables

**Table 1 — Dimension comparison** (all emit cases):
```
Network              Nodes  Analytical    v4 D   v4 gap    nf D   nf gap   v4-nf
─────────────────────────────────────────────────────────────────────────────────
(2,2) gen 4            692      2.000   1.650   -17.5%   1.651   -17.5%  +0.001
(2,2) gen 5          2,732      2.000   1.720   -14.0%   1.719   -14.1%  -0.001
...
```

**Table 2 — Convergence curves** (one section per flower family):
```
(2,2)-flower convergence:  d_B = 2.000
  Gen   Nodes    v4 D    nf D    v4 gap%   nf gap%
    4     692   1.650   1.651    -17.5%    -17.5%
    5   2,732   1.720   1.719    -14.0%    -14.1%
    ...
```

**Table 3 — Refusal/control summary:**
```
Network              v4 verdict    nf verdict    Match?
────────────────────────────────────────────────────────
(1,2) gen 8          REFUSED       REFUSED       ✓
BA (n=1000, m=3)     REFUSED       REFUSED       ✓
...
```

### JSON Report

Written to `scripts/calibration-report.json`. Structure:

```json
{
  "metadata": {
    "timestamp": "2026-03-02T...",
    "python_version": "3.12.x",
    "navi_fractal_version": "0.1.0",
    "seed": 42,
    "total_elapsed_s": 45.2,
    "sign_conventions": {
      "analytical_gap": "measured - analytical (negative = underestimate)",
      "dimension_delta": "nf - v4 (near zero = implementations agree)"
    }
  },
  "comparisons": [
    {
      "spec": { "family": "flower", "label": "flower_22_gen8", "analytical_d": 2.0, "expect": "emit" },
      "v4": { "dimension": 1.812, "r2": 0.9994, "elapsed_s": 0.5, ... },
      "nf": { "dimension": 1.810, "r2": 0.9994, "elapsed_s": 6.4, ... },
      "deltas": { "dimension": -0.001, "r2": 0.0000, "analytical_gap_v4": -0.188, "analytical_gap_nf": -0.190 }
    }
  ],
  "convergence": {
    "flower_22": {
      "analytical_d": 2.000,
      "formula": "ln(u+v)/ln(u) = ln(4)/ln(2)",
      "generations": [
        { "gen": 4, "nodes": 692, "v4_d": 1.650, "nf_d": 1.651, "v4_gap_pct": -17.5, "nf_gap_pct": -17.5 }
      ]
    }
  }
}
```

The JSON is the diffable artifact: run calibration, commit the report, change navi-fractal
internals, rerun, diff the reports.

## Location

`scripts/calibrate.py` — standalone script, not part of the test suite. Run with:
```bash
uv run python scripts/calibrate.py
```

## Scope Boundary

**In scope:** Sandbox dimension, quality gate behavior, window selection metrics, timing,
finite-size convergence curves.

**Out of scope:** Multifractal spectrum, bootstrap CI comparison, weighted networks.

## Estimated Runtime

Under 60 seconds for the full corpus. The (2,2)-flower gen 8 at ~6s in navi-fractal
dominates. Lower generations are subsecond. Grid, path, and controls add a few seconds.
