# Calibration Regime: r=1 Anchor Fix + Convergence Rate Tracker

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix systematic r=1 exclusion in the saturation filter that causes convergence regression at high flower generations, and add a convergence rate tracker that validates sandbox estimates against the proved `O(1/g)` convergence from fd-formalization.

**Architecture:** Two independent changes. (A) One-line fix in `_sandbox.py` saturation filter exempting r=1 from the mass floor, plus a targeted test. (C) New standalone script `scripts/convergence_analysis.py` that reads `calibration-report.json`, fits `gap(g) = a/g + b` per family, compares against the theoretical bound from the Lean squeeze, and flags non-monotonic convergence.

**Tech Stack:** Python 3.12+, pytest, navi-fractal library, calibrate.py infrastructure

---

### Task 1: Write failing test for r=1 saturation filter fix

**Files:**
- Modify: `tests/test_sandbox.py` (append new test class)

**Step 1: Write the failing test**

Add to the end of `tests/test_sandbox.py`:

```python
class TestRadiusOneAnchor:
    def test_radius_one_survives_saturation_filter(self) -> None:
        """r=1 must appear in radii_eval for connected graphs with diameter >= 2.

        The saturation filter (mean_mass_eff <= 1.0) can exclude r=1 when
        geometric-mean ball mass is low. This removes the best anchor point
        for the scaling regression and causes convergence regression at high
        flower generations (e.g., gen 8 gap widens vs gen 7).
        """
        # A star graph has many degree-1 nodes whose r=1 ball has mass=2,
        # but the geometric mean of log-masses can still be > 0 since all
        # nodes have at least 1 neighbor. r=1 should always survive.
        g = Graph()
        for i in range(1, 51):
            g.add_edge(0, i)
        # Star is refused (insufficient window), but radii_eval should
        # still include r=1 if any radii survive.
        result = estimate_sandbox_dimension(g, seed=42)
        # Even if dimension is None, radii_eval tells us what survived filtering.
        if len(result.radii_eval) > 0:
            assert result.radii_eval[0] == 1, (
                f"r=1 was filtered out; radii_eval starts at {result.radii_eval[0]}"
            )
```

**Step 2: Run test to verify it fails**

Run: `cd /home/ndspence/GitHub/navi-fractal && uv run pytest tests/test_sandbox.py::TestRadiusOneAnchor -v`
Expected: FAIL — r=1 may be excluded by the mass floor filter on the star graph

**Note:** If this test passes already (star has high enough geometric mean), we need a graph where r=1 gets filtered. In that case, we verify the fix is correct by checking the gen 8 flower convergence improvement in Task 4 instead. Either way, the test documents the contract.

---

### Task 2: Apply r=1 saturation filter fix

**Files:**
- Modify: `src/navi_fractal/_sandbox.py:346`

**Step 1: Apply the fix**

Change line 346 from:
```python
        if mean_mass_eff <= 1.0:
            continue
```
to:
```python
        if mean_mass_eff <= 1.0 and r > 1:
            continue
```

This exempts r=1 from the mass floor. r=1 in any connected graph with >= 2 nodes has mass >= 2 for at least some centers — the geometric mean can dip below 1.0 due to sampling, but this is noise, not structural degeneracy.

**Step 2: Run test from Task 1**

Run: `cd /home/ndspence/GitHub/navi-fractal && uv run pytest tests/test_sandbox.py::TestRadiusOneAnchor -v`
Expected: PASS

**Step 3: Run full test suite to check for regressions**

Run: `cd /home/ndspence/GitHub/navi-fractal && uv run pytest tests/ -v --benchmark-disable`
Expected: All 196 tests pass. Grid/path dimension estimates should not change (r=1 was already included for those graphs). Flower tests in v4_smoke use the v4 backend, not navi-fractal, so they are unaffected.

**Step 4: Commit**

```bash
cd /home/ndspence/GitHub/navi-fractal
git add src/navi_fractal/_sandbox.py tests/test_sandbox.py
git commit -m "fix: exempt r=1 from saturation filter mass floor

r=1 is the best anchor point for the scaling regression. The
mass floor (mean_mass_eff <= 1.0) can exclude it when the
geometric-mean ball mass is low due to sampling noise in sparse
graphs. This caused convergence regression at high flower
generations (gen 8 gap widened vs gen 7).

Fix: skip the mass floor check for r=1 specifically. r=1 in
any connected graph with >=2 nodes always has mass >= 2 for
at least some centers.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Write convergence analysis script

**Files:**
- Create: `scripts/convergence_analysis.py`

**Step 1: Write the script**

```python
#!/usr/bin/env python3
# Copyright 2026 Nelson Spence
# SPDX-License-Identifier: Apache-2.0
"""Convergence rate analysis: compare sandbox gaps against proved O(1/g) bound.

Reads calibration-report.json, fits gap(g) = a/g + b per flower family,
compares empirical rate against theoretical bound from fd-formalization's
squeeze theorem, and flags non-monotonic convergence.

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


def _load_report() -> dict:
    """Load calibration-report.json from the scripts directory."""
    report_path = Path(__file__).resolve().parent / "calibration-report.json"
    if not report_path.exists():
        print(f"ERROR: {report_path} not found. Run calibrate.py first.", file=sys.stderr)
        sys.exit(1)
    return json.loads(report_path.read_text())


def _extract_flower_params(group_key: str, report: dict) -> tuple[int, int] | None:
    """Extract (u, v) from convergence group data."""
    conv = report.get("convergence", {}).get(group_key)
    if conv is None:
        return None
    formula = conv.get("formula", "")
    # Parse from formula string "ln(U+V)/ln(U) = ln(U+V)/ln(U)"
    # or fall back to group key pattern "flower_UV"
    if group_key.startswith("flower_"):
        digits = group_key[len("flower_"):]
        if len(digits) == 2:
            return int(digits[0]), int(digits[1])
    return None


def _fit_inverse_g(
    generations: list[int], gaps: list[float]
) -> tuple[float, float, float]:
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
    ss_xy = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    ss_yy = sum((y - y_mean) ** 2 for y in ys)

    if ss_xx == 0:
        return 0.0, y_mean, 0.0

    a = ss_xy / ss_xx
    b = y_mean - a * x_mean
    ss_res = sum((y - (a * x + b)) ** 2 for x, y in zip(xs, ys))
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


def analyze(report: dict) -> list[dict]:
    """Analyze convergence for all flower families."""
    convergence = report.get("convergence", {})
    results = []

    for group_key, group_data in sorted(convergence.items()):
        params = _extract_flower_params(group_key, report)
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

        results.append({
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
        })

    return results


def print_table(results: list[dict]) -> None:
    """Print human-readable convergence analysis table."""
    print("\n=== Convergence Rate Analysis ===")
    print("(Comparing sandbox gap decay against proved O(1/g) bound)\n")

    header = f"{'Family':<12} {'d_B':>6} {'Gens':>4} {'a_emp':>8} {'a_theory':>9} {'Amp':>5} {'R²':>6} {'Mono':>5} {'Anomalies'}"
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
    print("Amp: amplification factor = |a_emp| / a_theory")
    print("Mono: OK = gap shrinks monotonically, WARN = regression detected")


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
```

**Step 2: Run the script on existing (pre-fix) calibration data**

Run: `cd /home/ndspence/GitHub/navi-fractal && uv run python scripts/convergence_analysis.py`
Expected: Table showing convergence rates per family. The (2,2)-flower should show `Mono: WARN` with gen 8 flagged as an anomaly.

**Step 3: Commit**

```bash
cd /home/ndspence/GitHub/navi-fractal
git add scripts/convergence_analysis.py
git commit -m "feat: add convergence rate tracker for flower calibration

Reads calibration-report.json, fits gap(g) = a/g + b per flower
family, compares empirical convergence rate against the proved
O(1/g) bound from fd-formalization's squeeze theorem, and flags
non-monotonic convergence (e.g., gen 8 regression).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Re-run calibration and verify improvement

**Files:**
- Modified by calibrate.py: `scripts/calibration-report.json`

**Step 1: Save old report for comparison**

Run: `cd /home/ndspence/GitHub/navi-fractal && cp scripts/calibration-report.json scripts/calibration-report-pre-fix.json`

**Step 2: Re-run full calibration**

Run: `cd /home/ndspence/GitHub/navi-fractal && uv run python scripts/calibrate.py`
Expected: Completes in ~15s. Check stdout for the (2,2) gen 8 dimension — should be closer to gen 7's estimate if r=1 was previously being filtered.

**Step 3: Run convergence analysis on new data**

Run: `cd /home/ndspence/GitHub/navi-fractal && uv run python scripts/convergence_analysis.py`
Expected: If the fix helped, the (2,2)-flower gen 8 anomaly should resolve (Mono: OK) or the gap should shrink.

**Step 4: Diff the reports**

Run: `cd /home/ndspence/GitHub/navi-fractal && python3 -c "
import json
old = json.loads(open('scripts/calibration-report-pre-fix.json').read())
new = json.loads(open('scripts/calibration-report.json').read())
for o, n in zip(old['comparisons'], new['comparisons']):
    if o['family'] != 'flower': continue
    od = o['nf'].get('dimension')
    nd = n['nf'].get('dimension')
    if od and nd and abs(od - nd) > 0.001:
        print(f\"{o['label']}: {od:.4f} -> {nd:.4f} (delta={nd-od:+.4f})\")
    elif od == nd:
        print(f\"{o['label']}: {od:.4f} (unchanged)\")
"`
Expected: Shows which flower dimensions changed. Entries where r=1 was previously filtered should show positive delta (dimension increased toward analytical value).

**Step 5: Clean up temp file and commit updated report**

```bash
cd /home/ndspence/GitHub/navi-fractal
rm scripts/calibration-report-pre-fix.json
git add scripts/calibration-report.json
git commit -m "data: regenerate calibration report after r=1 fix

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Run full regression suite

**Files:** None modified — verification only.

**Step 1: Full test suite**

Run: `cd /home/ndspence/GitHub/navi-fractal && uv run pytest tests/ -v --benchmark-disable`
Expected: All tests pass. If any flower dimension assertions in v4_smoke shifted outside tolerance, the tests use the v4 backend (unaffected by our change) so they should still pass.

**Step 2: Lint + typecheck**

Run: `cd /home/ndspence/GitHub/navi-fractal && uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`
Expected: Clean.

Run: `cd /home/ndspence/GitHub/navi-fractal && uv run mypy --strict src/navi_fractal/`
Expected: Clean.

---

### Task 6: Code review

Dispatch code reviewer agent to audit:
1. The r=1 fix in `_sandbox.py:346` — verify it doesn't break the saturation filter for legitimate cases (e.g., disconnected graphs where r=1 truly has mass=1)
2. The convergence analysis script — verify the fit formula, theoretical bound, and monotonicity check are mathematically correct
3. The test — verify it actually exercises the code path we fixed

---

## Parallelization notes

- **Tasks 1-2 (fix A)** and **Task 3 (script C)** are fully independent and can run in parallel
- **Task 4** depends on both 1-2 and 3
- **Task 5** depends on 4
- **Task 6** depends on 5
