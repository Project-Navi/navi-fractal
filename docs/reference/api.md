# API Reference

All public symbols are importable from `navi_fractal`.

```python
from navi_fractal import (
    CompiledGraph,
    DimensionSummary,
    Graph,
    LinFit,
    QualityGateReason,
    Reason,
    SandboxResult,
    compile_to_undirected_metric_graph,
    degree_preserving_rewire_undirected,
    estimate_sandbox_dimension,
    make_grid_graph,
    make_path_graph,
    sandbox_quality_gate,
)
```

---

## Core Function

### `estimate_sandbox_dimension`

```python
def estimate_sandbox_dimension(
    g: Graph | CompiledGraph,
    *,
    seed: int = 0,
    rng: random.Random | None = None,
    n_centers: int = 256,
    radii: Sequence[int] | None = None,
    r_cap: int = 32,
    component_policy: str = "giant",
    mean_mode: str = "geometric",
    min_points: int = 6,
    min_radius_ratio: float = 3.0,
    r2_min: float = 0.85,
    min_delta_y: float = 0.5,
    max_saturation_frac: float = 0.95,
    delta_power_win: float = 1.5,
    require_positive_slope: bool = True,
    use_wls: bool = True,
    curvature_guard: bool = True,
    delta_quadratic_win: float = 3.0,
    slope_stability_guard: bool = False,
    slope_stability_sub_len: int | None = None,
    max_slope_range: float = 0.5,
    bootstrap_reps: int = 0,
    bootstrap_seed: int | None = None,
    var_floor: float = 1e-6,
    notes: str = "",
) -> SandboxResult
```

Estimate the sandbox (mass-radius) fractal dimension of a graph.

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `g` | — | Input graph (`Graph` or `CompiledGraph`) |
| `seed` | `0` | RNG seed for center selection |
| `rng` | `None` | Optional pre-seeded `random.Random` instance |
| `n_centers` | `256` | Number of random BFS centers |
| `radii` | `None` | Custom radius sequence (bypasses auto-radii if set) |
| `r_cap` | `32` | Maximum radius from auto-radii |
| `component_policy` | `"giant"` | `"giant"` or `"all"` --- whether to restrict to the largest connected component |
| `mean_mode` | `"geometric"` | `"geometric"` or `"arithmetic"` --- aggregation across centers |
| `min_points` | `6` | Minimum radii in a candidate window |
| `min_radius_ratio` | `3.0` | Minimum r_max / r_min for a window |
| `r2_min` | `0.85` | Minimum \( R^2 \) for a window to be considered |
| `min_delta_y` | `0.5` | Minimum vertical span in log-log space |
| `max_saturation_frac` | `0.95` | Maximum fraction of total nodes for a radius to be included |
| `delta_power_win` | `1.5` | Minimum AICc advantage for power-law over exponential |
| `require_positive_slope` | `True` | Reject windows with negative slope |
| `use_wls` | `True` | Use weighted least squares (weights = 1/variance) |
| `curvature_guard` | `True` | Enable the quadratic curvature guard |
| `delta_quadratic_win` | `3.0` | AICc threshold for curvature guard |
| `slope_stability_guard` | `False` | Enable sub-window slope stability check |
| `slope_stability_sub_len` | `None` | Sub-window length (defaults to `min_points`) |
| `max_slope_range` | `0.5` | Maximum slope range across sub-windows |
| `bootstrap_reps` | `0` | Number of bootstrap replicates (0 = no bootstrap) |
| `bootstrap_seed` | `None` | Separate seed for bootstrap (defaults to `seed`) |
| `var_floor` | `1e-6` | Minimum variance for WLS weights |
| `notes` | `""` | Free-text notes attached to the result |

**Returns:** [`SandboxResult`](#sandboxresult)

---

## Quality Gate

### `sandbox_quality_gate`

```python
def sandbox_quality_gate(
    result: SandboxResult,
    *,
    preset: str = "inclusive",
    r2_min: float | None = None,
    stderr_max: float | None = None,
    min_log_span: float | None = None,
    radius_ratio_min: float | None = None,
    aicc_min: float | None = None,
) -> tuple[bool, QualityGateReason, str | None]
```

Post-hoc quality gate applied after estimation.

**Presets:** `"inclusive"` (lenient) or `"strict"` (publication-grade). Individual parameters override preset values when provided.

**Returns:** `(passed, reason, detail)` --- boolean pass/fail, reason code, and optional detail string.

---

## Graph Types

### `Graph`

```python
class Graph:
    def __init__(self) -> None: ...
    def add_node(self, node: object) -> None: ...
    def add_edge(self, u: object, v: object) -> None: ...
    @property
    def nodes(self) -> set[object]: ...
    @property
    def adj(self) -> dict[object, set[object]]: ...
    def __len__(self) -> int: ...
```

Mutable undirected graph. Nodes can be any hashable object. `add_edge` implicitly adds both nodes. `len(g)` returns the node count.

### `CompiledGraph`

```python
@dataclass(frozen=True)
class CompiledGraph:
    n: int                               # number of nodes
    adj: tuple[tuple[int, ...], ...]     # sorted adjacency lists
    label_to_id: dict[object, int]       # original label → internal int
    id_to_label: tuple[object, ...]      # internal int → original label
```

Immutable, integer-indexed graph with sorted adjacency lists for deterministic BFS.
The label maps allow round-tripping between your original node labels and the internal integer IDs.

### `compile_to_undirected_metric_graph`

```python
def compile_to_undirected_metric_graph(g: Graph) -> CompiledGraph
```

Compile a `Graph` into a `CompiledGraph`. Useful when running multiple analyses on the same graph to avoid repeated compilation.

---

## Result Types

### `SandboxResult`

```python
@dataclass(frozen=True)
class SandboxResult:
    # Dimension estimate
    dimension: float | None
    reason: Reason
    reason_detail: str | None

    # Model selection
    model_preference: str
    delta_aicc: float | None
    powerlaw_fit: LinFit | None
    exponential_fit: LinFit | None

    # Window metrics
    window_r_min: int | None
    window_r_max: int | None
    window_log_span: float | None
    window_delta_y: float | None
    window_slope_range: float | None
    window_aicc_quad_minus_lin: float | None

    # Confidence intervals
    dimension_ci: tuple[float, float] | None
    delta_aicc_ci: tuple[float, float] | None
    bootstrap_valid_reps: int

    # Raw evaluation data
    radii_eval: tuple[int, ...]
    mean_mass_eval: tuple[float, ...]
    y_eval: tuple[float, ...]

    # Component audit
    n_nodes_original: int
    n_nodes_measured: int
    retained_fraction: float

    # Reproducibility
    n_centers: int
    seed: int
    notes: str
```

Frozen dataclass containing the complete audit trail of a dimension estimation. See [Interpreting Results](../getting-started/interpreting-results.md) for a field-by-field guide.

### `LinFit`

```python
@dataclass(frozen=True)
class LinFit:
    slope: float         # dimension estimate (for powerlaw fit)
    intercept: float     # y-intercept in log-log space
    r2: float            # coefficient of determination
    slope_stderr: float  # standard error of slope
    sse: float           # sum of squared residuals
    n_points: int        # number of radii in the window
```

### `DimensionSummary`

```python
@dataclass(frozen=True)
class DimensionSummary:
    dimension: float | None
    accepted: bool
    reason: Reason
    r2: float | None
    ci: tuple[float, float] | None
```

Lightweight summary for quick inspection.

---

## Enums

### `Reason`

See [Reason Codes](reason-codes.md) for detailed descriptions of each value.

| Value | Meaning |
|-------|---------|
| `ACCEPTED` | All gates passed |
| `EMPTY_GRAPH` | No nodes |
| `TRIVIAL_GRAPH` | Diameter \( \leq 1 \) |
| `GIANT_COMPONENT_TOO_SMALL` | Giant component too small |
| `NO_VALID_RADII` | Too few radii |
| `NO_WINDOW_PASSES_R2` | No window meets \( R^2 \) threshold |
| `AICC_PREFERS_EXPONENTIAL` | Exponential fits better |
| `CURVATURE_GUARD` | Significant curvature in log-log |
| `SLOPE_STABILITY_GUARD` | Unstable local slopes |
| `NEGATIVE_SLOPE` | Negative best-fit slope |

### `QualityGateReason`

| Value | Meaning |
|-------|---------|
| `PASSED` | All thresholds met |
| `NOT_ACCEPTED` | Underlying result was refused |
| `R2_TOO_LOW` | R² below threshold |
| `STDERR_TOO_HIGH` | Slope stderr too high |
| `LOG_SPAN_TOO_SMALL` | Window too narrow |
| `RADIUS_RATIO_TOO_SMALL` | r_max/r_min too small |
| `AICC_MARGIN_TOO_SMALL` | AICc margin too small |

---

## Helpers

### `make_grid_graph`

```python
def make_grid_graph(rows: int, cols: int) -> Graph
```

Create a 2D grid graph with `rows × cols` nodes.

### `make_path_graph`

```python
def make_path_graph(n: int) -> Graph
```

Create a path graph with `n` nodes.

---

## Null Model

### `degree_preserving_rewire_undirected`

```python
def degree_preserving_rewire_undirected(
    cg: CompiledGraph,
    *,
    seed: int = 0,
    rng: random.Random | None = None,
    n_swaps: int | None = None,
    verify: bool = True,
) -> CompiledGraph
```

Degree-preserving random rewiring of a compiled graph. Useful as a null model to test whether fractal structure is a property of the degree sequence or the topology.
