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
import platform
import random as _random
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# v4 import — add docs/reference/ to sys.path
# ---------------------------------------------------------------------------
_V4_DIR = str(Path(__file__).resolve().parent.parent / "docs" / "reference")
if _V4_DIR not in sys.path:
    sys.path.insert(0, _V4_DIR)

from fractal_analysis_v4_mfa import Graph as V4Graph  # noqa: E402
from fractal_analysis_v4_mfa import estimate_sandbox_dimension as v4_estimate  # noqa: E402

from navi_fractal import Graph as NFGraph  # noqa: E402
from navi_fractal import estimate_sandbox_dimension as nf_estimate  # noqa: E402

# ---------------------------------------------------------------------------
# Graph registry
# ---------------------------------------------------------------------------


@dataclass
class GraphSpec:
    """One graph instance in the calibration corpus."""

    family: str  # "flower", "grid", "path", "ba", "er", "complete"
    label: str  # human-readable: "flower_22_gen8"
    params: dict  # constructor args
    analytical_d: float | None  # exact d_B if known
    expect: str  # "emit" or "refuse"
    group: str | None  # convergence group key, e.g. "flower_22"
    slow: bool = False  # True = skipped in --quick mode


def _build_registry(*, quick: bool = False) -> list[GraphSpec]:
    """Build the calibration corpus.

    If quick=True, drops the largest/slowest generations for faster iteration
    during development. The full corpus runs in --quick=False (default).
    """
    specs: list[GraphSpec] = []

    # (2,2)-flower convergence series — d_B = ln(4)/ln(2) = 2.0
    d_22 = math.log(4) / math.log(2)
    for gen in (4, 5, 6, 7, 8):
        specs.append(
            GraphSpec(
                family="flower",
                label=f"flower_22_gen{gen}",
                params={"u": 2, "v": 2, "gen": gen},
                analytical_d=d_22,
                expect="emit",
                group="flower_22",
                slow=(gen >= 7),
            )
        )

    # (3,3)-flower convergence series — d_B = ln(6)/ln(3)
    d_33 = math.log(6) / math.log(3)
    for gen in (3, 4, 5):
        specs.append(
            GraphSpec(
                family="flower",
                label=f"flower_33_gen{gen}",
                params={"u": 3, "v": 3, "gen": gen},
                analytical_d=d_33,
                expect="emit",
                group="flower_33",
            )
        )

    # (4,4)-flower convergence series — d_B = ln(8)/ln(4) = 1.5
    d_44 = math.log(8) / math.log(4)
    for gen in (3, 4):
        specs.append(
            GraphSpec(
                family="flower",
                label=f"flower_44_gen{gen}",
                params={"u": 4, "v": 4, "gen": gen},
                analytical_d=d_44,
                expect="emit",
                group="flower_44",
            )
        )

    # (2,3)-flower convergence series — d_B = ln(5)/ln(2)
    d_23 = math.log(5) / math.log(2)
    for gen in (4, 5, 6):
        specs.append(
            GraphSpec(
                family="flower",
                label=f"flower_23_gen{gen}",
                params={"u": 2, "v": 3, "gen": gen},
                analytical_d=d_23,
                expect="emit",
                group="flower_23",
                slow=(gen >= 6),
            )
        )

    # Transfractal — (1,2)-flower, infinite d_B, expect refuse
    specs.append(
        GraphSpec(
            family="flower",
            label="flower_12_gen8",
            params={"u": 1, "v": 2, "gen": 8},
            analytical_d=None,
            expect="refuse",
            group=None,
        )
    )

    # Standard geometries
    specs.append(
        GraphSpec(
            family="grid",
            label="grid_30x30",
            params={"width": 30, "height": 30},
            analytical_d=2.0,
            expect="emit",
            group=None,
        )
    )
    specs.append(
        GraphSpec(
            family="path",
            label="path_100",
            params={"n": 100},
            analytical_d=1.0,
            expect="emit",
            group=None,
        )
    )

    # Non-fractal controls (seeded for reproducibility)
    specs.append(
        GraphSpec(
            family="ba",
            label="ba_n1000_m3",
            params={"n": 1000, "m": 3, "seed": 42},
            analytical_d=None,
            expect="refuse",
            group=None,
        )
    )
    specs.append(
        GraphSpec(
            family="er",
            label="er_n500_p01",
            params={"n": 500, "p": 0.01, "seed": 42},
            analytical_d=None,
            expect="refuse",
            group=None,
        )
    )
    specs.append(
        GraphSpec(
            family="complete",
            label="complete_k50",
            params={"n": 50},
            analytical_d=None,
            expect="refuse",
            group=None,
        )
    )

    if quick:
        specs = [s for s in specs if not s.slow]

    return specs


# ---------------------------------------------------------------------------
# Graph constructors — build both V4Graph and NFGraph from same edges
# ---------------------------------------------------------------------------


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


def _build_graphs(spec: GraphSpec) -> tuple[V4Graph, NFGraph, int]:
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
    msg = f"unknown family: {spec.family}"
    raise ValueError(msg)


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
    dimension_delta: float | None  # nf.dimension - v4.dimension
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
    v4g, nfg, n = _build_graphs(spec)
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


# ---------------------------------------------------------------------------
# Table renderers (stdout)
# ---------------------------------------------------------------------------


def _fmt_dim(d: float | None) -> str:
    """Format dimension value or REFUSED."""
    return f"{d:.4f}" if d is not None else "REFUSED"


def _fmt_gap_pct(measured: float | None, analytical: float | None) -> str:
    """Format gap as percentage of analytical value, or '---'."""
    if measured is None or analytical is None or analytical == 0.0:
        return "---"
    gap_pct = 100.0 * (measured - analytical) / analytical
    return f"{gap_pct:+.2f}%"


def _fmt_delta(d: float | None) -> str:
    """Format a delta value with sign, or '---'."""
    return f"{d:+.4f}" if d is not None else "---"


def _fmt_time(s: float) -> str:
    """Format elapsed seconds."""
    return f"{s:.2f}s"


def print_dimension_table(comparisons: list[Comparison]) -> None:
    """Print Table 1: dimension estimates for all emit-expected cases."""
    emit_cases = [c for c in comparisons if c.spec.expect == "emit"]
    if not emit_cases:
        return

    print("=" * 100)
    print("TABLE 1: Dimension Estimates (emit cases)")
    print("=" * 100)

    header = (
        f"{'Graph':<22} {'Nodes':>7} {'Analyt':>8} "
        f"{'v4 D':>8} {'v4 gap%':>8} "
        f"{'nf D':>8} {'nf gap%':>8} "
        f"{'v4-nf':>8} {'Time':>8}"
    )
    print(header)
    print("-" * 100)

    for c in emit_cases:
        v4_gap = _fmt_gap_pct(c.v4.dimension, c.spec.analytical_d)
        nf_gap = _fmt_gap_pct(c.nf.dimension, c.spec.analytical_d)
        delta = _fmt_delta(c.dimension_delta)
        total_time = _fmt_time(c.v4.elapsed_s + c.nf.elapsed_s)
        analytical = f"{c.spec.analytical_d:.4f}" if c.spec.analytical_d is not None else "---"

        row = (
            f"{c.spec.label:<22} {c.v4.n_nodes:>7} {analytical:>8} "
            f"{_fmt_dim(c.v4.dimension):>8} {v4_gap:>8} "
            f"{_fmt_dim(c.nf.dimension):>8} {nf_gap:>8} "
            f"{delta:>8} {total_time:>8}"
        )
        print(row)

    print()


def print_convergence_tables(comparisons: list[Comparison]) -> None:
    """Print Table 2: convergence series grouped by flower family."""
    # Collect groups
    groups: dict[str, list[Comparison]] = {}
    for c in comparisons:
        if c.spec.group is not None:
            groups.setdefault(c.spec.group, []).append(c)

    if not groups:
        return

    print("=" * 100)
    print("TABLE 2: Convergence Series")
    print("=" * 100)

    for group_key, members in groups.items():
        # All members share the same analytical_d
        analytical = members[0].spec.analytical_d
        analytical_str = f"{analytical:.4f}" if analytical is not None else "---"
        print(f"\n  {group_key}  (analytical d_B = {analytical_str})")

        header = (
            f"  {'Graph':<22} {'Nodes':>7} "
            f"{'v4 D':>8} {'v4 gap%':>8} "
            f"{'nf D':>8} {'nf gap%':>8}"
        )
        print(header)
        print("  " + "-" * 73)

        for c in members:
            v4_gap = _fmt_gap_pct(c.v4.dimension, c.spec.analytical_d)
            nf_gap = _fmt_gap_pct(c.nf.dimension, c.spec.analytical_d)
            row = (
                f"  {c.spec.label:<22} {c.v4.n_nodes:>7} "
                f"{_fmt_dim(c.v4.dimension):>8} {v4_gap:>8} "
                f"{_fmt_dim(c.nf.dimension):>8} {nf_gap:>8}"
            )
            print(row)

    print()


def print_refusal_table(comparisons: list[Comparison]) -> None:
    """Print Table 3: refusal cases with verdict comparison."""
    refuse_cases = [c for c in comparisons if c.spec.expect == "refuse"]
    if not refuse_cases:
        return

    print("=" * 100)
    print("TABLE 3: Refusal Cases")
    print("=" * 100)

    header = (
        f"{'Graph':<22} {'Nodes':>7} "
        f"{'v4 verdict':>12} {'nf verdict':>12} {'Match':>7}"
    )
    print(header)
    print("-" * 100)

    for c in refuse_cases:
        v4_verdict = "REFUSED" if c.v4.dimension is None else f"D={c.v4.dimension:.4f}"
        nf_verdict = "REFUSED" if c.nf.dimension is None else f"D={c.nf.dimension:.4f}"
        v4_refused = c.v4.dimension is None
        nf_refused = c.nf.dimension is None
        match = "yes" if v4_refused == nf_refused else "NO"
        row = (
            f"{c.spec.label:<22} {c.v4.n_nodes:>7} "
            f"{v4_verdict:>12} {nf_verdict:>12} {match:>7}"
        )
        print(row)

    print()


# ---------------------------------------------------------------------------
# JSON report writer
# ---------------------------------------------------------------------------


def _round_or_none(val: float | None, digits: int) -> float | None:
    """Round a float to the given number of digits, or return None."""
    return round(val, digits) if val is not None else None


def _gap_pct(measured: float | None, analytical: float | None) -> float | None:
    """Compute gap as percentage of analytical value, or None."""
    if measured is None or analytical is None or analytical == 0.0:
        return None
    return round(100.0 * (measured - analytical) / analytical, 4)


def _run_result_to_dict(r: RunResult) -> dict:
    """Serialize a RunResult to a JSON-safe dict."""
    return {
        "backend": r.backend,
        "dimension": _round_or_none(r.dimension, 6),
        "reason": r.reason,
        "r2": _round_or_none(r.r2, 6),
        "slope": _round_or_none(r.slope, 6),
        "slope_stderr": _round_or_none(r.slope_stderr, 6),
        "window_r_min": r.window_r_min,
        "window_r_max": r.window_r_max,
        "window_log_span": _round_or_none(r.window_log_span, 6),
        "window_delta_y": _round_or_none(r.window_delta_y, 6),
        "delta_aicc": _round_or_none(r.delta_aicc, 4),
        "elapsed_s": round(r.elapsed_s, 4),
        "n_nodes": r.n_nodes,
    }


def _flower_formula(u: int, v: int) -> str:
    """Build the analytical formula string for (u,v)-flower d_B."""
    return f"ln({u + v})/ln({u})"


def write_json_report(comparisons: list[Comparison], total_elapsed: float) -> str:
    """Write structured JSON report and return the output path."""
    report_path = Path(__file__).resolve().parent / "calibration-report.json"

    # --- metadata ---
    metadata = {
        "timestamp": datetime.now(UTC).isoformat(),
        "python_version": platform.python_version(),
        "seed": SEED,
        "total_elapsed_s": round(total_elapsed, 2),
        "corpus_size": len(comparisons),
        "sign_conventions": {
            "analytical_gap": "measured - analytical (positive = overestimate)",
            "gap_pct": "100 * (measured - analytical) / analytical",
            "dimension_delta": "nf - v4 (positive = nf higher)",
        },
    }

    # --- per-graph comparisons ---
    comp_list = []
    for c in comparisons:
        entry = {
            "label": c.spec.label,
            "family": c.spec.family,
            "group": c.spec.group,
            "expect": c.spec.expect,
            "analytical_d": _round_or_none(c.spec.analytical_d, 6),
            "v4": _run_result_to_dict(c.v4),
            "nf": _run_result_to_dict(c.nf),
            "deltas": {
                "dimension_delta": _round_or_none(c.dimension_delta, 6),
                "r2_delta": _round_or_none(c.r2_delta, 6),
                "analytical_gap_v4": _round_or_none(c.analytical_gap_v4, 6),
                "analytical_gap_nf": _round_or_none(c.analytical_gap_nf, 6),
                "gap_pct_v4": _gap_pct(c.v4.dimension, c.spec.analytical_d),
                "gap_pct_nf": _gap_pct(c.nf.dimension, c.spec.analytical_d),
            },
        }
        comp_list.append(entry)

    # --- convergence groups ---
    groups: dict[str, list[Comparison]] = {}
    for c in comparisons:
        if c.spec.group is not None:
            groups.setdefault(c.spec.group, []).append(c)

    convergence: dict[str, dict] = {}
    for group_key, members in groups.items():
        analytical = members[0].spec.analytical_d
        # Build formula string for flowers
        params = members[0].spec.params
        if "u" in params and "v" in params:
            u_val, v_val = params["u"], params["v"]
            formula = f"ln({u_val + v_val})/ln({u_val}) = {_flower_formula(u_val, v_val)}"
        else:
            formula = None

        generations = []
        for c in members:
            generations.append(
                {
                    "label": c.spec.label,
                    "n_nodes": c.v4.n_nodes,
                    "v4_dimension": _round_or_none(c.v4.dimension, 6),
                    "nf_dimension": _round_or_none(c.nf.dimension, 6),
                    "gap_pct_v4": _gap_pct(c.v4.dimension, analytical),
                    "gap_pct_nf": _gap_pct(c.nf.dimension, analytical),
                }
            )

        convergence[group_key] = {
            "analytical_d": _round_or_none(analytical, 6),
            "formula": formula,
            "generations": generations,
        }

    report = {
        "metadata": metadata,
        "comparisons": comp_list,
        "convergence": convergence,
    }

    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return str(report_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="v4 vs navi-fractal calibration")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Skip largest generations for faster iteration",
    )
    args = parser.parse_args()

    print("calibrate.py — v4 vs navi-fractal calibration instrument")
    print()

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

    json_path = write_json_report(comparisons, total)
    print(f"JSON report written to: {json_path}")


if __name__ == "__main__":
    main()
