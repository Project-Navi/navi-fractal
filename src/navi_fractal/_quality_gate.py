# SPDX-License-Identifier: Apache-2.0
"""Post-hoc quality gate for sandbox dimension results.

Separate from the estimator's acceptance decision. The quality gate
applies a policy threshold --- it can reject what the estimator accepted,
but never accepts what the estimator refused.
"""

from __future__ import annotations

from navi_fractal._sandbox import SandboxResult
from navi_fractal._types import QualityGateReason, Reason


def sandbox_quality_gate(
    result: SandboxResult,
    *,
    preset: str = "inclusive",
    r2_min: float | None = None,
    stderr_max: float | None = None,
    radius_ratio_min: float | None = None,
    aicc_min: float | None = None,
) -> tuple[bool, QualityGateReason, str | None]:
    """Post-hoc acceptance policy for sandbox dimension results.

    Returns (passed, reason, detail).

    Presets:
        "inclusive" --- R2 >= 0.85, stderr <= 0.50, ratio >= 3.0, delta-AICc >= 1.5
        "strict"   --- R2 >= 0.95, stderr <= 0.20, ratio >= 4.0, delta-AICc >= 3.0

    All thresholds overridable via keyword arguments.
    """
    if preset == "inclusive":
        defaults = (0.85, 0.50, 3.0, 1.5)
    elif preset == "strict":
        defaults = (0.95, 0.20, 4.0, 3.0)
    else:
        raise ValueError(f"Unknown preset: {preset!r}, expected 'inclusive' or 'strict'")

    r2_threshold = r2_min if r2_min is not None else defaults[0]
    stderr_threshold = stderr_max if stderr_max is not None else defaults[1]
    ratio_threshold = radius_ratio_min if radius_ratio_min is not None else defaults[2]
    aicc_threshold = aicc_min if aicc_min is not None else defaults[3]

    if result.dimension is None or result.reason != Reason.ACCEPTED:
        return False, QualityGateReason.NOT_ACCEPTED, f"estimator refused: {result.reason.name}"

    fit = result.powerlaw_fit
    if fit is None:  # pragma: no cover — guaranteed when dimension is not None
        return False, QualityGateReason.NOT_ACCEPTED, "no fit available"

    if fit.r2 < r2_threshold:
        return (
            False,
            QualityGateReason.R2_TOO_LOW,
            f"R2={fit.r2:.4f} < {r2_threshold}",
        )

    if fit.slope_stderr > stderr_threshold:
        return (
            False,
            QualityGateReason.STDERR_TOO_HIGH,
            f"stderr={fit.slope_stderr:.4f} > {stderr_threshold}",
        )

    # Radius ratio check: r_max / r_min of the scaling window
    if result.window_r_min is not None and result.window_r_max is not None:
        if result.window_r_min > 0:
            ratio = result.window_r_max / result.window_r_min
            if ratio < ratio_threshold:
                return (
                    False,
                    QualityGateReason.RADIUS_RATIO_TOO_SMALL,
                    f"radius_ratio={ratio:.2f} < {ratio_threshold}",
                )

    # delta-AICc check
    if result.delta_aicc is not None:
        if result.delta_aicc < aicc_threshold:
            return (
                False,
                QualityGateReason.AICC_MARGIN_TOO_SMALL,
                f"delta_AICc={result.delta_aicc:.2f} < {aicc_threshold}",
            )

    return True, QualityGateReason.PASSED, None
