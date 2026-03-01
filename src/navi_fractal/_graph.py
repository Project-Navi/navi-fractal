# SPDX-License-Identifier: Apache-2.0
"""Graph containers and compilation.

Graph — mutable input container with set-based adjacency.
CompiledGraph — frozen, deterministic adjacency for reproducible traversal.
"""

from __future__ import annotations

from dataclasses import dataclass


class Graph:
    """Mutable graph for convenient construction.

    Nodes are arbitrary hashable labels. Edges are undirected.
    """

    def __init__(self) -> None:
        self._adj: dict[object, set[object]] = {}

    def add_node(self, node: object) -> None:
        """Add a node (idempotent)."""
        if node not in self._adj:
            self._adj[node] = set()

    def add_edge(self, u: object, v: object) -> None:
        """Add an undirected edge (idempotent). Adds nodes if needed."""
        if u not in self._adj:
            self._adj[u] = set()
        if v not in self._adj:
            self._adj[v] = set()
        if u != v:  # no self-loops
            self._adj[u].add(v)
            self._adj[v].add(u)

    @property
    def nodes(self) -> set[object]:
        """Return all nodes."""
        return set(self._adj.keys())

    @property
    def adj(self) -> dict[object, set[object]]:
        """Return adjacency dict (read-only view)."""
        return self._adj

    def __len__(self) -> int:
        return len(self._adj)


@dataclass(frozen=True)
class CompiledGraph:
    """Frozen graph with integer node IDs and sorted adjacency tuples.

    Guarantees deterministic traversal order for reproducible results.
    """

    n: int
    adj: tuple[tuple[int, ...], ...]
    label_to_id: dict[object, int]
    id_to_label: tuple[object, ...]


def compile_to_undirected_metric_graph(g: Graph) -> CompiledGraph:
    """Compile a Graph to a deterministic CompiledGraph.

    Nodes are assigned integer IDs in insertion order (Python 3.7+ dict ordering).
    Adjacency lists are sorted for deterministic BFS traversal.
    """
    nodes = list(g.adj.keys())
    label_to_id: dict[object, int] = {node: i for i, node in enumerate(nodes)}

    adj_lists: list[tuple[int, ...]] = []
    for node in nodes:
        neighbors = sorted(label_to_id[nb] for nb in g.adj[node])
        adj_lists.append(tuple(neighbors))

    return CompiledGraph(
        n=len(nodes),
        adj=tuple(adj_lists),
        label_to_id=label_to_id,
        id_to_label=tuple(nodes),
    )
