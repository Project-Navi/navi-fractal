# SPDX-License-Identifier: Apache-2.0
"""Shared test fixtures."""

from __future__ import annotations

import pytest

from navi_fractal import (
    CompiledGraph,
    Graph,
    compile_to_undirected_metric_graph,
    make_grid_graph,
    make_path_graph,
)


@pytest.fixture
def small_grid() -> Graph:
    """5x5 grid graph."""
    return make_grid_graph(5, 5)


@pytest.fixture
def compiled_small_grid(small_grid: Graph) -> CompiledGraph:
    """Compiled 5x5 grid graph."""
    return compile_to_undirected_metric_graph(small_grid)


@pytest.fixture
def medium_grid() -> Graph:
    """30x30 grid graph for sandbox estimation."""
    return make_grid_graph(30, 30)


@pytest.fixture
def path_graph() -> Graph:
    """Path graph with 100 nodes."""
    return make_path_graph(100)


@pytest.fixture
def complete_graph() -> Graph:
    """Complete graph K_20."""
    g = Graph()
    nodes = list(range(20))
    for u in nodes:
        for v in nodes:
            if u < v:
                g.add_edge(u, v)
    return g


@pytest.fixture
def empty_graph() -> Graph:
    """Empty graph with no nodes."""
    return Graph()


@pytest.fixture
def single_node_graph() -> Graph:
    """Graph with a single node."""
    g = Graph()
    g.add_node(0)
    return g


@pytest.fixture
def dust_cloud_graph() -> Graph:
    """Graph with many isolated nodes — giant component has 1 node."""
    g = Graph()
    for i in range(10):
        g.add_node(i)
    return g


@pytest.fixture
def star_graph() -> Graph:
    """Star graph S_50: central node connected to 50 leaves."""
    g = Graph()
    for i in range(1, 51):
        g.add_edge(0, i)
    return g


@pytest.fixture
def large_grid() -> Graph:
    """50x50 grid for null model comparison."""
    return make_grid_graph(50, 50)
