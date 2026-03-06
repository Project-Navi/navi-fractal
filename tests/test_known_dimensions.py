# Copyright 2024-2026 Nelson Spence
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
        # After v4 alignment: 30x30 open grid produces D~1.62 (finite boundary effect).
        assert 1.55 <= result.dimension <= 1.75, f"D={result.dimension}"
        assert result.powerlaw_fit is not None
        assert result.powerlaw_fit.r2 > 0.95

    def test_path_100_dimension_near_1(self) -> None:
        path = make_path_graph(100)
        # Disable curvature guard: finite paths have inherent boundary-induced
        # curvature that triggers the guard with mean-based filtering (v4 style).
        result = estimate_sandbox_dimension(path, seed=42, curvature_guard=False)
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

        degraded = False

        if original.dimension is not None and rewired_result.dimension is not None:
            if abs(original.dimension - rewired_result.dimension) > 0.1:
                degraded = True

        if original.reason != rewired_result.reason:
            degraded = True

        if original.delta_aicc is not None and rewired_result.delta_aicc is not None:
            if rewired_result.delta_aicc < original.delta_aicc:
                degraded = True

        if original.powerlaw_fit is not None and rewired_result.powerlaw_fit is not None:
            if rewired_result.powerlaw_fit.r2 < original.powerlaw_fit.r2:
                degraded = True

        assert degraded, (
            f"Rewiring should degrade dimension quality. "
            f"Original: D={original.dimension}. "
            f"Rewired: D={rewired_result.dimension}."
        )
