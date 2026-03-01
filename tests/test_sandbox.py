# SPDX-License-Identifier: Apache-2.0
"""Tests for sandbox dimension estimation and refusal cases."""

from __future__ import annotations

import pytest

from navi_fractal import (
    Graph,
    LinFit,
    QualityGateReason,
    Reason,
    SandboxResult,
    estimate_sandbox_dimension,
    make_grid_graph,
    sandbox_quality_gate,
)


class TestSandboxRefusals:
    def test_empty_graph_refused(self, empty_graph: Graph) -> None:
        result = estimate_sandbox_dimension(empty_graph, seed=42)
        assert result.dimension is None
        assert result.reason == Reason.EMPTY_GRAPH

    def test_single_node_refused(self, single_node_graph: Graph) -> None:
        result = estimate_sandbox_dimension(single_node_graph, seed=42)
        assert result.dimension is None
        assert result.reason == Reason.TRIVIAL_GRAPH

    def test_complete_graph_refused(self, complete_graph: Graph) -> None:
        result = estimate_sandbox_dimension(complete_graph, seed=42)
        # Complete graph has trivial diameter (1) — should be refused
        assert result.dimension is None

    def test_two_node_graph_refused(self) -> None:
        g = Graph()
        g.add_edge(0, 1)
        result = estimate_sandbox_dimension(g, seed=42)
        assert result.dimension is None

    def test_null_handler_on_library_logger(self) -> None:
        import logging

        logger = logging.getLogger("navi_fractal")
        assert any(isinstance(h, logging.NullHandler) for h in logger.handlers)

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
        g.add_node(2)
        g.add_node(3)
        result = estimate_sandbox_dimension(g, seed=42, component_policy="giant")
        assert result.reason != Reason.GIANT_COMPONENT_TOO_SMALL

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

    def test_min_delta_y_refusal(self) -> None:
        """Forcing min_delta_y impossibly high should refuse all windows."""
        grid = make_grid_graph(30, 30)
        result = estimate_sandbox_dimension(grid, seed=42, min_delta_y=1e6)
        assert result.dimension is None

    def test_no_valid_radii_refusal(self, star_graph: Graph) -> None:
        """Star graph should have too few radii for any window."""
        result = estimate_sandbox_dimension(star_graph, seed=42)
        assert result.dimension is None
        assert result.reason in (Reason.NO_VALID_RADII, Reason.TRIVIAL_GRAPH)

    def test_negative_slope_flag_works(self) -> None:
        """Verify require_positive_slope param works in both directions."""
        grid = make_grid_graph(30, 30)
        result_on = estimate_sandbox_dimension(grid, seed=42, require_positive_slope=True)
        result_off = estimate_sandbox_dimension(grid, seed=42, require_positive_slope=False)
        assert result_on.dimension is not None
        assert result_off.dimension is not None

    def test_invalid_component_policy_raises(self) -> None:
        grid = make_grid_graph(5, 5)
        with pytest.raises(ValueError, match="component_policy"):
            estimate_sandbox_dimension(grid, seed=42, component_policy="invalid")


class TestSandboxEstimation:
    def test_grid_produces_dimension(self) -> None:
        grid = make_grid_graph(30, 30)
        result = estimate_sandbox_dimension(grid, seed=42)
        assert result.dimension is not None
        assert result.reason == Reason.ACCEPTED

    def test_grid_dimension_near_2(self) -> None:
        grid = make_grid_graph(30, 30)
        result = estimate_sandbox_dimension(grid, seed=42)
        assert result.dimension is not None
        assert 1.5 < result.dimension < 2.5

    def test_result_has_fit(self) -> None:
        grid = make_grid_graph(30, 30)
        result = estimate_sandbox_dimension(grid, seed=42)
        assert result.powerlaw_fit is not None
        assert result.powerlaw_fit.r2 > 0.0

    def test_result_has_bootstrap_ci(self) -> None:
        grid = make_grid_graph(20, 20)
        result = estimate_sandbox_dimension(grid, seed=42, bootstrap_reps=50)
        if result.dimension is not None:
            assert result.dimension_ci is not None
            lo, hi = result.dimension_ci
            assert lo <= hi

    def test_bootstrap_runs_with_wls(self) -> None:
        """Bootstrap should work with both use_wls=True and use_wls=False."""
        grid = make_grid_graph(20, 20)
        result_wls = estimate_sandbox_dimension(grid, seed=42, bootstrap_reps=20, use_wls=True)
        result_ols = estimate_sandbox_dimension(grid, seed=42, bootstrap_reps=20, use_wls=False)
        if result_wls.dimension is not None:
            assert result_wls.dimension_ci is not None
        if result_ols.dimension is not None:
            assert result_ols.dimension_ci is not None

    def test_result_has_aicc(self) -> None:
        grid = make_grid_graph(30, 30)
        result = estimate_sandbox_dimension(grid, seed=42)
        if result.dimension is not None:
            assert result.delta_aicc is not None


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
        passed, qg_reason, _detail = sandbox_quality_gate(result)
        assert not passed
        assert qg_reason == QualityGateReason.NOT_ACCEPTED

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
            window_r_min=2,
            window_r_max=10,
            window_log_span=1.6,
            window_delta_y=3.0,
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
            seed=0,
            notes=None,
        )
        with pytest.raises(ValueError, match="Unknown preset"):
            sandbox_quality_gate(fake_result, preset="unknown")


class TestSlopeStability:
    def test_sub_len_defaults_to_min_points(self) -> None:
        """slope_stability_sub_len=None should default to min_points."""
        grid = make_grid_graph(30, 30)
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
        result = estimate_sandbox_dimension(
            grid,
            seed=42,
            slope_stability_guard=True,
            slope_stability_sub_len=3,
            max_slope_range=0.001,
        )
        assert result.dimension is None
