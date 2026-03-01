# SPDX-License-Identifier: Apache-2.0
"""Tests for regression utilities."""

from __future__ import annotations

import pytest

from navi_fractal._regression import aicc, ols, quadratic_fit_residual, wls


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
