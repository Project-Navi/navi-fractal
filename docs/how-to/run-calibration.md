# Run Calibration

This guide explains how to run the calibration suite, interpret its output, and
add your own reference networks.

## What calibration means

Calibration compares navi-fractal's sandbox dimension estimates against networks
with known analytical dimensions. If the estimator consistently recovers (or
converges toward) the true dimension on these reference networks, you can trust
its output on networks where the answer is unknown.

The calibration suite also runs a legacy implementation (v4) side-by-side, so you
can verify that navi-fractal matches or improves on its predecessor.

## The (u,v)-flower family

The primary calibration targets are **(u,v)-flower graphs** -- deterministic
recursive networks built by edge replacement. At each generation, every edge is
replaced by two parallel paths of length u and v. The resulting graph has an
exact box-counting dimension:

```
d_B = log(u + v) / log(u)
```

This formula is proved analytically (and formally verified in Lean 4 in the
companion fd-formalization project). Because the dimension is exact and the
construction is deterministic, flowers are ideal calibration targets.

The calibration corpus includes several flower families:

| Family | d_B | Generations tested |
|--------|-----|-------------------|
| (2,2)-flower | 2.0 | 4, 5, 6, 7, 8 |
| (3,3)-flower | log(6)/log(3) ~= 1.631 | 3, 4, 5 |
| (4,4)-flower | 1.5 | 3, 4 |
| (2,3)-flower | log(5)/log(2) ~= 2.322 | 4, 5, 6 |

The corpus also includes standard geometries (30x30 grid with d_B = 2.0, path
graph with d_B = 1.0) and non-fractal controls that should be *refused*
(Barabási-Albert, Erdős-Rényi, complete graph, (1,2)-flower which is
transfractal).

## Running the calibration script

The calibration script lives at `scripts/calibrate.py`. Run it with:

```bash
uv run python scripts/calibrate.py
```

This runs the full corpus (19 graph instances). For faster iteration during
development, skip the largest generations:

```bash
uv run python scripts/calibrate.py --quick
```

The `--quick` flag drops generations marked as `slow` (e.g., gen 7 and 8 of the
(2,2)-flower), reducing runtime from ~15 seconds to a few seconds.

### What it produces

1. **Three tables on stdout:**
   - **Table 1 (Dimension Estimates):** all emit-expected cases with v4 and
     navi-fractal dimensions, analytical gap percentages, and timing.
   - **Table 2 (Convergence Series):** flower families grouped by (u,v), showing
     how the gap shrinks with increasing generation.
   - **Table 3 (Refusal Cases):** non-fractal controls, verifying both backends
     refuse to emit a dimension.

2. **A structured JSON report** at `scripts/calibration-report.json`.

## Reading the calibration report

The JSON report has three top-level sections:

### `metadata`

```json
{
  "timestamp": "2026-03-07T19:42:06.768529+00:00",
  "python_version": "3.12.12",
  "seed": 42,
  "total_elapsed_s": 13.49,
  "corpus_size": 19,
  "sign_conventions": {
    "analytical_gap": "measured - analytical (positive = overestimate)",
    "gap_pct": "100 * (measured - analytical) / analytical",
    "dimension_delta": "nf - v4 (positive = nf higher)"
  }
}
```

The `sign_conventions` block documents all sign choices so you do not have to
guess whether a positive gap means overestimate or underestimate.

### `comparisons`

A list of per-graph entries. Each entry contains:

- `label`, `family`, `group`, `expect` -- graph identity and expected behavior.
- `analytical_d` -- the exact dimension (null for non-fractal controls).
- `v4` and `nf` -- full result objects for each backend, including `dimension`,
  `reason`, `r2`, `slope`, `slope_stderr`, `window_r_min`, `window_r_max`,
  `window_log_span`, `window_delta_y`, `delta_aicc`, `elapsed_s`, and
  `n_nodes`.
- `deltas` -- pre-computed differences: `dimension_delta` (nf minus v4),
  `r2_delta`, `analytical_gap_v4`, `analytical_gap_nf`, `gap_pct_v4`,
  `gap_pct_nf`.

### `convergence`

Groups flower families by (u,v) and lists per-generation results:

```json
{
  "flower_22": {
    "analytical_d": 2.0,
    "formula": "ln(4)/ln(2) = ln(4)/ln(2)",
    "generations": [
      {
        "label": "flower_22_gen4",
        "n_nodes": 172,
        "v4_dimension": 1.378992,
        "nf_dimension": 1.379703,
        "gap_pct_v4": -31.0504,
        "gap_pct_nf": -31.0148
      }
    ]
  }
}
```

The negative `gap_pct` values indicate systematic underestimation, which is
expected: the sandbox measures local ball-mass scaling on a finite graph, while
the analytical dimension is an asymptotic property. The gap shrinks with
increasing generation as the graph better approximates the fractal limit.

## Running convergence analysis

The convergence analysis script reads `calibration-report.json` and fits the
relationship between generation number and estimation gap:

```bash
uv run python scripts/convergence_analysis.py
```

For machine-readable output:

```bash
uv run python scripts/convergence_analysis.py --json
```

### What it does

For each flower family, the script:

1. Extracts the gap percentage at each generation.
2. Fits `gap(g) = a/g + b` via least squares, where `g` is the generation
   number.
3. Computes the theoretical convergence rate constant from the formally proved
   squeeze bounds: `a_theory = 100 * log(2) / log(u+v)`.
4. Reports the amplification factor `|a_empirical| / a_theory`. Values greater
   than 1 are expected because the sandbox measures a different geometric
   quantity (local ball-mass scaling) than the global log-ratio proved in the
   formalization.
5. Checks monotonicity -- whether the absolute gap shrinks at every generation
   step. Non-monotonic convergence (flagged as `WARN`) is a legitimate outcome
   of window selection, not a bug.

### Reading the output table

```
Family        d_B  Gens    a_emp  a_theory   Amp     R2  Mono  Anomalies
(2,2)-flower 2.000    5   -82.3      50.0  1.6x  0.952    OK
(3,3)-flower 1.631    3   -41.2      38.7  1.1x  0.999    OK
```

- **a_emp**: empirical rate constant from the 1/g fit (negative = underestimate
  shrinking toward zero).
- **a_theory**: theoretical upper bound from the Lean squeeze theorem.
- **Amp**: how much faster the sandbox gap decays compared to the proved bound.
  Values near 1.0 mean the bound is tight; larger values mean the sandbox
  converges faster than the worst-case bound predicts.
- **Mono**: `OK` if the gap shrinks monotonically across generations; `WARN` if
  any generation shows a regression.

## Adding your own reference networks

To add a new network to the calibration corpus, edit the `_build_registry`
function in `scripts/calibrate.py`.

### Step 1: Define a GraphSpec

Add a `GraphSpec` entry to the `specs` list:

```python
specs.append(
    GraphSpec(
        family="my_family",
        label="my_graph_v1",
        params={"n": 500, "p": 0.05},
        analytical_d=1.585,       # exact d_B, or None if unknown
        expect="emit",            # "emit" or "refuse"
        group="my_convergence",   # group key for convergence series, or None
        slow=False,               # True to skip in --quick mode
    )
)
```

- Set `analytical_d` to the exact box-counting dimension if known. Set it to
  `None` for non-fractal controls.
- Set `expect="refuse"` for graphs where the estimator should decline to emit
  a dimension (non-fractal topologies, trivial graphs).
- Set `group` to a shared key if you have multiple generations of the same
  family and want them to appear together in the convergence table.

### Step 2: Write a constructor

Add a builder function that returns `(V4Graph, NFGraph, int)` -- both graph
representations and the node count:

```python
def _build_my_family(n: int, p: float) -> tuple[V4Graph, NFGraph, int]:
    v4g = V4Graph(directed=False)
    nfg = NFGraph()
    for node_id in range(n):
        v4g.add_node(node_id)
        nfg.add_node(node_id)
    # ... add edges to both v4g and nfg ...
    return v4g, nfg, n
```

### Step 3: Register the constructor

Add a dispatch clause to `_build_graphs`:

```python
if spec.family == "my_family":
    return _build_my_family(p["n"], p["p"])
```

### Step 4: Run and verify

```bash
uv run python scripts/calibrate.py
```

Check that your new graph appears in the correct table (Table 1 for emit cases,
Table 3 for refusal cases) and that the JSON report includes it. If you added a
convergence series, run the convergence analysis to verify the gap trend:

```bash
uv run python scripts/convergence_analysis.py
```
