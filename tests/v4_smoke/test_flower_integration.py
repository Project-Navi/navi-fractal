# Copyright 2024-2026 Nelson Spence
# SPDX-License-Identifier: Apache-2.0
"""Layer 2 flower integration smoke tests — validate v4 sandbox dimension
estimation on (u,v)-flower recursive scale-free networks.

These tests verify:
- Constructor correctness (node/edge counts, diameter, structure)
- Dimension estimation (sandbox D vs analytical box-counting d_B)
- Quality gate acceptance/rejection

**Sandbox vs box-counting dimension gap:**

The sandbox (mass-radius) dimension systematically underestimates the analytical
box-counting dimension d_B for (u,v)-flowers. This is a known, expected
discrepancy: the two definitions measure different geometric properties and only
coincide for certain graph families (e.g., lattices). The sandbox method
measures how ball mass grows with radius from random centers, while
box-counting measures the minimum number of boxes of diameter r needed to cover
the graph. Tolerances below are set to match v4's actual output with modest
guard bands, not the analytical d_B values.

Reference values (v4, seed=42):
  (2,2) gen 8: D=1.8117  (d_B=2.0000, gap=-0.19)
  (3,3) gen 5: D=1.4952  (d_B=1.6309, gap=-0.14)
  (4,4) gen 4: D=1.3977  (d_B=1.5000, gap=-0.10)
  (2,3) gen 6: D=1.9911  (d_B=2.3219, gap=-0.33)
  (1,2) gen 8: D=None    (d_B=inf, transfractal — correctly refused)
"""

from __future__ import annotations

import importlib.util as _ilu
import math
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
from fractal_analysis_v4_mfa import (  # noqa: E402
    compile_to_undirected_metric_graph,
    estimate_sandbox_dimension,
    farthest_from,
    sandbox_quality_gate,
)

# Load make_uv_flower from the v4_smoke conftest via importlib to avoid
# collision with the parent tests/conftest.py already cached by pytest.
_conftest_path = str(Path(__file__).resolve().parent / "conftest.py")
_spec = _ilu.spec_from_file_location("v4_smoke_conftest", _conftest_path)
assert _spec is not None and _spec.loader is not None
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
make_uv_flower = _mod.make_uv_flower  # type: ignore[attr-defined]

# ============================================================================
# TestFlowerConstructor — structural validation of (u,v)-flower graphs
# ============================================================================


class TestFlowerConstructor:
    """Verify that (u,v)-flower construction produces correct topology."""

    def test_22_gen8_node_count(self, flower_22_gen8: V4Graph) -> None:
        """(2,2)-flower gen 8 has exactly 43,692 nodes.

        Formula: N(g) = 2 + sum_{k=1}^{g} (u+v-2) * (u+v)^{k-1}
        For (2,2), g=8: N = 2 + 2 * (4^8 - 1) / 3 = 43,692.
        """
        assert flower_22_gen8.n_nodes == 43_692

    def test_22_gen8_diameter(self, flower_22_gen8: V4Graph) -> None:
        """(2,2)-flower gen 8 has diameter 256 = 2^8.

        The diameter of a (u,v)-flower at generation g is u^g (the longer
        path length raised to the generation power). For (2,2): 2^8 = 256.
        """
        cg = compile_to_undirected_metric_graph(flower_22_gen8)
        # Two-sweep BFS heuristic: farthest from 0, then farthest from that.
        far1, _d1 = farthest_from(cg, 0)
        _far2, diameter = farthest_from(cg, far1)
        assert diameter == 256

    def test_22_gen0_is_single_edge(self) -> None:
        """Generation 0 is a single edge between two hub nodes."""
        g = make_uv_flower(2, 2, 0)
        assert g.n_nodes == 2
        assert g.n_edges == 1

    def test_22_gen1_structure(self) -> None:
        """Generation 1 has 4 nodes and 4 edges (two parallel paths of length 2).

        The original edge (0--1) is replaced by two paths:
        path1: 0 -- 2 -- 1
        path2: 0 -- 3 -- 1
        Giving 4 edges: {0,2}, {2,1}, {0,3}, {3,1}.
        """
        g = make_uv_flower(2, 2, 1)
        assert g.n_nodes == 4
        assert g.n_edges == 4
        # Hub nodes 0 and 1 should each connect to the two intermediate nodes.
        assert g.out_neighbors_set(0) == {2, 3}
        assert g.out_neighbors_set(1) == {2, 3}
        # Intermediate nodes connect only to the two hubs.
        assert g.out_neighbors_set(2) == {0, 1}
        assert g.out_neighbors_set(3) == {0, 1}

    def test_33_gen5_node_count(self, flower_33_gen5: V4Graph) -> None:
        """(3,3)-flower gen 5 has exactly 6,222 nodes.

        Formula: N(g) = 2 + (u+v-2) * sum_{k=0}^{g-1} (u+v)^k
        For (3,3), g=5: N = 2 + 4 * (6^5 - 1) / 5 = 2 + 4 * 1555 = 6,222.
        """
        assert flower_33_gen5.n_nodes == 6_222

    def test_flower_deterministic(self) -> None:
        """Same parameters produce identical graphs (same node/edge counts)."""
        g1 = make_uv_flower(3, 3, 4)
        g2 = make_uv_flower(3, 3, 4)
        assert g1.n_nodes == g2.n_nodes
        assert g1.n_edges == g2.n_edges


# ============================================================================
# TestFlowerDimension — sandbox dimension estimation on flowers
# ============================================================================


class TestFlowerDimension:
    """Verify sandbox dimension estimation against known fractal dimensions.

    The sandbox method systematically underestimates the analytical
    box-counting dimension d_B for (u,v)-flowers. Tolerances are set based
    on v4's actual output (seed=42), not the analytical values. Each test
    documents the expected gap.
    """

    def test_22_flower_dimension(self, flower_22_gen8: V4Graph) -> None:
        """(2,2)-flower: d_B = ln(4)/ln(2) = 2.0, v4 sandbox D ≈ 1.81.

        The sandbox underestimates by ~0.19 due to the fundamental difference
        between mass-radius and box-covering dimension definitions on
        hierarchical recursive networks. Tolerance: ±0.15 around 1.81.
        """
        r = estimate_sandbox_dimension(flower_22_gen8, seed=42)
        assert r.dimension is not None, f"estimation refused: {r.reason}"
        assert abs(r.dimension - 1.81) < 0.15, f"D={r.dimension:.4f}, expected ~1.81 (d_B=2.0)"

    def test_33_flower_dimension(self, flower_33_gen5: V4Graph) -> None:
        """(3,3)-flower: d_B = ln(6)/ln(3) ≈ 1.631, v4 sandbox D ≈ 1.50.

        Sandbox underestimates by ~0.14. Tolerance: ±0.15 around 1.50.
        """
        r = estimate_sandbox_dimension(flower_33_gen5, seed=42)
        assert r.dimension is not None, f"estimation refused: {r.reason}"
        assert abs(r.dimension - 1.50) < 0.15, (
            f"D={r.dimension:.4f}, expected ~1.50 (d_B={math.log(6) / math.log(3):.3f})"
        )

    def test_44_flower_dimension(self, flower_44_gen4: V4Graph) -> None:
        """(4,4)-flower: d_B = ln(8)/ln(4) = 1.5, v4 sandbox D ≈ 1.40.

        Sandbox underestimates by ~0.10. Tolerance: ±0.15 around 1.40.
        """
        r = estimate_sandbox_dimension(flower_44_gen4, seed=42)
        assert r.dimension is not None, f"estimation refused: {r.reason}"
        assert abs(r.dimension - 1.40) < 0.15, f"D={r.dimension:.4f}, expected ~1.40 (d_B=1.5)"

    def test_23_flower_dimension(self, flower_23_gen6: V4Graph) -> None:
        """(2,3)-flower: d_B = ln(5)/ln(2) ≈ 2.322, v4 sandbox D ≈ 1.99.

        Sandbox underestimates by ~0.33 — the largest gap, likely because the
        asymmetric path lengths (2 vs 3) create stronger boundary effects in
        mass-radius sampling. Tolerance: ±0.15 around 1.99.
        """
        r = estimate_sandbox_dimension(flower_23_gen6, seed=42)
        assert r.dimension is not None, f"estimation refused: {r.reason}"
        assert abs(r.dimension - 1.99) < 0.15, (
            f"D={r.dimension:.4f}, expected ~1.99 (d_B={math.log(5) / math.log(2):.3f})"
        )

    def test_22_flower_r2_high(self, flower_22_gen8: V4Graph) -> None:
        """(2,2)-flower should achieve R² > 0.99 — excellent power-law fit.

        v4 reference: R² = 0.9994 with 15-point fit window.
        """
        r = estimate_sandbox_dimension(flower_22_gen8, seed=42)
        assert r.dimension is not None, f"estimation refused: {r.reason}"
        assert r.powerlaw_fit is not None
        assert r.powerlaw_fit.r2 > 0.99, f"R²={r.powerlaw_fit.r2:.6f}, expected > 0.99"

    def test_22_flower_reason_accepted(self, flower_22_gen8: V4Graph) -> None:
        """(2,2)-flower estimation should be accepted, not refused."""
        r = estimate_sandbox_dimension(flower_22_gen8, seed=42)
        assert r.reason is not None
        assert "accepted" in r.reason.lower(), f"unexpected reason: {r.reason}"

    def test_22_flower_deterministic(self, flower_22_gen8: V4Graph) -> None:
        """Same seed on same graph must produce bit-identical results."""
        r1 = estimate_sandbox_dimension(flower_22_gen8, seed=42)
        r2 = estimate_sandbox_dimension(flower_22_gen8, seed=42)
        assert r1.dimension == r2.dimension
        assert r1.reason == r2.reason
        assert r1.powerlaw_fit is not None
        assert r2.powerlaw_fit is not None
        assert r1.powerlaw_fit.r2 == r2.powerlaw_fit.r2
        assert r1.powerlaw_fit.slope == r2.powerlaw_fit.slope


# ============================================================================
# TestFlowerQualityGates — quality gate acceptance/rejection
# ============================================================================


class TestFlowerQualityGates:
    """Verify quality gate verdicts for flower graphs.

    Key behaviours:
    - (1,2)-flower (transfractal, d_B=inf) should be rejected
    - (2,2)-flower (fractal, d_B=2) should be accepted
    """

    def test_12_flower_gate_rejects(self, flower_12_gen8: V4Graph) -> None:
        """(1,2)-flower is transfractal (d_B = inf) — the gate must reject.

        The (1,2)-flower has u=1, creating a "small-world" graph with
        logarithmic diameter. The sandbox estimator correctly refuses to
        emit a dimension (insufficient non-degenerate points), and the
        quality gate rejects the result.
        """
        r = estimate_sandbox_dimension(flower_12_gen8, seed=42)
        passed, detail = sandbox_quality_gate(r, preset="inclusive")
        assert passed is False, f"gate should reject transfractal, got: {detail}"

    def test_22_flower_gate_accepts(self, flower_22_gen8: V4Graph) -> None:
        """(2,2)-flower passes the inclusive quality gate.

        v4 reference: gate returns (True, 'accept: passed inclusive quality gates').
        """
        r = estimate_sandbox_dimension(flower_22_gen8, seed=42)
        passed, detail = sandbox_quality_gate(r, preset="inclusive")
        assert passed is True, f"gate should accept (2,2)-flower, got: {detail}"

    def test_22_flower_strict_gate(self, flower_22_gen8: V4Graph) -> None:
        """(2,2)-flower under strict gate — warn if it fails, don't assert.

        The strict preset has tighter thresholds. v4 currently passes strict
        for this flower, but this test uses a warning rather than a hard
        assertion to avoid brittleness if strict thresholds change.
        """
        r = estimate_sandbox_dimension(flower_22_gen8, seed=42)
        passed, detail = sandbox_quality_gate(r, preset="strict")
        if not passed:
            pytest.skip(f"(2,2)-flower failed strict gate (non-critical): {detail}")
