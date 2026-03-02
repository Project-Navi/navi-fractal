# Calibration Instrument Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a scientific calibration instrument that runs v4 and navi-fractal side-by-side on identical graphs, producing both human-readable tables and a diffable JSON report with finite-size convergence curves.

**Architecture:** Graph Registry + Comparison Engine. A declarative registry defines the test corpus (~20 graph instances including multi-generation flower convergence series). A comparison engine runs both backends, normalizes results into a common schema, computes deltas. Output renders as three stdout tables plus a structured JSON report.

**Tech Stack:** Python 3.12+ stdlib only. v4 imported via sys.path from `docs/reference/`. navi-fractal imported normally. No external dependencies.

---

### Task 1: Create scripts/ directory and skeleton

**Files:**
- Create: `scripts/calibrate.py`

**Step 1: Create the script skeleton with imports and main guard**

```python
#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Calibration instrument: v4 vs navi-fractal side-by-side comparison.

Runs both implementations on identical graphs and produces:
1. Human-readable comparison tables (stdout)
2. Structured JSON report (scripts/calibration-report.json)

Usage:
    uv run python scripts/calibrate.py          # full corpus
    uv run python scripts/calibrate.py --quick   # skip largest generations
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# v4 import — add docs/reference/ to sys.path
# ---------------------------------------------------------------------------
_V4_DIR = str(Path(__file__).resolve().parent.parent / "docs" / "reference")
if _V4_DIR not in sys.path:
    sys.path.insert(0, _V4_DIR)

from fractal_analysis_v4_mfa import (  # noqa: E402
    Graph as V4Graph,
    estimate_sandbox_dimension as v4_estimate,
)

# ---------------------------------------------------------------------------
# navi-fractal import
# ---------------------------------------------------------------------------
from navi_fractal import (  # noqa: E402
    Graph as NFGraph,
    estimate_sandbox_dimension as nf_estimate,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="v4 vs navi-fractal calibration")
    parser.add_argument(
        "--quick", action="store_true",
        help="Skip largest generations for faster iteration",
    )
    args = parser.parse_args()

    print("calibrate.py — v4 vs navi-fractal calibration instrument")
    print()


if __name__ == "__main__":
    main()
```

**Step 2: Verify the skeleton runs**

Run: `uv run python scripts/calibrate.py`
Expected: prints the header line and exits cleanly.

**Step 3: Commit**

```bash
git add scripts/calibrate.py
git commit -m "chore: scaffold calibration instrument skeleton"
```

---

### Task 2: Graph Registry

**Files:**
- Modify: `scripts/calibrate.py`

**Step 1: Add GraphSpec dataclass and the full corpus registry**

Add after the imports, before `main()`:

```python
# ---------------------------------------------------------------------------
# Graph registry
# ---------------------------------------------------------------------------

@dataclass
class GraphSpec:
    """One graph instance in the calibration corpus."""
    family: str          # "flower", "grid", "path", "ba", "er", "complete"
    label: str           # human-readable: "flower_22_gen8"
    params: dict         # constructor args
    analytical_d: float | None  # exact d_B if known
    expect: str          # "emit" or "refuse"
    group: str | None    # convergence group key, e.g. "flower_22"
    slow: bool = False   # True = skipped in --quick mode


def _build_registry(*, quick: bool = False) -> list[GraphSpec]:
    """Build the calibration corpus.

    If quick=True, drops the largest/slowest generations for faster iteration
    during development. The full corpus runs in --quick=False (default).
    """
    specs: list[GraphSpec] = []

    # (2,2)-flower convergence series — d_B = ln(4)/ln(2) = 2.0
    d_22 = math.log(4) / math.log(2)
    for gen in (4, 5, 6, 7, 8):
        specs.append(GraphSpec(
            family="flower", label=f"flower_22_gen{gen}",
            params={"u": 2, "v": 2, "gen": gen},
            analytical_d=d_22, expect="emit", group="flower_22",
            slow=(gen >= 7),  # gen 7+8 are the expensive ones
        ))

    # (3,3)-flower convergence series — d_B = ln(6)/ln(3)
    d_33 = math.log(6) / math.log(3)
    for gen in (3, 4, 5):
        specs.append(GraphSpec(
            family="flower", label=f"flower_33_gen{gen}",
            params={"u": 3, "v": 3, "gen": gen},
            analytical_d=d_33, expect="emit", group="flower_33",
        ))

    # (4,4)-flower convergence series — d_B = ln(8)/ln(4) = 1.5
    d_44 = math.log(8) / math.log(4)
    for gen in (3, 4):
        specs.append(GraphSpec(
            family="flower", label=f"flower_44_gen{gen}",
            params={"u": 4, "v": 4, "gen": gen},
            analytical_d=d_44, expect="emit", group="flower_44",
        ))

    # (2,3)-flower convergence series — d_B = ln(5)/ln(2)
    d_23 = math.log(5) / math.log(2)
    for gen in (4, 5, 6):
        specs.append(GraphSpec(
            family="flower", label=f"flower_23_gen{gen}",
            params={"u": 2, "v": 3, "gen": gen},
            analytical_d=d_23, expect="emit", group="flower_23",
            slow=(gen >= 6),  # gen 6 is ~12K nodes
        ))

    # Transfractal — (1,2)-flower, infinite d_B, expect refuse
    specs.append(GraphSpec(
        family="flower", label="flower_12_gen8",
        params={"u": 1, "v": 2, "gen": 8},
        analytical_d=None, expect="refuse", group=None,
    ))

    # Standard geometries
    specs.append(GraphSpec(
        family="grid", label="grid_30x30",
        params={"width": 30, "height": 30},
        analytical_d=2.0, expect="emit", group=None,
    ))
    specs.append(GraphSpec(
        family="path", label="path_100",
        params={"n": 100},
        analytical_d=1.0, expect="emit", group=None,
    ))

    # Non-fractal controls (seeded for reproducibility)
    specs.append(GraphSpec(
        family="ba", label="ba_n1000_m3",
        params={"n": 1000, "m": 3, "seed": 42},
        analytical_d=None, expect="refuse", group=None,
    ))
    specs.append(GraphSpec(
        family="er", label="er_n500_p01",
        params={"n": 500, "p": 0.01, "seed": 42},
        analytical_d=None, expect="refuse", group=None,
    ))
    specs.append(GraphSpec(
        family="complete", label="complete_k50",
        params={"n": 50},
        analytical_d=None, expect="refuse", group=None,
    ))

    if quick:
        specs = [s for s in specs if not s.slow]

    return specs
```

**Step 2: Verify registry builds without error**

Add to `main()`:
```python
    registry = _build_registry(quick=args.quick)
    print(f"Corpus: {len(registry)} graph instances")
```

Run: `uv run python scripts/calibrate.py`
Expected: `Corpus: 21 graph instances`

Run: `uv run python scripts/calibrate.py --quick`
Expected: `Corpus: 18 graph instances` (drops 3 slow generations)

**Step 3: Commit**

```bash
git add scripts/calibrate.py
git commit -m "feat(calibrate): add graph registry with 21 test cases"
```

---

### Task 3: Graph Constructors

**Files:**
- Modify: `scripts/calibrate.py`

**Step 1: Add dual-graph constructors**

Each constructor returns `(V4Graph, NFGraph, int)` — both representations of the same graph, plus node count. Add after the registry:

```python
# ---------------------------------------------------------------------------
# Graph constructors — build both V4Graph and NFGraph from same edges
# ---------------------------------------------------------------------------

import random as _random  # for BA/ER constructors


def _build_flower(u: int, v: int, gen: int) -> tuple[V4Graph, NFGraph, int]:
    """Build (u,v)-flower in both graph representations."""
    next_node = 2
    edges: set[frozenset[int]] = {frozenset({0, 1})}
    for _g in range(gen):
        new_edges: set[frozenset[int]] = set()
        for edge in edges:
            a, b = tuple(edge)
            prev = a
            for _j in range(u - 1):
                new_edges.add(frozenset({prev, next_node}))
                prev = next_node
                next_node += 1
            new_edges.add(frozenset({prev, b}))
            prev = a
            for _j in range(v - 1):
                new_edges.add(frozenset({prev, next_node}))
                prev = next_node
                next_node += 1
            new_edges.add(frozenset({prev, b}))
        edges = new_edges

    v4g = V4Graph(directed=False)
    nfg = NFGraph()
    for node_id in range(next_node):
        v4g.add_node(node_id)
        nfg.add_node(node_id)
    for edge in edges:
        a, b = tuple(edge)
        v4g.add_edge(a, b)
        nfg.add_edge(a, b)
    return v4g, nfg, next_node


def _build_grid(width: int, height: int) -> tuple[V4Graph, NFGraph, int]:
    """Build width x height grid in both representations."""
    n = width * height
    v4g = V4Graph(directed=False)
    nfg = NFGraph()
    for node_id in range(n):
        v4g.add_node(node_id)
        nfg.add_node(node_id)
    for r in range(height):
        for c in range(width):
            node_id = r * width + c
            if c + 1 < width:
                right = r * width + (c + 1)
                v4g.add_edge(node_id, right)
                nfg.add_edge(node_id, right)
            if r + 1 < height:
                down = (r + 1) * width + c
                v4g.add_edge(node_id, down)
                nfg.add_edge(node_id, down)
    return v4g, nfg, n


def _build_path(n: int) -> tuple[V4Graph, NFGraph, int]:
    """Build path graph with n nodes in both representations."""
    v4g = V4Graph(directed=False)
    nfg = NFGraph()
    for node_id in range(n):
        v4g.add_node(node_id)
        nfg.add_node(node_id)
    for i in range(n - 1):
        v4g.add_edge(i, i + 1)
        nfg.add_edge(i, i + 1)
    return v4g, nfg, n


def _build_ba(n: int, m: int, *, seed: int) -> tuple[V4Graph, NFGraph, int]:
    """Build Barabasi-Albert preferential attachment graph in both representations."""
    rng = _random.Random(seed)
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

    v4g = V4Graph(directed=False)
    nfg = NFGraph()
    for node_id in range(n):
        v4g.add_node(node_id)
        nfg.add_node(node_id)
    for u_node, neighbors in adj.items():
        for v_node in neighbors:
            if u_node < v_node:
                v4g.add_edge(u_node, v_node)
                nfg.add_edge(u_node, v_node)
    return v4g, nfg, n


def _build_er(n: int, p: float, *, seed: int) -> tuple[V4Graph, NFGraph, int]:
    """Build Erdos-Renyi G(n,p) random graph in both representations."""
    rng = _random.Random(seed)
    v4g = V4Graph(directed=False)
    nfg = NFGraph()
    for node_id in range(n):
        v4g.add_node(node_id)
        nfg.add_node(node_id)
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < p:
                v4g.add_edge(i, j)
                nfg.add_edge(i, j)
    return v4g, nfg, n


def _build_complete(n: int) -> tuple[V4Graph, NFGraph, int]:
    """Build complete graph K_n in both representations."""
    v4g = V4Graph(directed=False)
    nfg = NFGraph()
    for node_id in range(n):
        v4g.add_node(node_id)
        nfg.add_node(node_id)
    for i in range(n):
        for j in range(i + 1, n):
            v4g.add_edge(i, j)
            nfg.add_edge(i, j)
    return v4g, nfg, n


def build_graphs(spec: GraphSpec) -> tuple[V4Graph, NFGraph, int]:
    """Dispatch to the appropriate constructor based on spec.family."""
    p = spec.params
    if spec.family == "flower":
        return _build_flower(p["u"], p["v"], p["gen"])
    if spec.family == "grid":
        return _build_grid(p["width"], p["height"])
    if spec.family == "path":
        return _build_path(p["n"])
    if spec.family == "ba":
        return _build_ba(p["n"], p["m"], seed=p["seed"])
    if spec.family == "er":
        return _build_er(p["n"], p["p"], seed=p["seed"])
    if spec.family == "complete":
        return _build_complete(p["n"])
    raise ValueError(f"unknown family: {spec.family}")
```

**Step 2: Smoke-test the constructors**

Add to `main()`:
```python
    for spec in registry:
        _, _, n = build_graphs(spec)
        print(f"  {spec.label}: {n:,} nodes")
```

Run: `uv run python scripts/calibrate.py`
Expected: 21 lines, each showing label and node count. (2,2) gen 8 should show 43,692.

**Step 3: Commit**

```bash
git add scripts/calibrate.py
git commit -m "feat(calibrate): add dual-graph constructors for all families"
```

---

### Task 4: Comparison Engine

**Files:**
- Modify: `scripts/calibrate.py`

**Step 1: Add RunResult and Comparison dataclasses, plus the run/compare functions**

Add after the constructors:

```python
# ---------------------------------------------------------------------------
# Comparison engine
# ---------------------------------------------------------------------------

SEED = 42  # global seed for all estimation calls


@dataclass
class RunResult:
    """Normalized result from one backend."""
    backend: str
    dimension: float | None
    reason: str
    r2: float | None
    slope: float | None
    slope_stderr: float | None
    window_r_min: int | None
    window_r_max: int | None
    window_log_span: float | None
    window_delta_y: float | None
    delta_aicc: float | None
    elapsed_s: float
    n_nodes: int


@dataclass
class Comparison:
    """Side-by-side comparison of v4 and navi-fractal on one graph."""
    spec: GraphSpec
    v4: RunResult
    nf: RunResult
    dimension_delta: float | None    # nf.dimension - v4.dimension
    r2_delta: float | None
    analytical_gap_v4: float | None  # v4.dimension - spec.analytical_d
    analytical_gap_nf: float | None  # nf.dimension - spec.analytical_d


def _run_v4(v4g: V4Graph, n_nodes: int) -> RunResult:
    """Run v4 estimator and normalize the result."""
    t0 = time.perf_counter()
    res = v4_estimate(v4g, seed=SEED)
    elapsed = time.perf_counter() - t0

    fit = res.powerlaw_fit
    return RunResult(
        backend="v4",
        dimension=res.dimension,
        reason=res.reason if isinstance(res.reason, str) else str(res.reason),
        r2=fit.r2 if fit else None,
        slope=fit.slope if fit else None,
        slope_stderr=fit.slope_stderr if fit else None,
        window_r_min=res.window_r_min,
        window_r_max=res.window_r_max,
        window_log_span=res.window_log_span,
        window_delta_y=res.window_delta_y,
        delta_aicc=res.delta_aicc,
        elapsed_s=elapsed,
        n_nodes=n_nodes,
    )


def _run_nf(nfg: NFGraph, n_nodes: int) -> RunResult:
    """Run navi-fractal estimator and normalize the result."""
    t0 = time.perf_counter()
    res = nf_estimate(nfg, seed=SEED)
    elapsed = time.perf_counter() - t0

    fit = res.powerlaw_fit
    return RunResult(
        backend="navi-fractal",
        dimension=res.dimension,
        reason=res.reason.value if hasattr(res.reason, "value") else str(res.reason),
        r2=fit.r2 if fit else None,
        slope=fit.slope if fit else None,
        slope_stderr=fit.slope_stderr if fit else None,
        window_r_min=res.window_r_min,
        window_r_max=res.window_r_max,
        window_log_span=res.window_log_span,
        window_delta_y=res.window_delta_y,
        delta_aicc=res.delta_aicc,
        elapsed_s=elapsed,
        n_nodes=n_nodes,
    )


def compare(spec: GraphSpec) -> Comparison:
    """Run both backends on the same graph and compute deltas."""
    v4g, nfg, n = build_graphs(spec)
    v4_result = _run_v4(v4g, n)
    nf_result = _run_nf(nfg, n)

    # Deltas (all use convention: nf - v4, or measured - analytical)
    dim_delta = None
    if v4_result.dimension is not None and nf_result.dimension is not None:
        dim_delta = nf_result.dimension - v4_result.dimension

    r2_delta = None
    if v4_result.r2 is not None and nf_result.r2 is not None:
        r2_delta = nf_result.r2 - v4_result.r2

    gap_v4 = None
    if v4_result.dimension is not None and spec.analytical_d is not None:
        gap_v4 = v4_result.dimension - spec.analytical_d

    gap_nf = None
    if nf_result.dimension is not None and spec.analytical_d is not None:
        gap_nf = nf_result.dimension - spec.analytical_d

    return Comparison(
        spec=spec,
        v4=v4_result,
        nf=nf_result,
        dimension_delta=dim_delta,
        r2_delta=r2_delta,
        analytical_gap_v4=gap_v4,
        analytical_gap_nf=gap_nf,
    )
```

**Step 2: Wire into main and run one graph to test**

Replace the smoke-test loop in `main()` with:
```python
    registry = _build_registry()
    # Quick sanity check on one small graph
    test_spec = [s for s in registry if s.label == "flower_22_gen4"][0]
    c = compare(test_spec)
    print(f"{c.spec.label}: v4={c.v4.dimension}, nf={c.nf.dimension}, delta={c.dimension_delta}")
```

Run: `uv run python scripts/calibrate.py`
Expected: Prints flower_22_gen4 with dimension values for both backends and a small delta.

**Step 3: Commit**

```bash
git add scripts/calibrate.py
git commit -m "feat(calibrate): add comparison engine with normalized RunResult"
```

---

### Task 5: Stdout Tables

**Files:**
- Modify: `scripts/calibrate.py`

**Step 1: Add the three table renderers**

Add after the comparison engine:

```python
# ---------------------------------------------------------------------------
# Stdout table rendering
# ---------------------------------------------------------------------------

def _fmt_dim(d: float | None) -> str:
    return f"{d:.3f}" if d is not None else "REFUSED"


def _fmt_gap_pct(measured: float | None, analytical: float | None) -> str:
    if measured is None or analytical is None:
        return "—"
    return f"{100 * (measured - analytical) / analytical:+.1f}%"


def _fmt_delta(d: float | None) -> str:
    return f"{d:+.4f}" if d is not None else "—"


def _fmt_time(s: float) -> str:
    return f"{s:.1f}s"


def print_dimension_table(comparisons: list[Comparison]) -> None:
    """Table 1: dimension comparison for all emit cases."""
    emit = [c for c in comparisons if c.spec.expect == "emit"]
    if not emit:
        return

    hdr = f"{'Network':<25} {'Nodes':>8} {'Analyt.':>8} {'v4 D':>8} {'v4 gap':>8} {'nf D':>8} {'nf gap':>8} {'v4-nf':>8} {'v4':>6} {'nf':>6}"
    print("=" * len(hdr))
    print("DIMENSION COMPARISON")
    print("=" * len(hdr))
    print(hdr)
    print("-" * len(hdr))
    for c in emit:
        analyt = f"{c.spec.analytical_d:.3f}" if c.spec.analytical_d else "—"
        print(
            f"{c.spec.label:<25} "
            f"{c.v4.n_nodes:>8,} "
            f"{analyt:>8} "
            f"{_fmt_dim(c.v4.dimension):>8} "
            f"{_fmt_gap_pct(c.v4.dimension, c.spec.analytical_d):>8} "
            f"{_fmt_dim(c.nf.dimension):>8} "
            f"{_fmt_gap_pct(c.nf.dimension, c.spec.analytical_d):>8} "
            f"{_fmt_delta(c.dimension_delta):>8} "
            f"{_fmt_time(c.v4.elapsed_s):>6} "
            f"{_fmt_time(c.nf.elapsed_s):>6}"
        )
    print()


def print_convergence_tables(comparisons: list[Comparison]) -> None:
    """Table 2: convergence curves grouped by flower family."""
    groups: dict[str, list[Comparison]] = {}
    for c in comparisons:
        if c.spec.group:
            groups.setdefault(c.spec.group, []).append(c)

    if not groups:
        return

    print("=" * 80)
    print("CONVERGENCE CURVES")
    print("=" * 80)
    for group_key, members in sorted(groups.items()):
        members.sort(key=lambda c: c.spec.params.get("gen", 0))
        analyt = members[0].spec.analytical_d
        analyt_str = f"{analyt:.3f}" if analyt else "?"
        u = members[0].spec.params["u"]
        v = members[0].spec.params["v"]
        print(f"\n({u},{v})-flower convergence:  d_B = {analyt_str}")
        print(f"  {'Gen':>4} {'Nodes':>8} {'v4 D':>8} {'nf D':>8} {'v4 gap%':>9} {'nf gap%':>9}")
        print(f"  {'-'*4} {'-'*8} {'-'*8} {'-'*8} {'-'*9} {'-'*9}")
        for c in members:
            gen = c.spec.params["gen"]
            print(
                f"  {gen:>4} "
                f"{c.v4.n_nodes:>8,} "
                f"{_fmt_dim(c.v4.dimension):>8} "
                f"{_fmt_dim(c.nf.dimension):>8} "
                f"{_fmt_gap_pct(c.v4.dimension, analyt):>9} "
                f"{_fmt_gap_pct(c.nf.dimension, analyt):>9}"
            )
    print()


def print_refusal_table(comparisons: list[Comparison]) -> None:
    """Table 3: refusal/control summary."""
    refuse = [c for c in comparisons if c.spec.expect == "refuse"]
    if not refuse:
        return

    print("=" * 70)
    print("REFUSAL / CONTROL SUMMARY")
    print("=" * 70)
    print(f"{'Network':<25} {'v4 verdict':<20} {'nf verdict':<20} {'Match?':>6}")
    print("-" * 70)
    for c in refuse:
        v4_v = "REFUSED" if c.v4.dimension is None else f"D={c.v4.dimension:.3f}"
        nf_v = "REFUSED" if c.nf.dimension is None else f"D={c.nf.dimension:.3f}"
        match = "yes" if (c.v4.dimension is None) == (c.nf.dimension is None) else "NO"
        print(f"{c.spec.label:<25} {v4_v:<20} {nf_v:<20} {match:>6}")
    print()
```

**Step 2: Wire into main**

Replace the test code in `main()` with the full run loop:
```python
    registry = _build_registry(quick=args.quick)
    mode = "quick" if args.quick else "full"
    print(f"Corpus: {len(registry)} graph instances, seed={SEED}, mode={mode}")
    print()

    t_total = time.perf_counter()
    comparisons: list[Comparison] = []
    for i, spec in enumerate(registry, 1):
        print(f"  [{i}/{len(registry)}] {spec.label}...", end="", flush=True)
        c = compare(spec)
        comparisons.append(c)
        d_str = f"v4={_fmt_dim(c.v4.dimension)} nf={_fmt_dim(c.nf.dimension)}"
        print(f" {d_str} ({c.v4.elapsed_s + c.nf.elapsed_s:.1f}s)")
    total = time.perf_counter() - t_total
    print(f"\nTotal: {total:.1f}s\n")

    print_dimension_table(comparisons)
    print_convergence_tables(comparisons)
    print_refusal_table(comparisons)
```

**Step 3: Run the full corpus**

Run: `uv run python scripts/calibrate.py`
Expected: Progress lines for 21 graphs, then three formatted tables. Total under 60s.

**Step 4: Commit**

```bash
git add scripts/calibrate.py
git commit -m "feat(calibrate): add stdout table rendering (dimension, convergence, refusal)"
```

---

### Task 6: JSON Report

**Files:**
- Modify: `scripts/calibrate.py`

**Step 1: Add the JSON report writer**

Add after the table renderers:

```python
# ---------------------------------------------------------------------------
# JSON report
# ---------------------------------------------------------------------------

def _run_result_to_dict(r: RunResult) -> dict:
    return {
        "backend": r.backend,
        "dimension": r.dimension,
        "reason": r.reason,
        "r2": r.r2,
        "slope": r.slope,
        "slope_stderr": r.slope_stderr,
        "window_r_min": r.window_r_min,
        "window_r_max": r.window_r_max,
        "window_log_span": r.window_log_span,
        "window_delta_y": r.window_delta_y,
        "delta_aicc": r.delta_aicc,
        "elapsed_s": round(r.elapsed_s, 4),
        "n_nodes": r.n_nodes,
    }


def write_json_report(
    comparisons: list[Comparison], total_elapsed: float
) -> Path:
    """Write structured JSON report to scripts/calibration-report.json."""
    report: dict = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "python_version": sys.version.split()[0],
            "seed": SEED,
            "total_elapsed_s": round(total_elapsed, 2),
            "corpus_size": len(comparisons),
            "sign_conventions": {
                "analytical_gap": "measured - analytical (negative = underestimate)",
                "dimension_delta": "nf - v4 (near zero = implementations agree)",
            },
        },
        "comparisons": [],
        "convergence": {},
    }

    # Per-graph comparisons
    for c in comparisons:
        entry: dict = {
            "spec": {
                "family": c.spec.family,
                "label": c.spec.label,
                "params": c.spec.params,
                "analytical_d": c.spec.analytical_d,
                "expect": c.spec.expect,
                "group": c.spec.group,
            },
            "v4": _run_result_to_dict(c.v4),
            "nf": _run_result_to_dict(c.nf),
            "deltas": {
                "dimension": _round_or_none(c.dimension_delta, 6),
                "r2": _round_or_none(c.r2_delta, 6),
                "analytical_gap_v4": _round_or_none(c.analytical_gap_v4, 6),
                "analytical_gap_nf": _round_or_none(c.analytical_gap_nf, 6),
            },
        }
        report["comparisons"].append(entry)

    # Convergence groups
    groups: dict[str, list[Comparison]] = {}
    for c in comparisons:
        if c.spec.group:
            groups.setdefault(c.spec.group, []).append(c)

    for group_key, members in sorted(groups.items()):
        members.sort(key=lambda c: c.spec.params.get("gen", 0))
        analyt = members[0].spec.analytical_d
        u = members[0].spec.params["u"]
        v = members[0].spec.params["v"]
        report["convergence"][group_key] = {
            "analytical_d": analyt,
            "formula": f"ln({u}+{v})/ln({u}) = ln({u+v})/ln({u})",
            "generations": [
                {
                    "gen": c.spec.params["gen"],
                    "nodes": c.v4.n_nodes,
                    "v4_d": c.v4.dimension,
                    "nf_d": c.nf.dimension,
                    "v4_gap_pct": _gap_pct(c.v4.dimension, analyt),
                    "nf_gap_pct": _gap_pct(c.nf.dimension, analyt),
                }
                for c in members
            ],
        }

    out_path = Path(__file__).resolve().parent / "calibration-report.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n")
    return out_path


def _round_or_none(val: float | None, digits: int) -> float | None:
    return round(val, digits) if val is not None else None


def _gap_pct(measured: float | None, analytical: float | None) -> float | None:
    if measured is None or analytical is None:
        return None
    return round(100 * (measured - analytical) / analytical, 2)
```

**Step 2: Wire JSON output into main**

Add at the end of `main()`, after the table prints:
```python
    json_path = write_json_report(comparisons, total)
    print(f"JSON report written to: {json_path}")
```

**Step 3: Run and verify**

Run: `uv run python scripts/calibrate.py`
Expected: Tables print as before, plus `JSON report written to: .../scripts/calibration-report.json`. Verify the JSON is valid:

Run: `uv run python -c "import json; json.load(open('scripts/calibration-report.json')); print('valid')" `
Expected: `valid`

**Step 4: Commit**

```bash
git add scripts/calibrate.py
git commit -m "feat(calibrate): add JSON report with convergence data and sign conventions"
```

---

### Task 7: Full Integration Run and Baseline Commit

**Files:**
- Modify: `scripts/calibrate.py` (final polish)
- Commit: `scripts/calibration-report.json` (baseline)

**Step 1: Run the full instrument end-to-end**

Run: `uv run python scripts/calibrate.py`
Expected:
- 21 progress lines
- Total under 60s
- Table 1: dimension comparison for ~15 emit cases
- Table 2: convergence curves for 4 flower families
- Table 3: refusal summary for 4 refuse cases
- JSON report written

**Step 2: Verify --quick mode works**

Run: `uv run python scripts/calibrate.py --quick`
Expected: Fewer graphs (skips gen 7+8 for (2,2)-flower, gen 6 for (2,3)-flower). Runs in under 15s.

**Step 3: Run existing tests to ensure nothing is broken**

Run: `uv run pytest tests/ -v --benchmark-disable`
Expected: 196 passed (no regressions from the calibrate script)

**Step 4: Run linting**

Run: `uv run ruff check scripts/`
Expected: Clean (or suppress any expected warnings)

**Step 5: Commit the instrument and baseline report**

The JSON report is committed intentionally — it serves as the measurement baseline.
When navi-fractal internals change, rerun the instrument and `git diff` the JSON
to see exactly how measurements shifted. This diff history documents measurement
characteristics over time.

```bash
git add scripts/calibrate.py scripts/calibration-report.json
git commit -m "feat: calibration instrument v1 with baseline report"
```

---

## Execution Notes

**API normalization summary** (for the implementer):
- v4 `SandboxResult.reason` is a string → use as-is
- navi-fractal `SandboxResult.reason` is a `Reason` enum → use `.value`
- v4 `LinFit.n` → don't need it in RunResult
- navi-fractal `LinFit.n_points` → don't need it in RunResult
- v4 uses `min_log_span` parameter directly, navi-fractal uses `min_radius_ratio` → both use defaults (equivalent: `log(3.0)` ≈ `log(3.0)`)
- Both take `seed=SEED` as first kwarg

**Parameter alignment:** Both implementations are called with their defaults (aligned during v4-alignment work). The only difference is the estimation seed, which is set to `SEED = 42` for both.

**The `import random` line:** This appears in the constructors section. Use `import random as _random` to avoid collision with any stdlib shadows. Already shown in the plan code.
