# Copyright 2024-2026 Nelson Spence
# SPDX-License-Identifier: Apache-2.0
"""Tests for BFS utilities."""

from __future__ import annotations

from navi_fractal import Graph, compile_to_undirected_metric_graph
from navi_fractal._bfs import (
    ball_mass,
    bfs_layer_counts,
    bfs_layers,
    estimate_diameter,
    masses_from_layer_counts,
)


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


class TestBfsLayerCounts:
    def test_path_layer_counts(self) -> None:
        g = Graph()
        for i in range(5):
            if i > 0:
                g.add_edge(i, i - 1)
        cg = compile_to_undirected_metric_graph(g)
        node_0_id = cg.label_to_id[0]
        counts = bfs_layer_counts(cg, node_0_id)
        # Path from end: 1 node at each distance 0..4
        assert counts == [1, 1, 1, 1, 1]
        assert sum(counts) == 5

    def test_star_layer_counts(self) -> None:
        """Star graph: center has all nodes at distance 1."""
        g = Graph()
        for i in range(1, 6):
            g.add_edge(0, i)
        cg = compile_to_undirected_metric_graph(g)
        center_id = cg.label_to_id[0]
        counts = bfs_layer_counts(cg, center_id)
        assert counts == [1, 5]

    def test_single_node_layer_counts(self) -> None:
        g = Graph()
        g.add_node(0)
        cg = compile_to_undirected_metric_graph(g)
        counts = bfs_layer_counts(cg, 0)
        assert counts == [1]

    def test_agrees_with_bfs_layers(self) -> None:
        """Layer counts must produce the same masses as the distance-array approach."""
        g = Graph()
        for i in range(10):
            if i > 0:
                g.add_edge(i, i - 1)
        # Add a branch
        g.add_edge(3, 10)
        g.add_edge(10, 11)
        cg = compile_to_undirected_metric_graph(g)

        for center in range(cg.n):
            dist = bfs_layers(cg, center)
            counts = bfs_layer_counts(cg, center)
            radii = list(range(1, max(dist) + 2))

            old_masses = [ball_mass(dist, r) for r in radii]
            new_masses = masses_from_layer_counts(counts, radii)
            assert old_masses == new_masses, f"center={center}"


class TestMassesFromLayerCounts:
    def test_simple(self) -> None:
        # counts[0]=1 (source), counts[1]=3, counts[2]=2
        counts = [1, 3, 2]
        assert masses_from_layer_counts(counts, [0]) == [1]
        assert masses_from_layer_counts(counts, [1]) == [4]
        assert masses_from_layer_counts(counts, [2]) == [6]
        assert masses_from_layer_counts(counts, [0, 1, 2]) == [1, 4, 6]

    def test_radius_beyond_max(self) -> None:
        counts = [1, 2]
        # Radius 5 is beyond max distance 1, should return total
        assert masses_from_layer_counts(counts, [5]) == [3]

    def test_multiple_radii(self) -> None:
        counts = [1, 1, 1, 1, 1]  # path: 1 node at each distance
        assert masses_from_layer_counts(counts, [0, 1, 2, 3, 4]) == [1, 2, 3, 4, 5]


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
