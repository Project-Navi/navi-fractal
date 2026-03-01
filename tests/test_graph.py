# SPDX-License-Identifier: Apache-2.0
"""Tests for graph construction and compilation."""

from __future__ import annotations

import pytest

from navi_fractal import (
    Graph,
    compile_to_undirected_metric_graph,
)


class TestGraph:
    def test_add_node(self) -> None:
        g = Graph()
        g.add_node("a")
        assert "a" in g.nodes

    def test_add_node_idempotent(self) -> None:
        g = Graph()
        g.add_node("a")
        g.add_node("a")
        assert len(g) == 1

    def test_add_edge(self) -> None:
        g = Graph()
        g.add_edge("a", "b")
        assert "b" in g.adj["a"]
        assert "a" in g.adj["b"]

    def test_add_edge_creates_nodes(self) -> None:
        g = Graph()
        g.add_edge("a", "b")
        assert "a" in g.nodes
        assert "b" in g.nodes

    def test_no_self_loops(self) -> None:
        g = Graph()
        g.add_edge("a", "a")
        assert "a" not in g.adj["a"]

    def test_len(self) -> None:
        g = Graph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        assert len(g) == 3


class TestCompiledGraph:
    def test_compilation(self) -> None:
        g = Graph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        cg = compile_to_undirected_metric_graph(g)
        assert cg.n == 3
        assert len(cg.adj) == 3

    def test_adjacency_sorted(self) -> None:
        g = Graph()
        g.add_edge("a", "c")
        g.add_edge("a", "b")
        cg = compile_to_undirected_metric_graph(g)
        a_id = cg.label_to_id["a"]
        neighbors = cg.adj[a_id]
        assert neighbors == tuple(sorted(neighbors))

    def test_frozen(self) -> None:
        g = Graph()
        g.add_edge("a", "b")
        cg = compile_to_undirected_metric_graph(g)
        with pytest.raises(AttributeError):
            cg.n = 99  # type: ignore[misc]

    def test_label_roundtrip(self) -> None:
        g = Graph()
        g.add_edge("x", "y")
        cg = compile_to_undirected_metric_graph(g)
        for label in ["x", "y"]:
            node_id = cg.label_to_id[label]
            assert cg.id_to_label[node_id] == label
