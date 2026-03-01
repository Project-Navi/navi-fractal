# SPDX-License-Identifier: Apache-2.0
"""Tests for degree-preserving rewiring null model."""

from __future__ import annotations

import random

from navi_fractal import (
    Graph,
    compile_to_undirected_metric_graph,
    degree_preserving_rewire_undirected,
    make_grid_graph,
)


class TestRewiring:
    def test_preserves_degree_sequence(self) -> None:
        grid = make_grid_graph(10, 10)
        cg = compile_to_undirected_metric_graph(grid)
        rewired = degree_preserving_rewire_undirected(cg, seed=42)
        original_degrees = sorted(len(cg.adj[i]) for i in range(cg.n))
        rewired_degrees = sorted(len(rewired.adj[i]) for i in range(rewired.n))
        assert original_degrees == rewired_degrees

    def test_preserves_node_count(self) -> None:
        grid = make_grid_graph(5, 5)
        cg = compile_to_undirected_metric_graph(grid)
        rewired = degree_preserving_rewire_undirected(cg, seed=42)
        assert rewired.n == cg.n

    def test_preserves_edge_count(self) -> None:
        grid = make_grid_graph(5, 5)
        cg = compile_to_undirected_metric_graph(grid)
        rewired = degree_preserving_rewire_undirected(cg, seed=42)
        original_edges = sum(len(cg.adj[i]) for i in range(cg.n)) // 2
        rewired_edges = sum(len(rewired.adj[i]) for i in range(rewired.n)) // 2
        assert original_edges == rewired_edges

    def test_changes_structure(self) -> None:
        grid = make_grid_graph(10, 10)
        cg = compile_to_undirected_metric_graph(grid)
        rewired = degree_preserving_rewire_undirected(cg, seed=42)
        # At least some adjacency should differ
        diffs = sum(1 for i in range(cg.n) if cg.adj[i] != rewired.adj[i])
        assert diffs > 0

    def test_deterministic(self) -> None:
        grid = make_grid_graph(5, 5)
        cg = compile_to_undirected_metric_graph(grid)
        r1 = degree_preserving_rewire_undirected(cg, seed=123)
        r2 = degree_preserving_rewire_undirected(cg, seed=123)
        assert r1.adj == r2.adj

    def test_different_seeds_differ(self) -> None:
        grid = make_grid_graph(10, 10)
        cg = compile_to_undirected_metric_graph(grid)
        r1 = degree_preserving_rewire_undirected(cg, seed=1)
        r2 = degree_preserving_rewire_undirected(cg, seed=2)
        assert r1.adj != r2.adj

    def test_rng_parameter_overrides_seed(self) -> None:
        """When rng is provided, it should be used instead of seed."""
        grid = make_grid_graph(10, 10)
        cg = compile_to_undirected_metric_graph(grid)
        rng = random.Random(42)
        rewired = degree_preserving_rewire_undirected(cg, seed=0, rng=rng)
        rewired_seed42 = degree_preserving_rewire_undirected(cg, seed=42)
        rewired_seed0 = degree_preserving_rewire_undirected(cg, seed=0)
        assert rewired.adj == rewired_seed42.adj
        assert rewired.adj != rewired_seed0.adj

    def test_tiny_graph_unchanged(self) -> None:
        g = Graph()
        g.add_edge(0, 1)
        cg = compile_to_undirected_metric_graph(g)
        rewired = degree_preserving_rewire_undirected(cg, seed=42)
        # Only one edge — nothing to swap with
        assert rewired.adj == cg.adj
