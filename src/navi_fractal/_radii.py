# SPDX-License-Identifier: Apache-2.0
"""Automatic radius selection for sandbox dimension estimation."""

from __future__ import annotations

import math


def auto_radii(diameter: int, *, max_fraction: float = 0.3) -> list[int]:
    """Select radii for sandbox dimension estimation.

    Strategy: dense prefix (1, 2, 3, ...) up to min(10, cap), then
    log-spaced radii up to cap = floor(max_fraction * diameter).

    Returns sorted unique integer radii >= 1.
    """
    if diameter <= 0:
        return []

    cap = max(1, math.floor(max_fraction * diameter))

    # Dense prefix
    dense_end = min(10, cap)
    radii: set[int] = set(range(1, dense_end + 1))

    # Log-spaced tail
    if cap > dense_end:
        n_log = max(10, int(math.log2(cap)) + 1)
        for i in range(n_log + 1):
            r = math.floor(dense_end * math.exp(i * math.log(cap / dense_end) / n_log))
            r = max(dense_end + 1, min(r, cap))
            radii.add(r)
        radii.add(cap)

    return sorted(radii)
