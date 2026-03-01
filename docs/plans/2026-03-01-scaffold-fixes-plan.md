# Scaffold Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all CRITICAL and IMPORTANT audit findings from the adversarial design-vs-scaffold review, aligning the v0.1.0 scaffold with navi-fractal-design-v2 spec.

**Architecture:** Logic fixes first (Tasks 1-7, each a green TDD commit), then SandboxResult field expansion (Task 8, coordinated migration), then comprehensive test coverage (Tasks 9-11).

**Tech Stack:** Python 3.12+, stdlib only. Dev: pytest, ruff, mypy --strict, bandit.

**Reference files:**
- Design spec: `docs/design/navi-fractal-design-v2.md`
- Main module: `src/navi_fractal/_sandbox.py`
- Types: `src/navi_fractal/_types.py`
- Quality gate: `src/navi_fractal/_quality_gate.py`
- Null model: `src/navi_fractal/_null_model.py`
- Regression: `src/navi_fractal/_regression.py`
- Public API: `src/navi_fractal/__init__.py`
- CLAUDE.md has all test/lint/type-check commands

**Audit findings map:** Each task header lists which audit finding(s) it addresses (C = CRITICAL, I = IMPORTANT).

---

### Task 1: Add NullHandler and validate component_policy

**Audit findings:** I2 (NullHandler), I3 (component_policy validation)

**Files:**
- Modify: `src/navi_fractal/__init__.py`
- Modify: `src/navi_fractal/_sandbox.py`
- Modify: `tests/test_sandbox.py`

**Step 1: Write failing tests**

Add to `tests/test_sandbox.py` in `TestSandboxRefusals`:

```python
def test_null_handler_on_library_logger(self) -> None:
    import logging

    logger = logging.getLogger("navi_fractal")
    assert any(isinstance(h, logging.NullHandler) for h in logger.handlers)

def test_invalid_component_policy_raises(self) -> None:
    grid = make_grid_graph(5, 5)
    with pytest.raises(ValueError, match="component_policy"):
        estimate_sandbox_dimension(grid, seed=42, component_policy="invalid")
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sandbox.py::TestSandboxRefusals::test_null_handler_on_library_logger tests/test_sandbox.py::TestSandboxRefusals::test_invalid_component_policy_raises -v --benchmark-disable`
Expected: 2 FAILED

**Step 3: Implement NullHandler**

In `src/navi_fractal/__init__.py`, add after the existing imports (before `__all__`):

```python
import logging

logging.getLogger("navi_fractal").addHandler(logging.NullHandler())
```

**Step 4: Implement component_policy validation**

In `src/navi_fractal/_sandbox.py`, in `estimate_sandbox_dimension()`, add immediately after the `cg` compilation block (after line ~88) and before the trivial checks:

```python
    # Validate component_policy
    if component_policy not in ("giant", "all"):
        raise ValueError(
            f"component_policy must be 'giant' or 'all', got {component_policy!r}"
        )
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/ -v --benchmark-disable && uv run ruff check src/ tests/ && uv run mypy --strict src/navi_fractal/`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add src/navi_fractal/__init__.py src/navi_fractal/_sandbox.py tests/test_sandbox.py
git commit -m "fix: add NullHandler and validate component_policy

Addresses audit findings I2 and I3:
- Add logging.NullHandler() to library logger per Python best practice
- Reject invalid component_policy values with ValueError

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Fix GIANT_COMPONENT_TOO_SMALL threshold and populate reason_detail

**Audit findings:** I4 (threshold), I6 (reason_detail)

**Files:**
- Modify: `src/navi_fractal/_sandbox.py`
- Modify: `tests/test_sandbox.py`
- Modify: `tests/conftest.py`

**Step 1: Write failing tests**

Add fixture to `tests/conftest.py`:

```python
@pytest.fixture
def dust_cloud_graph() -> Graph:
    """Graph with many isolated nodes — giant component has 1 node."""
    g = Graph()
    for i in range(10):
        g.add_node(i)
    return g
```

Add to `tests/test_sandbox.py` in `TestSandboxRefusals`:

```python
def test_giant_component_too_small(self, dust_cloud_graph: Graph) -> None:
    result = estimate_sandbox_dimension(dust_cloud_graph, seed=42)
    assert result.dimension is None
    assert result.reason == Reason.GIANT_COMPONENT_TOO_SMALL
    assert result.reason_detail is not None
    assert "giant=" in result.reason_detail
    assert "total=" in result.reason_detail

def test_two_node_giant_accepted_for_processing(self) -> None:
    """A 2-node giant component should NOT be refused as too small."""
    g = Graph()
    g.add_edge(0, 1)
    # Add isolated nodes so component policy is exercised
    g.add_node(2)
    g.add_node(3)
    result = estimate_sandbox_dimension(g, seed=42, component_policy="giant")
    # Should NOT be GIANT_COMPONENT_TOO_SMALL — may be refused for other reasons
    assert result.reason != Reason.GIANT_COMPONENT_TOO_SMALL
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sandbox.py::TestSandboxRefusals::test_giant_component_too_small tests/test_sandbox.py::TestSandboxRefusals::test_two_node_giant_accepted_for_processing -v --benchmark-disable`
Expected: FAILED (dust_cloud may give TRIVIAL_GRAPH or wrong threshold)

**Step 3: Implement**

In `src/navi_fractal/_sandbox.py`, in `estimate_sandbox_dimension()`:

1. Track original node count before component selection. Add after compilation:

```python
    n_nodes_original = cg.n
```

2. Fix the threshold and add detail. Replace the component selection block (lines ~102-105):

```python
    # Component selection
    if component_policy == "giant":
        cg = _extract_giant_component(cg)
        if cg.n <= 1:
            return empty_result(
                Reason.GIANT_COMPONENT_TOO_SMALL,
                n_centers=n_centers,
                detail=f"giant={cg.n}, total={n_nodes_original}",
            )
```

3. Add detail strings to the diameter refusal (line ~110):

```python
    if diam <= 1:
        return empty_result(
            Reason.TRIVIAL_GRAPH,
            n_centers=n_centers,
            detail=f"diameter={diam}",
        )
```

4. Add detail to the NO_VALID_RADII refusal (line ~114-115):

```python
    if len(radii) < min_points:
        return empty_result(
            Reason.NO_VALID_RADII,
            n_centers=n_centers,
            detail=f"got {len(radii)} radii, need {min_points}",
        )
```

5. Add detail to the post-filtering NO_VALID_RADII (line ~169-184). Change the `reason_detail` in the SandboxResult construction:

```python
            reason_detail=f"got {len(log_radii)} non-degenerate radii, need {min_points}",
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ -v --benchmark-disable && uv run ruff check src/ tests/ && uv run mypy --strict src/navi_fractal/`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/navi_fractal/_sandbox.py tests/test_sandbox.py tests/conftest.py
git commit -m "fix: correct GIANT_COMPONENT_TOO_SMALL threshold, populate reason_detail

- Change threshold from <= 2 to <= 1 (spec says < 2 nodes)
- Add reason_detail strings to all early refusal paths
- Add dust_cloud_graph fixture for component policy testing

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Wire unreachable Reason codes into window search

**Audit finding:** C3 (AICC_PREFERS_EXPONENTIAL, CURVATURE_GUARD, SLOPE_STABILITY_GUARD unreachable)

**Files:**
- Modify: `src/navi_fractal/_sandbox.py`
- Modify: `tests/test_sandbox.py`

**Context:** The window search loop uses `continue` when AICc, curvature, or slope stability checks fail, but never updates `best_reason` to reflect which check failed. All failures report `NO_WINDOW_PASSES_R2`. Fix by tracking the deepest rejection reason across all windows.

**Step 1: Write failing tests**

Add to `tests/test_sandbox.py` in `TestSandboxRefusals`:

```python
def test_aicc_prefers_exponential_refusal(self) -> None:
    """Forcing delta_power_win impossibly high should trigger AICC refusal."""
    grid = make_grid_graph(30, 30)
    result = estimate_sandbox_dimension(grid, seed=42, delta_power_win=1e6)
    assert result.dimension is None
    assert result.reason == Reason.AICC_PREFERS_EXPONENTIAL

def test_slope_stability_guard_refusal(self) -> None:
    """Forcing max_slope_range impossibly low should trigger stability refusal."""
    grid = make_grid_graph(30, 30)
    result = estimate_sandbox_dimension(
        grid,
        seed=42,
        slope_stability_guard=True,
        max_slope_range=0.001,
    )
    assert result.dimension is None
    assert result.reason == Reason.SLOPE_STABILITY_GUARD
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sandbox.py::TestSandboxRefusals::test_aicc_prefers_exponential_refusal tests/test_sandbox.py::TestSandboxRefusals::test_slope_stability_guard_refusal -v --benchmark-disable`
Expected: FAILED (both return `NO_WINDOW_PASSES_R2` instead of specific reason)

**Step 3: Implement priority-based reason tracking**

In `src/navi_fractal/_sandbox.py`, modify the window search section.

1. Replace the `best_reason` initialization (line ~192) and add a depth tracker:

```python
    best_reason: Reason = Reason.NO_WINDOW_PASSES_R2
    _reject_depth: int = -1
```

2. In the window loop, after the R² check passes but AICc check fails (line ~228-230), update tracking:

```python
            delta = aicc_exp - aicc_pw
            if delta < delta_power_win:
                if _reject_depth < 1:
                    best_reason = Reason.AICC_PREFERS_EXPONENTIAL
                    _reject_depth = 1
                continue
```

3. After the curvature guard check fails (line ~236-237), update tracking:

```python
            if curvature_guard:
                quad_sse = quadratic_fit_residual(wx, wy)
                aicc_quad = aicc(quad_sse, n_w, 3)
                if aicc_quad < aicc_pw - 6.0:
                    if _reject_depth < 2:
                        best_reason = Reason.CURVATURE_GUARD
                        _reject_depth = 2
                    continue
```

4. After the slope stability guard fails (line ~240-254), update tracking:

```python
            if slope_stability_guard and n_w >= 4:
                local_slopes: list[float] = []
                for i in range(n_w - 1):
                    dx = wx[i + 1] - wx[i]
                    if dx > 0:
                        local_slopes.append((wy[i + 1] - wy[i]) / dx)
                if local_slopes:
                    mean_slope = math.fsum(local_slopes) / len(local_slopes)
                    if mean_slope != 0.0:
                        slope_var = math.fsum(
                            (s - mean_slope) ** 2 for s in local_slopes
                        ) / len(local_slopes)
                        cv = math.sqrt(slope_var) / abs(mean_slope)
                        if cv > max_slope_range:
                            if _reject_depth < 3:
                                best_reason = Reason.SLOPE_STABILITY_GUARD
                                _reject_depth = 3
                            continue
```

5. When a window succeeds (line ~264), reset:

```python
                best_reason = Reason.ACCEPTED
                _reject_depth = 4  # Higher than any rejection
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ -v --benchmark-disable && uv run ruff check src/ tests/ && uv run mypy --strict src/navi_fractal/`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/navi_fractal/_sandbox.py tests/test_sandbox.py
git commit -m "fix: wire unreachable Reason codes into window search loop

Track the deepest rejection reason across all windows using priority-based
tracking. When no window passes, report the most specific failure cause
instead of the generic NO_WINDOW_PASSES_R2.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Implement min_delta_y filter

**Audit finding:** C4 (min_delta_y accepted but never used)

**Files:**
- Modify: `src/navi_fractal/_sandbox.py`
- Modify: `tests/test_sandbox.py`

**Context:** The `min_delta_y` parameter (default 0.5) is accepted but never checked. The design spec requires: reject windows where the response range in log-mass is less than `min_delta_y`. This prevents accepting windows that "fit well" only because they have almost no variation.

**Step 1: Write failing test**

Add to `tests/test_sandbox.py` in `TestSandboxRefusals`:

```python
def test_min_delta_y_refusal(self) -> None:
    """Forcing min_delta_y impossibly high should refuse all windows."""
    grid = make_grid_graph(30, 30)
    result = estimate_sandbox_dimension(grid, seed=42, min_delta_y=1e6)
    assert result.dimension is None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sandbox.py::TestSandboxRefusals::test_min_delta_y_refusal -v --benchmark-disable`
Expected: FAILED (dimension is not None because min_delta_y is never checked)

**Step 3: Implement min_delta_y filter**

In `src/navi_fractal/_sandbox.py`, in the window search loop, add the response range check right after the `min_log_span` check (after line ~204):

```python
            # Minimum response range in log-mass
            delta_y = wy[-1] - wy[0]
            if delta_y < min_delta_y:
                continue
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ -v --benchmark-disable && uv run ruff check src/ tests/ && uv run mypy --strict src/navi_fractal/`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/navi_fractal/_sandbox.py tests/test_sandbox.py
git commit -m "fix: implement min_delta_y filter in window search

Reject windows where log-mass response range is less than min_delta_y.
Prevents accepting windows with negligible variation that happen to
fit well.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Fix slope stability algorithm

**Audit finding:** C5 (point-to-point CV instead of sub-window OLS range; slope_stability_sub_len dead)

**Files:**
- Modify: `src/navi_fractal/_sandbox.py`
- Modify: `tests/test_sandbox.py`

**Context:** Design spec says: "Compute OLS slope on every contiguous sub-window of length `slope_stability_sub_len`. Collect all local slopes. `window_slope_range = max(local_slopes) - min(local_slopes)`. Refuse if `window_slope_range > max_slope_range`." Current code computes point-to-point slopes and their coefficient of variation — fundamentally wrong algorithm.

**Step 1: Write failing test**

Add to `tests/test_sandbox.py` in a new class:

```python
class TestSlopeStability:
    def test_sub_len_defaults_to_min_points(self) -> None:
        """slope_stability_sub_len=None should default to min_points."""
        grid = make_grid_graph(30, 30)
        # With default sub_len (None → min_points=6) and generous range → should pass
        result = estimate_sandbox_dimension(
            grid,
            seed=42,
            slope_stability_guard=True,
            max_slope_range=10.0,
        )
        assert result.dimension is not None

    def test_custom_sub_len_used(self) -> None:
        """Custom slope_stability_sub_len should be used instead of min_points."""
        grid = make_grid_graph(30, 30)
        # Very short sub-windows with very tight range → should refuse
        result = estimate_sandbox_dimension(
            grid,
            seed=42,
            slope_stability_guard=True,
            slope_stability_sub_len=3,
            max_slope_range=0.001,
        )
        assert result.dimension is None
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sandbox.py::TestSlopeStability -v --benchmark-disable`
Expected: FAILED (slope_stability_sub_len is ignored; algorithm uses CV not range)

**Step 3: Replace slope stability algorithm**

In `src/navi_fractal/_sandbox.py`, replace the entire slope stability guard block in the window loop with:

```python
            # Slope stability guard: sub-window OLS range
            if slope_stability_guard:
                sub_len = (
                    slope_stability_sub_len
                    if slope_stability_sub_len is not None
                    else min_points
                )
                if n_w >= sub_len >= 2:
                    local_slopes: list[float] = []
                    for sub_start in range(n_w - sub_len + 1):
                        sub_x = wx[sub_start : sub_start + sub_len]
                        sub_y = wy[sub_start : sub_start + sub_len]
                        sub_fit = ols(sub_x, sub_y)
                        local_slopes.append(sub_fit.slope)
                    if len(local_slopes) >= 2:
                        slope_range = max(local_slopes) - min(local_slopes)
                        if slope_range > max_slope_range:
                            if _reject_depth < 3:
                                best_reason = Reason.SLOPE_STABILITY_GUARD
                                _reject_depth = 3
                            continue
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ -v --benchmark-disable && uv run ruff check src/ tests/ && uv run mypy --strict src/navi_fractal/`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/navi_fractal/_sandbox.py tests/test_sandbox.py
git commit -m "fix: replace slope stability CV with sub-window OLS range

Per design spec: compute OLS slope on every contiguous sub-window of
length slope_stability_sub_len, reject if max - min > max_slope_range.
Also wires slope_stability_sub_len parameter (was dead code).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Fix bootstrap to respect use_wls

**Audit finding:** I5 (bootstrap always uses OLS regardless of use_wls)

**Files:**
- Modify: `src/navi_fractal/_sandbox.py`
- Modify: `tests/test_sandbox.py`

**Context:** Bootstrap resamples always call `ols()` even when `use_wls=True`. Should use same regression method as the primary fit for consistency.

**Step 1: Write failing test**

Add to `tests/test_sandbox.py` in `TestSandboxEstimation`:

```python
def test_bootstrap_runs_with_wls(self) -> None:
    """Bootstrap should work with both use_wls=True and use_wls=False."""
    grid = make_grid_graph(20, 20)
    result_wls = estimate_sandbox_dimension(
        grid, seed=42, bootstrap_reps=20, use_wls=True
    )
    result_ols = estimate_sandbox_dimension(
        grid, seed=42, bootstrap_reps=20, use_wls=False
    )
    if result_wls.dimension is not None:
        assert result_wls.bootstrap_ci is not None
    if result_ols.dimension is not None:
        assert result_ols.bootstrap_ci is not None
```

**Step 2: Run test to verify it passes (baseline)**

Run: `uv run pytest tests/test_sandbox.py::TestSandboxEstimation::test_bootstrap_runs_with_wls -v --benchmark-disable`
Expected: PASS (both run, but WLS path isn't actually using WLS — fix is still needed)

**Step 3: Implement WLS in bootstrap**

In `src/navi_fractal/_sandbox.py`, in the bootstrap section (lines ~301-329), modify the bootstrap fit to use WLS when `use_wls=True`.

Replace the bootstrap fit line (line ~322-323):

```python
            boot_x = log_radii[w_start:w_end]
            boot_ww = mass_variances[w_start:w_end]
            if len(boot_x) >= 2:
                if use_wls:
                    boot_inv_var = [1.0 / v for v in boot_ww]
                    boot_fit = wls(boot_x, boot_log_masses, boot_inv_var)
                else:
                    boot_fit = ols(boot_x, boot_log_masses)
                boot_slopes.append(boot_fit.slope)
```

Note: the bootstrap variance computation also needs to handle the WLS case. The bootstrap resamples centers and recomputes means. The original `mass_variances` from the primary estimation serve as reasonable weight proxies. For a more rigorous approach, recompute variances per bootstrap sample, but using the primary variances as fixed weights is acceptable and consistent.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ -v --benchmark-disable && uv run ruff check src/ tests/ && uv run mypy --strict src/navi_fractal/`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/navi_fractal/_sandbox.py tests/test_sandbox.py
git commit -m "fix: bootstrap respects use_wls setting

Bootstrap resamples now use WLS when use_wls=True, matching the
primary fit method for consistency.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 7: Add rng parameter to null model

**Audit finding:** I1 (null model missing rng parameter)

**Files:**
- Modify: `src/navi_fractal/_null_model.py`
- Modify: `tests/test_null_model.py`

**Step 1: Write failing test**

Add to `tests/test_null_model.py` in `TestRewiring`:

```python
import random

def test_rng_parameter_overrides_seed(self) -> None:
    """When rng is provided, it should be used instead of seed."""
    grid = make_grid_graph(10, 10)
    cg = compile_to_undirected_metric_graph(grid)
    rng = random.Random(42)
    rewired = degree_preserving_rewire_undirected(cg, seed=0, rng=rng)
    # Result should match seed=42, not seed=0
    rewired_seed42 = degree_preserving_rewire_undirected(cg, seed=42)
    rewired_seed0 = degree_preserving_rewire_undirected(cg, seed=0)
    assert rewired.adj == rewired_seed42.adj
    assert rewired.adj != rewired_seed0.adj
```

Add `import random` at the top of the test file.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_null_model.py::TestRewiring::test_rng_parameter_overrides_seed -v --benchmark-disable`
Expected: FAILED (TypeError: unexpected keyword argument 'rng')

**Step 3: Implement rng parameter**

In `src/navi_fractal/_null_model.py`, update the function signature (line ~18-24):

```python
def degree_preserving_rewire_undirected(
    cg: CompiledGraph,
    *,
    seed: int = 0,
    rng: random.Random | None = None,
    n_swaps: int | None = None,
    verify: bool = True,
) -> CompiledGraph:
```

And update the RNG initialization (line ~40):

```python
    if rng is None:
        rng = random.Random(seed)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/ -v --benchmark-disable && uv run ruff check src/ tests/ && uv run mypy --strict src/navi_fractal/`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/navi_fractal/_null_model.py tests/test_null_model.py
git commit -m "feat: add rng parameter to degree_preserving_rewire_undirected

Optional random.Random instance overrides seed parameter, matching
the pattern used by estimate_sandbox_dimension for Monte Carlo
pipelines that manage their own RNG streams.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 8: Expand and rename SandboxResult fields

**Audit findings:** C1 (missing ~15 fields), C2 (field naming mismatches)

**Files:**
- Modify: `src/navi_fractal/_types.py`
- Modify: `src/navi_fractal/_sandbox.py`
- Modify: `src/navi_fractal/_quality_gate.py`
- Modify: `tests/test_sandbox.py`
- Modify: `tests/test_quality_gates.py`

**Context:** This is the largest single task. SandboxResult grows from 13 to 24 fields. Field renames cascade to quality gate and all tests. This is a coordinated migration, not TDD — all changes must happen atomically for tests to pass.

**Step 1: Add ModelPreference type alias to `_types.py`**

Add after the imports in `src/navi_fractal/_types.py`:

```python
from typing import Literal

ModelPreference = Literal["powerlaw", "none"]
```

**Step 2: Rewrite SandboxResult in `_sandbox.py`**

Replace the entire `SandboxResult` class with:

```python
@dataclass(frozen=True)
class SandboxResult:
    """Result of sandbox dimension estimation.

    Two-tier access:
    - Quick: result.summary() → DimensionSummary (5 fields, stable contract)
    - Full: access fields directly for audit trail and reproducibility
    """

    # Dimension estimate
    dimension: float | None
    reason: Reason
    reason_detail: str | None

    # Model selection
    model_preference: ModelPreference
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

    # Confidence interval
    dimension_ci: tuple[float, float] | None

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
    notes: str | None

    def summary(self) -> DimensionSummary:
        """Return a lightweight summary for downstream consumers."""
        return DimensionSummary(
            dimension=self.dimension,
            accepted=self.dimension is not None,
            reason=self.reason,
            r2=self.powerlaw_fit.r2 if self.powerlaw_fit is not None else None,
            ci=self.dimension_ci,
        )
```

Add the import at the top of `_sandbox.py`:

```python
from navi_fractal._types import DimensionSummary, LinFit, ModelPreference, Reason
```

**Step 3: Rewrite `_make_empty_result`**

```python
def _make_empty_result(
    reason: Reason,
    *,
    n_centers: int,
    n_nodes_original: int,
    n_nodes_measured: int,
    seed: int,
    detail: str | None = None,
) -> SandboxResult:
    """Create a refused SandboxResult with empty diagnostics."""
    retained = n_nodes_measured / n_nodes_original if n_nodes_original > 0 else 0.0
    return SandboxResult(
        dimension=None,
        reason=reason,
        reason_detail=detail,
        model_preference="none",
        delta_aicc=None,
        powerlaw_fit=None,
        exponential_fit=None,
        window_r_min=None,
        window_r_max=None,
        window_log_span=None,
        window_delta_y=None,
        window_slope_range=None,
        window_aicc_quad_minus_lin=None,
        dimension_ci=None,
        radii_eval=(),
        mean_mass_eval=(),
        y_eval=(),
        n_nodes_original=n_nodes_original,
        n_nodes_measured=n_nodes_measured,
        retained_fraction=retained,
        n_centers=n_centers,
        seed=seed,
        notes=None,
    )
```

**Step 4: Update `estimate_sandbox_dimension` construction sites**

This requires updating all call sites of `_make_empty_result` and all `SandboxResult(...)` constructions.

1. At the top of the function, track the seed:

```python
    _seed = seed  # Store for result metadata
```

2. Track original node count after compilation:

```python
    n_nodes_original = cg.n
```

3. Update all `empty_result(...)` calls to pass new required params. Example for EMPTY_GRAPH:

```python
    if cg.n == 0:
        return empty_result(
            Reason.EMPTY_GRAPH,
            n_centers=n_centers,
            n_nodes_original=0,
            n_nodes_measured=0,
            seed=_seed,
        )
```

4. After component selection, track measured node count:

```python
    n_nodes_measured = cg.n
    retained_fraction = n_nodes_measured / n_nodes_original if n_nodes_original > 0 else 0.0
```

5. In the aggregation loop, also track `radii_eval` and `mean_mass_eval`:

```python
    radii_eval: list[int] = []
    log_radii: list[float] = []
    mean_mass_eval: list[float] = []
    y_eval: list[float] = []
    mass_variances: list[float] = []

    for j, r in enumerate(radii):
        # ... existing filtering logic ...

        if mean_mode == "geometric":
            log_vals = [math.log(m) for m in col if m > 0]
            if not log_vals:
                continue
            mean_log = math.fsum(log_vals) / len(log_vals)
            var_log = (
                math.fsum((lv - mean_log) ** 2 for lv in log_vals) / len(log_vals)
                if len(log_vals) > 1
                else 0.0
            )
            radii_eval.append(r)
            log_radii.append(math.log(r))
            mean_mass_eval.append(math.exp(mean_log))
            y_eval.append(mean_log)
            mass_variances.append(max(var_log, variance_floor))
        else:  # arithmetic
            mean_m = math.fsum(col) / len(col)
            if mean_m <= 0:
                continue
            var_m = (
                math.fsum((m - mean_m) ** 2 for m in col) / len(col)
                if len(col) > 1
                else 0.0
            )
            radii_eval.append(r)
            log_radii.append(math.log(r))
            mean_mass_eval.append(mean_m)
            y_eval.append(math.log(mean_m))
            mass_variances.append(max(var_m / (mean_m * mean_m), variance_floor))
```

6. In the window loop, track additional diagnostics for the best window. Add tracking variables before the loop:

```python
    best_exp_fit: LinFit | None = None
    best_delta_aicc: float | None = None
    best_slope_range: float | None = None
    best_aicc_quad_minus_lin: float | None = None
```

In the window loop, when a window becomes the best, also save:

```python
            score = (log_span, fit.r2, -fit.slope_stderr)
            if score > best_score:
                best_score = score
                best_fit = fit
                best_window = (start, end)
                best_exp_fit = exp_fit
                best_delta_aicc = delta
                best_reason = Reason.ACCEPTED
                _reject_depth = 4
```

And track curvature diagnostic when computed:

```python
            if curvature_guard:
                quad_sse = quadratic_fit_residual(wx, wy)
                aicc_quad = aicc(quad_sse, n_w, 3)
                if aicc_quad < aicc_pw - 6.0:
                    # ... rejection tracking ...
                    continue
                # Track for best window candidate
                _current_aicc_quad_minus_lin = aicc_quad - aicc_pw
```

Save it when window becomes best:

```python
                best_aicc_quad_minus_lin = (
                    _current_aicc_quad_minus_lin if curvature_guard else None
                )
```

Track slope range similarly when slope stability is computed.

7. Update the NO_WINDOW result construction (lines ~266-281):

```python
    if best_fit is None or best_window is None:
        return SandboxResult(
            dimension=None,
            reason=best_reason,
            reason_detail=None,
            model_preference="none",
            delta_aicc=None,
            powerlaw_fit=None,
            exponential_fit=None,
            window_r_min=None,
            window_r_max=None,
            window_log_span=None,
            window_delta_y=None,
            window_slope_range=None,
            window_aicc_quad_minus_lin=None,
            dimension_ci=None,
            radii_eval=tuple(radii_eval),
            mean_mass_eval=tuple(mean_mass_eval),
            y_eval=tuple(y_eval),
            n_nodes_original=n_nodes_original,
            n_nodes_measured=n_nodes_measured,
            retained_fraction=retained_fraction,
            n_centers=actual_n_centers,
            seed=_seed,
            notes=None,
        )
```

8. Update the NEGATIVE_SLOPE result construction similarly.

9. Compute window metrics for the final success result:

```python
    w_start, w_end = best_window
    window_r_min_val = radii_eval[w_start]
    window_r_max_val = radii_eval[w_end - 1]
    window_log_span = math.log(window_r_max_val) - math.log(window_r_min_val)
    window_delta_y = y_eval[w_end - 1] - y_eval[w_start]
```

10. Update the final success result construction:

```python
    return SandboxResult(
        dimension=dimension,
        reason=Reason.ACCEPTED,
        reason_detail=None,
        model_preference="powerlaw",
        delta_aicc=best_delta_aicc,
        powerlaw_fit=best_fit,
        exponential_fit=best_exp_fit,
        window_r_min=window_r_min_val,
        window_r_max=window_r_max_val,
        window_log_span=window_log_span,
        window_delta_y=window_delta_y,
        window_slope_range=best_slope_range,
        window_aicc_quad_minus_lin=best_aicc_quad_minus_lin,
        dimension_ci=bootstrap_ci,
        radii_eval=tuple(radii_eval),
        mean_mass_eval=tuple(mean_mass_eval),
        y_eval=tuple(y_eval),
        n_nodes_original=n_nodes_original,
        n_nodes_measured=n_nodes_measured,
        retained_fraction=retained_fraction,
        n_centers=actual_n_centers,
        seed=_seed,
        notes=None,
    )
```

**Step 5: Update `_quality_gate.py`**

Replace field references:
- `result.fit` → `result.powerlaw_fit`
- `result.window_start` / `result.window_end` / `result.log_radii` radius ratio computation → direct `result.window_r_min` / `result.window_r_max`:

```python
    # Radius ratio check
    if result.window_r_min is not None and result.window_r_max is not None:
        if result.window_r_min > 0:
            ratio = result.window_r_max / result.window_r_min
            if ratio < ratio_threshold:
                return (
                    False,
                    QualityGateReason.RADIUS_RATIO_TOO_SMALL,
                    f"radius_ratio={ratio:.2f} < {ratio_threshold}",
                )
```

- `result.aicc_powerlaw` / `result.aicc_exponential` → `result.delta_aicc`:

```python
    # delta-AICc check
    if result.delta_aicc is not None:
        if result.delta_aicc < aicc_threshold:
            return (
                False,
                QualityGateReason.AICC_MARGIN_TOO_SMALL,
                f"delta_AICc={result.delta_aicc:.2f} < {aicc_threshold}",
            )
```

**Step 6: Update `tests/test_sandbox.py`**

Update `test_unknown_preset_raises` fake_result construction to use new field names:

```python
    def test_unknown_preset_raises(self) -> None:
        fake_fit = LinFit(
            slope=2.0, intercept=0.0, r2=0.99, slope_stderr=0.01, sse=0.001, n_points=10
        )
        fake_result = SandboxResult(
            dimension=2.0,
            reason=Reason.ACCEPTED,
            reason_detail=None,
            model_preference="powerlaw",
            delta_aicc=10.0,
            powerlaw_fit=fake_fit,
            exponential_fit=None,
            window_r_min=1,
            window_r_max=10,
            window_log_span=2.3,
            window_delta_y=1.5,
            window_slope_range=None,
            window_aicc_quad_minus_lin=None,
            dimension_ci=None,
            radii_eval=(),
            mean_mass_eval=(),
            y_eval=(),
            n_nodes_original=100,
            n_nodes_measured=100,
            retained_fraction=1.0,
            n_centers=100,
            seed=42,
            notes=None,
        )
        with pytest.raises(ValueError, match="Unknown preset"):
            sandbox_quality_gate(fake_result, preset="unknown")
```

Update field access in existing tests:
- `result.fit` → `result.powerlaw_fit`
- `result.bootstrap_ci` → `result.dimension_ci`
- `result.aicc_powerlaw` / `result.aicc_exponential` → `result.delta_aicc`

**Step 7: Run full check suite**

Run: `uv run pytest tests/ -v --benchmark-disable && uv run ruff check src/ tests/ && uv run mypy --strict src/navi_fractal/`
Expected: ALL PASS

**Step 8: Commit**

```bash
git add src/navi_fractal/_types.py src/navi_fractal/_sandbox.py src/navi_fractal/_quality_gate.py tests/test_sandbox.py tests/test_quality_gates.py
git commit -m "feat: expand SandboxResult to full audit trail per design spec

Grows from 13 to 24 fields per navi-fractal-design-v2:
- Renames: fit→powerlaw_fit, bootstrap_ci→dimension_ci,
  window_start/end→window_r_min/r_max, radii→radii_eval,
  log_masses→y_eval, aicc_powerlaw/exponential→delta_aicc
- Adds: model_preference, exponential_fit, window_log_span,
  window_delta_y, window_slope_range, window_aicc_quad_minus_lin,
  mean_mass_eval, n_nodes_original, n_nodes_measured,
  retained_fraction, seed, notes
- Updates quality gate and all tests for new field names

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 9: Add known geometry and refusal path tests

**Audit findings:** C6 (7/9 refusal paths untested), C7 (Star S50 missing), C8 (rewired grid missing), I7 (test bounds loose)

**Files:**
- Create: `tests/test_known_dimensions.py`
- Modify: `tests/test_sandbox.py`
- Modify: `tests/conftest.py`

**Step 1: Add fixtures**

Add to `tests/conftest.py`:

```python
@pytest.fixture
def star_graph() -> Graph:
    """Star graph S_50: central node connected to 50 leaves."""
    g = Graph()
    for i in range(1, 51):
        g.add_edge(0, i)
    return g


@pytest.fixture
def large_grid() -> Graph:
    """50x50 grid for null model comparison."""
    return make_grid_graph(50, 50)
```

**Step 2: Create `tests/test_known_dimensions.py`**

```python
# SPDX-License-Identifier: Apache-2.0
"""Known geometry dimension tests per design spec section 1."""

from __future__ import annotations

from navi_fractal import (
    Graph,
    Reason,
    compile_to_undirected_metric_graph,
    degree_preserving_rewire_undirected,
    estimate_sandbox_dimension,
    make_grid_graph,
    make_path_graph,
)


class TestKnownGeometries:
    def test_grid_30x30_dimension_near_2(self) -> None:
        grid = make_grid_graph(30, 30)
        result = estimate_sandbox_dimension(grid, seed=42)
        assert result.dimension is not None
        assert result.reason == Reason.ACCEPTED
        assert 1.8 <= result.dimension <= 2.2, f"D={result.dimension}"
        assert result.powerlaw_fit is not None
        assert result.powerlaw_fit.r2 > 0.95

    def test_path_100_dimension_near_1(self) -> None:
        path = make_path_graph(100)
        result = estimate_sandbox_dimension(path, seed=42)
        assert result.dimension is not None
        assert result.reason == Reason.ACCEPTED
        assert 0.8 <= result.dimension <= 1.2, f"D={result.dimension}"

    def test_complete_k50_refused(self) -> None:
        g = Graph()
        for u in range(50):
            for v in range(u + 1, 50):
                g.add_edge(u, v)
        result = estimate_sandbox_dimension(g, seed=42)
        assert result.dimension is None
        assert result.reason in (Reason.NO_VALID_RADII, Reason.TRIVIAL_GRAPH)

    def test_star_s50_refused(self) -> None:
        g = Graph()
        for i in range(1, 51):
            g.add_edge(0, i)
        result = estimate_sandbox_dimension(g, seed=42)
        assert result.dimension is None

    def test_rewired_grid_50x50_degraded(self) -> None:
        """Rewiring should degrade at least one dimension quality metric."""
        grid = make_grid_graph(50, 50)
        cg = compile_to_undirected_metric_graph(grid)

        original = estimate_sandbox_dimension(cg, seed=42)
        rewired = degree_preserving_rewire_undirected(cg, seed=99)
        rewired_result = estimate_sandbox_dimension(rewired, seed=42)

        # At least one of these should change
        degraded = False

        # Dimension changed significantly
        if original.dimension is not None and rewired_result.dimension is not None:
            if abs(original.dimension - rewired_result.dimension) > 0.1:
                degraded = True

        # Reason changed (accepted → refused or vice versa)
        if original.reason != rewired_result.reason:
            degraded = True

        # Delta AICc dropped
        if original.delta_aicc is not None and rewired_result.delta_aicc is not None:
            if rewired_result.delta_aicc < original.delta_aicc:
                degraded = True

        # R² dropped
        if original.powerlaw_fit is not None and rewired_result.powerlaw_fit is not None:
            if rewired_result.powerlaw_fit.r2 < original.powerlaw_fit.r2:
                degraded = True

        assert degraded, (
            f"Rewiring should degrade dimension quality. "
            f"Original: D={original.dimension}, R²={original.powerlaw_fit.r2 if original.powerlaw_fit else None}. "
            f"Rewired: D={rewired_result.dimension}, R²={rewired_result.powerlaw_fit.r2 if rewired_result.powerlaw_fit else None}."
        )
```

**Step 3: Add remaining refusal path tests to `tests/test_sandbox.py`**

Add to `TestSandboxRefusals`:

```python
def test_no_valid_radii_refusal(self, star_graph: Graph) -> None:
    """Star graph should have too few radii for any window."""
    result = estimate_sandbox_dimension(star_graph, seed=42)
    assert result.dimension is None
    # Star has diameter 2 → very few radii → should be NO_VALID_RADII or TRIVIAL
    assert result.reason in (Reason.NO_VALID_RADII, Reason.TRIVIAL_GRAPH)

def test_negative_slope_refusal(self) -> None:
    """NEGATIVE_SLOPE is tested indirectly: verify require_positive_slope param works."""
    grid = make_grid_graph(30, 30)
    # With require_positive_slope=False, a grid should still get accepted
    result = estimate_sandbox_dimension(grid, seed=42, require_positive_slope=False)
    assert result.dimension is not None
    # With require_positive_slope=True (default), same grid is accepted (positive slope)
    result2 = estimate_sandbox_dimension(grid, seed=42, require_positive_slope=True)
    assert result2.dimension is not None
    # Note: NEGATIVE_SLOPE is extremely hard to trigger with natural graphs because
    # BFS ball mass is monotonically non-decreasing. The flag is a safety guard.
```

**Step 4: Run tests**

Run: `uv run pytest tests/ -v --benchmark-disable && uv run ruff check src/ tests/ && uv run mypy --strict src/navi_fractal/`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add tests/test_known_dimensions.py tests/test_sandbox.py tests/conftest.py
git commit -m "test: add known geometry and refusal path coverage

- Grid 30x30 D ∈ [1.8, 2.2] with R² > 0.95
- Path 100 D ∈ [0.8, 1.2]
- Complete K50 refused
- Star S50 refused
- Rewired grid 50x50 shows degradation
- NO_VALID_RADII via star graph
- NEGATIVE_SLOPE flag verification

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 10: Add determinism and quality gate override tests

**Audit findings:** C9 (quality gate overrides untested), spec section 3 (determinism), spec section 4 (gate tests)

**Files:**
- Create: `tests/test_determinism.py`
- Modify: `tests/test_quality_gates.py`

**Step 1: Create `tests/test_determinism.py`**

```python
# SPDX-License-Identifier: Apache-2.0
"""Determinism tests: identical results across runs with same seed."""

from __future__ import annotations

from navi_fractal import (
    estimate_sandbox_dimension,
    make_grid_graph,
)

FLOAT_ATOL_SAME_PLATFORM = 1e-12


class TestDeterminism:
    def test_structural_fields_identical(self) -> None:
        """Structural fields must be exactly equal across runs."""
        grid = make_grid_graph(30, 30)
        r1 = estimate_sandbox_dimension(grid, seed=42)
        r2 = estimate_sandbox_dimension(grid, seed=42)

        assert r1.reason == r2.reason
        assert r1.model_preference == r2.model_preference
        assert r1.window_r_min == r2.window_r_min
        assert r1.window_r_max == r2.window_r_max
        assert r1.radii_eval == r2.radii_eval
        assert r1.n_centers == r2.n_centers
        assert r1.n_nodes_original == r2.n_nodes_original
        assert r1.n_nodes_measured == r2.n_nodes_measured

    def test_float_fields_within_tolerance(self) -> None:
        """Float fields must match within platform tolerance."""
        grid = make_grid_graph(30, 30)
        r1 = estimate_sandbox_dimension(grid, seed=42)
        r2 = estimate_sandbox_dimension(grid, seed=42)

        assert r1.dimension is not None
        assert r2.dimension is not None
        assert abs(r1.dimension - r2.dimension) < FLOAT_ATOL_SAME_PLATFORM
        assert r1.powerlaw_fit is not None
        assert r2.powerlaw_fit is not None
        assert abs(r1.powerlaw_fit.r2 - r2.powerlaw_fit.r2) < FLOAT_ATOL_SAME_PLATFORM
        assert (
            abs(r1.powerlaw_fit.slope_stderr - r2.powerlaw_fit.slope_stderr)
            < FLOAT_ATOL_SAME_PLATFORM
        )

    def test_different_seeds_differ(self) -> None:
        """Different seeds should produce different center selections."""
        grid = make_grid_graph(30, 30)
        r1 = estimate_sandbox_dimension(grid, seed=1)
        r2 = estimate_sandbox_dimension(grid, seed=2)
        # At least the raw evaluation data should differ
        assert r1.y_eval != r2.y_eval or r1.dimension != r2.dimension
```

**Step 2: Expand `tests/test_quality_gates.py`**

Replace the file content with:

```python
# SPDX-License-Identifier: Apache-2.0
"""Tests for quality gate presets, overrides, and detail strings."""

from __future__ import annotations

import pytest

from navi_fractal import (
    LinFit,
    QualityGateReason,
    Reason,
    SandboxResult,
    estimate_sandbox_dimension,
    make_grid_graph,
    sandbox_quality_gate,
)


def _make_accepted_result(
    *,
    r2: float = 0.99,
    slope_stderr: float = 0.01,
    window_r_min: int = 1,
    window_r_max: int = 10,
    delta_aicc: float = 10.0,
) -> SandboxResult:
    """Helper: build a synthetic accepted SandboxResult for gate testing."""
    fit = LinFit(
        slope=2.0, intercept=0.0, r2=r2, slope_stderr=slope_stderr,
        sse=0.001, n_points=10,
    )
    return SandboxResult(
        dimension=2.0,
        reason=Reason.ACCEPTED,
        reason_detail=None,
        model_preference="powerlaw",
        delta_aicc=delta_aicc,
        powerlaw_fit=fit,
        exponential_fit=None,
        window_r_min=window_r_min,
        window_r_max=window_r_max,
        window_log_span=2.3,
        window_delta_y=1.5,
        window_slope_range=None,
        window_aicc_quad_minus_lin=None,
        dimension_ci=None,
        radii_eval=(),
        mean_mass_eval=(),
        y_eval=(),
        n_nodes_original=100,
        n_nodes_measured=100,
        retained_fraction=1.0,
        n_centers=100,
        seed=42,
        notes=None,
    )


class TestPresets:
    def test_inclusive_accepts_grid(self) -> None:
        grid = make_grid_graph(30, 30)
        result = estimate_sandbox_dimension(grid, seed=42)
        passed, qg_reason, detail = sandbox_quality_gate(result, preset="inclusive")
        assert passed, detail
        assert qg_reason == QualityGateReason.PASSED

    def test_strict_more_selective(self) -> None:
        grid = make_grid_graph(30, 30)
        result = estimate_sandbox_dimension(grid, seed=42)
        inc_passed, _, _ = sandbox_quality_gate(result, preset="inclusive")
        strict_passed, _, _ = sandbox_quality_gate(result, preset="strict")
        if strict_passed:
            assert inc_passed

    def test_refused_result_returns_not_accepted(self) -> None:
        from navi_fractal import Graph

        result = estimate_sandbox_dimension(Graph(), seed=42)
        passed, reason, detail = sandbox_quality_gate(result)
        assert not passed
        assert reason == QualityGateReason.NOT_ACCEPTED
        assert detail is not None

    def test_unknown_preset_raises(self) -> None:
        result = _make_accepted_result()
        with pytest.raises(ValueError, match="Unknown preset"):
            sandbox_quality_gate(result, preset="unknown")


class TestParameterOverrides:
    def test_r2_override(self) -> None:
        result = _make_accepted_result(r2=0.90)
        passed, reason, detail = sandbox_quality_gate(result, preset="inclusive", r2_min=0.95)
        assert not passed
        assert reason == QualityGateReason.R2_TOO_LOW
        assert detail is not None
        assert "0.90" in detail

    def test_stderr_override(self) -> None:
        result = _make_accepted_result(slope_stderr=0.30)
        passed, reason, detail = sandbox_quality_gate(
            result, preset="inclusive", stderr_max=0.10
        )
        assert not passed
        assert reason == QualityGateReason.STDERR_TOO_HIGH
        assert detail is not None
        assert "0.30" in detail or "0.3" in detail

    def test_radius_ratio_override(self) -> None:
        result = _make_accepted_result(window_r_min=3, window_r_max=6)
        passed, reason, detail = sandbox_quality_gate(
            result, preset="inclusive", radius_ratio_min=5.0
        )
        assert not passed
        assert reason == QualityGateReason.RADIUS_RATIO_TOO_SMALL
        assert detail is not None

    def test_aicc_override(self) -> None:
        result = _make_accepted_result(delta_aicc=2.0)
        passed, reason, detail = sandbox_quality_gate(
            result, preset="inclusive", aicc_min=5.0
        )
        assert not passed
        assert reason == QualityGateReason.AICC_MARGIN_TOO_SMALL
        assert detail is not None
        assert "2.0" in detail or "2.00" in detail


class TestDetailStrings:
    def test_detail_contains_threshold(self) -> None:
        result = _make_accepted_result(r2=0.80)
        _, _, detail = sandbox_quality_gate(result, preset="inclusive")
        assert detail is not None
        assert "0.85" in detail  # inclusive R² threshold
```

**Step 3: Run tests**

Run: `uv run pytest tests/ -v --benchmark-disable && uv run ruff check src/ tests/ && uv run mypy --strict src/navi_fractal/`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add tests/test_determinism.py tests/test_quality_gates.py
git commit -m "test: add determinism tests and quality gate override coverage

- Determinism: structural equality, float tolerance, seed variation
- Quality gate: parameter overrides (r2, stderr, ratio, aicc),
  detail string content, refused result → NOT_ACCEPTED

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 11: Add benchmarks for 100x100 and 300x300 grids

**Audit finding:** I9 (missing benchmark sizes)

**Files:**
- Modify: `tests/test_benchmark.py`

**Step 1: Add benchmarks**

Append to `tests/test_benchmark.py`:

```python
@pytest.fixture
def grid_100x100_compiled():  # type: ignore[no-untyped-def]
    g = make_grid_graph(100, 100)
    return compile_to_undirected_metric_graph(g)


@pytest.fixture
def grid_300x300_compiled():  # type: ignore[no-untyped-def]
    g = make_grid_graph(300, 300)
    return compile_to_undirected_metric_graph(g)


class TestLargeBenchmarks:
    def test_sandbox_100x100(self, benchmark, grid_100x100_compiled) -> None:  # type: ignore[no-untyped-def]
        benchmark.pedantic(
            estimate_sandbox_dimension,
            args=(grid_100x100_compiled,),
            kwargs={"seed": 42, "n_centers": 64, "bootstrap_reps": 0},
            rounds=3,
            iterations=1,
        )

    def test_sandbox_300x300(self, benchmark, grid_300x300_compiled) -> None:  # type: ignore[no-untyped-def]
        benchmark.pedantic(
            estimate_sandbox_dimension,
            args=(grid_300x300_compiled,),
            kwargs={"seed": 42, "n_centers": 64, "bootstrap_reps": 0},
            rounds=1,
            iterations=1,
        )
```

**Step 2: Run benchmarks**

Run: `uv run pytest tests/test_benchmark.py -v`
Expected: ALL PASS (benchmark output shows timing)

**Step 3: Run full test suite (without benchmarks)**

Run: `uv run pytest tests/ -v --benchmark-disable && uv run ruff check src/ tests/ && uv run mypy --strict src/navi_fractal/`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add tests/test_benchmark.py
git commit -m "test: add 100x100 and 300x300 grid benchmarks

Per design spec: benchmark at 10K and 90K nodes with pedantic mode.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Notes

### Hard-to-test refusal paths

Two refusal paths are extremely difficult to trigger with natural graphs:

- **CURVATURE_GUARD** — Requires a graph where quadratic log-log fits significantly better than linear. Most regular geometries produce approximately linear log-log relationships. May need a multi-scale graph (e.g., a graph that transitions between dimensions at different scales). If a natural construction cannot be found, a comment in the test file should document this.

- **NEGATIVE_SLOPE** — BFS ball mass is monotonically non-decreasing, so the OLS/WLS slope in log-log space is always non-negative for natural graphs. This is a safety guard for edge cases. Task 9 tests the `require_positive_slope` parameter works correctly in both directions.

### Post-implementation verification

After all 11 tasks complete, verify:

```bash
uv run pytest tests/ -v --benchmark-disable    # All tests pass
uv run ruff check src/ tests/                   # Lint clean
uv run ruff format --check src/ tests/          # Format clean
uv run mypy --strict src/navi_fractal/          # Type check clean
uv run bandit -r src/ -c pyproject.toml         # Security clean
```

### Remaining audit MINOR findings (not addressed in this plan)

- M1: Stale docstring parameter names — will be fixed naturally by Task 8
- M2: `_radius_index_for_log` O(n) scan — low priority, correct behavior
- M3: No `__repr__` on SandboxResult — deferred (frozen dataclass has adequate default)
- M4: `auto_radii` return type annotation — trivial fix, can be done opportunistically
- M5: `DimensionSummary.__eq__` float equality — inherent to dataclass design
- M6: No smoke test for `__all__` completeness — nice-to-have, not critical
