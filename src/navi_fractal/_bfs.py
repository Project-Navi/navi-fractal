# Copyright 2024-2026 Nelson Spence
# SPDX-License-Identifier: Apache-2.0
"""BFS utilities for mass computation and diameter estimation."""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence

from navi_fractal._graph import CompiledGraph


def bfs_layers(g: CompiledGraph, source: int) -> list[int]:
    """Return distance from source to every node (-1 if unreachable).

    Uses BFS on the compiled graph's sorted adjacency for determinism.
    """
    dist = [-1] * g.n
    dist[source] = 0
    queue: deque[int] = deque([source])
    while queue:
        u = queue.popleft()
        for v in g.adj[u]:
            if dist[v] == -1:
                dist[v] = dist[u] + 1
                queue.append(v)
    return dist


def bfs_layer_counts(g: CompiledGraph, source: int) -> list[int]:
    """Return layer counts: counts[d] = number of nodes at distance d.

    Uses BFS on the compiled graph's sorted adjacency for determinism.
    The returned list has length (max_distance + 1). Unreachable nodes
    are excluded from all counts.
    """
    dist = [-1] * g.n
    dist[source] = 0
    queue: deque[int] = deque([source])
    max_dist = 0
    while queue:
        u = queue.popleft()
        for v in g.adj[u]:
            if dist[v] == -1:
                d = dist[u] + 1
                dist[v] = d
                if d > max_dist:
                    max_dist = d
                queue.append(v)

    counts = [0] * (max_dist + 1)
    for d in dist:
        if d >= 0:
            counts[d] += 1
    return counts


def masses_from_layer_counts(
    layer_counts: list[int],
    radii: Sequence[int],
) -> list[int]:
    """Compute ball masses at each radius from layer counts using prefix sums.

    For each radius r, mass = sum of layer_counts[0..r] (inclusive).
    Radii beyond the maximum distance get the total reachable count.
    """
    # Build prefix sums: prefix[i] = sum(layer_counts[0..i])
    n_layers = len(layer_counts)
    prefix = [0] * n_layers
    prefix[0] = layer_counts[0]
    for i in range(1, n_layers):
        prefix[i] = prefix[i - 1] + layer_counts[i]

    total = prefix[-1]
    masses = []
    for r in radii:
        if r >= n_layers:
            masses.append(total)
        else:
            masses.append(prefix[r])
    return masses


def ball_mass(distances: list[int], radius: int) -> int:
    """Count nodes within distance <= radius from the BFS source.

    Unreachable nodes (distance == -1) are excluded.
    """
    count = 0
    for d in distances:
        if 0 <= d <= radius:
            count += 1
    return count


def estimate_diameter(g: CompiledGraph) -> int:
    """Estimate graph diameter using two-sweep BFS heuristic.

    Returns 0 for single-node graphs and considers only the component
    reachable from node 0.
    """
    if g.n <= 1:
        return 0

    # First sweep from node 0
    dist1 = bfs_layers(g, 0)
    far1 = max(range(g.n), key=lambda i: dist1[i] if dist1[i] >= 0 else -1)

    # Second sweep from the farthest node found
    dist2 = bfs_layers(g, far1)
    return max(d for d in dist2 if d >= 0)
