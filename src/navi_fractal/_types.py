# SPDX-License-Identifier: Apache-2.0
"""Shared types: enums, dataclasses, and regression results.

All public-facing type definitions live here to avoid circular imports
and keep the API surface explicit.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Literal

ModelPreference = Literal["powerlaw", "none"]


@enum.unique
class Reason(enum.Enum):
    """Reason code for sandbox dimension estimation outcome.

    ACCEPTED means a credible scaling window was found.
    All other values are refusal reasons (dimension will be None).
    """

    ACCEPTED = "accepted"
    EMPTY_GRAPH = "empty_graph"
    TRIVIAL_GRAPH = "trivial_graph"
    GIANT_COMPONENT_TOO_SMALL = "giant_component_too_small"
    NO_VALID_RADII = "no_valid_radii"
    NO_WINDOW_PASSES_R2 = "no_window_passes_r2"
    AICC_PREFERS_EXPONENTIAL = "aicc_prefers_exponential"
    CURVATURE_GUARD = "curvature_guard"
    SLOPE_STABILITY_GUARD = "slope_stability_guard"
    NEGATIVE_SLOPE = "negative_slope"


@enum.unique
class QualityGateReason(enum.Enum):
    """Reason code for quality gate outcome.

    Separate from Reason: "the instrument couldn't measure" vs
    "the measurement wasn't good enough for your policy."
    """

    PASSED = "passed"
    NOT_ACCEPTED = "not_accepted"
    R2_TOO_LOW = "r2_too_low"
    STDERR_TOO_HIGH = "stderr_too_high"
    LOG_SPAN_TOO_SMALL = "log_span_too_small"
    RADIUS_RATIO_TOO_SMALL = "radius_ratio_too_small"
    AICC_MARGIN_TOO_SMALL = "aicc_margin_too_small"


@dataclass(frozen=True)
class LinFit:
    """Result of a linear regression fit."""

    slope: float
    intercept: float
    r2: float
    slope_stderr: float
    sse: float
    n_points: int


@dataclass(frozen=True)
class DimensionSummary:
    """Lightweight summary of a sandbox dimension result.

    Stable public contract — will not grow. Use SandboxResult for full audit trail.
    """

    dimension: float | None
    accepted: bool
    reason: Reason
    r2: float | None
    ci: tuple[float, float] | None
