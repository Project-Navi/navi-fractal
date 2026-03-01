# SPDX-License-Identifier: Apache-2.0
"""Sandbox (mass-radius) fractal dimension estimation with quality gates.

Estimates D from <M(r)> ~ r^D. Refuses to emit a dimension unless positive
evidence of power-law scaling exists.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass

from navi_fractal._bfs import ball_mass, bfs_layers, estimate_diameter
from navi_fractal._graph import CompiledGraph, Graph, compile_to_undirected_metric_graph
from navi_fractal._radii import auto_radii
from navi_fractal._regression import aicc, ols, quadratic_fit_residual, wls
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
    notes: str | None

    def summary(self) -> DimensionSummary:
        """Return a lightweight summary for downstream consumers."""
        return DimensionSummary(
            dimension=self.dimension,
            accepted=self.dimension is not None,
            reason=self.reason,
            r2=self.powerlaw_fit.r2 if self.powerlaw_fit is not None else None,
            ci=self.dimension_ci,
        )


def estimate_sandbox_dimension(
    g: Graph | CompiledGraph,
    *,
    seed: int = 0,
    rng: random.Random | None = None,
    n_centers: int = 256,
    component_policy: str = "giant",
    mean_mode: str = "geometric",
    min_points: int = 6,
    min_radius_ratio: float = 3.0,
    r2_min: float = 0.85,
    min_delta_y: float = 0.5,
    max_saturation_frac: float = 0.2,
    delta_power_win: float = 1.5,
    require_positive_slope: bool = True,
    use_wls: bool = True,
    curvature_guard: bool = True,
    slope_stability_guard: bool = False,
    slope_stability_sub_len: int | None = None,
    max_slope_range: float = 0.5,
    bootstrap_reps: int = 0,
    variance_floor: float = 1e-12,
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
        )
    if cg.n == 1:
        return empty_result(
            Reason.TRIVIAL_GRAPH,
            n_centers=n_centers,
            n_nodes_original=1,
            n_nodes_measured=1,
            seed=_seed,
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
        )

    # Radii
    radii = auto_radii(diam)
    if len(radii) < min_points:
        return empty_result(
            Reason.NO_VALID_RADII,
            n_centers=n_centers,
            n_nodes_original=n_nodes_original,
            n_nodes_measured=n_nodes_measured,
            seed=_seed,
            detail=f"got {len(radii)} radii, need {min_points}",
        )

    # BFS mass collection
    if rng is None:
        rng = random.Random(seed)
    actual_n_centers = min(n_centers, cg.n)
    centers = rng.sample(range(cg.n), actual_n_centers)

    # Collect mass at each radius for each center
    mass_matrix: list[list[int]] = []
    for center in centers:
        distances = bfs_layers(cg, center)
        masses = [ball_mass(distances, r) for r in radii]
        mass_matrix.append(masses)

    saturation_threshold = int(max_saturation_frac * cg.n)

    # Aggregate across centers
    radii_eval: list[int] = []
    log_radii: list[float] = []  # kept as local variable for regression
    mean_mass_eval: list[float] = []
    y_eval: list[float] = []
    mass_variances: list[float] = []

    for j, r in enumerate(radii):
        col = [mass_matrix[i][j] for i in range(actual_n_centers)]

        # Filter degenerate (all <= 1) and saturated radii
        if all(m <= 1 for m in col):
            continue
        if all(m >= saturation_threshold for m in col) and saturation_threshold > 1:
            continue

        if mean_mode == "geometric":
            log_vals = [math.log(m) for m in col if m > 0]
            if not log_vals:
                continue
            mean_log = math.fsum(log_vals) / len(log_vals)
            var_log = (
                math.fsum((lv - mean_log) ** 2 for lv in log_vals) / len(log_vals)
                if len(log_vals) > 1
                else 0.0
            )
            radii_eval.append(r)
            log_radii.append(math.log(r))
            mean_mass_eval.append(math.exp(mean_log))
            y_eval.append(mean_log)
            mass_variances.append(max(var_log, variance_floor))
        else:  # arithmetic
            mean_m = math.fsum(col) / len(col)
            if mean_m <= 0:
                continue
            var_m = math.fsum((m - mean_m) ** 2 for m in col) / len(col) if len(col) > 1 else 0.0
            radii_eval.append(r)
            log_radii.append(math.log(r))
            mean_mass_eval.append(mean_m)
            y_eval.append(math.log(mean_m))
            # Delta method: Var(log(X)) ~ Var(X) / X**2
            mass_variances.append(max(var_m / (mean_m * mean_m), variance_floor))

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
            radii_eval=tuple(radii_eval),
            mean_mass_eval=tuple(mean_mass_eval),
            y_eval=tuple(y_eval),
            n_nodes_original=n_nodes_original,
            n_nodes_measured=n_nodes_measured,
            retained_fraction=retained_fraction,
            n_centers=actual_n_centers,
            seed=_seed,
            notes=None,
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
            delta_y = wy[-1] - wy[0]
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
            # Use OLS for both models to keep SSE on the same scale
            n_w = len(wx)
            ols_fit = ols(wx, wy)
            aicc_pw = aicc(ols_fit.sse, n_w, 2)

            # Exponential fit: log(M) = a * r + b (note: r, not log(r))
            exp_x = [math.exp(lx) for lx in wx]
            exp_fit_result = ols(exp_x, wy)
            aicc_exp = aicc(exp_fit_result.sse, n_w, 2)

            delta = aicc_exp - aicc_pw
            if delta < delta_power_win:
                if _reject_depth < 1:
                    best_reason = Reason.AICC_PREFERS_EXPONENTIAL
                    _reject_depth = 1
                continue

            # Curvature guard (uses same OLS-based AICc for consistency)
            _current_aicc_quad_minus_lin: float | None = None
            if curvature_guard:
                quad_sse = quadratic_fit_residual(wx, wy)
                aicc_quad = aicc(quad_sse, n_w, 3)
                _current_aicc_quad_minus_lin = aicc_quad - aicc_pw
                if aicc_quad < aicc_pw - 6.0:
                    if _reject_depth < 2:
                        best_reason = Reason.CURVATURE_GUARD
                        _reject_depth = 2
                    continue

            # Slope stability guard: sub-window OLS range
            _current_slope_range: float | None = None
            if slope_stability_guard:
                sub_len = (
                    slope_stability_sub_len if slope_stability_sub_len is not None else min_points
                )
                if n_w >= sub_len >= 2:
                    local_slopes: list[float] = []
                    for sub_start in range(n_w - sub_len + 1):
                        sub_x = wx[sub_start : sub_start + sub_len]
                        sub_y = wy[sub_start : sub_start + sub_len]
                        sub_fit = ols(sub_x, sub_y)
                        local_slopes.append(sub_fit.slope)
                    if len(local_slopes) >= 2:
                        _current_slope_range = max(local_slopes) - min(local_slopes)
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
            radii_eval=tuple(radii_eval),
            mean_mass_eval=tuple(mean_mass_eval),
            y_eval=tuple(y_eval),
            n_nodes_original=n_nodes_original,
            n_nodes_measured=n_nodes_measured,
            retained_fraction=retained_fraction,
            n_centers=actual_n_centers,
            seed=_seed,
            notes=None,
        )

    # Compute window metrics
    w_start, w_end = best_window
    window_r_min_val = radii_eval[w_start]
    window_r_max_val = radii_eval[w_end - 1]
    window_log_span_val = math.log(window_r_max_val) - math.log(window_r_min_val)
    window_delta_y_val = y_eval[w_end - 1] - y_eval[w_start]

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
            radii_eval=tuple(radii_eval),
            mean_mass_eval=tuple(mean_mass_eval),
            y_eval=tuple(y_eval),
            n_nodes_original=n_nodes_original,
            n_nodes_measured=n_nodes_measured,
            retained_fraction=retained_fraction,
            n_centers=actual_n_centers,
            seed=_seed,
            notes=None,
        )

    # Bootstrap confidence intervals
    dimension_ci: tuple[float, float] | None = None
    if bootstrap_reps > 0:
        boot_slopes: list[float] = []
        for _ in range(bootstrap_reps):
            # Resample centers
            boot_centers = rng.choices(range(actual_n_centers), k=actual_n_centers)
            boot_log_masses: list[float] = []
            for j_idx in range(w_start, w_end):
                j = _radius_index_for_log(log_radii[j_idx], radii)
                col = [mass_matrix[c][j] for c in boot_centers]
                if mean_mode == "geometric":
                    log_vals = [math.log(m) for m in col if m > 0]
                    boot_log_masses.append(math.fsum(log_vals) / len(log_vals) if log_vals else 0.0)
                else:
                    mean_m = math.fsum(col) / len(col)
                    boot_log_masses.append(math.log(mean_m) if mean_m > 0 else 0.0)

            boot_x = log_radii[w_start:w_end]
            boot_ww = mass_variances[w_start:w_end]
            if len(boot_x) >= 2:
                if use_wls:
                    boot_inv_var = [1.0 / v for v in boot_ww]
                    boot_fit = wls(boot_x, boot_log_masses, boot_inv_var)
                else:
                    boot_fit = ols(boot_x, boot_log_masses)
                boot_slopes.append(boot_fit.slope)

        if boot_slopes:
            boot_slopes.sort()
            lo = boot_slopes[max(0, int(0.025 * len(boot_slopes)))]
            hi = boot_slopes[min(len(boot_slopes) - 1, int(0.975 * len(boot_slopes)))]
            dimension_ci = (lo, hi)

    dimension = best_fit.slope
    logger.info(
        "Sandbox dimension D=%.4f (R2=%.4f, %d centers, window [%d:%d])",
        dimension,
        best_fit.r2,
        actual_n_centers,
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
        radii_eval=tuple(radii_eval),
        mean_mass_eval=tuple(mean_mass_eval),
        y_eval=tuple(y_eval),
        n_nodes_original=n_nodes_original,
        n_nodes_measured=n_nodes_measured,
        retained_fraction=retained_fraction,
        n_centers=actual_n_centers,
        seed=_seed,
        notes=None,
    )


def _make_empty_result(
    reason: Reason,
    *,
    n_centers: int,
    n_nodes_original: int,
    n_nodes_measured: int,
    seed: int,
    detail: str | None = None,
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
        radii_eval=(),
        mean_mass_eval=(),
        y_eval=(),
        n_nodes_original=n_nodes_original,
        n_nodes_measured=n_nodes_measured,
        retained_fraction=retained,
        n_centers=n_centers,
        seed=seed,
        notes=None,
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


def _radius_index_for_log(log_r: float, radii: list[int]) -> int:
    """Find the index in radii whose log matches log_r."""
    target_r = math.exp(log_r)
    best_idx = 0
    best_dist = float("inf")
    for i, r in enumerate(radii):
        dist = abs(r - target_r)
        if dist < best_dist:
            best_dist = dist
            best_idx = i
    return best_idx
