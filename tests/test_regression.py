# Copyright 2024-2026 Nelson Spence
# SPDX-License-Identifier: Apache-2.0
"""Tests for regression utilities."""

from __future__ import annotations

import math

import pytest

from navi_fractal._regression import (
    aicc,
    aicc_for_ols,
    aicc_for_wls,
    ols,
    quadratic_fit_residual,
    quadratic_fit_residual_wls,
    slope_range_over_subwindows,
    wls,
)


class TestOLS:
    def test_perfect_fit(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        fit = ols(x, y)
        assert abs(fit.slope - 2.0) < 1e-10
        assert abs(fit.intercept - 0.0) < 1e-10
        assert abs(fit.r2 - 1.0) < 1e-10

    def test_with_offset(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0]
        y = [3.0, 5.0, 7.0, 9.0]  # y = 2x + 1
        fit = ols(x, y)
        assert abs(fit.slope - 2.0) < 1e-10
        assert abs(fit.intercept - 1.0) < 1e-10

    def test_r2_imperfect(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [1.1, 1.9, 3.2, 3.8, 5.1]
        fit = ols(x, y)
        assert 0.9 < fit.r2 < 1.0

    def test_slope_stderr(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [1.1, 1.9, 3.2, 3.8, 5.1]
        fit = ols(x, y)
        assert fit.slope_stderr > 0
        assert fit.slope_stderr < 1.0

    def test_too_few_points(self) -> None:
        with pytest.raises(ValueError, match="at least 2"):
            ols([1.0], [1.0])

    def test_mismatched_lengths(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            ols([1.0, 2.0], [1.0])


class TestWLS:
    def test_uniform_weights_match_ols(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.1, 3.9, 6.2, 7.8, 10.1]
        w = [1.0, 1.0, 1.0, 1.0, 1.0]
        fit_ols = ols(x, y)
        fit_wls = wls(x, y, w)
        assert abs(fit_ols.slope - fit_wls.slope) < 1e-10
        assert abs(fit_ols.intercept - fit_wls.intercept) < 1e-10

    def test_high_weight_pulls_fit(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 50.0, 6.0, 8.0, 10.0]  # outlier at x=2 (off-center)
        w_uniform = [1.0, 1.0, 1.0, 1.0, 1.0]
        w_low_outlier = [1.0, 0.001, 1.0, 1.0, 1.0]
        fit_uniform = wls(x, y, w_uniform)
        fit_low = wls(x, y, w_low_outlier)
        # With low weight on outlier, slope should be closer to true slope (2.0)
        assert abs(fit_low.slope - 2.0) < abs(fit_uniform.slope - 2.0)


class TestAICc:
    """Tests for backward-compatible aicc alias (delegates to aicc_for_ols)."""

    def test_lower_sse_preferred(self) -> None:
        a1 = aicc(1.0, 20, 2)
        a2 = aicc(10.0, 20, 2)
        assert a1 < a2

    def test_more_params_penalized(self) -> None:
        a1 = aicc(1.0, 20, 2)
        a2 = aicc(1.0, 20, 3)
        assert a1 < a2

    def test_small_sample_correction(self) -> None:
        a_large = aicc(1.0, 100, 2)
        a_small = aicc(1.0, 5, 2)
        # Small sample has larger correction
        assert a_small > a_large

    def test_insufficient_points(self) -> None:
        assert aicc(1.0, 3, 2) == float("inf")

    def test_alias_matches_aicc_for_ols(self) -> None:
        assert aicc is aicc_for_ols


class TestAICcForOLS:
    """Tests for the renamed aicc_for_ols function."""

    def test_lower_sse_preferred(self) -> None:
        a1 = aicc_for_ols(1.0, 20, 2)
        a2 = aicc_for_ols(10.0, 20, 2)
        assert a1 < a2

    def test_more_params_penalized(self) -> None:
        a1 = aicc_for_ols(1.0, 20, 2)
        a2 = aicc_for_ols(1.0, 20, 3)
        assert a1 < a2

    def test_formula_matches_expected(self) -> None:
        # Manual calculation: n*log(sse/n) + 2k + 2k(k+1)/(n-k-1)
        sse, n, k = 5.0, 20, 2
        expected = n * math.log(sse / n) + 2 * k + (2 * k * (k + 1)) / (n - k - 1)
        assert abs(aicc_for_ols(sse, n, k) - expected) < 1e-12

    def test_zero_sse_returns_neg_inf(self) -> None:
        assert aicc_for_ols(0.0, 20, 2) == float("-inf")

    def test_insufficient_points(self) -> None:
        assert aicc_for_ols(1.0, 3, 2) == float("inf")
        assert aicc_for_ols(1.0, 2, 2) == float("inf")


class TestAICcForWLS:
    """Tests for the WLS AICc variant."""

    def test_formula_matches_expected(self) -> None:
        # chi2 + 2k + 2k(k+1)/(n-k-1)
        chi2, n, k = 5.0, 20, 2
        expected = chi2 + 2 * k + (2 * k * (k + 1)) / (n - k - 1)
        assert abs(aicc_for_wls(chi2, n, k) - expected) < 1e-12

    def test_differs_from_ols(self) -> None:
        # WLS and OLS formulas differ: OLS uses n*log(sse/n), WLS uses chi2 directly
        sse, n, k = 5.0, 20, 2
        ols_val = aicc_for_ols(sse, n, k)
        wls_val = aicc_for_wls(sse, n, k)
        assert ols_val != wls_val

    def test_lower_chi2_preferred(self) -> None:
        a1 = aicc_for_wls(1.0, 20, 2)
        a2 = aicc_for_wls(10.0, 20, 2)
        assert a1 < a2

    def test_more_params_penalized(self) -> None:
        a1 = aicc_for_wls(1.0, 20, 2)
        a2 = aicc_for_wls(1.0, 20, 3)
        assert a1 < a2

    def test_insufficient_points(self) -> None:
        assert aicc_for_wls(1.0, 3, 2) == float("inf")

    def test_small_sample_correction(self) -> None:
        a_large = aicc_for_wls(5.0, 100, 2)
        a_small = aicc_for_wls(5.0, 5, 2)
        assert a_small > a_large

    def test_zero_chi2_not_neg_inf(self) -> None:
        # WLS does NOT return -inf for zero chi2 (unlike OLS)
        result = aicc_for_wls(0.0, 20, 2)
        assert result != float("-inf")
        # Should be 0 + 2*2 + correction = 4 + small correction
        expected = 0.0 + 2 * 2 + (2 * 2 * 3) / (20 - 2 - 1)
        assert abs(result - expected) < 1e-12


class TestQuadraticFit:
    def test_perfect_quadratic(self) -> None:
        x = [float(i) for i in range(10)]
        y = [xi * xi for xi in x]
        sse = quadratic_fit_residual(x, y)
        assert sse < 1e-10

    def test_linear_data_nonzero_residual(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        sse = quadratic_fit_residual(x, y)
        # Quadratic should fit linear data perfectly (a=0)
        assert sse < 1e-10

    def test_too_few_points(self) -> None:
        assert quadratic_fit_residual([1.0, 2.0], [1.0, 2.0]) == float("inf")


class TestQuadraticFitWLS:
    """Tests for weighted quadratic fit."""

    def test_perfect_quadratic(self) -> None:
        x = [float(i) for i in range(10)]
        y = [xi * xi for xi in x]
        w = [1.0] * 10
        wsse = quadratic_fit_residual_wls(x, y, w)
        assert wsse < 1e-10

    def test_uniform_weights_match_ols(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        y = [xi * xi + 0.1 * xi - 0.5 for xi in x]
        w = [1.0] * len(x)
        ols_sse = quadratic_fit_residual(x, y)
        wls_wsse = quadratic_fit_residual_wls(x, y, w)
        assert abs(ols_sse - wls_wsse) < 1e-10

    def test_weighted_changes_result(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [1.0, 4.0, 10.0, 16.0, 25.0]  # noisy quadratic
        w_uniform = [1.0] * 5
        w_varied = [10.0, 0.1, 1.0, 0.1, 10.0]  # emphasize endpoints
        sse_uniform = quadratic_fit_residual_wls(x, y, w_uniform)
        sse_varied = quadratic_fit_residual_wls(x, y, w_varied)
        # Different weights should give different WSSE
        assert sse_uniform != sse_varied

    def test_too_few_points(self) -> None:
        assert quadratic_fit_residual_wls([1.0, 2.0], [1.0, 4.0], [1.0, 1.0]) == float("inf")

    def test_linear_data_fits_perfectly(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        w = [1.0] * 5
        wsse = quadratic_fit_residual_wls(x, y, w)
        # Quadratic should fit linear data perfectly (a=0)
        assert wsse < 1e-10


class TestSlopeRangeOverSubwindows:
    """Tests for slope_range_over_subwindows."""

    def test_constant_slope_gives_zero(self) -> None:
        # Perfect linear data: all sub-windows have the same slope
        x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0]  # slope = 2.0 everywhere
        sr = slope_range_over_subwindows(x, y, sub_len=3, use_wls=False)
        assert sr < 1e-10

    def test_curved_data_gives_nonzero(self) -> None:
        # Quadratic data: slope changes across sub-windows
        x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        y = [xi * xi for xi in x]
        sr = slope_range_over_subwindows(x, y, sub_len=3, use_wls=False)
        assert sr > 0.5

    def test_wls_requires_weights(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0]
        y = [1.0, 2.0, 3.0, 4.0]
        with pytest.raises(ValueError, match="w must be provided"):
            slope_range_over_subwindows(x, y, sub_len=3, use_wls=True)

    def test_wls_with_uniform_weights_matches_ols(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        y = [xi * xi for xi in x]
        w = [1.0] * len(x)
        sr_ols = slope_range_over_subwindows(x, y, sub_len=3, use_wls=False)
        sr_wls = slope_range_over_subwindows(x, y, sub_len=3, use_wls=True, w=w)
        assert abs(sr_ols - sr_wls) < 1e-10

    def test_sub_len_too_large(self) -> None:
        x = [1.0, 2.0, 3.0]
        y = [1.0, 2.0, 3.0]
        sr = slope_range_over_subwindows(x, y, sub_len=5, use_wls=False)
        assert sr == 0.0

    def test_single_subwindow_gives_zero(self) -> None:
        # When n == sub_len, only one window → range = 0
        x = [1.0, 2.0, 3.0]
        y = [1.0, 4.0, 9.0]
        sr = slope_range_over_subwindows(x, y, sub_len=3, use_wls=False)
        assert sr == 0.0
