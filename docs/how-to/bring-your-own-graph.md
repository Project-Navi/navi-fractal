# Bring Your Own Graph

This guide shows how to load your own network into navi-fractal for sandbox
dimension estimation. All examples end with a call to
`estimate_sandbox_dimension`, which returns a `SandboxResult`.

## Loading patterns

### Edge list (CSV)

If your data is a CSV with one edge per line (e.g., `src,dst`):

```python
from navi_fractal import Graph, estimate_sandbox_dimension

g = Graph()
with open("edges.csv") as f:
    for line in f:
        parts = line.strip().split(",")
        if len(parts) == 2:
            g.add_edge(parts[0], parts[1])

result = estimate_sandbox_dimension(g)
```

`add_edge` automatically creates nodes that do not already exist, so you do not
need a separate node-loading step. Self-loops are silently ignored.

### Adjacency matrix (NumPy)

Iterate the upper triangle of a symmetric adjacency matrix:

```python
import numpy as np
from navi_fractal import Graph, estimate_sandbox_dimension

adj = np.load("adjacency.npy")  # shape (n, n), symmetric, 0/1 entries
g = Graph()
n = adj.shape[0]
for i in range(n):
    g.add_node(i)  # ensure isolated nodes are included
    for j in range(i + 1, n):
        if adj[i, j]:
            g.add_edge(i, j)

result = estimate_sandbox_dimension(g)
```

### From NetworkX

If you already have a `networkx.Graph`, iterate its edge view:

```python
import networkx as nx
from navi_fractal import Graph, estimate_sandbox_dimension

nx_g = nx.karate_club_graph()

g = Graph()
for u, v in nx_g.edges():
    g.add_edge(u, v)

result = estimate_sandbox_dimension(g)
```

### Pre-compilation for repeated analyses

`estimate_sandbox_dimension` accepts either a mutable `Graph` or a frozen
`CompiledGraph`. If you plan to run multiple analyses on the same graph (e.g.,
sweeping parameters or comparing quality gate presets), compile once and reuse:

```python
from navi_fractal import (
    Graph,
    compile_to_undirected_metric_graph,
    estimate_sandbox_dimension,
)

g = Graph()
# ... add edges ...

cg = compile_to_undirected_metric_graph(g)

# Run with different parameters -- no re-compilation cost
result_default = estimate_sandbox_dimension(cg)
result_relaxed = estimate_sandbox_dimension(cg, r2_min=0.7)
result_tight = estimate_sandbox_dimension(cg, r2_min=0.95)
```

`compile_to_undirected_metric_graph` assigns integer IDs in insertion order
(Python 3.7+ dict ordering) and sorts adjacency lists for deterministic BFS
traversal.

## Node types

Any hashable Python object works as a node label: `str`, `int`, `tuple`,
`frozenset`, or your own `__hash__`/`__eq__` types. Internally, compilation maps
labels to integer IDs, so performance is the same regardless of label type.

```python
g = Graph()
g.add_edge("Alice", "Bob")
g.add_edge(("layer", 3), ("layer", 4))
g.add_edge(42, 99)
```

## Component policy

Real-world networks are often disconnected. The `component_policy` parameter
controls which nodes participate in estimation:

```python
# Default: measure only the giant component (largest connected component)
result = estimate_sandbox_dimension(g, component_policy="giant")

# Alternative: measure all nodes (treats disconnected components as one graph)
result = estimate_sandbox_dimension(g, component_policy="all")
```

**When to use each:**

- `"giant"` (default) -- Best for most networks. Satellite components distort
  ball-mass averages because BFS from a node in a small component saturates
  immediately. The giant component typically carries the fractal structure.

- `"all"` -- Use when your graph is connected by construction (e.g., a
  deterministic fractal like a Sierpinski graph) or when you specifically want
  to include all components in the measurement. If the graph is already
  connected, both policies produce identical results.

The `SandboxResult` reports `n_nodes_original` (total nodes in the input) and
`n_nodes_measured` (nodes actually used) so you can audit what fraction was
retained.

## Performance considerations

Estimation time scales as `O(n_centers * (n + m))` where `n` and `m` are
the node and edge counts of the measured component. Each center requires a
full BFS (layer counts), after which ball masses at all radii are computed
via prefix sums. The default `n_centers=256` keeps this practical for graphs
up to roughly 100K nodes on commodity hardware. For larger graphs:

- Reduce `n_centers` (e.g., `n_centers=64`) for a faster but noisier estimate.
- Lower `r_cap` (default 32) if the diameter is large and you only need
  short-range scaling behavior.
- Pre-compile with `compile_to_undirected_metric_graph` to avoid paying
  compilation cost on every call.

```python
# Fast exploratory run on a large graph
result = estimate_sandbox_dimension(
    large_graph,
    n_centers=64,
    r_cap=16,
)
```
