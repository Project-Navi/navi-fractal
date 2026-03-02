# SPDX-License-Identifier: Apache-2.0
"""Layer 3 cross-algorithm plausibility smoke tests — validate v4 sandbox
dimension estimation on grids, paths, and non-fractal networks.

These tests verify:
- Grid plausibility: 30x30 grid produces dimension in [1.55, 1.75] and is accepted
- Path plausibility: 100-node path produces dimension near 1.0
- Non-fractal rejection: BA, ER, and complete graphs are refused or rejected

Reference values (v4, seed=42):
  Grid 30x30:  D=1.6221  (accepted, gate passes inclusive)
  Path 100:    D=0.8284  (accepted with curvature_guard=False)
  BA(1000,3):  D=None    (refused: auto radii has < min_points; diam_est=5)
  ER(500,0.01):D=None    (refused: insufficient non-degenerate, non-saturated points)
  K50:         D=None    (refused: auto radii has < min_points; diam_est=1)
"""

from __future__ import annotations

import importlib.util as _ilu
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
    estimate_sandbox_dimension,
    make_grid_graph,
    sandbox_quality_gate,
)

# Load conftest helpers via importlib to avoid collision with parent conftest.
_conftest_path = str(Path(__file__).resolve().parent / "conftest.py")
_spec = _ilu.spec_from_file_location("v4_smoke_conftest", _conftest_path)
assert _spec is not None and _spec.loader is not None
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
make_ba_graph = _mod.make_ba_graph  # type: ignore[attr-defined]
make_er_graph = _mod.make_er_graph  # type: ignore[attr-defined]


# ============================================================================
# TestGridPlausibility — 30x30 grid dimension estimation
# ============================================================================


class TestGridPlausibility:
    """Verify sandbox dimension estimation on a 30x30 grid.

    A 30x30 grid is a finite 2D lattice.  The sandbox dimension is expected
    to be in [1.55, 1.75] due to boundary effects pulling the measured value
    below the theoretical d=2 of an infinite lattice.

    v4 reference (seed=42): D=1.6221, reason contains "accepted".
    """

    @pytest.fixture(scope="class")
    def grid_result(self) -> object:
        """Estimate sandbox dimension for 30x30 grid (shared across class)."""
        grid = make_grid_graph(30, 30)
        return estimate_sandbox_dimension(grid, seed=42)

    def test_30x30_grid_dimension_range(self, grid_result: object) -> None:
        """30x30 grid dimension should be in [1.55, 1.75].

        The boundary-affected 2D lattice produces a sandbox dimension below
        the theoretical d=2, typically around 1.62 for this size.
        """
        assert grid_result.dimension is not None, f"estimation refused: {grid_result.reason}"
        assert 1.55 <= grid_result.dimension <= 1.75, (
            f"D={grid_result.dimension:.4f}, expected in [1.55, 1.75]"
        )

    def test_30x30_grid_accepted(self, grid_result: object) -> None:
        """30x30 grid should be accepted with a credible scaling window."""
        assert grid_result.dimension is not None, f"estimation refused: {grid_result.reason}"
        assert "accepted" in grid_result.reason.lower(), f"unexpected reason: {grid_result.reason}"


# ============================================================================
# TestPathPlausibility — 100-node path graph
# ============================================================================


class TestPathPlausibility:
    """Verify sandbox dimension estimation on a 100-node path graph.

    A path graph is a 1D structure; the sandbox dimension should be near 1.0.
    The curvature guard is disabled because the path's scaling behaviour may
    trigger it due to the finite-size saturation at the endpoints.

    v4 reference (seed=42, curvature_guard=False): D=0.8284.
    """

    def test_path_100_dimension_near_1(self) -> None:
        """100-node path dimension should be in [0.8, 1.2].

        The theoretical dimension of a path is exactly 1.0, but boundary
        effects and the small size pull the measured value slightly below 1.
        """
        g = V4Graph(directed=False)
        for i in range(99):
            g.add_edge(i, i + 1)
        r = estimate_sandbox_dimension(g, seed=42, curvature_guard=False)
        assert r.dimension is not None, f"estimation refused: {r.reason}"
        assert 0.8 <= r.dimension <= 1.2, f"D={r.dimension:.4f}, expected in [0.8, 1.2]"


# ============================================================================
# TestNonFractalRejection — BA, ER, and complete graphs
# ============================================================================


class TestNonFractalRejection:
    """Verify that non-fractal networks are refused or rejected.

    The sandbox estimator should either refuse to emit a dimension entirely
    (dimension=None) or produce a result that fails the quality gate. These
    tests assert the disjunction: refused OR gate-rejected.

    v4 reference (seed=42):
      BA(1000,3):   D=None  (refused: insufficient radii, diam_est=5)
      ER(500,0.01): D=None  (refused: insufficient non-degenerate points)
      K50:          D=None  (refused: insufficient radii, diam_est=1)
    """

    def test_ba_model_rejected_or_poor_quality(self) -> None:
        """BA(n=1000, m=3) should be refused or rejected by the quality gate.

        Barabasi-Albert preferential attachment graphs have small-world
        structure (logarithmic diameter) that does not exhibit power-law
        mass-radius scaling.  v4 refuses with diam_est=5.
        """
        ba = make_ba_graph(1000, 3, seed=42)
        r = estimate_sandbox_dimension(ba, seed=42)
        if r.dimension is None:
            # Refused outright — this is the expected v4 behaviour.
            return
        passed, _detail = sandbox_quality_gate(r, preset="inclusive")
        assert not passed, (
            f"BA graph should be refused or gate-rejected, got D={r.dimension}, gate passed"
        )

    def test_er_random_rejected_or_poor_quality(self) -> None:
        """ER(n=500, p=0.01) should be refused or rejected by the quality gate.

        Erdos-Renyi random graphs with low edge probability produce sparse
        networks without clean power-law scaling.  v4 refuses due to
        insufficient non-degenerate, non-saturated radii.
        """
        er = make_er_graph(500, 0.01, seed=42)
        r = estimate_sandbox_dimension(er, seed=42)
        if r.dimension is None:
            # Refused outright — this is the expected v4 behaviour.
            return
        passed, _detail = sandbox_quality_gate(r, preset="inclusive")
        assert not passed, (
            f"ER graph should be refused or gate-rejected, got D={r.dimension}, gate passed"
        )

    def test_complete_k50_refused(self) -> None:
        """K50 complete graph should be refused (dimension=None).

        A complete graph on 50 nodes has diameter 1, so all radii are
        trivially saturated and the estimator cannot construct a scaling
        window.  v4 refuses with diam_est=1.
        """
        g = V4Graph(directed=False)
        for i in range(50):
            for j in range(i + 1, 50):
                g.add_edge(i, j)
        r = estimate_sandbox_dimension(g, seed=42)
        assert r.dimension is None, f"K50 should be refused, got D={r.dimension}, reason={r.reason}"
