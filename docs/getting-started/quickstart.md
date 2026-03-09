# Quickstart

This tutorial walks you through measuring the fractal dimension of a graph,
understanding when and why the instrument refuses to produce a number, and
applying post-hoc quality gates to your results.

## Your first measurement

```python
from navi_fractal import make_grid_graph, estimate_sandbox_dimension

grid = make_grid_graph(30, 30)
result = estimate_sandbox_dimension(grid, seed=42)

print(f"Dimension: {result.dimension:.3f}")       # 1.620
print(f"R²:        {result.powerlaw_fit.r2:.4f}")  # 0.9999
print(f"Window:    r=[{result.window_r_min}, {result.window_r_max}]")
print(f"Reason:    {result.reason.value}")          # accepted
```

`estimate_sandbox_dimension` runs the full measurement pipeline: it compiles the
graph into a deterministic internal representation, samples BFS neighborhoods from
random centers, computes mean mass at each radius, and searches for the best
contiguous scaling window in log-log space. A chain of statistical quality gates
decides whether the scaling evidence is strong enough to emit a dimension estimate.

When the gates pass, `result.dimension` holds the power-law slope and
`result.reason` is `Reason.ACCEPTED`. Every other field on the result provides
the audit trail --- the raw data, the fit diagnostics, and the window metrics
that led to this conclusion.

## When measurement is refused

```python
from navi_fractal import Graph, estimate_sandbox_dimension

# Complete graph -- trivially non-fractal
K50 = Graph()
for i in range(50):
    for j in range(i + 1, 50):
        K50.add_edge(i, j)

result = estimate_sandbox_dimension(K50, seed=42)
print(result.dimension)     # None
print(result.reason.value)  # trivial_graph
```

When `dimension` is `None`, the instrument is telling you it found no credible
evidence of power-law scaling. This is not an error --- it is the correct output.
The `reason` field gives you a machine-readable code explaining exactly why the
measurement was refused.

Some common refusal reasons:

| Reason | What happened |
|--------|--------------|
| `trivial_graph` | Graph is too small or has diameter <= 1 |
| `no_valid_radii` | Not enough distinct radii to fit a window |
| `no_window_passes_r2` | No contiguous window achieves the \( R^2 \) threshold |
| `aicc_prefers_exponential` | An exponential model fits the data better than a power law |
| `curvature_guard` | The log-log plot has significant curvature (quadratic beats linear) |

The refusal is the feature. A tool that always produces a number is not a
measurement instrument --- it is a number generator. navi-fractal earns your trust
by staying silent when the evidence is not there.

## Confidence intervals

```python
result = estimate_sandbox_dimension(grid, seed=42, bootstrap_reps=200)
if result.dimension_ci:
    lo, hi = result.dimension_ci
    print(f"D = {result.dimension:.3f} [{lo:.3f}, {hi:.3f}]")
```

When you set `bootstrap_reps > 0`, the estimator resamples the set of BFS centers
with replacement and re-fits the power-law slope for each replicate. The confidence
interval reports the 2.5th and 97.5th percentiles of the bootstrap distribution,
giving you a 95% interval for the dimension estimate.

The `bootstrap_valid_reps` field tells you how many replicates produced valid
fits. If this number is low relative to `bootstrap_reps`, the confidence interval
may be unreliable --- see [Interpreting Results](interpreting-results.md) for
guidance on what to watch for.

## Bring your own graph

```python
from navi_fractal import Graph, estimate_sandbox_dimension

g = Graph()
with open("edges.csv") as f:
    for line in f:
        u, v = line.strip().split(",")
        g.add_edge(u, v)

result = estimate_sandbox_dimension(g, seed=42)
```

`Graph` accepts any hashable type as node labels --- strings, integers, tuples,
whatever your data uses. Edges are undirected and self-loops are silently ignored.
When you pass a `Graph` to the estimator, it compiles it into a frozen internal
representation with deterministic traversal order before measurement begins.

For more loading patterns --- NetworkX interop, adjacency matrices, and large-scale
graphs --- see the how-to guides.

## Post-hoc quality gate

```python
from navi_fractal import sandbox_quality_gate

passed, reason, detail = sandbox_quality_gate(result, preset="inclusive")
if not passed:
    print(f"Quality gate failed: {reason.value} -- {detail}")
```

There are two layers of quality control in navi-fractal, and they serve different
purposes:

**Built-in gates** (part of `estimate_sandbox_dimension`) decide whether to emit
a dimension at all. They are the instrument's own judgment: "Is there positive
evidence of power-law scaling?" If these gates refuse, `dimension` is `None`.

**Post-hoc quality gate** (`sandbox_quality_gate`) is a policy layer that you
apply after measurement. It can reject what the estimator accepted, but it never
accepts what the estimator refused. This is where you encode your study's
standards: "Is this measurement good enough for my purpose?"

Two presets are available:

| Preset | \( R^2 \) min | Stderr max | Radius ratio | \( \Delta \)AICc | Log span |
|--------|--------|-----------|-------------|-----------|---------|
| `inclusive` | 0.85 | 0.25 | 3.0 | 1.5 | log(3) |
| `strict` | 0.95 | 0.20 | 4.0 | 3.0 | log(4) |

All thresholds are individually overridable via keyword arguments, so you can
mix a preset with custom values for specific checks.

## What's next

- **[Interpreting Results](interpreting-results.md)** --- a field-by-field guide
  to every value on `SandboxResult`, including red flags and what they mean.
- **How-to guides** --- advanced usage patterns including NetworkX interop,
  custom radii schedules, and null-model comparison.
