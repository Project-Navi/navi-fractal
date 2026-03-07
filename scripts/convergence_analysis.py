#!/usr/bin/env python3
# Copyright 2026 Nelson Spence
# SPDX-License-Identifier: Apache-2.0
"""Convergence rate analysis: compare sandbox gaps against proved O(1/g) bound.

Reads calibration-report.json, fits gap(g) = a/g + b per flower family,
compares empirical rate against theoretical bound from fd-formalization's
squeeze theorem, and flags non-monotonic convergence.

The theoretical bound comes from the Lean squeeze in FlowerLog.lean:
    log(N_g) - g*log(w) <= log(2)
Dividing by g*log(u) and expressing as percentage of d_B = log(w)/log(u)
gives rate constant = 100 * log(2) / log(u+v).

The amplification factor (Amp > 1) is expected: the proved bound applies to
the log-ratio log(N_g)/log(L_g), while the sandbox measures local ball-mass
scaling — a different geometric quantity that converges more slowly.

Usage:
    uv run python scripts/convergence_analysis.py
    uv run python scripts/convergence_analysis.py --json  # machine-readable output
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


def _load_report() -> dict[str, Any]:
    """Load calibration-report.json from the scripts directory."""
    report_path = Path(__file__).resolve().parent / "calibration-report.json"
    if not report_path.exists():
        print(f"ERROR: {report_path} not found. Run calibrate.py first.", file=sys.stderr)
        sys.exit(1)
    result: dict[str, Any] = json.loads(report_path.read_text())
    return result


def _extract_flower_params(
    group_key: str, comparisons: list[dict[str, Any]]
) -> tuple[int, int] | None:
    """Extract (u, v) from the first comparison entry matching this group."""
    # Verify the group exists as a flower family in the comparisons
    if not any(
        comp.get("group") == group_key and comp.get("family") == "flower" for comp in comparisons
    ):
        return None
    # Parse from group key pattern "flower_UV" (e.g., "flower_22", "flower_23")
    if not group_key.startswith("flower_"):
        return None
    suffix = group_key[len("flower_") :]
    # Support both "flower_22" (single digits) and "flower_10_12" (underscore-separated)
    if "_" in suffix:
        parts = suffix.split("_")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]), int(parts[1])
    elif len(suffix) == 2 and suffix.isdigit():
        return int(suffix[0]), int(suffix[1])
    return None


def _fit_inverse_g(generations: list[int], gaps: list[float]) -> tuple[float, float, float]:
    """Fit gap = a/g + b via least squares.

    Returns (a, b, r_squared).
    """
    n = len(generations)
    if n < 2:
        return 0.0, 0.0, 0.0

    # x = 1/g, y = gap
    xs = [1.0 / g for g in generations]
    ys = gaps

    x_mean = sum(xs) / n
    y_mean = sum(ys) / n

    ss_xx = sum((x - x_mean) ** 2 for x in xs)
    ss_xy = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True))
    ss_yy = sum((y - y_mean) ** 2 for y in ys)

    if ss_xx == 0:
        return 0.0, y_mean, 0.0

    a = ss_xy / ss_xx
    b = y_mean - a * x_mean
    ss_res = sum((y - (a * x + b)) ** 2 for x, y in zip(xs, ys, strict=True))
    r2 = 1.0 - ss_res / ss_yy if ss_yy > 0 else 0.0

    return a, b, r2


def _theoretical_bound(u: int, v: int) -> float:
    """Theoretical convergence rate constant from the Lean squeeze bounds.

    The squeeze gives: residual <= log(2) / (g * log(u))
    As a percentage of d_B = log(u+v)/log(u):
        rate_pct = 100 * log(2) / (log(u) * d_B)
                 = 100 * log(2) / log(u+v)
    """
    w = u + v
    return 100.0 * math.log(2) / math.log(w)


def _check_monotonicity(gaps: list[float]) -> list[int]:
    """Return indices where |gap| increases (convergence regression).

    gaps are negative (underestimation), so regression = gap becoming
    more negative at higher generation.
    """
    anomalies = []
    for i in range(1, len(gaps)):
        if abs(gaps[i]) > abs(gaps[i - 1]):
            anomalies.append(i)
    return anomalies


def analyze(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Analyze convergence for all flower families."""
    convergence = report.get("convergence", {})
    results = []

    comparisons: list[dict[str, Any]] = report.get("comparisons", [])
    for group_key, group_data in sorted(convergence.items()):
        params = _extract_flower_params(group_key, comparisons)
        if params is None:
            continue
        u, v = params
        analytical_d = group_data["analytical_d"]
        if analytical_d is None:
            continue

        gens_data = group_data["generations"]
        if len(gens_data) < 2:
            continue

        # Extract generation number from label (e.g., "flower_22_gen4" -> 4)
        generations = []
        gaps_nf = []
        gaps_v4 = []
        for entry in gens_data:
            label = entry["label"]
            gen = int(label.split("gen")[1])
            generations.append(gen)
            gaps_nf.append(entry.get("gap_pct_nf", 0.0) or 0.0)
            gaps_v4.append(entry.get("gap_pct_v4", 0.0) or 0.0)

        # Fit gap(g) = a/g + b
        a_nf, b_nf, r2_nf = _fit_inverse_g(generations, gaps_nf)
        a_v4, b_v4, r2_v4 = _fit_inverse_g(generations, gaps_v4)

        # Theoretical bound
        a_theory = _theoretical_bound(u, v)

        # Monotonicity check
        anomalies = _check_monotonicity(gaps_nf)
        anomaly_labels = [gens_data[i]["label"] for i in anomalies]

        results.append(
            {
                "group": group_key,
                "u": u,
                "v": v,
                "analytical_d": round(analytical_d, 6),
                "n_generations": len(generations),
                "generations": generations,
                "gaps_nf_pct": [round(g, 4) for g in gaps_nf],
                "fit_nf": {
                    "a": round(a_nf, 4),
                    "b": round(b_nf, 4),
                    "r2": round(r2_nf, 6),
                },
                "fit_v4": {
                    "a": round(a_v4, 4),
                    "b": round(b_v4, 4),
                    "r2": round(r2_v4, 6),
                },
                "theoretical_rate_pct": round(a_theory, 4),
                "amplification_nf": round(abs(a_nf) / a_theory, 2) if a_theory > 0 else None,
                "amplification_v4": round(abs(a_v4) / a_theory, 2) if a_theory > 0 else None,
                "monotonic": len(anomalies) == 0,
                "anomalies": anomaly_labels,
            }
        )

    return results


def print_table(results: list[dict[str, Any]]) -> None:
    """Print human-readable convergence analysis table."""
    print("\n=== Convergence Rate Analysis ===")
    print("(Comparing sandbox gap decay against proved O(1/g) bound)\n")

    header = (
        f"{'Family':<12} {'d_B':>6} {'Gens':>4} {'a_emp':>8} "
        f"{'a_theory':>9} {'Amp':>5} {'R²':>6} {'Mono':>5} {'Anomalies'}"
    )
    print(header)
    print("-" * len(header))

    for r in results:
        amp = f"{r['amplification_nf']:.1f}x" if r["amplification_nf"] else "N/A"
        mono = "OK" if r["monotonic"] else "WARN"
        anomalies = ", ".join(r["anomalies"]) if r["anomalies"] else ""
        print(
            f"({r['u']},{r['v']})-flower"
            f" {r['analytical_d']:>6.3f}"
            f" {r['n_generations']:>4}"
            f" {r['fit_nf']['a']:>8.1f}"
            f" {r['theoretical_rate_pct']:>9.1f}"
            f" {amp:>5}"
            f" {r['fit_nf']['r2']:>6.3f}"
            f" {mono:>5}"
            f" {anomalies}"
        )

    print()
    print("a_emp: empirical rate constant from fit gap(g) = a/g + b")
    print("a_theory: theoretical upper bound = 100 * log(2) / log(u+v)")
    print("Amp: |a_emp| / a_theory (expected > 1 — sandbox gap includes measurement noise)")
    print("Mono: OK = gap shrinks monotonically, WARN = regression detected")
    print()
    print("NOTE: Non-monotonic convergence (e.g., gen 8 regression) is a legitimate")
    print("window selection outcome, not a bug. The curvature guard correctly rejects")
    print("wide windows with non-linear scaling, and the scoring function correctly")
    print("prefers the widest surviving window. The sandbox measures local ball-mass")
    print("scaling, which differs from the global log-ratio proved in fd-formalization.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convergence rate analysis")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of table")
    args = parser.parse_args()

    report = _load_report()
    results = analyze(report)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_table(results)


if __name__ == "__main__":
    main()
