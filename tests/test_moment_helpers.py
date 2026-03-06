# Copyright 2024-2026 Nelson Spence
# SPDX-License-Identifier: Apache-2.0
"""Tests for moment aggregation helpers."""

from __future__ import annotations

import math

import pytest

from navi_fractal._sandbox import _moments_from_center_masses, _y_and_weights


class TestMomentsFromCenterMasses:
    def test_single_center(self) -> None:
        masses = [[1, 4, 9]]
        mean_m, var_m, _mean_log, var_log = _moments_from_center_masses(masses)
        assert len(mean_m) == 3
        assert abs(mean_m[0] - 1.0) < 1e-10
        assert abs(mean_m[1] - 4.0) < 1e-10
        assert all(v == 0.0 for v in var_m)
        assert all(v == 0.0 for v in var_log)

    def test_two_centers(self) -> None:
        masses = [[2, 8], [4, 8]]
        mean_m, var_m, _mean_log, _var_log = _moments_from_center_masses(masses)
        assert abs(mean_m[0] - 3.0) < 1e-10
        assert abs(mean_m[1] - 8.0) < 1e-10
        assert abs(var_m[0] - 2.0) < 1e-10  # sample variance of [2,4]

    def test_clamps_to_1(self) -> None:
        masses = [[0, 5]]
        mean_m, _var_m, mean_log, _var_log = _moments_from_center_masses(masses)
        assert abs(mean_m[0] - 1.0) < 1e-10
        assert abs(mean_log[0] - 0.0) < 1e-10

    def test_empty_raises(self) -> None:
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
            mean_mass=mean_m,
            var_mass=var_m,
            mean_log_mass=mean_log,
            var_log_mass=var_log,
            n_centers=10,
            use_wls=True,
            var_floor=1e-6,
        )
        assert abs(y[0] - math.log(4.0)) < 1e-10
        assert w is not None
        assert w[0] > 0

    def test_arithmetic_mode(self) -> None:
        mean_m = [4.0]
        var_m = [1.0]
        mean_log = [math.log(4.0)]
        var_log = [0.1]
        y, _w = _y_and_weights(
            mean_mode="arithmetic",
            mean_mass=mean_m,
            var_mass=var_m,
            mean_log_mass=mean_log,
            var_log_mass=var_log,
            n_centers=10,
            use_wls=True,
            var_floor=1e-6,
        )
        assert abs(y[0] - math.log(4.0)) < 1e-10

    def test_no_wls_returns_none_weights(self) -> None:
        _y, w = _y_and_weights(
            mean_mode="geometric",
            mean_mass=[4.0],
            var_mass=[1.0],
            mean_log_mass=[math.log(4.0)],
            var_log_mass=[0.1],
            n_centers=10,
            use_wls=False,
            var_floor=1e-6,
        )
        assert w is None
