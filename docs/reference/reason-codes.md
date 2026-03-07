# Reason Codes

Every `SandboxResult` includes a `reason` field from the `Reason` enum explaining why the result was accepted or refused.

## Accepted

| Code | Value | Meaning |
|------|-------|---------|
| `ACCEPTED` | `"accepted"` | All quality gates passed. Dimension estimate is available. |

## Refusal Codes

| Code | Value | Meaning |
|------|-------|---------|
| `EMPTY_GRAPH` | `"empty_graph"` | Input graph has no nodes. |
| `TRIVIAL_GRAPH` | `"trivial_graph"` | Graph has diameter ≤ 1 (complete graph, single edge, etc.). |
| `GIANT_COMPONENT_TOO_SMALL` | `"giant_component_too_small"` | Giant component is trivially small (0 or 1 nodes after extraction). Check `reason_detail` for `giant=N, total=M`. |
| `NO_VALID_RADII` | `"no_valid_radii"` | Too few distinct radii with non-trivial mass growth. |
| `NO_WINDOW_PASSES_R2` | `"no_window_passes_r2"` | No contiguous radius window achieves the minimum R² threshold. The graph likely has no power-law scaling regime. |
| `AICC_PREFERS_EXPONENTIAL` | `"aicc_prefers_exponential"` | Best window's AICc prefers exponential over power-law by the required margin. Suggests small-world rather than fractal structure. |
| `CURVATURE_GUARD` | `"curvature_guard"` | Best window has significant curvature in log-log space (quadratic fits better than linear). |
| `SLOPE_STABILITY_GUARD` | `"slope_stability_guard"` | Local slope varies too much across sub-windows. Scaling is not stable. |
| `NEGATIVE_SLOPE` | `"negative_slope"` | Best-fit slope is negative (mass decreases with radius). Only applies when `require_positive_slope=True`. |

## Quality Gate Reasons

The post-hoc `sandbox_quality_gate()` function returns a `QualityGateReason`:

| Code | Value | Meaning |
|------|-------|---------|
| `PASSED` | `"passed"` | Result meets all quality thresholds. |
| `NOT_ACCEPTED` | `"not_accepted"` | The underlying result was refused (dimension is None). |
| `R2_TOO_LOW` | `"r2_too_low"` | R² below gate threshold. |
| `STDERR_TOO_HIGH` | `"stderr_too_high"` | Slope standard error too high. |
| `LOG_SPAN_TOO_SMALL` | `"log_span_too_small"` | Scaling window too narrow in log space. |
| `RADIUS_RATIO_TOO_SMALL` | `"radius_ratio_too_small"` | r_max/r_min ratio too small. |
| `AICC_MARGIN_TOO_SMALL` | `"aicc_margin_too_small"` | AICc margin below gate threshold. |
