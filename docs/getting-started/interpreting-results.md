# Interpreting Results

Every call to `estimate_sandbox_dimension` returns a `SandboxResult` --- a frozen
dataclass containing the dimension estimate (or refusal), the full model
diagnostics, and enough raw data to reproduce the measurement independently.

This guide walks through every field group so you know exactly what you are
looking at.

## Dimension estimate

| Field | Type | Meaning |
|-------|------|---------|
| `dimension` | `float \| None` | Power-law slope from the best scaling window. `None` if the instrument refused to measure. |
| `reason` | `Reason` | Why the measurement was accepted or refused. `Reason.ACCEPTED` means a credible scaling window was found; all other values are refusal codes. |
| `reason_detail` | `str \| None` | Human-readable elaboration on the reason, when available. For example, `"diameter=1"` or `"got 3 radii, need 6"`. |

When `dimension` is `None`, every downstream field (fits, windows, CIs) may also
be `None`. Always check `reason` first.

## Model selection

| Field | Type | Meaning |
|-------|------|---------|
| `model_preference` | `str` | Either `"powerlaw"` (accepted) or `"none"` (refused). |
| `delta_aicc` | `float \| None` | AICc(exponential) minus AICc(power-law) for the best window. Positive values mean the power-law model is preferred. Larger is better. |
| `powerlaw_fit` | `LinFit \| None` | The power-law regression result for the best window. |
| `exponential_fit` | `LinFit \| None` | The competing exponential regression result for the same window. |

The AICc comparison is the heart of model selection. A `delta_aicc` of 5 or more
is conventionally considered strong evidence for the preferred model. Values between
1.5 and 5 indicate marginal preference --- the measurement is accepted, but treat
it with appropriate caution.

### LinFit fields

Both `powerlaw_fit` and `exponential_fit` are `LinFit` dataclasses with these fields:

| Field | Type | Meaning |
|-------|------|---------|
| `slope` | `float` | The regression slope. For `powerlaw_fit`, this is the dimension estimate. |
| `intercept` | `float` | The regression intercept in log-log (power-law) or log-linear (exponential) space. |
| `r2` | `float` | Coefficient of determination (\( R^2 \)). 1.0 is a perfect fit. |
| `slope_stderr` | `float` | Standard error of the slope estimate. Smaller means more precise. |
| `sse` | `float` | Sum of squared residuals. |
| `n_points` | `int` | Number of data points in the regression window. |

## Window metrics

These fields describe the scaling window that the estimator selected --- the
contiguous range of radii where the log-log relationship was evaluated.

| Field | Type | Meaning |
|-------|------|---------|
| `window_r_min` | `int \| None` | Smallest radius in the selected window. |
| `window_r_max` | `int \| None` | Largest radius in the selected window. |
| `window_log_span` | `float \| None` | \( \log r_{\max} - \log r_{\min} \). Measures how many decades the scaling window covers. Wider is generally more convincing. |
| `window_delta_y` | `float \| None` | Vertical span in log-log space: \( \max(\log M) - \min(\log M) \) across the window. A narrow delta_y means the mass barely changes, which makes slope estimation fragile. |
| `window_slope_range` | `float \| None` | Maximum minus minimum slope across sub-windows within the selected window. Only populated when the slope stability guard is enabled. Small values indicate consistent scaling. |
| `window_aicc_quad_minus_lin` | `float \| None` | AICc(quadratic) minus AICc(linear) for the selected window. Positive values mean the linear (power-law) model is preferred over a quadratic. Negative values would indicate curvature, but those windows are already rejected by the curvature guard. |

## Confidence intervals

| Field | Type | Meaning |
|-------|------|---------|
| `dimension_ci` | `tuple[float, float] \| None` | 95% bootstrap confidence interval for the dimension (2.5th and 97.5th percentiles). Only populated when `bootstrap_reps > 0` and enough valid replicates were produced. |
| `delta_aicc_ci` | `tuple[float, float] \| None` | 95% bootstrap confidence interval for `delta_aicc`. Useful for assessing whether model preference is stable under resampling. |
| `bootstrap_valid_reps` | `int` | Number of bootstrap replicates that produced valid fits. If this is much less than `bootstrap_reps`, the CI may not be trustworthy. |

The bootstrap resamples the set of BFS centers with replacement and re-fits the
regression for each replicate. This captures uncertainty from center selection
but not from the choice of scaling window, which is held fixed across replicates.

## Raw data

| Field | Type | Meaning |
|-------|------|---------|
| `radii_eval` | `tuple[int, ...]` | The radii that survived filtering (degenerate and saturated radii removed). |
| `mean_mass_eval` | `tuple[float, ...]` | Mean ball mass across centers at each evaluated radius. |
| `y_eval` | `tuple[float, ...]` | Log of mean mass at each evaluated radius. These are the y-values used in regression. |

These fields give you everything you need to reproduce the log-log plot and
verify the fit independently. The window indices (`window_r_min`, `window_r_max`)
tell you which subset of these arrays was used for the final regression.

## Audit trail

| Field | Type | Meaning |
|-------|------|---------|
| `n_nodes_original` | `int` | Total node count of the input graph. |
| `n_nodes_measured` | `int` | Node count after component extraction (giant component by default). |
| `retained_fraction` | `float` | `n_nodes_measured / n_nodes_original`. Shows how much of the graph was actually measured. |
| `n_centers` | `int` | Number of BFS centers sampled. |
| `seed` | `int` | Random seed used for center selection. Together with the graph, this makes the result fully reproducible. |
| `notes` | `str` | Free-form annotation string passed through from the caller. Useful for tagging results in batch runs. |

## Red flags

Not every accepted measurement is equally trustworthy. These signals should
prompt closer inspection before relying on a dimension estimate:

| Signal | What it means |
|--------|--------------|
| \( R^2 < 0.95 \) | Weak power-law fit --- the log-log relationship has substantial scatter. The dimension estimate may be unreliable. |
| \( \Delta\text{AICc} < 5 \) | Marginal model preference --- the exponential model fits nearly as well as the power law. Consider whether power-law scaling is genuinely present. |
| \( \log\text{-span} < 0.5 \) | Narrow scaling window --- the estimate is based on less than half a decade of radii. Small windows can produce good \( R^2 \) values by chance. |
| `retained_fraction < 0.5` | Most nodes were disconnected from the giant component. The measurement reflects the largest fragment, not the whole graph. |
| `bootstrap_valid_reps < 20` | Too few valid bootstrap replicates to produce a reliable confidence interval. The CI bounds may be misleading. |

These are not automatic rejection criteria --- the built-in gates and the post-hoc
quality gate handle that. They are diagnostic signals that help you decide how
much weight to place on a given measurement in your analysis.

## The summary shortcut

If you only need the headline numbers, `SandboxResult` offers a lightweight
projection:

```python
summary = result.summary()
print(summary.dimension)   # float | None
print(summary.accepted)    # bool
print(summary.reason)      # Reason
print(summary.r2)          # float | None
print(summary.ci)          # tuple[float, float] | None
```

`DimensionSummary` is a stable, five-field contract designed for downstream
consumers that do not need the full audit trail.
