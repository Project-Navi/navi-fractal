# SPDX-License-Identifier: Apache-2.0
"""Tests for shared type definitions."""

from __future__ import annotations

import pytest

from navi_fractal._types import DimensionSummary, QualityGateReason, Reason


class TestReasonEnum:
    def test_all_members_exist(self) -> None:
        expected = {
            "ACCEPTED",
            "EMPTY_GRAPH",
            "TRIVIAL_GRAPH",
            "GIANT_COMPONENT_TOO_SMALL",
            "NO_VALID_RADII",
            "NO_WINDOW_PASSES_R2",
            "AICC_PREFERS_EXPONENTIAL",
            "CURVATURE_GUARD",
            "SLOPE_STABILITY_GUARD",
            "NEGATIVE_SLOPE",
        }
        actual = {m.name for m in Reason}
        assert actual == expected

    def test_reason_is_enum(self) -> None:
        assert isinstance(Reason.ACCEPTED, Reason)


class TestQualityGateReasonEnum:
    def test_all_members_exist(self) -> None:
        expected = {
            "PASSED",
            "NOT_ACCEPTED",
            "R2_TOO_LOW",
            "STDERR_TOO_HIGH",
            "RADIUS_RATIO_TOO_SMALL",
            "AICC_MARGIN_TOO_SMALL",
        }
        actual = {m.name for m in QualityGateReason}
        assert actual == expected


class TestDimensionSummary:
    def test_construction(self) -> None:
        summary = DimensionSummary(
            dimension=1.85,
            accepted=True,
            reason=Reason.ACCEPTED,
            r2=0.997,
            ci=(1.70, 2.00),
        )
        assert summary.dimension == 1.85
        assert summary.accepted is True
        assert summary.reason is Reason.ACCEPTED
        assert summary.r2 == 0.997
        assert summary.ci == (1.70, 2.00)

    def test_frozen(self) -> None:
        summary = DimensionSummary(
            dimension=None,
            accepted=False,
            reason=Reason.EMPTY_GRAPH,
            r2=None,
            ci=None,
        )
        with pytest.raises(AttributeError):
            summary.dimension = 2.0  # type: ignore[misc]
