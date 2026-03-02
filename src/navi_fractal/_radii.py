# SPDX-License-Identifier: Apache-2.0
"""Automatic radius selection for sandbox dimension estimation."""

from __future__ import annotations

import math


def auto_radii(
    diam_est: int,
    *,
    r_cap: int = 32,
    dense_prefix: int = 6,
    log_points: int = 10,
    diam_frac: float = 0.3,
    min_r_max: int = 12,
) -> list[int]:
    """Select radii for sandbox dimension estimation.

    Strategy: dense prefix (1..dense_prefix), then log-spaced up to
    min(r_cap, diam_frac * diam_est), with min_r_max as floor.
    """
    if diam_est <= 1:
        return []
    r_max = int(max(min_r_max, diam_frac * diam_est))
    r_max = min(r_cap, max(1, r_max))
    r_max = min(r_max, max(1, diam_est))  # never exceed diameter
    if r_max < 2:
        return [1]

    radii: set[int] = set(range(1, min(dense_prefix, r_max) + 1))
    if r_max > dense_prefix:
        lo = max(dense_prefix + 1, 2)
        hi = r_max
        log_lo = math.log(lo)
        log_hi = math.log(hi)
        for i in range(log_points):
            t = i / max(1, (log_points - 1))
            r = round(math.exp(log_lo + t * (log_hi - log_lo)))
            r = max(1, min(r_max, r))
            radii.add(r)

    return sorted(radii)
