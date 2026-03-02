# SPDX-License-Identifier: Apache-2.0
"""Layer 1 math primitive smoke tests — validate v4 regression, AICc,
percentile, quadratic fit, moment aggregation, and slope stability functions.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# v4 import — add docs/reference/ to sys.path so we can import the v4 module.
# ---------------------------------------------------------------------------
_V4_DIR = str(Path(__file__).resolve().parents[2] / "docs" / "reference")
if _V4_DIR not in sys.path:
    sys.path.insert(0, _V4_DIR)

from fractal_analysis_v4_mfa import (  # noqa: E402
    _moments_from_center_masses,
    _percentile,
    _solve_3x3,
    aicc_for_ols,
    aicc_for_wls,
    linear_fit_ols,
    linear_fit_wls,
    quadratic_fit_sse_ols,
    slope_range_over_subwindows,
)

# ============================================================================
# TestOLS — Ordinary least squares regression
# ============================================================================


class TestOLS:
    """Smoke tests for linear_fit_ols."""

    def test_perfect_line(self) -> None:
        """y = 2x + 1 on 5 points: exact slope, intercept, R2."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0 * xi + 1.0 for xi in x]
        fit = linear_fit_ols(x, y)

        assert fit.slope == pytest.approx(2.0)
        assert fit.intercept == pytest.approx(1.0)
        assert fit.r2 == pytest.approx(1.0)
        assert fit.n == 5
        assert fit.weighted is False

    def test_known_residuals(self) -> None:
        """Noisy data: SSE > 0, R2 near but not equal to 1, finite stderr."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.1, 3.9, 6.2, 7.8, 10.1]  # noisy y ~ 2x
        fit = linear_fit_ols(x, y)

        assert fit.sse > 0.0
        assert 0.99 < fit.r2 < 1.0
        assert math.isfinite(fit.slope_stderr)
        assert fit.slope_stderr > 0.0

    def test_two_points_gives_perfect_fit(self) -> None:
        """Two points: R2=1.0, slope_stderr=inf (no degrees of freedom)."""
        x = [0.0, 1.0]
        y = [3.0, 7.0]
        fit = linear_fit_ols(x, y)

        assert fit.r2 == pytest.approx(1.0)
        assert fit.slope == pytest.approx(4.0)
        assert fit.intercept == pytest.approx(3.0)
        assert math.isinf(fit.slope_stderr)
        assert fit.n == 2

    def test_insufficient_points_raises(self) -> None:
        """Single point raises ValueError."""
        with pytest.raises(ValueError, match="need >=2"):
            linear_fit_ols([1.0], [2.0])


# ============================================================================
# TestWLS — Weighted least squares regression
# ============================================================================


class TestWLS:
    """Smoke tests for linear_fit_wls."""

    def test_uniform_weights_match_ols(self) -> None:
        """Uniform weights reproduce OLS slope, intercept, R2 exactly."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.3, 4.1, 5.8, 8.2, 9.9]
        w = [1.0, 1.0, 1.0, 1.0, 1.0]

        ols = linear_fit_ols(x, y)
        wls = linear_fit_wls(x, y, w)

        assert wls.slope == pytest.approx(ols.slope)
        assert wls.intercept == pytest.approx(ols.intercept)
        assert wls.r2 == pytest.approx(ols.r2)
        assert wls.weighted is True

    def test_downweight_outlier(self) -> None:
        """Downweighting an outlier shifts slope toward clean data."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y_clean = [2.0, 4.0, 6.0, 8.0, 10.0]  # perfect y = 2x

        # Corrupt last point
        y_dirty = y_clean[:]
        y_dirty[-1] = 20.0  # outlier

        # Equal weights: slope pulled by outlier
        fit_equal = linear_fit_wls(x, y_dirty, [1.0, 1.0, 1.0, 1.0, 1.0])

        # Downweight outlier: slope should be closer to 2.0
        fit_down = linear_fit_wls(x, y_dirty, [1.0, 1.0, 1.0, 1.0, 0.01])

        assert abs(fit_down.slope - 2.0) < abs(fit_equal.slope - 2.0)


# ============================================================================
# TestAICc — Corrected Akaike Information Criterion
# ============================================================================


class TestAICc:
    """Smoke tests for aicc_for_ols and aicc_for_wls."""

    def test_aicc_ols_formula(self) -> None:
        """Verify OLS AICc against exact formula."""
        sse = 5.0
        n = 10
        k = 2
        expected = n * math.log(sse / n) + 2 * k + (2 * k * (k + 1)) / (n - k - 1)
        result = aicc_for_ols(sse, n, k)
        assert result == pytest.approx(expected)

    def test_aicc_ols_edge_case_returns_inf(self) -> None:
        """n <= k+1 returns inf."""
        assert math.isinf(aicc_for_ols(1.0, 3, 2))
        assert math.isinf(aicc_for_ols(1.0, 2, 2))

    def test_aicc_wls_formula(self) -> None:
        """Verify WLS AICc against exact formula."""
        chi2 = 3.5
        n = 10
        k = 2
        expected = chi2 + 2 * k + (2 * k * (k + 1)) / (n - k - 1)
        result = aicc_for_wls(chi2, n, k)
        assert result == pytest.approx(expected)

    def test_aicc_wls_edge_case_returns_inf(self) -> None:
        """n <= k+1 returns inf."""
        assert math.isinf(aicc_for_wls(1.0, 3, 2))
        assert math.isinf(aicc_for_wls(1.0, 2, 2))

    def test_aicc_ols_lower_is_better(self) -> None:
        """Lower SSE gives lower AICc (same n, k)."""
        n, k = 20, 2
        aicc_low = aicc_for_ols(0.5, n, k)
        aicc_high = aicc_for_ols(5.0, n, k)
        assert aicc_low < aicc_high


# ============================================================================
# TestPercentile — Linear interpolation percentile
# ============================================================================


class TestPercentile:
    """Smoke tests for _percentile."""

    def test_median(self) -> None:
        """Median of [1,2,3,4,5] is 3.0."""
        assert _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 0.5) == pytest.approx(3.0)

    def test_interpolation(self) -> None:
        """q=0.25 on [1,2,3,4,5]: pos = (5-1)*0.25 = 1.0, value = 2.0."""
        result = _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 0.25)
        assert result == pytest.approx(2.0)

    def test_boundary_values(self) -> None:
        """q=0 gives first element, q=1 gives last element."""
        vals = [10.0, 20.0, 30.0]
        assert _percentile(vals, 0.0) == pytest.approx(10.0)
        assert _percentile(vals, 1.0) == pytest.approx(30.0)

    def test_interpolation_between_elements(self) -> None:
        """[0, 10] at q=0.3: pos=(2-1)*0.3=0.3, (1-0.3)*0 + 0.3*10 = 3.0."""
        result = _percentile([0.0, 10.0], 0.3)
        assert result == pytest.approx(3.0)


# ============================================================================
# TestQuadraticFit — Quadratic fit SSE (OLS)
# ============================================================================


class TestQuadraticFit:
    """Smoke tests for quadratic_fit_sse_ols."""

    def test_perfect_parabola(self) -> None:
        """y = x^2: quadratic fit should achieve SSE near zero."""
        x = [float(i) for i in range(10)]
        y = [xi * xi for xi in x]
        sse = quadratic_fit_sse_ols(x, y)
        assert sse < 1e-10

    def test_linear_data_small_quadratic_coeff(self) -> None:
        """y = 3x + 1: quadratic fit captures linear data with tiny SSE."""
        x = [float(i) for i in range(10)]
        y = [3.0 * xi + 1.0 for xi in x]
        sse = quadratic_fit_sse_ols(x, y)
        assert sse < 1e-8


# ============================================================================
# TestSolve3x3 — 3x3 linear system solver
# ============================================================================


class TestSolve3x3:
    """Smoke tests for _solve_3x3."""

    def test_identity_system(self) -> None:
        """Ix = b gives x = b."""
        a_mat = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        b = [3.0, 7.0, -2.0]
        x0, x1, x2 = _solve_3x3(a_mat, b)
        assert x0 == pytest.approx(3.0)
        assert x1 == pytest.approx(7.0)
        assert x2 == pytest.approx(-2.0)

    def test_known_system(self) -> None:
        """Verify solution by back-substitution: Ax = b."""
        a_mat = [[2.0, 1.0, -1.0], [-3.0, -1.0, 2.0], [-2.0, 1.0, 2.0]]
        b = [8.0, -11.0, -3.0]
        x0, x1, x2 = _solve_3x3(a_mat, b)

        # Verify by back-substitution
        for i in range(3):
            lhs = a_mat[i][0] * x0 + a_mat[i][1] * x1 + a_mat[i][2] * x2
            assert lhs == pytest.approx(b[i])


# ============================================================================
# TestMoments — Moment aggregation across centers
# ============================================================================


class TestMoments:
    """Smoke tests for _moments_from_center_masses."""

    def test_single_center(self) -> None:
        """Single center: mean = value, variance = 0."""
        center_masses = [[5, 10, 20]]
        mean_m, var_m, mean_log_m, var_log_m = _moments_from_center_masses(center_masses)

        assert mean_m == [pytest.approx(5.0), pytest.approx(10.0), pytest.approx(20.0)]
        assert var_m == [pytest.approx(0.0), pytest.approx(0.0), pytest.approx(0.0)]
        assert mean_log_m == [
            pytest.approx(math.log(5)),
            pytest.approx(math.log(10)),
            pytest.approx(math.log(20)),
        ]
        assert var_log_m == [pytest.approx(0.0), pytest.approx(0.0), pytest.approx(0.0)]

    def test_two_centers_known_variance(self) -> None:
        """Two centers: hand-computed mean and sample variance (n-1 denom)."""
        center_masses = [[4, 10], [8, 20]]
        mean_m, var_m, mean_log_m, _var_log_m = _moments_from_center_masses(center_masses)

        # mean_M
        assert mean_m[0] == pytest.approx(6.0)  # (4+8)/2
        assert mean_m[1] == pytest.approx(15.0)  # (10+20)/2

        # var_M (sample variance, n-1 denominator)
        # var = (sum_sq - n*mean^2) / (n-1)
        # radius 0: (16+64 - 2*36) / 1 = (80-72)/1 = 8.0
        assert var_m[0] == pytest.approx(8.0)
        # radius 1: (100+400 - 2*225) / 1 = (500-450)/1 = 50.0
        assert var_m[1] == pytest.approx(50.0)

        # mean_logM
        assert mean_log_m[0] == pytest.approx((math.log(4) + math.log(8)) / 2)
        assert mean_log_m[1] == pytest.approx((math.log(10) + math.log(20)) / 2)


# ============================================================================
# TestSlopeRange — Slope stability over subwindows
# ============================================================================


class TestSlopeRange:
    """Smoke tests for slope_range_over_subwindows."""

    def test_constant_slope_gives_zero_range(self) -> None:
        """Linear data: all subwindow slopes are identical, range = 0."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0 * xi + 1.0 for xi in x]
        sr = slope_range_over_subwindows(x, y, sub_len=3, use_wls=False)
        assert sr == pytest.approx(0.0, abs=1e-10)

    def test_curved_data_positive_range(self) -> None:
        """Quadratic data: subwindow slopes vary, range > 0."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [xi * xi for xi in x]  # y = x^2, slope varies
        sr = slope_range_over_subwindows(x, y, sub_len=3, use_wls=False)
        assert sr > 0.0
