# SPDX-License-Identifier: Apache-2.0
"""Tests for helper graph constructors."""

from __future__ import annotations

import pytest

from navi_fractal import make_grid_graph, make_path_graph


class TestMakeGridGraph:
    def test_grid_node_count(self) -> None:
        g = make_grid_graph(3, 4)
        assert len(g) == 12

    def test_grid_edge_count(self) -> None:
        g = make_grid_graph(3, 4)
        edges = sum(len(neighbors) for neighbors in g.adj.values()) // 2
        assert edges == 17

    def test_grid_invalid_dimensions(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            make_grid_graph(0, 5)
        with pytest.raises(ValueError, match="positive"):
            make_grid_graph(3, -1)


class TestMakePathGraph:
    def test_node_count(self) -> None:
        g = make_path_graph(10)
        assert len(g) == 10

    def test_edge_count(self) -> None:
        g = make_path_graph(10)
        edges = sum(len(neighbors) for neighbors in g.adj.values()) // 2
        assert edges == 9

    def test_endpoints_degree_1(self) -> None:
        g = make_path_graph(5)
        degrees = sorted(len(neighbors) for neighbors in g.adj.values())
        assert degrees[0] == 1
        assert degrees[-1] == 2

    def test_single_node(self) -> None:
        g = make_path_graph(1)
        assert len(g) == 1

    def test_invalid_size(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            make_path_graph(0)
        with pytest.raises(ValueError, match="positive"):
            make_path_graph(-1)
