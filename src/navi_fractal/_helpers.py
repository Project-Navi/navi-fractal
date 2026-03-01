# SPDX-License-Identifier: Apache-2.0
"""Helper graph constructors: grids, paths, and other standard topologies."""

from __future__ import annotations

from navi_fractal._graph import Graph


def make_grid_graph(rows: int, cols: int) -> Graph:
    """Create a 2D grid graph with rows * cols nodes.

    Nodes are labeled as (row, col) tuples.
    """
    if rows <= 0 or cols <= 0:
        raise ValueError(f"Grid dimensions must be positive, got {rows}x{cols}")
    g = Graph()
    for r in range(rows):
        for c in range(cols):
            g.add_node((r, c))
            if r > 0:
                g.add_edge((r, c), (r - 1, c))
            if c > 0:
                g.add_edge((r, c), (r, c - 1))
    return g


def make_path_graph(n: int) -> Graph:
    """Create a path graph with n nodes.

    Nodes are labeled as integers 0..n-1.
    """
    if n <= 0:
        raise ValueError(f"Path length must be positive, got {n}")
    g = Graph()
    for i in range(n):
        g.add_node(i)
        if i > 0:
            g.add_edge(i, i - 1)
    return g
