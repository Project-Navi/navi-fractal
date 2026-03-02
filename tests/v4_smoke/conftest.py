# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures and graph constructors for v4 smoke tests.

Provides:
- v4 imports (fractal_analysis_v4_mfa via sys.path)
- (u,v)-flower recursive scale-free constructor (Rozenfeld et al. 2007)
- Barabasi-Albert preferential attachment constructor
- Erdos-Renyi G(n,p) random graph constructor
- Pytest fixtures for standard flower instances
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# v4 import — add docs/reference/ to sys.path so we can import the v4 module.
# ---------------------------------------------------------------------------
_V4_DIR = str(Path(__file__).resolve().parents[2] / "docs" / "reference")
if _V4_DIR not in sys.path:
    sys.path.insert(0, _V4_DIR)

from fractal_analysis_v4_mfa import Graph as V4Graph  # noqa: E402

# ---------------------------------------------------------------------------
# (u,v)-flower constructor — Rozenfeld et al. 2007
# ---------------------------------------------------------------------------


def make_uv_flower(u: int, v: int, gen: int) -> V4Graph:
    """Build a (u,v)-flower recursive scale-free network.

    The (u,v)-flower is defined by:
    - Generation 0: a single edge between two hub nodes (0 and 1).
    - Each subsequent generation: every edge is replaced by two parallel
      paths of lengths u and v that share the edge's original endpoints.

    The box-counting dimension is d_B = ln(u+v) / ln(u) for u >= 2.

    Reference: Rozenfeld, Havlin & ben-Avraham (2007), NJP 9:175.
    """
    if u < 1 or v < 1:
        msg = f"u and v must be >= 1, got u={u}, v={v}"
        raise ValueError(msg)
    if gen < 0:
        msg = f"gen must be >= 0, got gen={gen}"
        raise ValueError(msg)

    # Track edges as a set of frozensets for undirected semantics.
    next_node = 2
    edges: set[frozenset[int]] = {frozenset({0, 1})}

    for _g in range(gen):
        new_edges: set[frozenset[int]] = set()
        for edge in edges:
            a, b = tuple(edge)
            # Path of length u from a to b
            prev = a
            for _j in range(u - 1):
                new_edges.add(frozenset({prev, next_node}))
                prev = next_node
                next_node += 1
            new_edges.add(frozenset({prev, b}))

            # Path of length v from a to b
            prev = a
            for _j in range(v - 1):
                new_edges.add(frozenset({prev, next_node}))
                prev = next_node
                next_node += 1
            new_edges.add(frozenset({prev, b}))

        edges = new_edges

    g = V4Graph(directed=False)
    for node_id in range(next_node):
        g.add_node(node_id)
    for edge in edges:
        a, b = tuple(edge)
        g.add_edge(a, b)

    return g


# ---------------------------------------------------------------------------
# Barabasi-Albert preferential attachment
# ---------------------------------------------------------------------------


def make_ba_graph(n: int, m: int, *, seed: int = 0) -> V4Graph:
    """Build a Barabasi-Albert preferential attachment graph.

    Starts with a complete graph on (m+1) nodes, then attaches each new node
    to m existing nodes chosen with probability proportional to their degree.
    """
    if n <= m:
        msg = f"n must be > m, got n={n}, m={m}"
        raise ValueError(msg)
    if m < 1:
        msg = f"m must be >= 1, got m={m}"
        raise ValueError(msg)

    rng = random.Random(seed)

    adj: dict[int, set[int]] = {i: set() for i in range(m + 1)}
    for i in range(m + 1):
        for j in range(i + 1, m + 1):
            adj[i].add(j)
            adj[j].add(i)

    stubs: list[int] = []
    for i in range(m + 1):
        stubs.extend([i] * m)

    for new_node in range(m + 1, n):
        adj[new_node] = set()
        targets: set[int] = set()
        while len(targets) < m:
            candidate = rng.choice(stubs)
            if candidate != new_node and candidate not in targets:
                targets.add(candidate)
        for t in targets:
            adj[new_node].add(t)
            adj[t].add(new_node)
            stubs.append(new_node)
            stubs.append(t)

    g = V4Graph(directed=False)
    for node_id in range(n):
        g.add_node(node_id)
    for u_node, neighbors in adj.items():
        for v_node in neighbors:
            if u_node < v_node:
                g.add_edge(u_node, v_node)

    return g


# ---------------------------------------------------------------------------
# Erdos-Renyi G(n,p) random graph
# ---------------------------------------------------------------------------


def make_er_graph(n: int, p: float, *, seed: int = 0) -> V4Graph:
    """Build an Erdos-Renyi G(n,p) random graph."""
    if n < 1:
        msg = f"n must be >= 1, got n={n}"
        raise ValueError(msg)
    if not 0.0 <= p <= 1.0:
        msg = f"p must be in [0, 1], got p={p}"
        raise ValueError(msg)

    rng = random.Random(seed)

    g = V4Graph(directed=False)
    for node_id in range(n):
        g.add_node(node_id)
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < p:
                g.add_edge(i, j)

    return g


# ---------------------------------------------------------------------------
# Pytest fixtures — standard flower instances
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def flower_22_gen8() -> V4Graph:
    """(2,2)-flower generation 8 — 43,692 nodes, d_B = ln4/ln2 = 2.0."""
    return make_uv_flower(2, 2, 8)


@pytest.fixture(scope="session")
def flower_33_gen5() -> V4Graph:
    """(3,3)-flower generation 5 — d_B = ln6/ln3 ~= 1.631."""
    return make_uv_flower(3, 3, 5)


@pytest.fixture(scope="session")
def flower_44_gen4() -> V4Graph:
    """(4,4)-flower generation 4 — d_B = ln8/ln4 = 1.5."""
    return make_uv_flower(4, 4, 4)


@pytest.fixture(scope="session")
def flower_23_gen6() -> V4Graph:
    """(2,3)-flower generation 6 — d_B = ln5/ln2 ~= 2.322."""
    return make_uv_flower(2, 3, 6)


@pytest.fixture(scope="session")
def flower_12_gen8() -> V4Graph:
    """(1,2)-flower generation 8 — transfractal (infinite d_B)."""
    return make_uv_flower(1, 2, 8)
