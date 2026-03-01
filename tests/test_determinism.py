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
        assert r1.y_eval != r2.y_eval or r1.dimension != r2.dimension
