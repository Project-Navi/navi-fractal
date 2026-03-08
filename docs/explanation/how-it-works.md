# How It Works

navi-fractal estimates fractal dimension using the **sandbox method** (also called
mass-radius analysis). This page explains every stage of the pipeline, why each
stage exists, and how the pieces fit together.

## The idea

In a fractal graph, the number of nodes reachable within distance \( r \) of a
center node grows as a power law:

\[
M(r) \sim r^D
\]

The exponent \( D \) is the fractal dimension. If you plot \( \log M(r) \)
against \( \log r \) and see a straight line, the slope of that line is \( D \).
If you don't see a straight line, the graph probably isn't fractal -- and
navi-fractal will refuse to report a dimension rather than giving you a
meaningless number.

The sandbox method works by picking random centers, measuring ball masses at
a range of radii, and looking for the radius window where the power-law
relationship holds most convincingly. The key insight is that *not every radius
range will show clean scaling* -- boundary effects dominate at large radii,
discretization noise dominates at small radii, and the interesting scaling
regime lives somewhere in between. The pipeline's job is to find that regime
or to conclude that it doesn't exist.

## The pipeline

### Step 1: Graph compilation

The input graph -- whatever form it arrives in -- is compiled into a
`CompiledGraph`: a sorted adjacency list with integer node IDs. This
compilation step is not just a convenience. By sorting the adjacency list
for every node, the BFS traversal order becomes deterministic regardless
of insertion order. Two graphs with the same edges will produce identical
measurements. The compilation also deduplicates edges and enforces
undirectedness.

### Step 2: Component selection

The `component_policy` parameter (default `"giant"`) controls whether to
measure the entire graph or restrict to the giant connected component.
The giant component is extracted via iterative DFS, and the subgraph is
rebuilt with fresh contiguous IDs and sorted adjacency. If the giant
component has one or fewer nodes, the measurement is refused with
`GIANT_COMPONENT_TOO_SMALL`.

For most real networks, restricting to the giant component is the right
choice: disconnected components create artificial boundaries that suppress
ball masses at large radii and distort the scaling window.

### Step 3: Diameter estimation

The graph diameter is estimated using a **two-sweep BFS heuristic**: run BFS
from node 0 to find the farthest node, then run BFS again from that node and
take the maximum distance. This gives an exact diameter on trees and a tight
lower bound on general graphs -- good enough for choosing radius ranges. If
the estimated diameter is 1 or less, the graph is too trivial to measure and
is refused.

### Step 4: Radius generation

The `auto_radii` function generates a carefully tuned set of measurement radii:

- **Dense prefix**: every integer radius from 1 up to `min(dense_prefix, r_max)`,
  where `dense_prefix` defaults to 6. Small radii carry the most information
  about local structure, so dense coverage here is important.
- **Log-spaced tail**: `log_points` (default 10) radii spaced logarithmically
  from just above the dense prefix up to `r_max`.
- **Cap**: `r_max` is `min(r_cap, max(min_r_max, 0.3 * diameter))`, where
  `r_cap` defaults to 32, `min_r_max` defaults to 12, and `diam_frac` defaults
  to 0.3. The 30% cap prevents measuring radii where most centers would see
  the entire graph, which produces saturated (useless) data points.

The result is a sorted list of unique integer radii: dense where it matters,
sparse where it doesn't, and never so large that saturation dominates.

### Step 5: BFS mass measurement

For each of `n_centers` randomly chosen center nodes (default 256, sampled
with replacement from a seeded RNG), `bfs_layer_counts` runs a full BFS and
returns an array where `counts[d]` is the number of nodes at exactly distance
`d` from the center. Then `masses_from_layer_counts` builds a prefix sum over
these layer counts and reads off the ball mass \( M(r) \) at each radius in
\( O(1) \) per radius. The result is a matrix: one row per center, one column
per radius.

### Step 6: Aggregation

The per-center masses are aggregated across centers at each radius. Two modes
are available:

- **Geometric mean** (default, `mean_mode="geometric"`): the y-values for
  regression are the arithmetic means of \( \log(\text{mass}) \) across centers.
  This is natural because the regression itself happens in log-log space. It
  also down-weights outlier centers that happen to sit near the graph boundary.
- **Arithmetic mean** (`mean_mode="arithmetic"`): the y-values are
  \( \log(\text{arithmetic mean of mass}) \). This is more sensitive to
  high-mass centers.

When weighted least squares is enabled (the default), the inverse variance of
the per-center log-masses is used as the weight for each radius, with a
variance floor to prevent division by zero.

### Step 7: Saturation filter

Before window search, radii where the effective mean mass exceeds
`max_saturation_frac` (default 0.95) times the total node count are removed.
These saturated points would pull the slope toward zero and contaminate the
fit. Radii where the effective mass is 1 or less (beyond radius 1) are also
removed -- they contribute no information.

### Step 8: Window search

This is the heart of the algorithm. The pipeline performs an **exhaustive
search** over all contiguous sub-sequences of the filtered radii that have at
least `min_points` entries (default 6). For each candidate window:

1. **Log-span check**: the window must span at least `min_radius_ratio`
   (default 3.0) in radius, measured as
   \( \log(r_{\max}/r_{\min}) \geq \log(3.0) \). Narrow windows produce
   unreliable slopes.

2. **Delta-y check**: the vertical span \( \max(y) - \min(y) \) in the window
   must exceed `min_delta_y` (default 0.5). Flat windows (where mass barely
   changes with radius) produce near-zero slopes with enormous relative error.

3. **Regression**: OLS or WLS fit of \( \log M \) vs \( \log r \). The slope
   is the candidate dimension.

4. **\( R^2 \) gate**: the fit must achieve \( R^2 \geq \) `r2_min`
   (default 0.85).

5. **AICc model selection**: compute AICc for both the power-law fit (linear
   in log-log) and an exponential fit (linear in \( r \) vs \( \log M \)).
   The power-law must win by at least `delta_power_win` (default 1.5) in AICc.

6. **Curvature guard** (optional, on by default): fit a quadratic in log-log
   and compare its AICc against the linear fit. If the quadratic wins by
   more than `delta_quadratic_win` (default 3.0), the window is rejected.

7. **Slope stability guard** (optional, off by default): compute slopes in
   overlapping sub-windows and reject if the range exceeds `max_slope_range`
   (default 0.5).

Windows that survive all gates are scored by a lexicographic key:
(log-span, \( R^2 \), −slope stderr). Wider windows win first; among
equally wide windows, better fit quality wins. The best-scoring survivor
is the final answer.

### Step 9: Bootstrap

If `bootstrap_reps > 0`, the pipeline resamples the set of centers with
replacement, recomputes the aggregated masses for each bootstrap replicate,
and re-fits the winning window. The 2.5th and 97.5th percentiles of the
bootstrap slope distribution become the 95% confidence interval for the
dimension. The delta-AICc distribution is also captured.

### Step 10: Result

The pipeline returns a `SandboxResult` -- a frozen dataclass containing either
a dimension estimate (with full diagnostics) or a refusal with a machine-readable
`Reason` code. Every intermediate quantity is preserved: radii, masses, fits,
window bounds, AICc scores, bootstrap counts. Nothing is hidden.

## Pipeline summary

| Step | What happens |
|------|-------------|
| Compile | Input graph → deterministic undirected metric graph |
| Component | Optionally restrict to giant connected component |
| Diameter | Two-sweep BFS heuristic |
| Radii | Dense prefix + log-spaced tail, capped at 30% of diameter |
| BFS mass | Seeded random centers, ball sizes \( M(r) \) at each radius |
| Aggregate | Geometric or arithmetic mean across centers |
| Window search | Exhaustive search with \( R^2 \), AICc, curvature, slope stability gates |
| Bootstrap | Resample centers for confidence intervals |
| Result | Full diagnostic dataclass or refusal with reason |

## Determinism

Given the same `seed` and Python version, `estimate_sandbox_dimension` produces
identical results. Three properties make this possible:

1. **Seeded RNG**: center selection uses `random.Random(seed)`, not the global
   random state.
2. **Sorted adjacency**: the compiled graph's adjacency lists are sorted, so
   BFS visits neighbors in a deterministic order.
3. **No floating-point non-determinism**: the pipeline avoids operations where
   IEEE 754 rounding could vary across platforms (no parallel reductions, no
   `sum()` over unordered collections).

If you change the seed, you get different centers and therefore different
masses, but the pipeline is otherwise identical. If you change the Python
version, floating-point behavior may differ in edge cases, but this has not
been observed in practice.
