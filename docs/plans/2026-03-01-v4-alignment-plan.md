# v4 Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align navi-fractal's sandbox estimator to v4 ground truth — fix defaults, algorithms, and factoring so that a 30x30 grid produces D~1.622 (matching v4) instead of D~1.613.

**Architecture:** Nine tasks in dependency order. Each task is TDD: write failing test, implement, verify, commit. v4 (`/home/ndspence/Downloads/fractal_analysis_v4_mfa.py`) is ground truth for all defaults and algorithms. Our `Reason`/`QualityGateReason` enums are kept as additive improvements over v4's free-form strings.

**Tech Stack:** Python 3.12+, stdlib only. Test runner: `uv run pytest`. Linter: `uv run ruff check`. Types: `uv run mypy --strict`.

**Reference:** Design doc at `docs/plans/2026-03-01-v4-alignment-design.md`.

---

### Task 1: SandboxResult Field Additions

Add two new fields to SandboxResult and update all construction sites. This unblocks everything else since tests that construct SandboxResult will break without the new fields.

**Files:**
- Modify: `src/navi_fractal/_sandbox.py`
- Modify: `tests/test_sandbox.py`
- Modify: `tests/test_quality_gates.py`

**Step 1: Add the two new fields to SandboxResult dataclass**

In `src/navi_fractal/_sandbox.py`, add after the `dimension_ci` field (line 53):

```python
    # Bootstrap diagnostics
    delta_aicc_ci: tuple[float, float] | None
    bootstrap_valid_reps: int
```

**Step 2: Update `_make_empty_result` to include new fields**

In `_make_empty_result()` (around line 519), add to the SandboxResult constructor:

```python
        delta_aicc_ci=None,
        bootstrap_valid_reps=0,
```

**Step 3: Update all inline SandboxResult constructors**

There are 4 inline constructors in `_sandbox.py` (lines ~246, ~376, ~411, ~481). Add `delta_aicc_ci=None, bootstrap_valid_reps=0` to each.

**Step 4: Update test helpers that construct SandboxResult**

In `tests/test_quality_gates.py`, update `_make_accepted_result()` (line 34) — add:
```python
        delta_aicc_ci=None,
        bootstrap_valid_reps=0,
```

In `tests/test_sandbox.py`, update `TestQualityGate.test_unknown_preset_raises` (line 173) — add the same two fields.

**Step 5: Run tests to verify everything passes**

Run: `uv run pytest tests/ -v --benchmark-disable`
Expected: All tests pass.

**Step 6: Commit**

```bash
git add src/navi_fractal/_sandbox.py tests/test_sandbox.py tests/test_quality_gates.py
git commit -m "feat: add delta_aicc_ci and bootstrap_valid_reps to SandboxResult"
```

---

### Task 2: Regression Module Alignment

Add `aicc_for_wls()`, rename `aicc()` to `aicc_for_ols()`, add `quadratic_fit_residual_wls()`, and add standalone `slope_range_over_subwindows()`.

**Files:**
- Modify: `src/navi_fractal/_regression.py`
- Modify: `src/navi_fractal/_sandbox.py` (update imports)
- Modify: `tests/test_regression.py`

**Step 1: Write failing tests for new regression functions**

Add to `tests/test_regression.py`:

```python
from navi_fractal._regression import (
    aicc_for_ols,
    aicc_for_wls,
    ols,
    quadratic_fit_residual,
    quadratic_fit_residual_wls,
    slope_range_over_subwindows,
    wls,
)


class TestAICcForOLS:
    def test_matches_old_aicc(self) -> None:
        """aicc_for_ols should produce identical results to the old aicc()."""
        assert aicc_for_ols(1.0, 20, 2) == aicc_for_ols(1.0, 20, 2)

    def test_lower_sse_preferred(self) -> None:
        a1 = aicc_for_ols(1.0, 20, 2)
        a2 = aicc_for_ols(10.0, 20, 2)
        assert a1 < a2

    def test_insufficient_points(self) -> None:
        assert aicc_for_ols(1.0, 3, 2) == float("inf")


class TestAICcForWLS:
    def test_basic_formula(self) -> None:
        """WLS AICc = chi2 + 2k + correction, NOT n*log(chi2/n) + 2k + correction."""
        chi2 = 5.0
        n = 20
        k = 2
        result = aicc_for_wls(chi2, n, k)
        correction = 2 * k * (k + 1) / (n - k - 1)
        expected = chi2 + 2 * k + correction
        assert abs(result - expected) < 1e-10

    def test_insufficient_points(self) -> None:
        assert aicc_for_wls(1.0, 3, 2) == float("inf")

    def test_different_from_ols(self) -> None:
        """WLS and OLS AICc should produce different values for same inputs."""
        result_wls = aicc_for_wls(5.0, 20, 2)
        result_ols = aicc_for_ols(5.0, 20, 2)
        assert result_wls != result_ols


class TestQuadraticFitWLS:
    def test_perfect_quadratic(self) -> None:
        x = [float(i) for i in range(10)]
        y = [xi * xi for xi in x]
        w = [1.0] * 10
        sse = quadratic_fit_residual_wls(x, y, w)
        assert sse < 1e-8

    def test_weighted_vs_unweighted(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [1.0, 4.0, 9.0, 16.0, 25.0]
        w_uniform = [1.0, 1.0, 1.0, 1.0, 1.0]
        sse_wls = quadratic_fit_residual_wls(x, y, w_uniform)
        sse_ols = quadratic_fit_residual(x, y)
        # With uniform weights, both should be near-zero for perfect quadratic
        assert sse_wls < 1e-8
        assert sse_ols < 1e-8

    def test_too_few_points(self) -> None:
        assert quadratic_fit_residual_wls([1.0, 2.0], [1.0, 4.0], [1.0, 1.0]) == float("inf")


class TestSlopeRangeOverSubwindows:
    def test_constant_slope(self) -> None:
        """Linear data should have zero slope range."""
        x = [float(i) for i in range(10)]
        y = [2.0 * xi + 1.0 for xi in x]
        sr = slope_range_over_subwindows(x, y, sub_len=4, use_wls=False)
        assert sr < 1e-8

    def test_curved_data_nonzero(self) -> None:
        """Quadratic data should have nonzero slope range."""
        x = [float(i) for i in range(10)]
        y = [xi * xi for xi in x]
        sr = slope_range_over_subwindows(x, y, sub_len=4, use_wls=False)
        assert sr > 0.1

    def test_wls_requires_weights(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0]
        y = [1.0, 2.0, 3.0, 4.0]
        import pytest
        with pytest.raises(ValueError, match="weights"):
            slope_range_over_subwindows(x, y, sub_len=2, use_wls=True)
```

Also update the existing import at top of test file:
```python
from navi_fractal._regression import (
    aicc_for_ols,
    aicc_for_wls,
    ols,
    quadratic_fit_residual,
    quadratic_fit_residual_wls,
    slope_range_over_subwindows,
    wls,
)
```

And update existing `TestAICc` class to use `aicc_for_ols` instead of `aicc`:
```python
class TestAICc:
    def test_lower_sse_preferred(self) -> None:
        a1 = aicc_for_ols(1.0, 20, 2)
        a2 = aicc_for_ols(10.0, 20, 2)
        assert a1 < a2
    # ... etc for all methods in this class
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_regression.py -v --benchmark-disable`
Expected: FAIL — `aicc_for_ols`, `aicc_for_wls`, etc. not importable.

**Step 3: Implement the functions in `_regression.py`**

3a. Rename `aicc()` to `aicc_for_ols()`. Keep `aicc` as a backward-compat alias:
```python
def aicc_for_ols(sse: float, n: int, k: int) -> float:
    """Corrected AICc for OLS: n*log(SSE/n) + 2k + correction."""
    if n <= k + 1:
        return float("inf")
    if sse <= 0.0:
        return float("-inf")
    aic = n * math.log(sse / n) + 2 * k
    correction = 2 * k * (k + 1) / (n - k - 1)
    return aic + correction

aicc = aicc_for_ols  # backward compat
```

3b. Add `aicc_for_wls()`:
```python
def aicc_for_wls(chi2: float, n: int, k: int) -> float:
    """Quasi-AICc for WLS using chi2 = sum(w_i * residual_i^2) as deviance proxy."""
    if n <= k + 1:
        return float("inf")
    return float(chi2 + 2 * k + (2 * k * (k + 1)) / (n - k - 1))
```

3c. Add `quadratic_fit_residual_wls()`:
```python
def quadratic_fit_residual_wls(
    x: list[float], y: list[float], weights: list[float]
) -> float:
    """WLS quadratic fit: y = a*x^2 + b*x + c, return weighted SSE."""
    n = len(x)
    if n < 3:
        return float("inf")
    if n != len(y) or n != len(weights):
        raise ValueError("x, y, and weights must have same length")

    # Weighted normal equations
    s0 = math.fsum(weights)
    s1 = math.fsum(w * xi for w, xi in zip(weights, x, strict=True))
    s2 = math.fsum(w * xi * xi for w, xi in zip(weights, x, strict=True))
    s3 = math.fsum(w * xi ** 3 for w, xi in zip(weights, x, strict=True))
    s4 = math.fsum(w * xi ** 4 for w, xi in zip(weights, x, strict=True))

    t0 = math.fsum(w * yi for w, yi in zip(weights, y, strict=True))
    t1 = math.fsum(w * xi * yi for w, xi, yi in zip(weights, x, y, strict=True))
    t2 = math.fsum(w * xi * xi * yi for w, xi, yi in zip(weights, x, y, strict=True))

    # 3x3 system: same Gaussian elimination as quadratic_fit_residual
    mat = [
        [s4, s3, s2, t2],
        [s3, s2, s1, t1],
        [s2, s1, s0, t0],
    ]

    for col in range(3):
        max_row = col
        max_val = abs(mat[col][col])
        for row in range(col + 1, 3):
            if abs(mat[row][col]) > max_val:
                max_val = abs(mat[row][col])
                max_row = row
        if max_val < 1e-15:
            return float("inf")
        mat[col], mat[max_row] = mat[max_row], mat[col]
        for row in range(col + 1, 3):
            factor = mat[row][col] / mat[col][col]
            for j in range(col, 4):
                mat[row][j] -= factor * mat[col][j]

    coeffs = [0.0, 0.0, 0.0]
    for i in range(2, -1, -1):
        val = mat[i][3]
        for j in range(i + 1, 3):
            val -= mat[i][j] * coeffs[j]
        if abs(mat[i][i]) < 1e-15:
            return float("inf")
        coeffs[i] = val / mat[i][i]

    a, b, c = coeffs
    sse = math.fsum(
        w * (yi - (a * xi * xi + b * xi + c)) ** 2
        for w, xi, yi in zip(weights, x, y, strict=True)
    )
    return sse
```

3d. Add `slope_range_over_subwindows()`:
```python
def slope_range_over_subwindows(
    x: list[float],
    y: list[float],
    *,
    sub_len: int,
    use_wls: bool,
    w: list[float] | None = None,
) -> float:
    """Range of OLS/WLS slopes across contiguous subwindows of length sub_len."""
    n = len(x)
    if sub_len < 2 or sub_len > n:
        raise ValueError("invalid subwindow length")
    slopes: list[float] = []
    for i in range(n - sub_len + 1):
        xs = x[i : i + sub_len]
        ys = y[i : i + sub_len]
        if use_wls:
            if w is None:
                raise ValueError("weights required for WLS slope stability")
            ws = w[i : i + sub_len]
            fit = wls(xs, ys, ws)
        else:
            fit = ols(xs, ys)
        slopes.append(fit.slope)
    return float(max(slopes) - min(slopes)) if slopes else float("inf")
```

**Step 4: Update `_sandbox.py` import to use `aicc_for_ols`**

Change line 18:
```python
from navi_fractal._regression import aicc_for_ols as aicc, ols, quadratic_fit_residual, wls
```

This keeps `aicc` as the local name so all existing call sites work unchanged.

**Step 5: Run full test suite**

Run: `uv run pytest tests/ -v --benchmark-disable`
Expected: All tests pass.

**Step 6: Commit**

```bash
git add src/navi_fractal/_regression.py src/navi_fractal/_sandbox.py tests/test_regression.py
git commit -m "feat: add aicc_for_wls, quadratic_fit_residual_wls, slope_range_over_subwindows"
```

---

### Task 3: auto_radii Alignment

Rewrite `auto_radii` to match v4 signature and algorithm exactly.

**Files:**
- Modify: `src/navi_fractal/_radii.py`
- Modify: `tests/test_sandbox.py` (radii may change — existing tests still pass)

**Step 1: Write failing test for new auto_radii signature**

Add to a new test class in `tests/test_regression.py` (or wherever convenient — but since there's no `test_radii.py`, add one):

Create `tests/test_radii.py`:
```python
# SPDX-License-Identifier: Apache-2.0
"""Tests for auto_radii alignment with v4."""

from __future__ import annotations

from navi_fractal._radii import auto_radii


class TestAutoRadii:
    def test_returns_sorted_unique(self) -> None:
        result = auto_radii(60)
        assert result == sorted(set(result))
        assert all(r >= 1 for r in result)

    def test_dense_prefix_is_6(self) -> None:
        """V4 uses dense_prefix=6, not 10."""
        result = auto_radii(60)
        # First 6 radii should be 1,2,3,4,5,6
        assert result[:6] == [1, 2, 3, 4, 5, 6]

    def test_r_cap_limits_max(self) -> None:
        """r_cap=32 should cap the maximum radius."""
        result = auto_radii(200, r_cap=32)
        assert max(result) <= 32

    def test_r_cap_default_32(self) -> None:
        """Default r_cap=32."""
        result = auto_radii(200)
        assert max(result) <= 32

    def test_min_r_max_floor(self) -> None:
        """min_r_max=12 ensures at least radius 12 even on small diameters."""
        result = auto_radii(20)
        assert max(result) >= min(12, 20)

    def test_never_exceeds_diameter(self) -> None:
        result = auto_radii(10)
        assert max(result) <= 10

    def test_small_diameter(self) -> None:
        result = auto_radii(1)
        assert result == [] or result == [1]

    def test_zero_diameter(self) -> None:
        assert auto_radii(0) == []

    def test_custom_dense_prefix(self) -> None:
        result = auto_radii(60, dense_prefix=3)
        assert result[:3] == [1, 2, 3]
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_radii.py -v --benchmark-disable`
Expected: FAIL — signature mismatch on `r_cap`, `dense_prefix`, etc.

**Step 3: Rewrite `auto_radii` in `_radii.py`**

Replace the entire function body with v4-aligned implementation:

```python
def auto_radii(
    diam_est: int,
    *,
    r_cap: int = 32,
    dense_prefix: int = 6,
    log_points: int = 10,
    diam_frac: float = 0.3,
    min_r_max: int = 12,
) -> list[int]:
    """Select radii for sandbox dimension estimation.

    Strategy: dense prefix (1..dense_prefix), then log-spaced up to
    min(r_cap, diam_frac * diam_est), with min_r_max as floor.
    """
    if diam_est <= 1:
        return []
    r_max = int(max(min_r_max, diam_frac * diam_est))
    r_max = min(r_cap, max(1, r_max))
    r_max = min(r_max, max(1, diam_est))  # never exceed diameter
    if r_max < 2:
        return [1]

    radii: set[int] = set(range(1, min(dense_prefix, r_max) + 1))
    if r_max > dense_prefix:
        lo = max(dense_prefix + 1, 2)
        hi = r_max
        log_lo = math.log(lo)
        log_hi = math.log(hi)
        for i in range(log_points):
            t = i / max(1, (log_points - 1))
            r = int(round(math.exp(log_lo + t * (log_hi - log_lo))))
            r = max(1, min(r_max, r))
            radii.add(r)

    return sorted(radii)
```

**Step 4: Update `_sandbox.py` to pass `r_cap`**

At line 176 (radii selection), change:
```python
radii = auto_radii(diam)
```
to:
```python
radii_list = auto_radii(diam, r_cap=r_cap)
```

Note: `r_cap` parameter doesn't exist yet on `estimate_sandbox_dimension` — it will be added in Task 7. For now, hardcode `r_cap=32` in the call:
```python
radii_list = auto_radii(diam, r_cap=32)
```

Also rename the local variable from `radii` to `radii_list` to avoid shadowing the future `radii` parameter.

**Step 5: Run full test suite**

Run: `uv run pytest tests/ -v --benchmark-disable`
Expected: All tests pass. (Some existing tests may produce slightly different D values due to changed radius distribution — the bounds are wide enough.)

**Step 6: Commit**

```bash
git add src/navi_fractal/_radii.py src/navi_fractal/_sandbox.py tests/test_radii.py
git commit -m "feat: align auto_radii to v4 (r_cap, dense_prefix=6, min_r_max)"
```

---

### Task 4: Moment Aggregation Factoring

Extract `_moments_from_center_masses()` and `_y_and_weights()` from inline code, matching v4 factoring.

**Files:**
- Modify: `src/navi_fractal/_sandbox.py`

**Step 1: Write failing tests for the two helpers**

Create `tests/test_moment_helpers.py`:

```python
# SPDX-License-Identifier: Apache-2.0
"""Tests for moment aggregation helpers."""

from __future__ import annotations

import math

from navi_fractal._sandbox import _moments_from_center_masses, _y_and_weights


class TestMomentsFromCenterMasses:
    def test_single_center(self) -> None:
        masses = [[1, 4, 9]]
        mean_m, var_m, mean_log, var_log = _moments_from_center_masses(masses)
        assert len(mean_m) == 3
        assert abs(mean_m[0] - 1.0) < 1e-10
        assert abs(mean_m[1] - 4.0) < 1e-10
        # Single center: variance should be 0
        assert all(v == 0.0 for v in var_m)
        assert all(v == 0.0 for v in var_log)

    def test_two_centers(self) -> None:
        masses = [[2, 8], [4, 8]]
        mean_m, var_m, mean_log, var_log = _moments_from_center_masses(masses)
        assert abs(mean_m[0] - 3.0) < 1e-10  # (2+4)/2
        assert abs(mean_m[1] - 8.0) < 1e-10  # (8+8)/2
        # Sample variance of [2,4] = (1+1)/1 = 2.0
        assert abs(var_m[0] - 2.0) < 1e-10

    def test_clamps_to_1(self) -> None:
        """Masses of 0 should be clamped to 1 for log."""
        masses = [[0, 5]]
        mean_m, var_m, mean_log, var_log = _moments_from_center_masses(masses)
        assert abs(mean_m[0] - 1.0) < 1e-10  # max(1, 0) = 1
        assert abs(mean_log[0] - 0.0) < 1e-10  # log(1) = 0

    def test_empty_raises(self) -> None:
        import pytest
        with pytest.raises(ValueError, match="no centers"):
            _moments_from_center_masses([])


class TestYAndWeights:
    def test_geometric_mode(self) -> None:
        mean_m = [4.0]
        var_m = [1.0]
        mean_log = [math.log(4.0)]
        var_log = [0.1]
        y, w = _y_and_weights(
            mean_mode="geometric",
            mean_M=mean_m, var_M=var_m,
            mean_logM=mean_log, var_logM=var_log,
            n_centers=10, use_wls=True, var_floor=1e-6,
        )
        assert abs(y[0] - math.log(4.0)) < 1e-10
        assert w is not None
        assert w[0] > 0

    def test_arithmetic_mode(self) -> None:
        mean_m = [4.0]
        var_m = [1.0]
        mean_log = [math.log(4.0)]
        var_log = [0.1]
        y, w = _y_and_weights(
            mean_mode="arithmetic",
            mean_M=mean_m, var_M=var_m,
            mean_logM=mean_log, var_logM=var_log,
            n_centers=10, use_wls=True, var_floor=1e-6,
        )
        assert abs(y[0] - math.log(4.0)) < 1e-10

    def test_no_wls_returns_none_weights(self) -> None:
        y, w = _y_and_weights(
            mean_mode="geometric",
            mean_M=[4.0], var_M=[1.0],
            mean_logM=[math.log(4.0)], var_logM=[0.1],
            n_centers=10, use_wls=False, var_floor=1e-6,
        )
        assert w is None
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_moment_helpers.py -v --benchmark-disable`
Expected: FAIL — functions not importable.

**Step 3: Implement the helpers in `_sandbox.py`**

Add before `estimate_sandbox_dimension()`:

```python
def _moments_from_center_masses(
    center_masses: Sequence[Sequence[int]],
) -> tuple[list[float], list[float], list[float], list[float]]:
    """Compute mean_M, var_M, mean_logM, var_logM across centers per radius."""
    n_centers = len(center_masses)
    if n_centers == 0:
        raise ValueError("no centers")

    n_radii = len(center_masses[0])
    sum_m = [0.0] * n_radii
    sum_m2 = [0.0] * n_radii
    sum_log = [0.0] * n_radii
    sum_log2 = [0.0] * n_radii

    for masses in center_masses:
        for i, m in enumerate(masses):
            mm = float(max(1, int(m)))
            lm = math.log(mm)
            sum_m[i] += mm
            sum_m2[i] += mm * mm
            sum_log[i] += lm
            sum_log2[i] += lm * lm

    mean_m = [s / n_centers for s in sum_m]
    mean_log = [s / n_centers for s in sum_log]

    if n_centers > 1:
        var_m = [
            max(0.0, (sum_m2[i] - n_centers * mean_m[i] ** 2) / (n_centers - 1))
            for i in range(n_radii)
        ]
        var_log = [
            max(0.0, (sum_log2[i] - n_centers * mean_log[i] ** 2) / (n_centers - 1))
            for i in range(n_radii)
        ]
    else:
        var_m = [0.0] * n_radii
        var_log = [0.0] * n_radii

    return mean_m, var_m, mean_log, var_log


def _y_and_weights(
    *,
    mean_mode: str,
    mean_M: Sequence[float],
    var_M: Sequence[float],
    mean_logM: Sequence[float],
    var_logM: Sequence[float],
    n_centers: int,
    use_wls: bool,
    var_floor: float,
) -> tuple[list[float], list[float] | None]:
    """Return y_eval and optional WLS weights for each radius."""
    y: list[float] = []
    w: list[float] | None = [] if use_wls else None

    for i in range(len(mean_M)):
        if mean_mode == "geometric":
            yi = float(mean_logM[i])
            y.append(yi)
            if use_wls:
                vy = float(var_logM[i]) / max(1, n_centers)
                vy = max(vy, var_floor)
                w.append(1.0 / vy)  # type: ignore[union-attr]
        else:
            mi = float(mean_M[i])
            yi = float(math.log(mi))
            y.append(yi)
            if use_wls:
                vy = (float(var_M[i]) / max(1, n_centers)) / max(mi * mi, 1e-30)
                vy = max(vy, var_floor)
                w.append(1.0 / vy)  # type: ignore[union-attr]

    return y, w
```

Add `from collections.abc import Sequence` to imports if not present.

**Step 4: Refactor `estimate_sandbox_dimension` to use the new helpers**

Replace the inline aggregation loop (lines 193-244) with:

```python
    # BFS mass collection
    if rng is None:
        rng = random.Random(seed)
    n_actual_centers = max(1, n_centers)
    centers = [rng.randrange(cg.n) for _ in range(n_actual_centers)]

    center_masses: list[list[int]] = []
    for center in centers:
        distances = bfs_layers(cg, center)
        masses = [ball_mass(distances, r) for r in radii_list]
        center_masses.append(masses)

    # Moment aggregation
    mean_M, var_M, mean_logM, var_logM = _moments_from_center_masses(center_masses)
    y_all, w_all = _y_and_weights(
        mean_mode=mean_mode,
        mean_M=mean_M,
        var_M=var_M,
        mean_logM=mean_logM,
        var_logM=var_logM,
        n_centers=len(centers),
        use_wls=use_wls,
        var_floor=var_floor,
    )

    # Filter degenerate + saturated radii (mean-based, v4 style)
    sat_thresh = max_saturation_frac * float(cg.n)
    radii_eval: list[int] = []
    log_radii: list[float] = []
    mean_mass_eval: list[float] = []
    y_eval: list[float] = []
    mass_variances: list[float] = []

    for i, r in enumerate(radii_list):
        mean_mass_eff = math.exp(mean_logM[i]) if mean_mode == "geometric" else mean_M[i]
        if mean_mass_eff <= 1.0:
            continue
        if mean_mass_eff >= sat_thresh:
            continue
        radii_eval.append(r)
        log_radii.append(math.log(r))
        mean_mass_eval.append(mean_M[i])
        y_eval.append(y_all[i])
        if w_all is not None:
            mass_variances.append(1.0 / w_all[i])  # store variance, not weight
        else:
            mass_variances.append(var_floor)
```

Note: This simultaneously implements Task 1d (center selection) and Task 1e (mean-based filtering) since the refactor naturally changes both.

**Step 5: Run full test suite**

Run: `uv run pytest tests/ -v --benchmark-disable`
Expected: All tests pass.

**Step 6: Commit**

```bash
git add src/navi_fractal/_sandbox.py tests/test_moment_helpers.py
git commit -m "refactor: extract _moments_from_center_masses and _y_and_weights helpers"
```

---

### Task 5: Threshold & Algorithm Fixes

Fix remaining defaults that differ from v4: `max_saturation_frac`, `var_floor` rename, curvature guard parameterization.

Note: Center selection (1d) and degenerate filtering (1e) were already done in Task 4.

**Files:**
- Modify: `src/navi_fractal/_sandbox.py`

**Step 1: Update function signature defaults**

Change in `estimate_sandbox_dimension()` signature:

- `max_saturation_frac: float = 0.2` → `max_saturation_frac: float = 0.95`
- `variance_floor: float = 1e-12` → `var_floor: float = 1e-6`
- Add `delta_quadratic_win: float = 3.0` parameter

Update all internal references from `variance_floor` to `var_floor`.

**Step 2: Parameterize curvature guard**

Replace the hardcoded curvature guard (line ~335):
```python
if aicc_quad < aicc_pw - 6.0:
```
with:
```python
if aicc_quad + delta_quadratic_win < aicc_pw:
```

**Step 3: Run full test suite**

Run: `uv run pytest tests/ -v --benchmark-disable`
Expected: All tests pass. Grid dimension may shift slightly due to changed defaults — existing bounds are wide enough.

**Step 4: Commit**

```bash
git add src/navi_fractal/_sandbox.py
git commit -m "feat: align thresholds to v4 (max_saturation_frac=0.95, var_floor=1e-6, delta_quadratic_win=3.0)"
```

---

### Task 6: Use Correct AICc Per Fit Type in Sandbox

Now that `aicc_for_wls` exists (Task 2), update the sandbox window search to use the correct AICc function based on `use_wls`.

**Files:**
- Modify: `src/navi_fractal/_sandbox.py`

**Step 1: Update imports**

Add `aicc_for_wls` to imports:
```python
from navi_fractal._regression import aicc_for_ols, aicc_for_wls, ols, quadratic_fit_residual, quadratic_fit_residual_wls, wls
```

**Step 2: Add fit/aicc function selection before window loop**

Before the window search loop, add:
```python
    aicc_fn = aicc_for_wls if use_wls else aicc_for_ols
```

**Step 3: Update window search to use `aicc_fn`**

Replace the OLS-only AICc computation block. Currently:
```python
            ols_fit = ols(wx, wy)
            aicc_pw = aicc(ols_fit.sse, n_w, 2)
            ...
            aicc_exp = aicc(exp_fit_result.sse, n_w, 2)
```

Replace with:
```python
            aicc_pw = aicc_fn(fit.sse, n_w, 2)
            ...
            exp_fit_result = (wls(exp_x, wy, inv_var) if use_wls else ols(exp_x, wy))
            aicc_exp = aicc_fn(exp_fit_result.sse, n_w, 2)
```

Remove the separate `ols_fit` computation — use the already-computed `fit` (which is WLS or OLS depending on `use_wls`).

**Step 4: Update curvature guard to use correct AICc and quadratic fit**

Replace:
```python
                quad_sse = quadratic_fit_residual(wx, wy)
                aicc_quad = aicc(quad_sse, n_w, 3)
```

With:
```python
                if use_wls:
                    quad_sse = quadratic_fit_residual_wls(wx, wy, inv_var)
                    aicc_quad = aicc_for_wls(quad_sse, n_w, 3)
                else:
                    quad_sse = quadratic_fit_residual(wx, wy)
                    aicc_quad = aicc_for_ols(quad_sse, n_w, 3)
```

**Step 5: Run full test suite**

Run: `uv run pytest tests/ -v --benchmark-disable`
Expected: All tests pass.

**Step 6: Commit**

```bash
git add src/navi_fractal/_sandbox.py
git commit -m "feat: use correct AICc per fit type (OLS vs WLS) in window search"
```

---

### Task 7: Quality Gate Alignment

Add `min_log_span` check, update `stderr_max` default, add `LOG_SPAN_TOO_SMALL` enum.

**Files:**
- Modify: `src/navi_fractal/_types.py`
- Modify: `src/navi_fractal/_quality_gate.py`
- Modify: `tests/test_quality_gates.py`

**Step 1: Write failing test for log_span check**

Add to `tests/test_quality_gates.py`:

```python
import math

class TestLogSpanOverride:
    def test_log_span_rejects_narrow(self) -> None:
        result = _make_accepted_result(window_r_min=2, window_r_max=3)
        # log(3/2) ~ 0.405, much less than log(3) ~ 1.099
        result = SandboxResult(
            dimension=2.0,
            reason=Reason.ACCEPTED,
            reason_detail=None,
            model_preference="powerlaw",
            delta_aicc=10.0,
            powerlaw_fit=LinFit(
                slope=2.0, intercept=0.0, r2=0.99,
                slope_stderr=0.01, sse=0.001, n_points=10,
            ),
            exponential_fit=None,
            window_r_min=2,
            window_r_max=3,
            window_log_span=math.log(3.0 / 2.0),
            window_delta_y=1.5,
            window_slope_range=None,
            window_aicc_quad_minus_lin=None,
            dimension_ci=None,
            delta_aicc_ci=None,
            bootstrap_valid_reps=0,
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
        passed, reason, detail = sandbox_quality_gate(result, preset="inclusive")
        assert not passed
        assert reason == QualityGateReason.LOG_SPAN_TOO_SMALL
```

Also update `_make_accepted_result` to accept `window_log_span` parameter:
```python
def _make_accepted_result(
    *,
    r2: float = 0.99,
    slope_stderr: float = 0.01,
    window_r_min: int = 1,
    window_r_max: int = 10,
    delta_aicc: float = 10.0,
    window_log_span: float = 2.3,
) -> SandboxResult:
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_quality_gates.py::TestLogSpanOverride -v --benchmark-disable`
Expected: FAIL — `QualityGateReason.LOG_SPAN_TOO_SMALL` doesn't exist.

**Step 3: Add enum member**

In `src/navi_fractal/_types.py`, add to `QualityGateReason`:
```python
    LOG_SPAN_TOO_SMALL = "log_span_too_small"
```

**Step 4: Update quality gate function**

In `src/navi_fractal/_quality_gate.py`:

4a. Add `import math` at top.

4b. Add `min_log_span: float | None = None` parameter to function signature.

4c. Change inclusive defaults tuple from `(0.85, 0.50, 3.0, 1.5)` to include log_span and new stderr:
```python
    if preset == "inclusive":
        defaults = (0.85, 0.25, 3.0, 1.5, math.log(3.0))
    elif preset == "strict":
        defaults = (0.95, 0.20, 4.0, 3.0, math.log(4.0))
```

4d. Add log_span threshold extraction:
```python
    log_span_threshold = min_log_span if min_log_span is not None else defaults[4]
```

4e. Add log_span check AFTER stderr check, BEFORE radius_ratio check:
```python
    if result.window_log_span is not None:
        if result.window_log_span < log_span_threshold:
            return (
                False,
                QualityGateReason.LOG_SPAN_TOO_SMALL,
                f"log_span={result.window_log_span:.4f} < {log_span_threshold:.4f}",
            )
```

**Step 5: Run full test suite**

Run: `uv run pytest tests/ -v --benchmark-disable`
Expected: All tests pass.

**Step 6: Commit**

```bash
git add src/navi_fractal/_types.py src/navi_fractal/_quality_gate.py tests/test_quality_gates.py
git commit -m "feat: add log_span quality gate check, align stderr_max to 0.25"
```

---

### Task 8: Missing Parameters

Add `radii`, `bootstrap_seed`, `r_cap`, and `notes` parameters, update signature.

**Files:**
- Modify: `src/navi_fractal/_sandbox.py`
- Modify: `tests/test_sandbox.py`

**Step 1: Write failing tests for new parameters**

Add to `tests/test_sandbox.py`:

```python
class TestNewParameters:
    def test_user_provided_radii(self) -> None:
        """Custom radii should bypass auto_radii."""
        grid = make_grid_graph(30, 30)
        result = estimate_sandbox_dimension(grid, seed=42, radii=[1, 2, 3, 5, 8, 13])
        # Should produce a result (accepted or refused) without error
        assert result.reason in (Reason.ACCEPTED, Reason.NO_WINDOW_PASSES_R2,
                                  Reason.AICC_PREFERS_EXPONENTIAL, Reason.NO_VALID_RADII)

    def test_r_cap_parameter(self) -> None:
        """r_cap should limit max radius from auto_radii."""
        grid = make_grid_graph(30, 30)
        result = estimate_sandbox_dimension(grid, seed=42, r_cap=10)
        if result.radii_eval:
            assert max(result.radii_eval) <= 10

    def test_delta_quadratic_win_parameter(self) -> None:
        """Setting delta_quadratic_win impossibly high should trigger curvature guard."""
        grid = make_grid_graph(30, 30)
        result = estimate_sandbox_dimension(grid, seed=42, delta_quadratic_win=1e6)
        # With impossibly strict curvature guard, should refuse
        assert result.dimension is None
        assert result.reason == Reason.CURVATURE_GUARD

    def test_var_floor_parameter(self) -> None:
        """var_floor parameter should be accepted (renamed from variance_floor)."""
        grid = make_grid_graph(30, 30)
        result = estimate_sandbox_dimension(grid, seed=42, var_floor=1e-3)
        assert result.dimension is not None

    def test_bootstrap_seed_separate(self) -> None:
        """Different bootstrap_seed should produce different CIs."""
        grid = make_grid_graph(20, 20)
        r1 = estimate_sandbox_dimension(grid, seed=42, bootstrap_reps=50, bootstrap_seed=1)
        r2 = estimate_sandbox_dimension(grid, seed=42, bootstrap_reps=50, bootstrap_seed=2)
        # Same main seed → same dimension, different bootstrap → different CI
        if r1.dimension is not None and r2.dimension is not None:
            assert r1.dimension == r2.dimension
            if r1.dimension_ci is not None and r2.dimension_ci is not None:
                assert r1.dimension_ci != r2.dimension_ci

    def test_notes_default_empty_string(self) -> None:
        """notes should default to empty string, not None."""
        grid = make_grid_graph(30, 30)
        result = estimate_sandbox_dimension(grid, seed=42)
        assert result.notes == ""
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sandbox.py::TestNewParameters -v --benchmark-disable`
Expected: FAIL — parameters not accepted.

**Step 3: Add parameters to signature**

Update `estimate_sandbox_dimension` signature to add:
```python
    radii: Sequence[int] | None = None,
    bootstrap_seed: int | None = None,
    r_cap: int = 32,
    notes: str = "",
```

Remove `notes: str | None` if it existed as `str | None`.

Add `from collections.abc import Sequence` to imports.

**Step 4: Implement `radii` parameter**

Replace the radii selection block:
```python
    if radii is not None:
        radii_list = sorted(set(int(r) for r in radii if int(r) >= 1))
    else:
        radii_list = auto_radii(diam, r_cap=r_cap)
```

**Step 5: Update `r_cap` passthrough**

Already handled — the signature now has `r_cap` and it's passed to `auto_radii`.

**Step 6: Update `notes` in all SandboxResult constructors**

Change all `notes=None` to `notes=notes` in the accepted result, and `notes=""` in `_make_empty_result` (or pass `notes` through).

**Step 7: Run full test suite**

Run: `uv run pytest tests/ -v --benchmark-disable`
Expected: All tests pass.

**Step 8: Commit**

```bash
git add src/navi_fractal/_sandbox.py tests/test_sandbox.py
git commit -m "feat: add radii, bootstrap_seed, r_cap, notes parameters"
```

---

### Task 9: Bootstrap Improvements

Rewrite bootstrap with `_percentile()`, validity threshold, direct index slicing, factored aggregation, and `delta_aicc_ci`.

**Files:**
- Modify: `src/navi_fractal/_sandbox.py`

**Step 1: Write failing test for improved bootstrap**

Add to `tests/test_sandbox.py`:

```python
class TestBootstrapImprovements:
    def test_bootstrap_produces_delta_aicc_ci(self) -> None:
        """Bootstrap should produce delta_aicc_ci alongside dimension_ci."""
        grid = make_grid_graph(20, 20)
        result = estimate_sandbox_dimension(grid, seed=42, bootstrap_reps=50)
        if result.dimension is not None and result.dimension_ci is not None:
            assert result.delta_aicc_ci is not None
            lo, hi = result.delta_aicc_ci
            assert lo <= hi

    def test_bootstrap_valid_reps_populated(self) -> None:
        grid = make_grid_graph(20, 20)
        result = estimate_sandbox_dimension(grid, seed=42, bootstrap_reps=50)
        if result.dimension_ci is not None:
            assert result.bootstrap_valid_reps > 0

    def test_bootstrap_min_validity(self) -> None:
        """With very few reps, bootstrap should not produce CI if too few are valid."""
        grid = make_grid_graph(20, 20)
        result = estimate_sandbox_dimension(grid, seed=42, bootstrap_reps=3)
        # 3 reps < max(10, 0.2*3) = 10, so CI should be None
        if result.dimension is not None:
            assert result.dimension_ci is None

    def test_bootstrap_seed_used(self) -> None:
        """bootstrap_seed should control bootstrap RNG separately."""
        grid = make_grid_graph(20, 20)
        r1 = estimate_sandbox_dimension(grid, seed=42, bootstrap_reps=50, bootstrap_seed=100)
        r2 = estimate_sandbox_dimension(grid, seed=42, bootstrap_reps=50, bootstrap_seed=100)
        # Same bootstrap_seed → identical CI
        assert r1.dimension_ci == r2.dimension_ci
```

**Step 2: Run tests to verify current behavior**

Run: `uv run pytest tests/test_sandbox.py::TestBootstrapImprovements -v --benchmark-disable`
Expected: Some tests may fail (delta_aicc_ci not populated, min_validity not enforced).

**Step 3: Add `_percentile()` helper**

Add to `_sandbox.py` before `estimate_sandbox_dimension`:

```python
def _percentile(sorted_vals: list[float], q: float) -> float:
    """Percentile with linear interpolation between adjacent ranks."""
    if not sorted_vals:
        return float("nan")
    if q <= 0:
        return float(sorted_vals[0])
    if q >= 1:
        return float(sorted_vals[-1])
    n = len(sorted_vals)
    pos = (n - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_vals[lo])
    t = pos - lo
    return float((1 - t) * sorted_vals[lo] + t * sorted_vals[hi])
```

**Step 4: Rewrite bootstrap loop**

Replace the entire bootstrap block (lines ~438-469) with v4-aligned version:

```python
    dimension_ci: tuple[float, float] | None = None
    delta_aicc_ci: tuple[float, float] | None = None
    boot_ok = 0

    if bootstrap_reps > 0:
        brng = random.Random(seed if bootstrap_seed is None else bootstrap_seed)
        boot_dims: list[float] = []
        boot_deltas: list[float] = []

        for _ in range(bootstrap_reps):
            # Resample center indices with replacement
            idxs = [brng.randrange(len(centers)) for _ in range(len(centers))]
            boot_masses = [center_masses[k] for k in idxs]

            # Recompute moments from resampled centers
            b_mean_M, b_var_M, b_mean_logM, b_var_logM = _moments_from_center_masses(
                boot_masses
            )
            b_y, b_w = _y_and_weights(
                mean_mode=mean_mode,
                mean_M=b_mean_M,
                var_M=b_var_M,
                mean_logM=b_mean_logM,
                var_logM=b_var_logM,
                n_centers=len(centers),
                use_wls=use_wls,
                var_floor=var_floor,
            )

            # Slice to winning window using original indices
            xw = log_radii[w_start:w_end]
            yw = b_y[w_start:w_end]  # direct index slicing, no round-trip

            if len(xw) < 2:
                continue

            try:
                if use_wls and b_w is not None:
                    ww = b_w[w_start:w_end]
                    b_fit_pow = wls(xw, yw, ww)
                    b_aicc_pow = aicc_for_wls(b_fit_pow.sse, len(xw), 2)
                    # Exponential alternative
                    exp_xw = [math.exp(lx) for lx in xw]
                    b_fit_exp = wls(exp_xw, yw, ww)
                    b_aicc_exp = aicc_for_wls(b_fit_exp.sse, len(exp_xw), 2)
                else:
                    b_fit_pow = ols(xw, yw)
                    b_aicc_pow = aicc_for_ols(b_fit_pow.sse, len(xw), 2)
                    exp_xw = [math.exp(lx) for lx in xw]
                    b_fit_exp = ols(exp_xw, yw)
                    b_aicc_exp = aicc_for_ols(b_fit_exp.sse, len(exp_xw), 2)

                boot_dims.append(float(b_fit_pow.slope))
                boot_deltas.append(float(b_aicc_exp - b_aicc_pow))
                boot_ok += 1
            except Exception:
                continue

        if boot_ok >= max(10, int(0.2 * bootstrap_reps)):
            dims_sorted = sorted(boot_dims)
            deltas_sorted = sorted(boot_deltas)
            dimension_ci = (_percentile(dims_sorted, 0.025), _percentile(dims_sorted, 0.975))
            delta_aicc_ci = (
                _percentile(deltas_sorted, 0.025),
                _percentile(deltas_sorted, 0.975),
            )
```

Note: `w_start` and `w_end` are the window indices from the `best_window` tuple. Make sure these are extracted before the bootstrap block:
```python
    w_start, w_end = best_window
```

Also note: the bootstrap slicing uses indices into `radii_list` (the full unfiltered list), NOT into `radii_eval` (filtered). The `log_radii` list here should correspond to all radii, and the window indices `w_start:w_end` should index into it correctly. IMPORTANT: verify that the window indices from the window search correspond to indices in the filtered arrays. If the window search iterates over filtered arrays, the indices are into those arrays, not the original `radii_list`. In that case, you need to map the window indices to indices in the full `radii_list` for the bootstrap slicing. This is a critical detail — trace through the v4 code carefully.

Actually, in v4, the window indices `wi` and `wj` are indices into the FULL `radii_eval` array (from `keep_idx[a]` and `keep_idx[b]`). The bootstrap slices `b_y[wi:wj+1]` from the full `b_y` array. So the window indices MUST be into the full radii array, not the filtered subset.

In our scaffold, the window search iterates over the FILTERED arrays (`log_radii`, `y_eval`), so `w_start:w_end` are indices into the filtered arrays. We need to either:
(a) Change the window search to use full-array indices (matching v4), or
(b) Map filtered indices back to full indices for bootstrap.

Option (a) is cleaner. Store the original full-array indices alongside the filtered arrays, and use them in the window search and bootstrap.

This is handled by storing a mapping from filtered index to original index:
```python
    # After filtering, store original indices for bootstrap
    original_indices: list[int] = []  # maps filtered idx → radii_list idx
    ...
    for i, r in enumerate(radii_list):
        ...
        original_indices.append(i)
```

Then in bootstrap, use `original_indices[w_start]` and `original_indices[w_end-1]+1` to slice from `b_y`.

**Step 5: Delete `_radius_index_for_log()`**

Remove the function (lines ~593-603 in current file). It's no longer used.

**Step 6: Update the final SandboxResult construction to include new fields**

```python
        delta_aicc_ci=delta_aicc_ci,
        bootstrap_valid_reps=boot_ok,
```

**Step 7: Run full test suite**

Run: `uv run pytest tests/ -v --benchmark-disable`
Expected: All tests pass.

**Step 8: Commit**

```bash
git add src/navi_fractal/_sandbox.py tests/test_sandbox.py
git commit -m "feat: align bootstrap to v4 (percentile interpolation, validity threshold, delta_aicc_ci)"
```

---

### Task 10: Final Test Tightening & Cleanup

Tighten grid bounds, add remaining test coverage, run lint/typecheck.

**Files:**
- Modify: `tests/test_known_dimensions.py`
- Modify: `tests/test_sandbox.py`

**Step 1: Tighten 30x30 grid bounds**

In `tests/test_known_dimensions.py`, line 25:
```python
        assert 1.55 <= result.dimension <= 1.75, f"D={result.dimension}"
```

Update the comment:
```python
        # After v4 alignment: 30x30 open grid produces D~1.62 (finite boundary effect).
        assert 1.55 <= result.dimension <= 1.75, f"D={result.dimension}"
```

**Step 2: Run the full test suite**

Run: `uv run pytest tests/ -v --benchmark-disable`
Expected: All tests pass.

**Step 3: Run lint and type check**

Run: `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy --strict src/navi_fractal/`
Expected: All green.

**Step 4: Fix any lint/type issues**

Address any issues from step 3.

**Step 5: Commit**

```bash
git add tests/test_known_dimensions.py
git commit -m "test: tighten 30x30 grid bounds to [1.55, 1.75] after v4 alignment"
```

**Step 6: Verify final D value**

Run a quick check:
```bash
uv run python -c "
from navi_fractal import make_grid_graph, estimate_sandbox_dimension
g = make_grid_graph(30, 30)
r = estimate_sandbox_dimension(g, seed=42)
print(f'D={r.dimension:.4f}, window=[{r.window_r_min}, {r.window_r_max}], R2={r.powerlaw_fit.r2:.4f}')
"
```

Expected: D should be close to 1.622 (matching v4).

---

## Execution Order Summary

| Order | Task | Description | Depends On |
|-------|------|-------------|------------|
| 1 | Task 1 | SandboxResult field additions | — |
| 2 | Task 2 | Regression module (aicc_for_wls, etc.) | — |
| 3 | Task 3 | auto_radii alignment | — |
| 4 | Task 4 | Moment aggregation factoring + center selection + filtering | — |
| 5 | Task 5 | Threshold defaults (saturation, var_floor, curvature) | Task 4 |
| 6 | Task 6 | Correct AICc per fit type in sandbox | Task 2 |
| 7 | Task 7 | Quality gate alignment | Task 1 |
| 8 | Task 8 | Missing parameters (radii, r_cap, bootstrap_seed, notes) | Tasks 3, 5 |
| 9 | Task 9 | Bootstrap improvements | Tasks 2, 4 |
| 10 | Task 10 | Final test tightening & cleanup | All |
