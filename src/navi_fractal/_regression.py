# SPDX-License-Identifier: Apache-2.0
"""Regression utilities: OLS, WLS, AICc, quadratic fit.

All implemented from scratch — stdlib only.
"""

from __future__ import annotations

import math

from navi_fractal._types import LinFit


def ols(x: list[float], y: list[float]) -> LinFit:
    """Ordinary least squares linear regression.

    Fits y = slope * x + intercept.
    """
    n = len(x)
    if n < 2:
        raise ValueError(f"OLS requires at least 2 points, got {n}")
    if n != len(y):
        raise ValueError(f"x and y must have same length, got {len(x)} and {len(y)}")

    sum_x = math.fsum(x)
    sum_y = math.fsum(y)
    sum_xx = math.fsum(xi * xi for xi in x)
    sum_xy = math.fsum(xi * yi for xi, yi in zip(x, y, strict=True))

    mean_x = sum_x / n
    mean_y = sum_y / n

    ss_xx = sum_xx - n * mean_x * mean_x
    ss_xy = sum_xy - n * mean_x * mean_y

    if ss_xx == 0.0:
        return LinFit(
            slope=0.0,
            intercept=mean_y,
            r2=0.0,
            slope_stderr=float("inf"),
            sse=0.0,
            n_points=n,
        )

    slope = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x

    # Residuals
    residuals = [yi - (slope * xi + intercept) for xi, yi in zip(x, y, strict=True)]
    sse = math.fsum(r * r for r in residuals)

    # R²
    ss_yy = math.fsum((yi - mean_y) ** 2 for yi in y)
    r2 = 1.0 - sse / ss_yy if ss_yy > 0.0 else 0.0

    # Slope standard error
    if n > 2 and ss_xx > 0.0:
        mse = sse / (n - 2)
        slope_stderr = math.sqrt(mse / ss_xx)
    else:
        slope_stderr = float("inf")

    return LinFit(
        slope=slope,
        intercept=intercept,
        r2=r2,
        slope_stderr=slope_stderr,
        sse=sse,
        n_points=n,
    )


def wls(x: list[float], y: list[float], weights: list[float]) -> LinFit:
    """Weighted least squares linear regression.

    Fits y = slope * x + intercept with the given weights.
    """
    n = len(x)
    if n < 2:
        raise ValueError(f"WLS requires at least 2 points, got {n}")
    if n != len(y) or n != len(weights):
        raise ValueError("x, y, and weights must have same length")

    sum_w = math.fsum(weights)
    if sum_w == 0.0:
        raise ValueError("Sum of weights is zero")

    sum_wx = math.fsum(w * xi for w, xi in zip(weights, x, strict=True))
    sum_wy = math.fsum(w * yi for w, yi in zip(weights, y, strict=True))
    sum_wxx = math.fsum(w * xi * xi for w, xi in zip(weights, x, strict=True))
    sum_wxy = math.fsum(w * xi * yi for w, xi, yi in zip(weights, x, y, strict=True))

    mean_x = sum_wx / sum_w
    mean_y = sum_wy / sum_w

    ss_xx = sum_wxx - sum_w * mean_x * mean_x
    ss_xy = sum_wxy - sum_w * mean_x * mean_y

    if ss_xx == 0.0:
        return LinFit(
            slope=0.0,
            intercept=mean_y,
            r2=0.0,
            slope_stderr=float("inf"),
            sse=0.0,
            n_points=n,
        )

    slope = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x

    # Weighted residuals
    sse = math.fsum(
        w * (yi - slope * xi - intercept) ** 2 for w, xi, yi in zip(weights, x, y, strict=True)
    )

    # Weighted R²
    ss_yy = math.fsum(w * (yi - mean_y) ** 2 for w, yi in zip(weights, y, strict=True))
    r2 = 1.0 - sse / ss_yy if ss_yy > 0.0 else 0.0

    # Slope standard error
    if n > 2 and ss_xx > 0.0:
        wmse = sse / (sum_w * (n - 2) / n)
        slope_stderr = math.sqrt(wmse / ss_xx) if wmse / ss_xx >= 0.0 else float("inf")
    else:
        slope_stderr = float("inf")

    return LinFit(
        slope=slope,
        intercept=intercept,
        r2=r2,
        slope_stderr=slope_stderr,
        sse=sse,
        n_points=n,
    )


def aicc(sse: float, n: int, k: int) -> float:
    """Corrected Akaike information criterion for small samples.

    k = number of estimated parameters (2 for linear, 3 for quadratic).
    """
    if n <= k + 1:
        return float("inf")
    if sse <= 0.0:
        return float("-inf")
    aic = n * math.log(sse / n) + 2 * k
    correction = 2 * k * (k + 1) / (n - k - 1)
    return aic + correction


def quadratic_fit_residual(x: list[float], y: list[float]) -> float:
    """Fit y = a*x^2 + b*x + c and return SSE.

    Uses 3x3 Gaussian elimination. Returns inf if system is singular.
    """
    n = len(x)
    if n < 3:
        return float("inf")

    # Build normal equations for [a, b, c]
    s = [0.0] * 5  # s[k] = sum(x^k) for k=0..4
    sy = [0.0] * 3  # sy[k] = sum(x^k * y) for k=0..2
    s[0] = float(n)
    for xi, yi in zip(x, y, strict=True):
        x1 = xi
        x2 = xi * xi
        x3 = x2 * xi
        x4 = x3 * xi
        s[1] += x1
        s[2] += x2
        s[3] += x3
        s[4] += x4
        sy[0] += yi
        sy[1] += x1 * yi
        sy[2] += x2 * yi

    # 3x3 augmented matrix
    mat = [
        [s[4], s[3], s[2], sy[2]],
        [s[3], s[2], s[1], sy[1]],
        [s[2], s[1], s[0], sy[0]],
    ]

    # Gaussian elimination with partial pivoting
    for col in range(3):
        max_row = col
        max_val = abs(mat[col][col])
        for row in range(col + 1, 3):
            if abs(mat[row][col]) > max_val:
                max_val = abs(mat[row][col])
                max_row = row
        if max_val < 1e-15:
            return float("inf")
        mat[col], mat[max_row] = mat[max_row], mat[col]

        for row in range(col + 1, 3):
            factor = mat[row][col] / mat[col][col]
            for j in range(col, 4):
                mat[row][j] -= factor * mat[col][j]

    # Back substitution
    coeffs = [0.0, 0.0, 0.0]
    for i in range(2, -1, -1):
        val = mat[i][3]
        for j in range(i + 1, 3):
            val -= mat[i][j] * coeffs[j]
        if abs(mat[i][i]) < 1e-15:
            return float("inf")
        coeffs[i] = val / mat[i][i]

    a, b, c = coeffs
    sse = math.fsum((yi - (a * xi * xi + b * xi + c)) ** 2 for xi, yi in zip(x, y, strict=True))
    return sse
