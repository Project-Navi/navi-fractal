# Copyright 2024-2026 Nelson Spence
# SPDX-License-Identifier: Apache-2.0
"""Tests for BFS utilities."""

from __future__ import annotations

from navi_fractal import Graph, compile_to_undirected_metric_graph
from navi_fractal._bfs import ball_mass, bfs_layers, estimate_diameter


class TestBfsLayers:
    def test_path_distances(self) -> None:
        g = Graph()
        for i in range(5):
            if i > 0:
                g.add_edge(i, i - 1)
        cg = compile_to_undirected_metric_graph(g)
        # Node 0 is at distance 0 from itself
        node_0_id = cg.label_to_id[0]
        dist = bfs_layers(cg, node_0_id)
        # Check max distance equals path length
        assert max(dist) == 4
        # All nodes reachable
        assert all(d >= 0 for d in dist)

    def test_unreachable_nodes(self) -> None:
        g = Graph()
        g.add_edge(0, 1)
        g.add_node(2)  # disconnected
        cg = compile_to_undirected_metric_graph(g)
        dist = bfs_layers(cg, 0)
        assert dist[cg.label_to_id[2]] == -1

    def test_single_node(self) -> None:
        g = Graph()
        g.add_node(0)
        cg = compile_to_undirected_metric_graph(g)
        dist = bfs_layers(cg, 0)
        assert dist == [0]


class TestBallMass:
    def test_ball_mass_includes_source(self) -> None:
        assert ball_mass([0, 1, 2, 3], radius=0) == 1

    def test_ball_mass_radius_1(self) -> None:
        assert ball_mass([0, 1, 2, 3], radius=1) == 2

    def test_ball_mass_full(self) -> None:
        assert ball_mass([0, 1, 2, 3], radius=3) == 4

    def test_ball_mass_excludes_unreachable(self) -> None:
        assert ball_mass([0, 1, -1, 2], radius=10) == 3


class TestEstimateDiameter:
    def test_path_diameter(self) -> None:
        g = Graph()
        for i in range(10):
            if i > 0:
                g.add_edge(i, i - 1)
        cg = compile_to_undirected_metric_graph(g)
        assert estimate_diameter(cg) == 9

    def test_single_node_diameter(self) -> None:
        g = Graph()
        g.add_node(0)
        cg = compile_to_undirected_metric_graph(g)
        assert estimate_diameter(cg) == 0

    def test_complete_graph_diameter(self) -> None:
        g = Graph()
        for i in range(5):
            for j in range(i + 1, 5):
                g.add_edge(i, j)
        cg = compile_to_undirected_metric_graph(g)
        assert estimate_diameter(cg) == 1
