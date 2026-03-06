# Copyright 2024-2026 Nelson Spence
# SPDX-License-Identifier: Apache-2.0
"""Null model: degree-preserving Maslov-Sneppen rewiring.

Preserves exact degree sequence while destroying higher-order structure
(clustering, community, fractal scaling).
"""

from __future__ import annotations

import logging
import random

from navi_fractal._graph import CompiledGraph

logger = logging.getLogger("navi_fractal")


def degree_preserving_rewire_undirected(
    cg: CompiledGraph,
    *,
    seed: int = 0,
    rng: random.Random | None = None,
    n_swaps: int | None = None,
    verify: bool = True,
) -> CompiledGraph:
    """Rewire edges while preserving the degree sequence.

    Implements the Maslov-Sneppen algorithm: repeatedly pick two random edges
    (u, v) and (x, y), swap to (u, x) and (v, y) if no self-loops or
    multi-edges result.

    Parameters:
        cg: Input compiled graph.
        seed: RNG seed for determinism. Ignored when *rng* is provided.
        rng: Optional pre-seeded ``random.Random`` instance.  When given,
            *seed* is ignored, allowing callers to manage their own RNG stream.
        n_swaps: Number of swap attempts. Defaults to 10 * edge_count.
        verify: If True, verify degree sequence is preserved after rewiring.

    Returns:
        A new CompiledGraph with rewired edges.
    """
    if rng is None:
        rng = random.Random(seed)

    # Build mutable edge set and adjacency
    adj: list[set[int]] = [set(cg.adj[i]) for i in range(cg.n)]
    edges: list[tuple[int, int]] = []
    for u in range(cg.n):
        for v in adj[u]:
            if u < v:
                edges.append((u, v))

    if len(edges) < 2:
        return cg

    if n_swaps is None:
        n_swaps = 10 * len(edges)

    successful = 0
    for _ in range(n_swaps):
        # Pick two random edge indices
        i1 = rng.randrange(len(edges))
        i2 = rng.randrange(len(edges))
        if i1 == i2:
            continue

        u, v = edges[i1]
        x, y = edges[i2]

        # Try swap: (u,v), (x,y) -> (u,x), (v,y)
        # Randomly choose which endpoints to swap
        if rng.random() < 0.5:
            new1 = (u, y)
            new2 = (v, x)
        else:
            new1 = (u, x)
            new2 = (v, y)

        a1, b1 = new1
        a2, b2 = new2

        # Check: no self-loops
        if a1 == b1 or a2 == b2:
            continue
        # Check: no multi-edges
        if b1 in adj[a1] or b2 in adj[a2]:
            continue
        # Check: the two new edges aren't identical
        if (min(a1, b1), max(a1, b1)) == (min(a2, b2), max(a2, b2)):
            continue

        # Perform swap
        adj[u].discard(v)
        adj[v].discard(u)
        adj[x].discard(y)
        adj[y].discard(x)

        adj[a1].add(b1)
        adj[b1].add(a1)
        adj[a2].add(b2)
        adj[b2].add(a2)

        edges[i1] = (min(a1, b1), max(a1, b1))
        edges[i2] = (min(a2, b2), max(a2, b2))
        successful += 1

    logger.info("Rewired %d/%d swap attempts", successful, n_swaps)

    # Verify degree sequence if requested
    if verify:
        for i in range(cg.n):
            if len(adj[i]) != len(cg.adj[i]):
                raise RuntimeError(
                    f"Degree sequence violated at node {i}: "
                    f"expected {len(cg.adj[i])}, got {len(adj[i])}"
                )

    # Build new CompiledGraph
    new_adj = tuple(tuple(sorted(adj[i])) for i in range(cg.n))
    return CompiledGraph(
        n=cg.n,
        adj=new_adj,
        label_to_id=cg.label_to_id,
        id_to_label=cg.id_to_label,
    )
