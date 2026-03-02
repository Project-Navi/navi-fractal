# v4 Smoke Test Suite Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Validate fractal_analysis_v4_mfa.py against analytical ground truths from the research literature before extracting its code into navi-fractal.

**Architecture:** Three-layer test suite in `tests/v4_smoke/`: (1) math primitives with hand-calculated ground truths, (2) (u,v)-flower integration tests with exact analytical dimensions from Rozenfeld 2007, (3) cross-algorithm plausibility checks on grids, paths, and non-fractal networks. Tests import v4 directly from `docs/reference/fractal_analysis_v4_mfa.py`.

**Tech Stack:** Python 3.12+, pytest, v4 reference module (stdlib only)

**Design doc:** `docs/plans/2026-03-02-v4-smoke-test-design.md`

**Key v4 API differences from navi-fractal (important for writing tests):**
- `sandbox_quality_gate()` returns `Tuple[bool, str]` (2-tuple), not 3-tuple
- `SandboxResult.reason` is a plain `str`, not a `Reason` enum
- `LinFit` has `n` (not `n_points`) and `weighted` fields
- `SandboxResult` has extra fields: `method`, `used_wls`, `y_mode`, `n_edges_measured`
- v4's `Graph` constructor takes `directed: bool = True`

---

### Task 1: Test Infrastructure — conftest.py with v4 Import and (u,v)-Flower Constructor

**Files:**
- Create: `tests/v4_smoke/__init__.py`
- Create: `tests/v4_smoke/conftest.py`

**Context:** All v4 smoke tests need to import from `docs/reference/fractal_analysis_v4_mfa.py`. The conftest handles sys.path setup and provides the (u,v)-flower constructor plus BA/ER graph generators as fixtures. The flower constructor is the most critical piece — it must produce deterministic networks whose structural properties (node count, diameter, hub degree) match analytical predictions.

**Reference:** Rozenfeld, Havlin & ben-Avraham, "Fractal and transfractal recursive scale-free nets", NJP 9:175 (2007). The (u,v)-flower is built by iterative edge replacement: generation 0 is a single edge; each generation replaces every edge with two parallel paths of lengths u and v sharing endpoints.

**Step 1: Create empty `__init__.py` and write `conftest.py` with v4 import + constructors**

```python
# tests/v4_smoke/__init__.py
# (empty — marks directory as test package)
```

```python
# tests/v4_smoke/conftest.py
# SPDX-License-Identifier: Apache-2.0
"""Test infrastructure for v4 smoke tests.

Provides:
- v4 module import via sys.path manipulation
- (u,v)-flower graph constructor (Rozenfeld et al. 2007, NJP 9:175)
- BA model and ER random graph constructors
- Shared fixtures
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import List, Set, Tuple

import pytest

# ---------------------------------------------------------------------------
# v4 import setup
# ---------------------------------------------------------------------------
_V4_DIR = str(Path(__file__).resolve().parent.parent.parent / "docs" / "reference")
if _V4_DIR not in sys.path:
    sys.path.insert(0, _V4_DIR)

from fractal_analysis_v4_mfa import (  # noqa: E402
    Graph,
    compile_to_undirected_metric_graph,
    estimate_sandbox_dimension,
    make_grid_graph,
    sandbox_quality_gate,
)


# ---------------------------------------------------------------------------
# (u,v)-flower constructor
# ---------------------------------------------------------------------------
def make_uv_flower(u: int, v: int, gen: int) -> Graph:
    """Build a (u,v)-flower network at the given generation.

    Generation 0: single edge between two hub nodes (0, 1).
    Each subsequent generation: replace every edge (a, b) with two parallel
    paths of lengths u and v, sharing endpoints a and b.

    The resulting graph has:
    - Diameter = u^gen (shortest path between original hubs)
    - Hub degree = 2^gen (original hub nodes 0 and 1)
    - Analytical box-counting dimension d_B = ln(u+v) / ln(u) for u >= 2

    Reference: Rozenfeld, Havlin & ben-Avraham (2007), NJP 9:175.
    """
    if u < 1 or v < 1:
        raise ValueError(f"u and v must be >= 1, got u={u}, v={v}")
    if gen < 0:
        raise ValueError(f"gen must be >= 0, got gen={gen}")

    g = Graph(directed=False)
    g.add_edge(0, 1)
    edges: List[Tuple[int, int]] = [(0, 1)]
    next_id = 2

    for _generation in range(gen):
        new_edges: List[Tuple[int, int]] = []
        for a, b in edges:
            # Path of length u: a -- x1 -- x2 -- ... -- x_{u-1} -- b
            chain_u = [a]
            for _ in range(u - 1):
                chain_u.append(next_id)
                g.add_node(next_id)
                next_id += 1
            chain_u.append(b)
            for i in range(len(chain_u) - 1):
                g.add_edge(chain_u[i], chain_u[i + 1])
                new_edges.append((chain_u[i], chain_u[i + 1]))

            # Path of length v: a -- y1 -- y2 -- ... -- y_{v-1} -- b
            chain_v = [a]
            for _ in range(v - 1):
                chain_v.append(next_id)
                g.add_node(next_id)
                next_id += 1
            chain_v.append(b)
            for i in range(len(chain_v) - 1):
                g.add_edge(chain_v[i], chain_v[i + 1])
                new_edges.append((chain_v[i], chain_v[i + 1]))

        edges = new_edges

    return g


# ---------------------------------------------------------------------------
# BA model constructor (non-fractal, Song et al. 2005)
# ---------------------------------------------------------------------------
def make_ba_graph(n: int, m: int, *, seed: int = 0) -> Graph:
    """Barabasi-Albert preferential attachment model.

    Starts with a complete graph on m+1 nodes, then adds n-(m+1) nodes
    each connecting to m existing nodes with probability proportional to degree.
    """
    rng = random.Random(seed)
    g = Graph(directed=False)

    # Initial complete graph on m+1 nodes
    for i in range(m + 1):
        for j in range(i + 1, m + 1):
            g.add_edge(i, j)

    # Degree tracking for preferential attachment
    degree: List[int] = [m] * (m + 1)
    stubs: List[int] = []
    for i in range(m + 1):
        stubs.extend([i] * m)

    for new_node in range(m + 1, n):
        targets: Set[int] = set()
        while len(targets) < m:
            t = rng.choice(stubs)
            if t != new_node:
                targets.add(t)
        g.add_node(new_node)
        for t in targets:
            g.add_edge(new_node, t)
            stubs.append(new_node)
            stubs.append(t)
        degree.append(m)
        for t in targets:
            degree[t] += 1

    return g


# ---------------------------------------------------------------------------
# ER random graph constructor (non-fractal, Liu et al. 2015)
# ---------------------------------------------------------------------------
def make_er_graph(n: int, p: float, *, seed: int = 0) -> Graph:
    """Erdos-Renyi G(n, p) random graph."""
    rng = random.Random(seed)
    g = Graph(directed=False)
    for i in range(n):
        g.add_node(i)
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < p:
                g.add_edge(i, j)
    return g


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def flower_22_gen8() -> Graph:
    """(2,2)-flower at generation 8. d_B = ln4/ln2 = 2.0 exactly."""
    return make_uv_flower(2, 2, 8)


@pytest.fixture
def flower_33_gen5() -> Graph:
    """(3,3)-flower at generation 5. d_B = ln6/ln3 ~ 1.631."""
    return make_uv_flower(3, 3, 5)


@pytest.fixture
def flower_44_gen4() -> Graph:
    """(4,4)-flower at generation 4. d_B = ln8/ln4 = 1.5 exactly."""
    return make_uv_flower(4, 4, 4)


@pytest.fixture
def flower_23_gen6() -> Graph:
    """(2,3)-flower at generation 6. d_B = ln5/ln2 ~ 2.322."""
    return make_uv_flower(2, 3, 6)


@pytest.fixture
def flower_12_gen8() -> Graph:
    """(1,2)-flower at generation 8. Transfractal (infinite d_B)."""
    return make_uv_flower(1, 2, 8)
```

**Step 2: Verify conftest imports correctly**

Run: `uv run python -c "import sys; sys.path.insert(0, 'docs/reference'); from fractal_analysis_v4_mfa import estimate_sandbox_dimension; print('v4 import OK')"`
Expected: `v4 import OK`

**Step 3: Verify flower constructor produces correct node count for (2,2) gen 8**

Run: `uv run python -c "
import sys; sys.path.insert(0, 'docs/reference')
from fractal_analysis_v4_mfa import Graph
# Inline test of flower constructor
sys.path.insert(0, 'tests/v4_smoke')
from conftest import make_uv_flower
g = make_uv_flower(2, 2, 8)
print(f'(2,2) gen 8: {g.n_nodes} nodes, {g.n_edges} edges')
"`
Expected: Node count should be 43,692 (per Fronczak 2024 Table 1). If different, the constructor has a bug — debug before proceeding.

**Step 4: Commit**

```bash
git add tests/v4_smoke/__init__.py tests/v4_smoke/conftest.py
git commit -m "test: add v4 smoke test infrastructure with (u,v)-flower constructor"
```

---

### Task 2: Layer 1A — OLS Regression Smoke Tests

**Files:**
- Create: `tests/v4_smoke/test_math_primitives.py`

**Context:** Test v4's `linear_fit_ols` against hand-calculated ground truths. These tests have zero graph dependencies — they validate pure mathematical correctness. If OLS is wrong, every dimension estimate is wrong.

**Step 1: Write OLS tests**

```python
# tests/v4_smoke/test_math_primitives.py
# SPDX-License-Identifier: Apache-2.0
"""Layer 1: Math primitive smoke tests against hand-calculated ground truths.

These tests validate v4's regression, AICc, and statistical functions
independently of any graph construction.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

_V4_DIR = str(Path(__file__).resolve().parent.parent.parent / "docs" / "reference")
if _V4_DIR not in sys.path:
    sys.path.insert(0, _V4_DIR)

from fractal_analysis_v4_mfa import (  # noqa: E402
    linear_fit_ols,
    linear_fit_wls,
    aicc_for_ols,
    aicc_for_wls,
    quadratic_fit_sse_ols,
    _solve_3x3,
    _moments_from_center_masses,
    _percentile,
    slope_range_over_subwindows,
)


class TestOLS:
    def test_perfect_line(self) -> None:
        """y = 2x + 1 should give slope=2, intercept=1, R2=1."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [3.0, 5.0, 7.0, 9.0, 11.0]  # y = 2x + 1
        fit = linear_fit_ols(x, y)
        assert abs(fit.slope - 2.0) < 1e-10
        assert abs(fit.intercept - 1.0) < 1e-10
        assert abs(fit.r2 - 1.0) < 1e-10
        assert fit.n == 5
        assert fit.weighted is False

    def test_known_residuals(self) -> None:
        """Hand-computed SSE and slope_stderr for noisy data."""
        # y = 2x + 1 with known perturbations
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [3.1, 4.9, 7.2, 8.8, 11.0]
        fit = linear_fit_ols(x, y)
        # Slope should be close to 2.0 but not exact
        assert 1.8 < fit.slope < 2.2
        # SSE should be positive (imperfect fit)
        assert fit.sse > 0.0
        # R2 should be high but not 1
        assert 0.99 < fit.r2 < 1.0
        # slope_stderr should be finite and small
        assert 0.0 < fit.slope_stderr < 0.5

    def test_two_points_gives_perfect_fit(self) -> None:
        """Two points always give R2=1 and slope_stderr=inf."""
        fit = linear_fit_ols([1.0, 3.0], [2.0, 6.0])
        assert abs(fit.slope - 2.0) < 1e-10
        assert abs(fit.r2 - 1.0) < 1e-10
        assert fit.slope_stderr == float("inf")

    def test_insufficient_points_raises(self) -> None:
        """OLS requires at least 2 points."""
        with pytest.raises(ValueError):
            linear_fit_ols([1.0], [2.0])
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/v4_smoke/test_math_primitives.py::TestOLS -v --benchmark-disable`
Expected: All 4 tests PASS. If any fail, v4's OLS has a bug — investigate.

**Step 3: Commit**

```bash
git add tests/v4_smoke/test_math_primitives.py
git commit -m "test: add OLS regression smoke tests (Layer 1A)"
```

---

### Task 3: Layer 1B — WLS Regression Smoke Tests

**Files:**
- Modify: `tests/v4_smoke/test_math_primitives.py`

**Context:** WLS is what v4 uses by default (`use_wls=True`). Verify that uniform weights reproduce OLS and that downweighting an outlier shifts the slope toward clean data.

**Step 1: Add WLS test class**

Append to `tests/v4_smoke/test_math_primitives.py`:

```python
class TestWLS:
    def test_uniform_weights_match_ols(self) -> None:
        """WLS with uniform weights should match OLS slope and R2."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [3.0, 5.0, 7.0, 9.0, 11.0]
        w = [1.0, 1.0, 1.0, 1.0, 1.0]
        fit_ols = linear_fit_ols(x, y)
        fit_wls = linear_fit_wls(x, y, w)
        assert abs(fit_wls.slope - fit_ols.slope) < 1e-10
        assert abs(fit_wls.intercept - fit_ols.intercept) < 1e-10
        assert abs(fit_wls.r2 - fit_ols.r2) < 1e-10
        assert fit_wls.weighted is True

    def test_downweight_outlier(self) -> None:
        """Downweighting an outlier should shift slope toward clean data."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y_clean = [3.0, 5.0, 7.0, 9.0, 11.0]  # y = 2x + 1
        # Corrupt last point
        y_noisy = [3.0, 5.0, 7.0, 9.0, 20.0]
        # OLS on noisy data: slope pulled up by outlier
        fit_ols_noisy = linear_fit_ols(x, y_noisy)
        # WLS with outlier downweighted
        w = [1.0, 1.0, 1.0, 1.0, 0.01]
        fit_wls = linear_fit_wls(x, y_noisy, w)
        # WLS slope should be closer to 2.0 than OLS slope
        assert abs(fit_wls.slope - 2.0) < abs(fit_ols_noisy.slope - 2.0)
```

**Step 2: Run tests**

Run: `uv run pytest tests/v4_smoke/test_math_primitives.py::TestWLS -v --benchmark-disable`
Expected: Both tests PASS.

**Step 3: Commit**

```bash
git add tests/v4_smoke/test_math_primitives.py
git commit -m "test: add WLS regression smoke tests (Layer 1B)"
```

---

### Task 4: Layer 1C — AICc Smoke Tests

**Files:**
- Modify: `tests/v4_smoke/test_math_primitives.py`

**Context:** AICc formulas are the backbone of v4's model selection (power-law vs exponential). Verify both OLS and WLS variants against the exact formula.

**Step 1: Add AICc test class**

```python
class TestAICc:
    def test_aicc_ols_formula(self) -> None:
        """Verify AICc_OLS matches the exact formula."""
        sse = 2.5
        n = 10
        k = 2  # linear fit: slope + intercept
        expected = n * math.log(sse / n) + 2 * k + (2 * k * (k + 1)) / (n - k - 1)
        result = aicc_for_ols(sse, n, k)
        assert abs(result - expected) < 1e-10

    def test_aicc_ols_edge_case_returns_inf(self) -> None:
        """n <= k+1 should return inf (insufficient data)."""
        assert aicc_for_ols(1.0, 3, 2) == float("inf")  # n=3, k=2: n <= k+1
        assert aicc_for_ols(1.0, 2, 2) == float("inf")  # n=2, k=2

    def test_aicc_wls_formula(self) -> None:
        """Verify AICc_WLS matches the quasi-AICc formula."""
        chi2 = 3.5
        n = 10
        k = 2
        expected = chi2 + 2 * k + (2 * k * (k + 1)) / (n - k - 1)
        result = aicc_for_wls(chi2, n, k)
        assert abs(result - expected) < 1e-10

    def test_aicc_wls_edge_case_returns_inf(self) -> None:
        """n <= k+1 should return inf."""
        assert aicc_for_wls(1.0, 3, 2) == float("inf")

    def test_aicc_ols_lower_is_better(self) -> None:
        """Lower SSE should give lower (better) AICc."""
        n, k = 20, 2
        aicc_good = aicc_for_ols(0.5, n, k)
        aicc_bad = aicc_for_ols(5.0, n, k)
        assert aicc_good < aicc_bad
```

**Step 2: Run tests**

Run: `uv run pytest tests/v4_smoke/test_math_primitives.py::TestAICc -v --benchmark-disable`
Expected: All 5 tests PASS.

**Step 3: Commit**

```bash
git add tests/v4_smoke/test_math_primitives.py
git commit -m "test: add AICc formula smoke tests (Layer 1C)"
```

---

### Task 5: Layer 1D — Percentile, Quadratic Fit, Moments, Slope Stability

**Files:**
- Modify: `tests/v4_smoke/test_math_primitives.py`

**Context:** Remaining math primitives. _percentile is used for bootstrap CIs, quadratic_fit_sse_ols for the curvature guard, _moments_from_center_masses for WLS weighting, slope_range_over_subwindows for the slope stability guard.

**Step 1: Add remaining test classes**

```python
class TestPercentile:
    def test_median(self) -> None:
        """Median of [1,2,3,4,5] should be 3.0."""
        assert _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 0.5) == 3.0

    def test_interpolation(self) -> None:
        """25th percentile of [1,2,3,4,5] with linear interpolation."""
        result = _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 0.25)
        # pos = (5-1)*0.25 = 1.0 -> index 1 -> value 2.0
        assert abs(result - 2.0) < 1e-10

    def test_boundary_values(self) -> None:
        """q=0 gives first element, q=1 gives last."""
        vals = [10.0, 20.0, 30.0]
        assert _percentile(vals, 0.0) == 10.0
        assert _percentile(vals, 1.0) == 30.0

    def test_interpolation_between_elements(self) -> None:
        """Non-integer position should interpolate linearly."""
        vals = [0.0, 10.0]
        result = _percentile(vals, 0.3)
        # pos = (2-1)*0.3 = 0.3, lo=0, hi=1, t=0.3
        # (1-0.3)*0.0 + 0.3*10.0 = 3.0
        assert abs(result - 3.0) < 1e-10


class TestQuadraticFit:
    def test_perfect_parabola(self) -> None:
        """y = x^2 should have SSE ~ 0."""
        x = [float(i) for i in range(10)]
        y = [xi * xi for xi in x]
        sse = quadratic_fit_sse_ols(x, y)
        assert sse < 1e-10

    def test_linear_data_small_quadratic_coeff(self) -> None:
        """Fitting a quadratic to linear data: SSE should match linear SSE closely."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0 * xi + 1.0 for xi in x]  # perfect line
        sse = quadratic_fit_sse_ols(x, y)
        # Quadratic can fit a line perfectly (c=0), so SSE ~ 0
        assert sse < 1e-8


class TestSolve3x3:
    def test_identity_system(self) -> None:
        """Ix = b should give x = b."""
        A = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        b = [3.0, 5.0, 7.0]
        x0, x1, x2 = _solve_3x3(A, b)
        assert abs(x0 - 3.0) < 1e-10
        assert abs(x1 - 5.0) < 1e-10
        assert abs(x2 - 7.0) < 1e-10

    def test_known_system(self) -> None:
        """Solve a system with known solution via Cramer's rule.

        2x + y + z = 1
        x + 3y + 2z = 2
        x + y + 3z = 3

        Solution: x = -1/3, y = -1/3, z = 4/3 (verify by substitution)
        """
        A = [[2.0, 1.0, 1.0], [1.0, 3.0, 2.0], [1.0, 1.0, 3.0]]
        b = [1.0, 2.0, 3.0]
        x0, x1, x2 = _solve_3x3(A, b)
        # Verify by substitution
        assert abs(2 * x0 + x1 + x2 - 1.0) < 1e-10
        assert abs(x0 + 3 * x1 + 2 * x2 - 2.0) < 1e-10
        assert abs(x0 + x1 + 3 * x2 - 3.0) < 1e-10


class TestMoments:
    def test_single_center(self) -> None:
        """Single center: mean = value, variance = 0."""
        center_masses = [[5, 10, 20]]
        mean_M, var_M, mean_logM, var_logM = _moments_from_center_masses(center_masses)
        assert abs(mean_M[0] - 5.0) < 1e-10
        assert abs(mean_M[1] - 10.0) < 1e-10
        assert abs(mean_M[2] - 20.0) < 1e-10
        # Single center -> variance = 0
        assert all(v == 0.0 for v in var_M)
        assert all(v == 0.0 for v in var_logM)

    def test_two_centers_known_variance(self) -> None:
        """Two centers with known mean and sample variance."""
        # Center 1: [4, 16], Center 2: [6, 4]
        center_masses = [[4, 16], [6, 4]]
        mean_M, var_M, mean_logM, var_logM = _moments_from_center_masses(center_masses)
        # mean_M[0] = (4+6)/2 = 5.0
        assert abs(mean_M[0] - 5.0) < 1e-10
        # mean_M[1] = (16+4)/2 = 10.0
        assert abs(mean_M[1] - 10.0) < 1e-10
        # Sample variance: var = ((4-5)^2 + (6-5)^2) / (2-1) = 2.0
        assert abs(var_M[0] - 2.0) < 1e-10
        # Sample variance: ((16-10)^2 + (4-10)^2) / 1 = 72.0
        assert abs(var_M[1] - 72.0) < 1e-10


class TestSlopeRange:
    def test_constant_slope_gives_zero_range(self) -> None:
        """Perfectly linear data should have zero slope range."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        y = [2.0 * xi + 1.0 for xi in x]
        result = slope_range_over_subwindows(x, y, sub_len=3, use_wls=False)
        assert abs(result) < 1e-10

    def test_curved_data_positive_range(self) -> None:
        """Quadratic data should have positive slope range."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        y = [xi * xi for xi in x]  # y = x^2: slope increases
        result = slope_range_over_subwindows(x, y, sub_len=3, use_wls=False)
        assert result > 0.0
```

**Step 2: Run all Layer 1 tests**

Run: `uv run pytest tests/v4_smoke/test_math_primitives.py -v --benchmark-disable`
Expected: All tests PASS (~20 tests total).

**Step 3: Commit**

```bash
git add tests/v4_smoke/test_math_primitives.py
git commit -m "test: add percentile, quadratic, moments, slope stability smoke tests (Layer 1D)"
```

---

### Task 6: Layer 2A — (u,v)-Flower Constructor Validation

**Files:**
- Create: `tests/v4_smoke/test_flower_integration.py`

**Context:** Before testing dimension estimates on flowers, validate that the constructor produces structurally correct graphs. If the fixture is wrong, every downstream test is meaningless.

**Important:** The node count formula depends on the specific construction. For (2,2)-flower gen 8, Fronczak et al. 2024 Table 1 reports N=43,692. The diameter should be u^gen = 2^8 = 256. If the node count doesn't match, the constructor implementation needs debugging — don't proceed until it matches.

**Step 1: Write constructor validation tests**

```python
# tests/v4_smoke/test_flower_integration.py
# SPDX-License-Identifier: Apache-2.0
"""Layer 2: (u,v)-flower integration tests with exact analytical dimensions.

Ground truth: Rozenfeld, Havlin & ben-Avraham (2007), NJP 9:175.
d_B = ln(u+v) / ln(u) for u >= 2.

Cross-references:
- Fronczak et al. 2024 (Sci. Rep. 14:9079), Table 1: (2,2)-flower N=43,692
- Lepek et al. 2025 (Chaos Solitons Fractals 199:116908): d_B=1.98 via FNB
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

_V4_DIR = str(Path(__file__).resolve().parent.parent.parent / "docs" / "reference")
if _V4_DIR not in sys.path:
    sys.path.insert(0, _V4_DIR)

from conftest import make_uv_flower
from fractal_analysis_v4_mfa import (  # noqa: E402
    Graph,
    compile_to_undirected_metric_graph,
    estimate_sandbox_dimension,
    sandbox_quality_gate,
)


class TestFlowerConstructor:
    def test_22_gen8_node_count(self, flower_22_gen8: Graph) -> None:
        """(2,2)-flower gen 8 should have 43,692 nodes (Fronczak 2024)."""
        assert flower_22_gen8.n_nodes == 43_692

    def test_22_gen8_diameter(self, flower_22_gen8: Graph) -> None:
        """Diameter of (2,2)-flower gen 8 should be 2^8 = 256."""
        from fractal_analysis_v4_mfa import farthest_from

        cg = compile_to_undirected_metric_graph(flower_22_gen8)
        # Hub node 0 is one of the original endpoints
        _, d1 = farthest_from(cg, 0)
        # The farthest node from hub 0 should be at distance 256
        assert d1 == 256

    def test_22_gen0_is_single_edge(self) -> None:
        """Generation 0: just two nodes and one edge."""
        g = make_uv_flower(2, 2, 0)
        assert g.n_nodes == 2
        assert g.n_edges == 1

    def test_22_gen1_structure(self) -> None:
        """Generation 1: two parallel paths of length 2."""
        g = make_uv_flower(2, 2, 1)
        # Each path has 1 internal node, plus 2 hubs = 4 nodes total
        assert g.n_nodes == 4
        # Two paths of length 2 = 4 edges
        assert g.n_edges == 4

    def test_33_gen5_node_count(self, flower_33_gen5: Graph) -> None:
        """(3,3)-flower gen 5 node count should be reasonable."""
        # Each generation multiplies edges by (u+v) = 6
        # and adds (u-1)+(v-1) = 4 new nodes per edge
        assert flower_33_gen5.n_nodes > 1000

    def test_flower_deterministic(self) -> None:
        """Same parameters should produce identical graphs."""
        g1 = make_uv_flower(2, 2, 3)
        g2 = make_uv_flower(2, 2, 3)
        assert g1.n_nodes == g2.n_nodes
        assert g1.n_edges == g2.n_edges
```

**Step 2: Run constructor tests**

Run: `uv run pytest tests/v4_smoke/test_flower_integration.py::TestFlowerConstructor -v --benchmark-disable`
Expected: All tests PASS. **Critical:** If `test_22_gen8_node_count` fails, the flower constructor is wrong. Debug by checking gen 1, gen 2, gen 3 incrementally until the pattern matches the formula.

**Step 3: Commit**

```bash
git add tests/v4_smoke/test_flower_integration.py
git commit -m "test: add (u,v)-flower constructor validation (Layer 2A)"
```

---

### Task 7: Layer 2B — Flower Dimension Estimation (Core Scientific Tests)

**Files:**
- Modify: `tests/v4_smoke/test_flower_integration.py`

**Context:** These are the most important tests in the entire suite. They verify that v4's sandbox algorithm produces dimension estimates matching the analytically exact values from Rozenfeld 2007: d_B = ln(u+v)/ln(u).

Tolerances are calibrated from the literature:
- ±0.10 for gen 8 (40K+ nodes): Lepek 2025 reports d_B=1.98 for (2,2)-flower via FNB
- ±0.15 for smaller generations (2-12K nodes): wider due to finite-size effects

**Step 1: Add dimension estimation tests**

```python
class TestFlowerDimension:
    def test_22_flower_dimension_near_2(self, flower_22_gen8: Graph) -> None:
        """d_B = ln(4)/ln(2) = 2.0 exactly. Sandbox should be within ±0.10.

        Rozenfeld et al. 2007, NJP 9:175.
        Cross-check: Fronczak et al. 2024 report d_B=2.0, Lepek et al. 2025 report 1.98.
        """
        result = estimate_sandbox_dimension(flower_22_gen8, seed=42)
        assert result.dimension is not None, f"Refused: {result.reason}"
        expected = math.log(4) / math.log(2)  # 2.0
        assert abs(result.dimension - expected) <= 0.10, (
            f"D={result.dimension:.4f}, expected {expected:.4f} ± 0.10"
        )

    def test_33_flower_dimension_near_1_631(self, flower_33_gen5: Graph) -> None:
        """d_B = ln(6)/ln(3) ~ 1.631.

        Rozenfeld et al. 2007, NJP 9:175.
        """
        result = estimate_sandbox_dimension(flower_33_gen5, seed=42)
        assert result.dimension is not None, f"Refused: {result.reason}"
        expected = math.log(6) / math.log(3)  # ~1.6309
        assert abs(result.dimension - expected) <= 0.15, (
            f"D={result.dimension:.4f}, expected {expected:.4f} ± 0.15"
        )

    def test_44_flower_dimension_near_1_5(self, flower_44_gen4: Graph) -> None:
        """d_B = ln(8)/ln(4) = 1.5 exactly.

        Rozenfeld et al. 2007, NJP 9:175.
        """
        result = estimate_sandbox_dimension(flower_44_gen4, seed=42)
        assert result.dimension is not None, f"Refused: {result.reason}"
        expected = math.log(8) / math.log(4)  # 1.5
        assert abs(result.dimension - expected) <= 0.15, (
            f"D={result.dimension:.4f}, expected {expected:.4f} ± 0.15"
        )

    def test_23_flower_dimension_near_2_322(self, flower_23_gen6: Graph) -> None:
        """d_B = ln(5)/ln(2) ~ 2.322.

        Rozenfeld et al. 2007, NJP 9:175.
        """
        result = estimate_sandbox_dimension(flower_23_gen6, seed=42)
        assert result.dimension is not None, f"Refused: {result.reason}"
        expected = math.log(5) / math.log(2)  # ~2.3219
        assert abs(result.dimension - expected) <= 0.15, (
            f"D={result.dimension:.4f}, expected {expected:.4f} ± 0.15"
        )

    def test_22_flower_r2_high(self, flower_22_gen8: Graph) -> None:
        """(2,2)-flower should have R² > 0.95 in scaling regime.

        Liu et al. 2015 (Chaos 25:023103): sandbox matches analytical values
        closely for deterministic fractal networks.
        """
        result = estimate_sandbox_dimension(flower_22_gen8, seed=42)
        assert result.dimension is not None
        assert result.powerlaw_fit is not None
        assert result.powerlaw_fit.r2 > 0.95, f"R²={result.powerlaw_fit.r2:.4f}"

    def test_22_flower_reason_accepted(self, flower_22_gen8: Graph) -> None:
        """(2,2)-flower should be accepted, not refused."""
        result = estimate_sandbox_dimension(flower_22_gen8, seed=42)
        assert result.dimension is not None
        assert result.reason == "accepted"

    def test_22_flower_deterministic(self, flower_22_gen8: Graph) -> None:
        """Same seed should produce identical dimension estimates."""
        r1 = estimate_sandbox_dimension(flower_22_gen8, seed=42)
        r2 = estimate_sandbox_dimension(flower_22_gen8, seed=42)
        assert r1.dimension == r2.dimension
        if r1.powerlaw_fit is not None and r2.powerlaw_fit is not None:
            assert r1.powerlaw_fit.slope == r2.powerlaw_fit.slope
```

**Step 2: Run flower dimension tests**

Run: `uv run pytest tests/v4_smoke/test_flower_integration.py::TestFlowerDimension -v --benchmark-disable`
Expected: All 7 tests PASS. The (2,2)-flower gen 8 test is the most important — if D is outside [1.90, 2.10], something is fundamentally wrong with either the constructor or v4's sandbox pipeline.

**Note:** These tests may take 10-30 seconds each for the larger flowers. That's expected.

**Step 3: Commit**

```bash
git add tests/v4_smoke/test_flower_integration.py
git commit -m "test: add flower dimension estimation tests (Layer 2B)"
```

---

### Task 8: Layer 2C — Transfractal Rejection and Quality Gate Tests

**Files:**
- Modify: `tests/v4_smoke/test_flower_integration.py`

**Context:** The (1,2)-flower is transfractal (small-world, infinite d_B). v4 might return a dimension with terrible R², or refuse outright. Either way, the quality gate must reject it. This tests the library's discrimination ability — can it tell fractal from non-fractal?

**Important design note:** Do NOT assert `dimension is None`. Instead, assert that `sandbox_quality_gate()` returns `(False, ...)`. v4 might return a number with bad R² rather than refusing. The gate verdict is what matters.

**Step 1: Add transfractal and quality gate tests**

```python
class TestFlowerQualityGates:
    def test_12_flower_gate_rejects(self, flower_12_gen8: Graph) -> None:
        """(1,2)-flower is transfractal (infinite d_B). Gate must reject.

        Rozenfeld et al. 2007: (1,v)-flowers are small-world / transfractal
        with no finite box-counting dimension.

        Note: v4 may return a dimension with poor R², or may refuse outright.
        Either way, the quality gate must reject.
        """
        result = estimate_sandbox_dimension(flower_12_gen8, seed=42)
        passed, detail = sandbox_quality_gate(result, preset="inclusive")
        assert not passed, (
            f"Transfractal (1,2)-flower should be rejected by quality gate. "
            f"D={result.dimension}, detail={detail}"
        )

    def test_22_flower_gate_accepts(self, flower_22_gen8: Graph) -> None:
        """(2,2)-flower should pass inclusive quality gate."""
        result = estimate_sandbox_dimension(flower_22_gen8, seed=42)
        passed, detail = sandbox_quality_gate(result, preset="inclusive")
        assert passed, f"(2,2)-flower should pass inclusive gate. detail={detail}"

    def test_22_flower_strict_gate(self, flower_22_gen8: Graph) -> None:
        """(2,2)-flower should likely pass strict quality gate too."""
        result = estimate_sandbox_dimension(flower_22_gen8, seed=42)
        if result.dimension is not None:
            passed, detail = sandbox_quality_gate(result, preset="strict")
            # Not asserting pass — strict is genuinely strict. Just log result.
            if not passed:
                import warnings

                warnings.warn(
                    f"(2,2)-flower failed strict gate: {detail}",
                    stacklevel=1,
                )
```

**Step 2: Run quality gate tests**

Run: `uv run pytest tests/v4_smoke/test_flower_integration.py::TestFlowerQualityGates -v --benchmark-disable`
Expected: First two PASS, third might warn but doesn't fail.

**Step 3: Commit**

```bash
git add tests/v4_smoke/test_flower_integration.py
git commit -m "test: add transfractal rejection and quality gate tests (Layer 2C)"
```

---

### Task 9: Layer 3 — Cross-Algorithm Plausibility Tests

**Files:**
- Create: `tests/v4_smoke/test_plausibility.py`

**Context:** Validate v4 against classical structures (grids, paths) and verify rejection of non-fractal networks (BA model, ER random, complete graph). These are coarser checks — they verify the pipeline behaves sensibly across different graph families.

**Step 1: Write plausibility tests**

```python
# tests/v4_smoke/test_plausibility.py
# SPDX-License-Identifier: Apache-2.0
"""Layer 3: Cross-algorithm plausibility checks.

Tests v4 on grids (known D~2 for 2D lattice), paths (D=1),
and non-fractal networks that should be rejected.

Ground truth sources:
- 2D grid: D=2 analytically, D~1.62 empirically due to boundary effects
- Path graph: D=1 analytically
- BA model: non-fractal (Song et al. 2005, Nature 433:392)
- ER random: non-fractal (Liu et al. 2015, Chaos 25:023103)
"""
from __future__ import annotations

import sys
from pathlib import Path

_V4_DIR = str(Path(__file__).resolve().parent.parent.parent / "docs" / "reference")
if _V4_DIR not in sys.path:
    sys.path.insert(0, _V4_DIR)

from conftest import make_ba_graph, make_er_graph
from fractal_analysis_v4_mfa import (  # noqa: E402
    Graph,
    estimate_sandbox_dimension,
    make_grid_graph,
    sandbox_quality_gate,
)


class TestGridPlausibility:
    def test_30x30_grid_dimension_range(self) -> None:
        """30x30 grid: D should be in [1.55, 1.75] (boundary-affected 2D lattice).

        This range is already validated in navi-fractal's own test suite.
        """
        grid = make_grid_graph(30, 30)
        result = estimate_sandbox_dimension(grid, seed=42)
        assert result.dimension is not None, f"Refused: {result.reason}"
        assert 1.55 <= result.dimension <= 1.75, f"D={result.dimension:.4f}"

    def test_30x30_grid_accepted(self) -> None:
        """Grid should be accepted by v4."""
        grid = make_grid_graph(30, 30)
        result = estimate_sandbox_dimension(grid, seed=42)
        assert result.dimension is not None
        assert result.reason == "accepted"


class TestPathPlausibility:
    def test_path_100_dimension_near_1(self) -> None:
        """Path graph (100 nodes): D should be near 1.0.

        Disable curvature guard: finite paths have inherent boundary curvature.
        """
        g = Graph(directed=False)
        for i in range(99):
            g.add_edge(i, i + 1)
        result = estimate_sandbox_dimension(g, seed=42, curvature_guard=False)
        assert result.dimension is not None, f"Refused: {result.reason}"
        assert 0.8 <= result.dimension <= 1.2, f"D={result.dimension:.4f}"


class TestNonFractalRejection:
    def test_ba_model_rejected_or_poor_quality(self) -> None:
        """BA model (m=3, n=1000) is non-fractal (Song et al. 2005).

        Should either be refused by the estimator (dimension=None)
        or fail the quality gate.
        """
        ba = make_ba_graph(1000, 3, seed=42)
        result = estimate_sandbox_dimension(ba, seed=42)
        if result.dimension is not None:
            passed, detail = sandbox_quality_gate(result, preset="inclusive")
            assert not passed, (
                f"BA model should fail quality gate. D={result.dimension}, detail={detail}"
            )

    def test_er_random_rejected_or_poor_quality(self) -> None:
        """ER random graph (n=500, p=0.01) is non-fractal (Liu et al. 2015).

        Should either be refused or fail quality gate.
        """
        er = make_er_graph(500, 0.01, seed=42)
        result = estimate_sandbox_dimension(er, seed=42)
        if result.dimension is not None:
            passed, detail = sandbox_quality_gate(result, preset="inclusive")
            assert not passed, (
                f"ER graph should fail quality gate. D={result.dimension}, detail={detail}"
            )

    def test_complete_k50_refused(self) -> None:
        """Complete graph K50: trivial diameter (1), should be refused."""
        g = Graph(directed=False)
        for i in range(50):
            for j in range(i + 1, 50):
                g.add_edge(i, j)
        result = estimate_sandbox_dimension(g, seed=42)
        assert result.dimension is None, (
            f"K50 should be refused. D={result.dimension}, reason={result.reason}"
        )
```

**Step 2: Run plausibility tests**

Run: `uv run pytest tests/v4_smoke/test_plausibility.py -v --benchmark-disable`
Expected: All 5 tests PASS.

**Step 3: Commit**

```bash
git add tests/v4_smoke/test_plausibility.py
git commit -m "test: add cross-algorithm plausibility tests (Layer 3)"
```

---

### Task 10: Full Suite Verification and Final Commit

**Files:**
- No new files

**Context:** Run the entire v4 smoke test suite end-to-end, plus navi-fractal's existing tests, to verify nothing is broken. Also run linting to ensure code quality.

**Step 1: Run v4 smoke tests**

Run: `uv run pytest tests/v4_smoke/ -v --benchmark-disable`
Expected: All ~32 tests PASS.

**Step 2: Run existing navi-fractal tests to verify no regressions**

Run: `uv run pytest tests/ -v --benchmark-disable`
Expected: All 151+ tests PASS (existing + new v4 smoke tests).

**Step 3: Run linting**

Run: `uv run ruff check tests/v4_smoke/`
Expected: Clean (no errors). If there are import-order issues from the sys.path manipulation, add appropriate `# noqa` comments.

Run: `uv run ruff format --check tests/v4_smoke/`
Expected: Clean.

**Step 4: Final commit if any fixes were needed**

```bash
git add tests/v4_smoke/
git commit -m "test: finalize v4 smoke test suite — 3-layer validation against research literature"
```

**Step 5: Summary report**

Print a summary of:
- Total test count per layer
- Any tests that needed tolerance adjustments
- Any v4 bugs discovered (dimension values that deviate from expected)
- The actual dimension values v4 produces for each flower configuration
