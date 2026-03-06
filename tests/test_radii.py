# Copyright 2024-2026 Nelson Spence
# SPDX-License-Identifier: Apache-2.0
"""Tests for auto_radii alignment with v4."""

from __future__ import annotations

from navi_fractal._radii import auto_radii


class TestAutoRadii:
    def test_returns_sorted_unique(self) -> None:
        result = auto_radii(60)
        assert result == sorted(set(result))
        assert all(r >= 1 for r in result)

    def test_dense_prefix_is_6(self) -> None:
        """V4 uses dense_prefix=6, not 10."""
        result = auto_radii(60)
        assert result[:6] == [1, 2, 3, 4, 5, 6]

    def test_r_cap_limits_max(self) -> None:
        result = auto_radii(200, r_cap=32)
        assert max(result) <= 32

    def test_r_cap_default_32(self) -> None:
        result = auto_radii(200)
        assert max(result) <= 32

    def test_min_r_max_floor(self) -> None:
        result = auto_radii(20)
        assert max(result) >= min(12, 20)

    def test_never_exceeds_diameter(self) -> None:
        result = auto_radii(10)
        assert max(result) <= 10

    def test_small_diameter(self) -> None:
        result = auto_radii(1)
        assert result == [] or result == [1]

    def test_zero_diameter(self) -> None:
        assert auto_radii(0) == []

    def test_custom_dense_prefix(self) -> None:
        result = auto_radii(60, dense_prefix=3)
        assert result[:3] == [1, 2, 3]
