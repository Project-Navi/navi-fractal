# Copyright 2024-2026 Nelson Spence
# SPDX-License-Identifier: Apache-2.0
"""Sandbox (mass-radius) fractal dimension estimation with quality gates.

Estimates D from <M(r)> ~ r^D. Refuses to emit a dimension unless positive
evidence of power-law scaling exists.
"""

from __future__ import annotations

import logging
import math
import random
from collections.abc import Sequence
from dataclasses import dataclass

from navi_fractal._bfs import ball_mass, bfs_layers, estimate_diameter
from navi_fractal._graph import CompiledGraph, Graph, compile_to_undirected_metric_graph
from navi_fractal._radii import auto_radii
from navi_fractal._regression import (
    aicc_for_ols,
    aicc_for_wls,
    ols,
    quadratic_fit_residual,
    quadratic_fit_residual_wls,
    slope_range_over_subwindows,
    wls,
)
from navi_fractal._types import DimensionSummary, LinFit, ModelPreference, Reason

logger = logging.getLogger("navi_fractal")


@dataclass(frozen=True)
class SandboxResult:
    """Result of sandbox dimension estimation.

    Two-tier access:
    - Quick: result.summary() -> DimensionSummary (5 fields, stable contract)
    - Full: access fields directly for audit trail and reproducibility
    """

    # Dimension estimate
    dimension: float | None
    reason: Reason
    reason_detail: str | None

    # Model selection
    model_preference: ModelPreference
    delta_aicc: float | None
    powerlaw_fit: LinFit | None
    exponential_fit: LinFit | None

    # Window metrics
    window_r_min: int | None
    window_r_max: int | None
    window_log_span: float | None
    window_delta_y: float | None
    window_slope_range: float | None
    window_aicc_quad_minus_lin: float | None

    # Confidence interval
    dimension_ci: tuple[float, float] | None

    # Bootstrap diagnostics
    delta_aicc_ci: tuple[float, float] | None
    bootstrap_valid_reps: int

    # Raw evaluation data
    radii_eval: tuple[int, ...]
    mean_mass_eval: tuple[float, ...]
    y_eval: tuple[float, ...]

    # Component audit
    n_nodes_original: int
    n_nodes_measured: int
    retained_fraction: float

    # Reproducibility
    n_centers: int
    seed: int
    notes: str

    def summary(self) -> DimensionSummary:
        """Return a lightweight summary for downstream consumers."""
        return DimensionSummary(
            dimension=self.dimension,
            accepted=self.dimension is not None,
            reason=self.reason,
            r2=self.powerlaw_fit.r2 if self.powerlaw_fit is not None else None,
            ci=self.dimension_ci,
        )


def _moments_from_center_masses(
    center_masses: Sequence[Sequence[int]],
) -> tuple[list[float], list[float], list[float], list[float]]:
    """Compute mean_M, var_M, mean_logM, var_logM across centers per radius."""
    n_centers = len(center_masses)
    if n_centers == 0:
        raise ValueError("no centers")

    n_radii = len(center_masses[0])
    sum_m = [0.0] * n_radii
    sum_m2 = [0.0] * n_radii
    sum_log = [0.0] * n_radii
    sum_log2 = [0.0] * n_radii

    for masses in center_masses:
        for i, m in enumerate(masses):
            mm = float(max(1, int(m)))
            lm = math.log(mm)
            sum_m[i] += mm
            sum_m2[i] += mm * mm
            sum_log[i] += lm
            sum_log2[i] += lm * lm

    mean_m = [s / n_centers for s in sum_m]
    mean_log = [s / n_centers for s in sum_log]

    if n_centers > 1:
        var_m = [
            max(0.0, (sum_m2[i] - n_centers * mean_m[i] ** 2) / (n_centers - 1))
            for i in range(n_radii)
        ]
        var_log = [
            max(0.0, (sum_log2[i] - n_centers * mean_log[i] ** 2) / (n_centers - 1))
            for i in range(n_radii)
        ]
    else:
        var_m = [0.0] * n_radii
        var_log = [0.0] * n_radii

    return mean_m, var_m, mean_log, var_log


def _y_and_weights(
    *,
    mean_mode: str,
    mean_mass: Sequence[float],
    var_mass: Sequence[float],
    mean_log_mass: Sequence[float],
    var_log_mass: Sequence[float],
    n_centers: int,
    use_wls: bool,
    var_floor: float,
) -> tuple[list[float], list[float] | None]:
    """Return y_eval and optional WLS weights for each radius."""
    y: list[float] = []
    w: list[float] | None = [] if use_wls else None

    for i in range(len(mean_mass)):
        if mean_mode == "geometric":
            yi = float(mean_log_mass[i])
            y.append(yi)
            if use_wls:
                vy = float(var_log_mass[i]) / max(1, n_centers)
                vy = max(vy, var_floor)
                w.append(1.0 / vy)  # type: ignore[union-attr]
        else:
            mi = float(mean_mass[i])
            yi = float(math.log(mi))
            y.append(yi)
            if use_wls:
                vy = (float(var_mass[i]) / max(1, n_centers)) / max(mi * mi, 1e-30)
                vy = max(vy, var_floor)
                w.append(1.0 / vy)  # type: ignore[union-attr]

    return y, w


def _percentile(sorted_vals: list[float], q: float) -> float:
    """Percentile with linear interpolation between adjacent ranks."""
    if not sorted_vals:
        return float("nan")
    if q <= 0:
        return float(sorted_vals[0])
    if q >= 1:
        return float(sorted_vals[-1])
    n = len(sorted_vals)
    pos = (n - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(sorted_vals[lo])
    t = pos - lo
    return float((1 - t) * sorted_vals[lo] + t * sorted_vals[hi])


def estimate_sandbox_dimension(
    g: Graph | CompiledGraph,
    *,
    seed: int = 0,
    rng: random.Random | None = None,
    n_centers: int = 256,
    radii: Sequence[int] | None = None,
    r_cap: int = 32,
    component_policy: str = "giant",
    mean_mode: str = "geometric",
    min_points: int = 6,
    min_radius_ratio: float = 3.0,
    r2_min: float = 0.85,
    min_delta_y: float = 0.5,
    max_saturation_frac: float = 0.95,
    delta_power_win: float = 1.5,
    require_positive_slope: bool = True,
    use_wls: bool = True,
    curvature_guard: bool = True,
    delta_quadratic_win: float = 3.0,
    slope_stability_guard: bool = False,
    slope_stability_sub_len: int | None = None,
    max_slope_range: float = 0.5,
    bootstrap_reps: int = 0,
    bootstrap_seed: int | None = None,
    var_floor: float = 1e-6,
    notes: str = "",
) -> SandboxResult:
    """Estimate sandbox fractal dimension with full quality gate chain.

    Returns a SandboxResult with either a dimension estimate or a refusal reason.
    """
    _seed = seed

    # Compile if needed
    cg: CompiledGraph
    if isinstance(g, Graph):
        cg = compile_to_undirected_metric_graph(g)
    else:
        cg = g

    # Validate component_policy
    if component_policy not in ("giant", "all"):
        raise ValueError(f"component_policy must be 'giant' or 'all', got {component_policy!r}")

    # Convert min_radius_ratio to log-space span threshold
    min_log_span = math.log(min_radius_ratio)

    empty_result = _make_empty_result

    # Trivial checks
    if cg.n == 0:
        return empty_result(
            Reason.EMPTY_GRAPH,
            n_centers=n_centers,
            n_nodes_original=0,
            n_nodes_measured=0,
            seed=_seed,
            notes=notes,
        )
    if cg.n == 1:
        return empty_result(
            Reason.TRIVIAL_GRAPH,
            n_centers=n_centers,
            n_nodes_original=1,
            n_nodes_measured=1,
            seed=_seed,
            notes=notes,
        )

    # Track original node count before component extraction
    n_nodes_original = cg.n

    # Component selection
    if component_policy == "giant":
        cg = _extract_giant_component(cg)
        if cg.n <= 1:
            return empty_result(
                Reason.GIANT_COMPONENT_TOO_SMALL,
                n_centers=n_centers,
                n_nodes_original=n_nodes_original,
                n_nodes_measured=cg.n,
                seed=_seed,
                detail=f"giant={cg.n}, total={n_nodes_original}",
                notes=notes,
            )

    n_nodes_measured = cg.n
    retained_fraction = n_nodes_measured / n_nodes_original if n_nodes_original > 0 else 0.0

    # Diameter
    diam = estimate_diameter(cg)
    if diam <= 1:
        return empty_result(
            Reason.TRIVIAL_GRAPH,
            n_centers=n_centers,
            n_nodes_original=n_nodes_original,
            n_nodes_measured=n_nodes_measured,
            seed=_seed,
            detail=f"diameter={diam}",
            notes=notes,
        )

    # Radii
    if radii is not None:
        radii_list = sorted({int(r) for r in radii if int(r) >= 1})
    else:
        radii_list = auto_radii(diam, r_cap=r_cap)
    if len(radii_list) < min_points:
        return empty_result(
            Reason.NO_VALID_RADII,
            n_centers=n_centers,
            n_nodes_original=n_nodes_original,
            n_nodes_measured=n_nodes_measured,
            seed=_seed,
            detail=f"got {len(radii_list)} radii, need {min_points}",
            notes=notes,
        )

    # Center selection (v4 style — with replacement)
    if rng is None:
        rng = random.Random(seed)
    n_actual = max(1, n_centers)
    centers = [rng.randrange(cg.n) for _ in range(n_actual)]

    # BFS mass collection
    center_masses: list[list[int]] = []
    for center in centers:
        distances = bfs_layers(cg, center)
        masses = [ball_mass(distances, r) for r in radii_list]
        center_masses.append(masses)

    # Moment aggregation using helpers
    mean_m, var_m, mean_log_m, var_log_m = _moments_from_center_masses(center_masses)
    y_all, w_all = _y_and_weights(
        mean_mode=mean_mode,
        mean_mass=mean_m,
        var_mass=var_m,
        mean_log_mass=mean_log_m,
        var_log_mass=var_log_m,
        n_centers=n_actual,
        use_wls=use_wls,
        var_floor=var_floor,
    )

    # Mean-based filtering (v4 style)
    sat_thresh = max_saturation_frac * float(cg.n)
    radii_eval: list[int] = []
    log_radii: list[float] = []
    mean_mass_eval: list[float] = []
    y_eval: list[float] = []
    mass_variances: list[float] = []
    original_indices: list[int] = []

    for i, r in enumerate(radii_list):
        mean_mass_eff = math.exp(mean_log_m[i]) if mean_mode == "geometric" else mean_m[i]
        if mean_mass_eff <= 1.0:
            continue
        if mean_mass_eff >= sat_thresh:
            continue
        radii_eval.append(r)
        log_radii.append(math.log(r))
        mean_mass_eval.append(mean_m[i])
        y_eval.append(y_all[i])
        original_indices.append(i)
        if w_all is not None:
            mass_variances.append(1.0 / w_all[i])
        else:
            mass_variances.append(var_floor)

    if len(log_radii) < min_points:
        return SandboxResult(
            dimension=None,
            reason=Reason.NO_VALID_RADII,
            reason_detail=f"got {len(log_radii)} non-degenerate radii, need {min_points}",
            model_preference="none",
            delta_aicc=None,
            powerlaw_fit=None,
            exponential_fit=None,
            window_r_min=None,
            window_r_max=None,
            window_log_span=None,
            window_delta_y=None,
            window_slope_range=None,
            window_aicc_quad_minus_lin=None,
            dimension_ci=None,
            delta_aicc_ci=None,
            bootstrap_valid_reps=0,
            radii_eval=tuple(radii_eval),
            mean_mass_eval=tuple(mean_mass_eval),
            y_eval=tuple(y_eval),
            n_nodes_original=n_nodes_original,
            n_nodes_measured=n_nodes_measured,
            retained_fraction=retained_fraction,
            n_centers=n_actual,
            seed=_seed,
            notes=notes,
        )

    # Window search: exhaustive over contiguous windows
    best_fit: LinFit | None = None
    best_score: tuple[float, float, float] = (-1.0, -1.0, float("inf"))
    best_window: tuple[int, int] | None = None
    best_exp_fit: LinFit | None = None
    best_delta_aicc: float | None = None
    best_slope_range: float | None = None
    best_aicc_quad_minus_lin: float | None = None
    best_reason: Reason = Reason.NO_WINDOW_PASSES_R2
    _reject_depth: int = -1

    aicc_fn = aicc_for_wls if use_wls else aicc_for_ols

    n_pts = len(log_radii)
    for start in range(n_pts):
        for end in range(start + min_points, n_pts + 1):
            wx = log_radii[start:end]
            wy = y_eval[start:end]
            ww = mass_variances[start:end]

            # Minimum log span
            log_span = wx[-1] - wx[0]
            if log_span < min_log_span:
                continue

            # Minimum response range in log-mass
            delta_y = max(wy) - min(wy)
            if delta_y < min_delta_y:
                continue

            # Fit
            if use_wls:
                inv_var = [1.0 / v for v in ww]
                fit = wls(wx, wy, inv_var)
            else:
                fit = ols(wx, wy)

            # R** gate
            if fit.r2 < r2_min:
                continue

            # AICc discrimination: power-law vs exponential
            n_w = len(wx)
            aicc_pw = aicc_fn(fit.sse, n_w, 2)

            # Exponential fit: log(M) = a * r + b (note: r, not log(r))
            exp_x = [math.exp(lx) for lx in wx]
            if use_wls:
                exp_fit_result = wls(exp_x, wy, inv_var)
            else:
                exp_fit_result = ols(exp_x, wy)
            aicc_exp = aicc_fn(exp_fit_result.sse, n_w, 2)

            delta = aicc_exp - aicc_pw
            if delta < delta_power_win:
                if _reject_depth < 1:
                    best_reason = Reason.AICC_PREFERS_EXPONENTIAL
                    _reject_depth = 1
                continue

            _current_aicc_quad_minus_lin: float | None = None
            if curvature_guard:
                if use_wls:
                    quad_sse = quadratic_fit_residual_wls(wx, wy, inv_var)
                    aicc_quad = aicc_for_wls(quad_sse, n_w, 3)
                else:
                    quad_sse = quadratic_fit_residual(wx, wy)
                    aicc_quad = aicc_for_ols(quad_sse, n_w, 3)
                _current_aicc_quad_minus_lin = aicc_quad - aicc_pw
                if aicc_quad + delta_quadratic_win < aicc_pw:
                    if _reject_depth < 2:
                        best_reason = Reason.CURVATURE_GUARD
                        _reject_depth = 2
                    continue

            # Slope stability guard: sub-window slope range
            _current_slope_range: float | None = None
            if slope_stability_guard:
                sub_len = (
                    slope_stability_sub_len if slope_stability_sub_len is not None else min_points
                )
                if n_w >= sub_len >= 2:
                    w_arg = inv_var if use_wls else None
                    _current_slope_range = slope_range_over_subwindows(
                        wx,
                        wy,
                        sub_len=sub_len,
                        use_wls=use_wls,
                        w=w_arg,
                    )
                    if _current_slope_range > max_slope_range:
                        if _reject_depth < 3:
                            best_reason = Reason.SLOPE_STABILITY_GUARD
                            _reject_depth = 3
                        continue

            # Score: prefer widest, then best R**, then lowest stderr
            score = (log_span, fit.r2, -fit.slope_stderr)
            if score > best_score:
                best_score = score
                best_fit = fit
                best_window = (start, end)
                best_exp_fit = exp_fit_result
                best_delta_aicc = delta
                best_slope_range = _current_slope_range
                best_aicc_quad_minus_lin = _current_aicc_quad_minus_lin
                best_reason = Reason.ACCEPTED
                _reject_depth = 4

    if best_fit is None or best_window is None:
        return SandboxResult(
            dimension=None,
            reason=best_reason,
            reason_detail=None,
            model_preference="none",
            delta_aicc=None,
            powerlaw_fit=None,
            exponential_fit=None,
            window_r_min=None,
            window_r_max=None,
            window_log_span=None,
            window_delta_y=None,
            window_slope_range=None,
            window_aicc_quad_minus_lin=None,
            dimension_ci=None,
            delta_aicc_ci=None,
            bootstrap_valid_reps=0,
            radii_eval=tuple(radii_eval),
            mean_mass_eval=tuple(mean_mass_eval),
            y_eval=tuple(y_eval),
            n_nodes_original=n_nodes_original,
            n_nodes_measured=n_nodes_measured,
            retained_fraction=retained_fraction,
            n_centers=n_actual,
            seed=_seed,
            notes=notes,
        )

    # Compute window metrics
    w_start, w_end = best_window
    window_r_min_val = radii_eval[w_start]
    window_r_max_val = radii_eval[w_end - 1]
    window_log_span_val = math.log(window_r_max_val) - math.log(window_r_min_val)
    window_delta_y_val = max(y_eval[w_start:w_end]) - min(y_eval[w_start:w_end])

    # Positive slope guard
    if require_positive_slope and best_fit.slope <= 0:
        return SandboxResult(
            dimension=None,
            reason=Reason.NEGATIVE_SLOPE,
            reason_detail=f"slope={best_fit.slope:.4f} <= 0",
            model_preference="none",
            delta_aicc=best_delta_aicc,
            powerlaw_fit=best_fit,
            exponential_fit=best_exp_fit,
            window_r_min=window_r_min_val,
            window_r_max=window_r_max_val,
            window_log_span=window_log_span_val,
            window_delta_y=window_delta_y_val,
            window_slope_range=best_slope_range,
            window_aicc_quad_minus_lin=best_aicc_quad_minus_lin,
            dimension_ci=None,
            delta_aicc_ci=None,
            bootstrap_valid_reps=0,
            radii_eval=tuple(radii_eval),
            mean_mass_eval=tuple(mean_mass_eval),
            y_eval=tuple(y_eval),
            n_nodes_original=n_nodes_original,
            n_nodes_measured=n_nodes_measured,
            retained_fraction=retained_fraction,
            n_centers=n_actual,
            seed=_seed,
            notes=notes,
        )

    # Bootstrap confidence intervals
    dimension_ci: tuple[float, float] | None = None
    delta_aicc_ci: tuple[float, float] | None = None
    boot_ok = 0

    if bootstrap_reps > 0:
        boot_rng = random.Random(bootstrap_seed if bootstrap_seed is not None else _seed)
        boot_dims: list[float] = []
        boot_deltas: list[float] = []

        # Map filtered window indices to original radii_list indices
        oi_start = original_indices[w_start]
        oi_end = original_indices[w_end - 1] + 1

        for _ in range(bootstrap_reps):
            # Resample center indices with replacement
            idxs = [boot_rng.randrange(len(centers)) for _ in range(len(centers))]
            boot_masses = [center_masses[k] for k in idxs]

            # Recompute moments from resampled centers
            b_mean_m, b_var_m, b_mean_log_m, b_var_log_m = _moments_from_center_masses(boot_masses)
            b_y, b_w = _y_and_weights(
                mean_mode=mean_mode,
                mean_mass=b_mean_m,
                var_mass=b_var_m,
                mean_log_mass=b_mean_log_m,
                var_log_mass=b_var_log_m,
                n_centers=len(centers),
                use_wls=use_wls,
                var_floor=var_floor,
            )

            # Slice to winning window using original indices (direct, no round-trip)
            xw = log_radii[w_start:w_end]
            yw = b_y[oi_start:oi_end]

            if len(xw) < 2 or len(yw) != len(xw):
                continue

            try:
                if use_wls and b_w is not None:
                    ww_boot = b_w[oi_start:oi_end]
                    b_fit_pow = wls(xw, yw, ww_boot)
                    b_aicc_pow = aicc_for_wls(b_fit_pow.sse, len(xw), 2)
                    exp_xw = [math.exp(lx) for lx in xw]
                    b_fit_exp = wls(exp_xw, yw, ww_boot)
                    b_aicc_exp = aicc_for_wls(b_fit_exp.sse, len(exp_xw), 2)
                else:
                    b_fit_pow = ols(xw, yw)
                    b_aicc_pow = aicc_for_ols(b_fit_pow.sse, len(xw), 2)
                    exp_xw = [math.exp(lx) for lx in xw]
                    b_fit_exp = ols(exp_xw, yw)
                    b_aicc_exp = aicc_for_ols(b_fit_exp.sse, len(exp_xw), 2)

                boot_dims.append(float(b_fit_pow.slope))
                boot_deltas.append(float(b_aicc_exp - b_aicc_pow))
                boot_ok += 1
            except Exception:  # noqa: S112  # nosec B112
                continue

        if boot_ok >= max(10, int(0.2 * bootstrap_reps)):
            dims_sorted = sorted(boot_dims)
            deltas_sorted = sorted(boot_deltas)
            dimension_ci = (
                _percentile(dims_sorted, 0.025),
                _percentile(dims_sorted, 0.975),
            )
            delta_aicc_ci = (
                _percentile(deltas_sorted, 0.025),
                _percentile(deltas_sorted, 0.975),
            )

    dimension = best_fit.slope
    logger.info(
        "Sandbox dimension D=%.4f (R2=%.4f, %d centers, window [%d:%d])",
        dimension,
        best_fit.r2,
        n_actual,
        best_window[0],
        best_window[1],
    )

    return SandboxResult(
        dimension=dimension,
        reason=Reason.ACCEPTED,
        reason_detail=None,
        model_preference="powerlaw",
        delta_aicc=best_delta_aicc,
        powerlaw_fit=best_fit,
        exponential_fit=best_exp_fit,
        window_r_min=window_r_min_val,
        window_r_max=window_r_max_val,
        window_log_span=window_log_span_val,
        window_delta_y=window_delta_y_val,
        window_slope_range=best_slope_range,
        window_aicc_quad_minus_lin=best_aicc_quad_minus_lin,
        dimension_ci=dimension_ci,
        delta_aicc_ci=delta_aicc_ci,
        bootstrap_valid_reps=boot_ok,
        radii_eval=tuple(radii_eval),
        mean_mass_eval=tuple(mean_mass_eval),
        y_eval=tuple(y_eval),
        n_nodes_original=n_nodes_original,
        n_nodes_measured=n_nodes_measured,
        retained_fraction=retained_fraction,
        n_centers=n_actual,
        seed=_seed,
        notes=notes,
    )


def _make_empty_result(
    reason: Reason,
    *,
    n_centers: int,
    n_nodes_original: int,
    n_nodes_measured: int,
    seed: int,
    detail: str | None = None,
    notes: str = "",
) -> SandboxResult:
    """Create a refused SandboxResult with empty diagnostics."""
    retained = n_nodes_measured / n_nodes_original if n_nodes_original > 0 else 0.0
    return SandboxResult(
        dimension=None,
        reason=reason,
        reason_detail=detail,
        model_preference="none",
        delta_aicc=None,
        powerlaw_fit=None,
        exponential_fit=None,
        window_r_min=None,
        window_r_max=None,
        window_log_span=None,
        window_delta_y=None,
        window_slope_range=None,
        window_aicc_quad_minus_lin=None,
        dimension_ci=None,
        delta_aicc_ci=None,
        bootstrap_valid_reps=0,
        radii_eval=(),
        mean_mass_eval=(),
        y_eval=(),
        n_nodes_original=n_nodes_original,
        n_nodes_measured=n_nodes_measured,
        retained_fraction=retained,
        n_centers=n_centers,
        seed=seed,
        notes=notes,
    )


def _extract_giant_component(cg: CompiledGraph) -> CompiledGraph:
    """Extract the largest connected component as a new CompiledGraph."""
    visited = [False] * cg.n
    components: list[list[int]] = []

    for start in range(cg.n):
        if visited[start]:
            continue
        component: list[int] = []
        stack = [start]
        while stack:
            node = stack.pop()
            if visited[node]:
                continue
            visited[node] = True
            component.append(node)
            for nb in cg.adj[node]:
                if not visited[nb]:
                    stack.append(nb)
        components.append(component)

    if not components:
        return cg

    giant = max(components, key=len)
    if len(giant) == cg.n:
        return cg  # Already connected

    # Rebuild with new IDs
    old_to_new = {old: new for new, old in enumerate(sorted(giant))}
    new_adj: list[tuple[int, ...]] = []
    new_labels: list[object] = []
    for old in sorted(giant):
        new_labels.append(cg.id_to_label[old])
        neighbors = tuple(sorted(old_to_new[nb] for nb in cg.adj[old] if nb in old_to_new))
        new_adj.append(neighbors)

    new_label_to_id = {label: i for i, label in enumerate(new_labels)}

    return CompiledGraph(
        n=len(giant),
        adj=tuple(new_adj),
        label_to_id=new_label_to_id,
        id_to_label=tuple(new_labels),
    )
