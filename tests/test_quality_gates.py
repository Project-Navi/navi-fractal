# SPDX-License-Identifier: Apache-2.0
"""Tests for quality gate presets, parameter overrides, and detail strings."""

from __future__ import annotations

import math

from navi_fractal import (
    LinFit,
    QualityGateReason,
    Reason,
    SandboxResult,
    estimate_sandbox_dimension,
    make_grid_graph,
    sandbox_quality_gate,
)


def _make_accepted_result(
    *,
    r2: float = 0.99,
    slope_stderr: float = 0.01,
    window_r_min: int = 1,
    window_r_max: int = 10,
    delta_aicc: float = 10.0,
    window_log_span: float = 2.3,
) -> SandboxResult:
    """Helper: build a synthetic accepted SandboxResult for gate testing."""
    fit = LinFit(
        slope=2.0,
        intercept=0.0,
        r2=r2,
        slope_stderr=slope_stderr,
        sse=0.001,
        n_points=10,
    )
    return SandboxResult(
        dimension=2.0,
        reason=Reason.ACCEPTED,
        reason_detail=None,
        model_preference="powerlaw",
        delta_aicc=delta_aicc,
        powerlaw_fit=fit,
        exponential_fit=None,
        window_r_min=window_r_min,
        window_r_max=window_r_max,
        window_log_span=window_log_span,
        window_delta_y=1.5,
        window_slope_range=None,
        window_aicc_quad_minus_lin=None,
        dimension_ci=None,
        delta_aicc_ci=None,
        bootstrap_valid_reps=0,
        radii_eval=(),
        mean_mass_eval=(),
        y_eval=(),
        n_nodes_original=100,
        n_nodes_measured=100,
        retained_fraction=1.0,
        n_centers=100,
        seed=42,
        notes="",
    )


class TestPresets:
    def test_inclusive_accepts_grid(self) -> None:
        grid = make_grid_graph(30, 30)
        result = estimate_sandbox_dimension(grid, seed=42)
        passed, qg_reason, detail = sandbox_quality_gate(result, preset="inclusive")
        assert passed, detail
        assert qg_reason == QualityGateReason.PASSED

    def test_strict_more_selective(self) -> None:
        """Strict should be at least as selective as inclusive."""
        grid = make_grid_graph(30, 30)
        result = estimate_sandbox_dimension(grid, seed=42)
        inc_passed, _, _ = sandbox_quality_gate(result, preset="inclusive")
        strict_passed, _, _ = sandbox_quality_gate(result, preset="strict")
        if strict_passed:
            assert inc_passed  # strict passing implies inclusive passing


class TestParameterOverrides:
    def test_r2_override(self) -> None:
        result = _make_accepted_result(r2=0.90)
        passed, reason, detail = sandbox_quality_gate(result, preset="inclusive", r2_min=0.95)
        assert not passed
        assert reason == QualityGateReason.R2_TOO_LOW
        assert detail is not None
        assert "0.90" in detail

    def test_stderr_override(self) -> None:
        result = _make_accepted_result(slope_stderr=0.30)
        passed, reason, detail = sandbox_quality_gate(result, preset="inclusive", stderr_max=0.10)
        assert not passed
        assert reason == QualityGateReason.STDERR_TOO_HIGH
        assert detail is not None

    def test_radius_ratio_override(self) -> None:
        result = _make_accepted_result(window_r_min=3, window_r_max=6)
        passed, reason, detail = sandbox_quality_gate(
            result, preset="inclusive", radius_ratio_min=5.0
        )
        assert not passed
        assert reason == QualityGateReason.RADIUS_RATIO_TOO_SMALL
        assert detail is not None

    def test_aicc_override(self) -> None:
        result = _make_accepted_result(delta_aicc=2.0)
        passed, reason, detail = sandbox_quality_gate(result, preset="inclusive", aicc_min=5.0)
        assert not passed
        assert reason == QualityGateReason.AICC_MARGIN_TOO_SMALL
        assert detail is not None


class TestLogSpanOverride:
    def test_log_span_rejects_narrow(self) -> None:
        """Window with log_span < log(3) should be rejected."""
        result = _make_accepted_result(window_log_span=math.log(3.0 / 2.0))
        passed, reason, _detail = sandbox_quality_gate(result, preset="inclusive")
        assert not passed
        assert reason == QualityGateReason.LOG_SPAN_TOO_SMALL

    def test_log_span_passes_wide(self) -> None:
        """Window with log_span > log(3) should pass."""
        result = _make_accepted_result(window_log_span=math.log(5.0))
        passed, _reason, _detail = sandbox_quality_gate(result, preset="inclusive")
        assert passed

    def test_log_span_override(self) -> None:
        """Custom min_log_span should override preset."""
        result = _make_accepted_result(window_log_span=math.log(2.0))
        passed, _reason, _detail = sandbox_quality_gate(
            result, preset="inclusive", min_log_span=math.log(1.5)
        )
        assert passed


class TestDetailStrings:
    def test_detail_contains_threshold(self) -> None:
        result = _make_accepted_result(r2=0.80)
        _, _, detail = sandbox_quality_gate(result, preset="inclusive")
        assert detail is not None
        assert "0.85" in detail  # inclusive R2 threshold
