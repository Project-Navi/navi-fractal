# Tune Quality Gates

navi-fractal has a two-layer quality gate system. Layer 1 runs during estimation
and determines whether the estimator emits a dimension at all. Layer 2 is a
post-hoc filter you apply to accepted results. This guide shows how to configure
both layers.

## Layer 1: built-in gates

These parameters are arguments to `estimate_sandbox_dimension`. They control
which scaling windows are considered and whether the estimator accepts or refuses
the best candidate.

### Gate parameters

| Parameter | Default | What it controls |
|-----------|---------|-----------------|
| `r2_min` | `0.85` | Minimum \( R^2 \) for a window to be considered |
| `delta_power_win` | `1.5` | Minimum AICc advantage for power-law over exponential |
| `curvature_guard` | `True` | Whether to check for quadratic curvature in the scaling window |
| `delta_quadratic_win` | `3.0` | Minimum AICc advantage for quadratic over linear (rejects when exceeded) |
| `slope_stability_guard` | `False` | Whether to check for local slope variation across sub-windows |
| `max_slope_range` | `0.5` | Maximum range of local slopes across sub-windows (only active when `slope_stability_guard=True`) |
| `require_positive_slope` | `True` | Reject windows with negative slope (mass decreasing with radius) |
| `min_delta_y` | `0.5` | Minimum vertical span in log-log space (rejects flat curves) |
| `max_saturation_frac` | `0.95` | Fraction of total nodes at which a radius is considered saturated |
| `min_radius_ratio` | `3.0` | Minimum ratio of r_max/r_min in the scaling window |
| `min_points` | `6` | Minimum number of radii in the scaling window |

### Relaxing gates for exploratory analysis

When you are exploring a new dataset and want to see what the estimator would
produce even with marginal scaling evidence:

```python
from navi_fractal import estimate_sandbox_dimension

result = estimate_sandbox_dimension(
    g,
    r2_min=0.7,
    delta_power_win=0.5,
    min_delta_y=0.3,
    min_radius_ratio=2.0,
)
```

This lowers the \( R^2 \) threshold, weakens the power-law vs. exponential
discrimination, and accepts narrower scaling windows. Use the result for
hypothesis generation, not publication.

### Tightening gates for publication

When you need high confidence that the reported dimension reflects genuine
power-law scaling:

```python
result = estimate_sandbox_dimension(
    g,
    r2_min=0.95,
    delta_power_win=3.0,
    slope_stability_guard=True,
    max_slope_range=0.3,
    min_radius_ratio=4.0,
)
```

Enabling `slope_stability_guard` adds a check that the local slope does not vary
by more than `max_slope_range` across sub-windows. This catches cases where a
high global \( R^2 \) masks a systematic drift in the local exponent. Raising
`min_radius_ratio` to 4.0 requires the scaling window to span at least a factor
of 4 in radius.

### How the gates interact

The estimator tries every contiguous sub-range of radii as a candidate window.
A candidate is rejected if it fails any active gate. Among surviving candidates,
the estimator selects the one with the widest log-span (most decades of scaling).
If no candidate survives, the estimator refuses to emit a dimension and sets
`result.reason` to the specific failure mode.

## Layer 2: post-hoc quality gate

The `sandbox_quality_gate` function applies a policy threshold after estimation.
It can reject what the estimator accepted, but never accepts what the estimator
refused. This separation lets you run the estimator once with permissive settings
and then apply different acceptance policies to the same result.

### Presets

Two built-in presets define threshold bundles:

| Threshold | `"inclusive"` (default) | `"strict"` |
|-----------|----------------------|-----------|
| \( R^2 \) minimum | 0.85 | 0.95 |
| Slope stderr maximum | 0.25 | 0.20 |
| Radius ratio minimum | 3.0 | 4.0 |
| Delta-AICc minimum | 1.5 | 3.0 |
| Log-span minimum | \( \ln 3 \approx 1.10 \) | \( \ln 4 \approx 1.39 \) |

### Applying the post-hoc gate

```python
from navi_fractal import estimate_sandbox_dimension, sandbox_quality_gate

result = estimate_sandbox_dimension(g)

# Apply the inclusive preset (default)
passed, reason, detail = sandbox_quality_gate(result, preset="inclusive")
if passed:
    print(f"Dimension: {result.dimension:.4f}")
else:
    print(f"Rejected: {reason.value} -- {detail}")
```

### Using the strict preset

```python
passed, reason, detail = sandbox_quality_gate(result, preset="strict")
```

The strict preset is appropriate for publication-grade claims. It requires higher
\( R^2 \), tighter standard error, a wider scaling window, and stronger AICc
discrimination.

### Overriding individual thresholds

You can override any threshold while keeping the rest of a preset's defaults:

```python
# Start from strict but allow slightly lower R-squared
passed, reason, detail = sandbox_quality_gate(
    result,
    preset="strict",
    r2_min=0.92,
)
```

Available overrides: `r2_min`, `stderr_max`, `min_log_span`, `radius_ratio_min`,
`aicc_min`.

### Return value

`sandbox_quality_gate` returns a 3-tuple:

- `passed` (`bool`) --- whether the result meets all thresholds.
- `reason` (`QualityGateReason`) --- an enum value. `PASSED` if accepted, or a
  specific failure reason: `NOT_ACCEPTED`, `R2_TOO_LOW`, `STDERR_TOO_HIGH`,
  `LOG_SPAN_TOO_SMALL`, `RADIUS_RATIO_TOO_SMALL`, `AICC_MARGIN_TOO_SMALL`.
- `detail` (`str | None`) --- a human-readable explanation of the failure, or
  `None` if passed.

### Typical workflow

Run the estimator once with default (or relaxed) settings, then apply multiple
gate presets to the same result:

```python
from navi_fractal import (
    compile_to_undirected_metric_graph,
    estimate_sandbox_dimension,
    sandbox_quality_gate,
)

cg = compile_to_undirected_metric_graph(g)
result = estimate_sandbox_dimension(cg)

for preset in ("inclusive", "strict"):
    passed, reason, detail = sandbox_quality_gate(result, preset=preset)
    status = "PASS" if passed else f"FAIL ({reason.name})"
    print(f"  {preset:>10}: {status}")
```
