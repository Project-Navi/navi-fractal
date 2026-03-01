# Scaffold Refactoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align v0.1.0 scaffold with the v2 design spec — enums, module extraction, parameter renames — so implementation work starts on a clean foundation.

**Architecture:** Bottom-up migration. Create `_types.py` (shared types, no internal deps), then update each consumer module in dependency order. Each task produces a green commit.

**Tech Stack:** Python 3.12+, stdlib only. pytest, ruff, mypy --strict.

---

### Task 1: Create `_types.py` with `Reason` and `QualityGateReason` enums

**Files:**
- Create: `src/navi_fractal/_types.py`
- Test: `tests/test_types.py` (new — verify enum members exist)

**Step 1: Write the failing test**

Create `tests/test_types.py`:

```python
# SPDX-License-Identifier: Apache-2.0
"""Tests for shared type definitions."""

from __future__ import annotations

from navi_fractal._types import QualityGateReason, Reason


class TestReasonEnum:
    def test_all_members_exist(self) -> None:
        expected = {
            "ACCEPTED",
            "EMPTY_GRAPH",
            "TRIVIAL_GRAPH",
            "GIANT_COMPONENT_TOO_SMALL",
            "NO_VALID_RADII",
            "NO_WINDOW_PASSES_R2",
            "AICC_PREFERS_EXPONENTIAL",
            "CURVATURE_GUARD",
            "SLOPE_STABILITY_GUARD",
            "NEGATIVE_SLOPE",
        }
        actual = {m.name for m in Reason}
        assert actual == expected

    def test_reason_is_enum(self) -> None:
        assert isinstance(Reason.ACCEPTED, Reason)


class TestQualityGateReasonEnum:
    def test_all_members_exist(self) -> None:
        expected = {
            "PASSED",
            "NOT_ACCEPTED",
            "R2_TOO_LOW",
            "STDERR_TOO_HIGH",
            "RADIUS_RATIO_TOO_SMALL",
            "AICC_MARGIN_TOO_SMALL",
        }
        actual = {m.name for m in QualityGateReason}
        assert actual == expected
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_types.py -v --benchmark-disable`
Expected: FAIL — `ModuleNotFoundError: No module named 'navi_fractal._types'`

**Step 3: Write the implementation**

Create `src/navi_fractal/_types.py`:

```python
# SPDX-License-Identifier: Apache-2.0
"""Shared types: enums, dataclasses, and regression results.

All public-facing type definitions live here to avoid circular imports
and keep the API surface explicit.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class Reason(enum.Enum):
    """Reason code for sandbox dimension estimation outcome.

    ACCEPTED means a credible scaling window was found.
    All other values are refusal reasons (dimension will be None).
    """

    ACCEPTED = "accepted"
    EMPTY_GRAPH = "empty_graph"
    TRIVIAL_GRAPH = "trivial_graph"
    GIANT_COMPONENT_TOO_SMALL = "giant_component_too_small"
    NO_VALID_RADII = "no_valid_radii"
    NO_WINDOW_PASSES_R2 = "no_window_passes_r2"
    AICC_PREFERS_EXPONENTIAL = "aicc_prefers_exponential"
    CURVATURE_GUARD = "curvature_guard"
    SLOPE_STABILITY_GUARD = "slope_stability_guard"
    NEGATIVE_SLOPE = "negative_slope"


class QualityGateReason(enum.Enum):
    """Reason code for quality gate outcome.

    Separate from Reason: "the instrument couldn't measure" vs
    "the measurement wasn't good enough for your policy."
    """

    PASSED = "passed"
    NOT_ACCEPTED = "not_accepted"
    R2_TOO_LOW = "r2_too_low"
    STDERR_TOO_HIGH = "stderr_too_high"
    RADIUS_RATIO_TOO_SMALL = "radius_ratio_too_small"
    AICC_MARGIN_TOO_SMALL = "aicc_margin_too_small"


@dataclass(frozen=True)
class LinFit:
    """Result of a linear regression fit."""

    slope: float
    intercept: float
    r2: float
    slope_stderr: float
    sse: float
    n_points: int


@dataclass(frozen=True)
class DimensionSummary:
    """Lightweight summary of a sandbox dimension result.

    Stable public contract — will not grow. Use SandboxResult for full audit trail.
    """

    dimension: float | None
    accepted: bool
    reason: Reason
    r2: float | None
    ci: tuple[float, float] | None
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_types.py -v --benchmark-disable`
Expected: PASS

**Step 5: Run full suite to confirm nothing broke**

Run: `uv run pytest tests/ -v --benchmark-disable`
Expected: All 66 tests PASS (new module has no consumers yet)

**Step 6: Lint and type check**

Run: `uv run ruff check src/navi_fractal/_types.py tests/test_types.py && uv run mypy --strict src/navi_fractal/_types.py`
Expected: Clean

**Step 7: Commit**

```bash
git add src/navi_fractal/_types.py tests/test_types.py
git commit -m "refactor: add _types module with Reason, QualityGateReason, LinFit, DimensionSummary"
```

---

### Task 2: Move `LinFit` from `_regression.py` to `_types.py`

**Files:**
- Modify: `src/navi_fractal/_regression.py` (remove LinFit class, add import from _types)
- Modify: `src/navi_fractal/_sandbox.py` (update import path)
- Modify: `src/navi_fractal/__init__.py` (import LinFit from _types instead of _regression)

**Step 1: Update `_regression.py`**

Remove the `LinFit` dataclass (lines 13-22) and the `from dataclasses import dataclass` import. Add:

```python
from navi_fractal._types import LinFit
```

Keep the existing `ols`, `wls`, `aicc`, `quadratic_fit_residual` functions unchanged. They already use `LinFit` as a return type.

**Step 2: Update `_sandbox.py` import**

Change line 18 from:
```python
from navi_fractal._regression import LinFit, aicc, ols, quadratic_fit_residual, wls
```
to:
```python
from navi_fractal._regression import aicc, ols, quadratic_fit_residual, wls
from navi_fractal._types import LinFit
```

**Step 3: Update `__init__.py`**

Change line 16 from:
```python
from navi_fractal._regression import LinFit
```
to:
```python
from navi_fractal._types import LinFit
```

**Step 4: Run full suite**

Run: `uv run pytest tests/ -v --benchmark-disable`
Expected: All tests PASS — `LinFit` is the same class, just imported from a new location.

Note: `tests/test_sandbox.py:89` imports `from navi_fractal._regression import LinFit` — this still works because `_regression.py` re-exports it via its own import.

**Step 5: Lint and type check**

Run: `uv run ruff check src/ tests/ && uv run mypy --strict src/navi_fractal/`
Expected: Clean

**Step 6: Commit**

```bash
git add src/navi_fractal/_regression.py src/navi_fractal/_sandbox.py src/navi_fractal/__init__.py
git commit -m "refactor: move LinFit to _types module"
```

---

### Task 3: Create `_helpers.py` — move `make_grid_graph`, add `make_path_graph`

**Files:**
- Create: `src/navi_fractal/_helpers.py`
- Modify: `src/navi_fractal/_graph.py` (remove `make_grid_graph`)
- Modify: `src/navi_fractal/__init__.py` (import from `_helpers`)
- Modify: `tests/conftest.py` (path_graph fixture will use `make_path_graph`)
- Create: `tests/test_helpers.py` (test `make_path_graph`)

**Step 1: Write the failing test for `make_path_graph`**

Create `tests/test_helpers.py`:

```python
# SPDX-License-Identifier: Apache-2.0
"""Tests for helper graph constructors."""

from __future__ import annotations

import pytest

from navi_fractal import make_grid_graph, make_path_graph


class TestMakePathGraph:
    def test_node_count(self) -> None:
        g = make_path_graph(10)
        assert len(g) == 10

    def test_edge_count(self) -> None:
        g = make_path_graph(10)
        edges = sum(len(neighbors) for neighbors in g.adj.values()) // 2
        assert edges == 9  # n-1 edges

    def test_endpoints_degree_1(self) -> None:
        g = make_path_graph(5)
        degrees = sorted(len(neighbors) for neighbors in g.adj.values())
        assert degrees[0] == 1  # endpoint
        assert degrees[-1] == 2  # interior

    def test_single_node(self) -> None:
        g = make_path_graph(1)
        assert len(g) == 1

    def test_invalid_size(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            make_path_graph(0)
        with pytest.raises(ValueError, match="positive"):
            make_path_graph(-1)


class TestMakeGridGraphImport:
    """Verify make_grid_graph still works after moving to _helpers."""

    def test_grid_still_works(self) -> None:
        g = make_grid_graph(3, 3)
        assert len(g) == 9
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_helpers.py -v --benchmark-disable`
Expected: FAIL — `ImportError: cannot import name 'make_path_graph'`

**Step 3: Create `_helpers.py`**

```python
# SPDX-License-Identifier: Apache-2.0
"""Helper graph constructors: grids, paths, and other standard topologies."""

from __future__ import annotations

from navi_fractal._graph import Graph


def make_grid_graph(rows: int, cols: int) -> Graph:
    """Create a 2D grid graph with rows * cols nodes.

    Nodes are labeled as (row, col) tuples.
    """
    if rows <= 0 or cols <= 0:
        raise ValueError(f"Grid dimensions must be positive, got {rows}x{cols}")
    g = Graph()
    for r in range(rows):
        for c in range(cols):
            g.add_node((r, c))
            if r > 0:
                g.add_edge((r, c), (r - 1, c))
            if c > 0:
                g.add_edge((r, c), (r, c - 1))
    return g


def make_path_graph(n: int) -> Graph:
    """Create a path graph with n nodes.

    Nodes are labeled as integers 0..n-1.
    """
    if n <= 0:
        raise ValueError(f"Path length must be positive, got {n}")
    g = Graph()
    for i in range(n):
        g.add_node(i)
        if i > 0:
            g.add_edge(i, i - 1)
    return g
```

**Step 4: Remove `make_grid_graph` from `_graph.py`**

Delete lines 86-101 from `src/navi_fractal/_graph.py` (the `make_grid_graph` function).

**Step 5: Update `__init__.py`**

Change the graph imports from:
```python
from navi_fractal._graph import (
    CompiledGraph,
    Graph,
    compile_to_undirected_metric_graph,
    make_grid_graph,
)
```
to:
```python
from navi_fractal._graph import (
    CompiledGraph,
    Graph,
    compile_to_undirected_metric_graph,
)
from navi_fractal._helpers import make_grid_graph, make_path_graph
```

Add `"make_path_graph"` to `__all__`.

**Step 6: Update `tests/conftest.py`**

Update the `path_graph` fixture to use `make_path_graph`:

```python
from navi_fractal import (
    CompiledGraph,
    Graph,
    compile_to_undirected_metric_graph,
    make_grid_graph,
    make_path_graph,
)

# ... keep small_grid, compiled_small_grid, medium_grid, complete_graph,
# empty_graph, single_node_graph fixtures unchanged ...

@pytest.fixture
def path_graph() -> Graph:
    """Path graph with 100 nodes."""
    return make_path_graph(100)
```

**Step 7: Move grid graph tests from `test_graph.py` to `test_helpers.py`**

Move the `TestMakeGridGraph` class (lines 85-100 of `test_graph.py`) into `test_helpers.py`. Remove it from `test_graph.py` and update imports in `test_graph.py` to remove `make_grid_graph`.

Updated `test_graph.py` imports:
```python
from navi_fractal import (
    Graph,
    compile_to_undirected_metric_graph,
)
```

Add to `test_helpers.py`:
```python
class TestMakeGridGraph:
    def test_grid_node_count(self) -> None:
        g = make_grid_graph(3, 4)
        assert len(g) == 12

    def test_grid_edge_count(self) -> None:
        g = make_grid_graph(3, 4)
        edges = sum(len(neighbors) for neighbors in g.adj.values()) // 2
        assert edges == 17

    def test_grid_invalid_dimensions(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            make_grid_graph(0, 5)
        with pytest.raises(ValueError, match="positive"):
            make_grid_graph(3, -1)
```

(Remove the duplicate `TestMakeGridGraphImport` class — it's subsumed by the moved tests.)

**Step 8: Run full suite**

Run: `uv run pytest tests/ -v --benchmark-disable`
Expected: All tests PASS

**Step 9: Lint and type check**

Run: `uv run ruff check src/ tests/ && uv run mypy --strict src/navi_fractal/`
Expected: Clean

**Step 10: Commit**

```bash
git add src/navi_fractal/_helpers.py src/navi_fractal/_graph.py src/navi_fractal/__init__.py tests/conftest.py tests/test_helpers.py tests/test_graph.py
git commit -m "refactor: extract helpers module, add make_path_graph"
```

---

### Task 4: Migrate `SandboxResult` to use `Reason` enum and add `reason_detail`

**Files:**
- Modify: `src/navi_fractal/_sandbox.py` (SandboxResult, all reason strings, _make_empty_result)
- Modify: `tests/test_sandbox.py` (all reason assertions)
- Modify: `tests/test_known_dimensions.py` (reason in assertion messages)
- Modify: `tests/test_determinism.py` (reason field comparison)

**Step 1: Update `SandboxResult` dataclass in `_sandbox.py`**

Replace the current dataclass (lines 23-41) with:

```python
@dataclass(frozen=True)
class SandboxResult:
    """Result of sandbox dimension estimation.

    If dimension is None, the estimation was refused. Check reason for why.
    """

    dimension: float | None
    reason: Reason
    reason_detail: str | None
    fit: LinFit | None
    radii: tuple[int, ...]
    log_radii: tuple[float, ...]
    log_masses: tuple[float, ...]
    window_start: int | None
    window_end: int | None
    n_centers: int
    bootstrap_ci: tuple[float, float] | None
    aicc_powerlaw: float | None
    aicc_exponential: float | None

    def summary(self) -> DimensionSummary:
        """Return a lightweight summary for downstream consumers."""
        return DimensionSummary(
            dimension=self.dimension,
            accepted=self.dimension is not None,
            reason=self.reason,
            r2=self.fit.r2 if self.fit is not None else None,
            ci=self.bootstrap_ci,
        )
```

Add `Reason` and `DimensionSummary` to the imports from `_types`:
```python
from navi_fractal._types import DimensionSummary, LinFit, Reason
```

**Step 2: Update `_make_empty_result`**

Replace the function (lines 353-368) with:

```python
def _make_empty_result(reason: Reason, *, n_centers: int, detail: str | None = None) -> SandboxResult:
    """Create a refused SandboxResult with empty diagnostics."""
    return SandboxResult(
        dimension=None,
        reason=reason,
        reason_detail=detail,
        fit=None,
        radii=(),
        log_radii=(),
        log_masses=(),
        window_start=None,
        window_end=None,
        n_centers=n_centers,
        bootstrap_ci=None,
        aicc_powerlaw=None,
        aicc_exponential=None,
    )
```

**Step 3: Update all reason strings in `estimate_sandbox_dimension`**

| Line | Old | New |
|------|-----|-----|
| 78 | `"empty graph"` | `Reason.EMPTY_GRAPH` |
| 80 | `"single-node graph"` | `Reason.TRIVIAL_GRAPH` |
| 86 | `"giant component too small"` | `Reason.GIANT_COMPONENT_TOO_SMALL` |
| 91 | `"trivial diameter"` | `Reason.TRIVIAL_GRAPH`, detail=`"diameter <= 1"` |
| 96 | `"insufficient radii"` | `Reason.NO_VALID_RADII` |
| 152 | `"insufficient non-degenerate radii after filtering"` | `Reason.NO_VALID_RADII`, detail=`"insufficient non-degenerate radii after filtering"` |
| 171 | `"no window passed quality gates"` | `Reason.NO_WINDOW_PASSES_R2` |
| 243, 303 | `"accepted"` | `Reason.ACCEPTED` |

For the inline `SandboxResult(...)` construction at line 150 and 246, add `reason_detail=None` (or the relevant detail string).

For the accepted result at line 301, add `reason_detail=None`.

**Step 4: Update `tests/test_sandbox.py`**

Update imports:
```python
from navi_fractal import (
    Graph,
    Reason,
    estimate_sandbox_dimension,
    make_grid_graph,
    sandbox_quality_gate,
)
```

Update assertions:
- Line 20: `assert "empty" in result.reason` → `assert result.reason == Reason.EMPTY_GRAPH`
- Line 25: `assert "single" in result.reason` → `assert result.reason == Reason.TRIVIAL_GRAPH`
- Line 44: `assert result.reason == "accepted"` → `assert result.reason == Reason.ACCEPTED`

Update the fake SandboxResult in `test_unknown_preset_raises` (lines 96-108):
- `reason="accepted"` → `reason=Reason.ACCEPTED`
- Add `reason_detail=None` field

**Step 5: Run full suite**

Run: `uv run pytest tests/ -v --benchmark-disable`
Expected: All tests PASS

**Step 6: Lint and type check**

Run: `uv run ruff check src/ tests/ && uv run mypy --strict src/navi_fractal/`
Expected: Clean

**Step 7: Commit**

```bash
git add src/navi_fractal/_sandbox.py tests/test_sandbox.py
git commit -m "refactor: migrate SandboxResult.reason to Reason enum, add reason_detail"
```

---

### Task 5: Extract `_quality_gate.py` with `QualityGateReason` enum

**Files:**
- Create: `src/navi_fractal/_quality_gate.py`
- Modify: `src/navi_fractal/_sandbox.py` (remove `sandbox_quality_gate`)
- Modify: `src/navi_fractal/__init__.py` (import from `_quality_gate`)
- Modify: `tests/test_sandbox.py` (update quality gate assertions to 3-tuple)
- Modify: `tests/test_quality_gates.py` (update to 3-tuple, import QualityGateReason)

**Step 1: Create `_quality_gate.py`**

```python
# SPDX-License-Identifier: Apache-2.0
"""Post-hoc quality gate for sandbox dimension results.

Separate from the estimator's acceptance decision. The quality gate
applies a policy threshold — it can reject what the estimator accepted,
but never accepts what the estimator refused.
"""

from __future__ import annotations

import math

from navi_fractal._sandbox import SandboxResult
from navi_fractal._types import QualityGateReason, Reason


def sandbox_quality_gate(
    result: SandboxResult,
    *,
    preset: str = "inclusive",
    r2_min: float | None = None,
    stderr_max: float | None = None,
    radius_ratio_min: float | None = None,
    aicc_min: float | None = None,
) -> tuple[bool, QualityGateReason, str | None]:
    """Post-hoc acceptance policy for sandbox dimension results.

    Returns (passed, reason, detail).

    Presets:
        "inclusive" — R² >= 0.85, stderr <= 0.50, ratio >= 3.0, ΔAICc >= 1.5
        "strict"   — R² >= 0.95, stderr <= 0.20, ratio >= 4.0, ΔAICc >= 3.0

    All thresholds overridable via keyword arguments.
    """
    if preset == "inclusive":
        defaults = (0.85, 0.50, 3.0, 1.5)
    elif preset == "strict":
        defaults = (0.95, 0.20, 4.0, 3.0)
    else:
        raise ValueError(f"Unknown preset: {preset!r}, expected 'inclusive' or 'strict'")

    r2_threshold = r2_min if r2_min is not None else defaults[0]
    stderr_threshold = stderr_max if stderr_max is not None else defaults[1]
    ratio_threshold = radius_ratio_min if radius_ratio_min is not None else defaults[2]
    aicc_threshold = aicc_min if aicc_min is not None else defaults[3]

    if result.dimension is None or result.reason != Reason.ACCEPTED:
        return False, QualityGateReason.NOT_ACCEPTED, f"estimator refused: {result.reason.name}"

    assert result.fit is not None  # guaranteed when dimension is not None

    if result.fit.r2 < r2_threshold:
        return (
            False,
            QualityGateReason.R2_TOO_LOW,
            f"R²={result.fit.r2:.4f} < {r2_threshold}",
        )

    if result.fit.slope_stderr > stderr_threshold:
        return (
            False,
            QualityGateReason.STDERR_TOO_HIGH,
            f"stderr={result.fit.slope_stderr:.4f} > {stderr_threshold}",
        )

    # Radius ratio check: r_max / r_min of the scaling window
    if result.window_start is not None and result.window_end is not None and result.log_radii:
        log_r_min = result.log_radii[result.window_start]
        log_r_max = result.log_radii[result.window_end - 1]
        ratio = math.exp(log_r_max - log_r_min)
        if ratio < ratio_threshold:
            return (
                False,
                QualityGateReason.RADIUS_RATIO_TOO_SMALL,
                f"radius_ratio={ratio:.2f} < {ratio_threshold}",
            )

    # ΔAICc check
    if result.aicc_powerlaw is not None and result.aicc_exponential is not None:
        delta = result.aicc_exponential - result.aicc_powerlaw
        if delta < aicc_threshold:
            return (
                False,
                QualityGateReason.AICC_MARGIN_TOO_SMALL,
                f"ΔAICc={delta:.2f} < {aicc_threshold}",
            )

    return True, QualityGateReason.PASSED, None
```

**Step 2: Remove `sandbox_quality_gate` from `_sandbox.py`**

Delete lines 317-350 (the `sandbox_quality_gate` function) from `_sandbox.py`.

**Step 3: Update `__init__.py`**

Replace the sandbox imports:
```python
from navi_fractal._quality_gate import sandbox_quality_gate
from navi_fractal._sandbox import (
    SandboxResult,
    estimate_sandbox_dimension,
)
from navi_fractal._types import DimensionSummary, LinFit, QualityGateReason, Reason
```

Add `"DimensionSummary"`, `"QualityGateReason"`, `"Reason"` to `__all__`.

**Step 4: Update `tests/test_sandbox.py` quality gate tests**

Update the `TestQualityGate` class to handle 3-tuple returns:

```python
from navi_fractal import (
    Graph,
    QualityGateReason,
    Reason,
    estimate_sandbox_dimension,
    make_grid_graph,
    sandbox_quality_gate,
)

# ...

class TestQualityGate:
    def test_inclusive_passes_good_result(self) -> None:
        grid = make_grid_graph(30, 30)
        result = estimate_sandbox_dimension(grid, seed=42)
        if result.dimension is not None:
            passed, qg_reason, detail = sandbox_quality_gate(result, preset="inclusive")
            assert passed, detail
            assert qg_reason == QualityGateReason.PASSED

    def test_refused_result_fails_gate(self, empty_graph: Graph) -> None:
        result = estimate_sandbox_dimension(empty_graph, seed=42)
        passed, qg_reason, detail = sandbox_quality_gate(result)
        assert not passed
        assert qg_reason == QualityGateReason.NOT_ACCEPTED

    def test_unknown_preset_raises(self) -> None:
        from navi_fractal._sandbox import SandboxResult

        fake_fit = LinFit(
            slope=2.0, intercept=0.0, r2=0.99, slope_stderr=0.01, sse=0.001, n_points=10
        )
        fake_result = SandboxResult(
            dimension=2.0,
            reason=Reason.ACCEPTED,
            reason_detail=None,
            fit=fake_fit,
            radii=(),
            log_radii=(),
            log_masses=(),
            window_start=0,
            window_end=10,
            n_centers=100,
            bootstrap_ci=None,
            aicc_powerlaw=None,
            aicc_exponential=None,
        )
        with pytest.raises(ValueError, match="Unknown preset"):
            sandbox_quality_gate(fake_result, preset="unknown")
```

**Step 5: Update `tests/test_quality_gates.py`**

```python
from navi_fractal import (
    QualityGateReason,
    estimate_sandbox_dimension,
    make_grid_graph,
    sandbox_quality_gate,
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
```

**Step 6: Run full suite**

Run: `uv run pytest tests/ -v --benchmark-disable`
Expected: All tests PASS

**Step 7: Lint and type check**

Run: `uv run ruff check src/ tests/ && uv run mypy --strict src/navi_fractal/`
Expected: Clean

**Step 8: Commit**

```bash
git add src/navi_fractal/_quality_gate.py src/navi_fractal/_sandbox.py src/navi_fractal/__init__.py tests/test_sandbox.py tests/test_quality_gates.py
git commit -m "refactor: extract quality gate module with QualityGateReason enum"
```

---

### Task 6: Rename `estimate_sandbox_dimension` parameters to match spec

**Files:**
- Modify: `src/navi_fractal/_sandbox.py` (parameter names and defaults)
- Modify: `tests/test_sandbox.py` (update kwarg names in calls)
- Modify: `tests/test_known_dimensions.py` (update kwarg names)
- Modify: `tests/test_determinism.py` (update kwarg names)
- Modify: `tests/test_benchmark.py` (update kwarg names)

**Step 1: Update function signature in `_sandbox.py`**

Change:
```python
def estimate_sandbox_dimension(
    g: Graph | CompiledGraph,
    *,
    seed: int,
    n_centers: int = 256,
    component_policy: str = "giant",
    mean_mode: str = "geometric",
    r2_min: float = 0.85,
    delta_aicc_min: float = 1.5,
    curvature_guard: bool = True,
    slope_stability_guard: bool = True,
    slope_stability_max_cv: float = 0.5,
    bootstrap_reps: int = 200,
    use_wls: bool = True,
    min_window_points: int = 6,
    min_log_span: float = 0.5,
    saturation_fraction: float = 0.2,
    variance_floor: float = 1e-12,
) -> SandboxResult:
```

To:
```python
def estimate_sandbox_dimension(
    g: Graph | CompiledGraph,
    *,
    seed: int = 0,
    rng: random.Random | None = None,
    n_centers: int = 256,
    component_policy: str = "giant",
    mean_mode: str = "geometric",
    min_points: int = 6,
    min_radius_ratio: float = 3.0,
    r2_min: float = 0.85,
    min_delta_y: float = 0.5,
    max_saturation_frac: float = 0.2,
    delta_power_win: float = 1.5,
    require_positive_slope: bool = True,
    use_wls: bool = True,
    curvature_guard: bool = True,
    slope_stability_guard: bool = False,
    slope_stability_sub_len: int | None = None,
    max_slope_range: float = 0.5,
    bootstrap_reps: int = 0,
    variance_floor: float = 1e-12,
) -> SandboxResult:
```

Key changes:
- `seed` default: required → `0`
- New `rng` parameter: `random.Random | None = None`
- `min_window_points` → `min_points`
- `min_log_span` → `min_radius_ratio` (convert internally: `min_log_span = math.log(min_radius_ratio)`)
- `delta_aicc_min` → `delta_power_win`
- `saturation_fraction` → `max_saturation_frac`
- `slope_stability_max_cv` → `max_slope_range` (semantics change deferred to implementation)
- `slope_stability_guard` default: `True` → `False`
- `bootstrap_reps` default: `200` → `0`
- New `require_positive_slope: bool = True`
- New `min_delta_y: float = 0.5`
- New `slope_stability_sub_len: int | None = None`

**Step 2: Update internal references in the function body**

- `min_window_points` → `min_points` (lines 95, 149, 175)
- `delta_aicc_min` → `delta_power_win` (line 208)
- `saturation_fraction` → `max_saturation_frac` (line 110)
- `slope_stability_max_cv` → `max_slope_range` (line 232)
- Add: `min_log_span = math.log(min_radius_ratio)` at top of function, use `min_log_span` in existing logic (line 182)
- Add: RNG creation logic:
  ```python
  if rng is None:
      rng = random.Random(seed)
  ```
  (replaces line 99: `rng = random.Random(seed)`)

**Step 3: Add `require_positive_slope` check**

After the best window is found (before bootstrap, around line 245), add:

```python
if best_fit is not None and require_positive_slope and best_fit.slope <= 0:
    return SandboxResult(
        dimension=None,
        reason=Reason.NEGATIVE_SLOPE,
        reason_detail=f"slope={best_fit.slope:.4f} <= 0",
        # ... rest of fields from best window data ...
    )
```

Note: `min_delta_y` filtering logic will be added during implementation phase (response range check inside window search loop). For now the parameter exists in the signature with correct default but is unused — add a comment: `# min_delta_y filtering implemented in v0.1.0 implementation phase`.

**Step 4: Update all test files**

In `tests/test_sandbox.py`:
- All calls to `estimate_sandbox_dimension(g, seed=42)` — now `seed` has a default, so these still work. No changes needed for the `seed` kwarg.
- `bootstrap_reps=50` in `test_result_has_bootstrap_ci` — name unchanged, just default changed.

In `tests/test_benchmark.py`:
- `bootstrap_reps=0` — name unchanged, still valid.

No test changes needed for parameter renames because all existing test calls use kwargs that still exist (`seed`, `n_centers`, `bootstrap_reps`). The renamed params (`delta_aicc_min`, `min_window_points`, etc.) are never used in test calls — they use defaults.

**Step 5: Run full suite**

Run: `uv run pytest tests/ -v --benchmark-disable`
Expected: All tests PASS

**Step 6: Lint and type check**

Run: `uv run ruff check src/ tests/ && uv run mypy --strict src/navi_fractal/`
Expected: Clean

**Step 7: Commit**

```bash
git add src/navi_fractal/_sandbox.py
git commit -m "refactor: rename parameters to match v2 spec, add rng/require_positive_slope/min_delta_y"
```

---

### Task 7: Update `__init__.py` to final export list and verify

**Files:**
- Modify: `src/navi_fractal/__init__.py` (final cleanup)

**Step 1: Write the final `__init__.py`**

```python
# SPDX-License-Identifier: Apache-2.0
"""Audit-grade fractal dimension estimation for graphs.

Refuses to emit a dimension unless positive evidence of power-law scaling exists.
"""

from __future__ import annotations

from navi_fractal._graph import (
    CompiledGraph,
    Graph,
    compile_to_undirected_metric_graph,
)
from navi_fractal._helpers import make_grid_graph, make_path_graph
from navi_fractal._null_model import degree_preserving_rewire_undirected
from navi_fractal._quality_gate import sandbox_quality_gate
from navi_fractal._sandbox import SandboxResult, estimate_sandbox_dimension
from navi_fractal._types import DimensionSummary, LinFit, QualityGateReason, Reason

__all__ = [
    "CompiledGraph",
    "DimensionSummary",
    "Graph",
    "LinFit",
    "QualityGateReason",
    "Reason",
    "SandboxResult",
    "compile_to_undirected_metric_graph",
    "degree_preserving_rewire_undirected",
    "estimate_sandbox_dimension",
    "make_grid_graph",
    "make_path_graph",
    "sandbox_quality_gate",
]
```

**Step 2: Run full suite**

Run: `uv run pytest tests/ -v --benchmark-disable`
Expected: All tests PASS

**Step 3: Lint, type check, and format check**

Run: `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy --strict src/navi_fractal/`
Expected: All clean

**Step 4: Commit**

```bash
git add src/navi_fractal/__init__.py
git commit -m "refactor: finalize public API exports for v2 spec"
```

---

### Task 8: Final verification — all tests, lint, mypy, bandit

**Step 1: Run everything**

```bash
uv run pytest tests/ -v --benchmark-disable
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy --strict src/navi_fractal/
uv run bandit -r src/ -c pyproject.toml
```

Expected: All green.

**Step 2: Verify export count**

```bash
uv run python -c "import navi_fractal; print(len(navi_fractal.__all__), 'exports:', sorted(navi_fractal.__all__))"
```

Expected: `14 exports: ['CompiledGraph', 'DimensionSummary', 'Graph', 'LinFit', 'QualityGateReason', 'Reason', 'SandboxResult', 'compile_to_undirected_metric_graph', 'degree_preserving_rewire_undirected', 'estimate_sandbox_dimension', 'make_grid_graph', 'make_path_graph', 'sandbox_quality_gate']`

Wait — that's 13. Recount: CompiledGraph, DimensionSummary, Graph, LinFit, QualityGateReason, Reason, SandboxResult, compile_to_undirected_metric_graph, degree_preserving_rewire_undirected, estimate_sandbox_dimension, make_grid_graph, make_path_graph, sandbox_quality_gate = 13 exports.

The spec lists 14 symbols but that's because it lists `make_grid_graph` and `make_path_graph` on separate lines within the same import group. Actual unique symbols: 13. Correct.

**Step 3: Commit (if any cleanup was needed)**

No commit needed if everything passed in Step 1.
