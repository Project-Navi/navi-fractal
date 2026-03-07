---
hide:
  - navigation
  - toc
---

<div class="hero-glow" markdown>

# navi-fractal

**Audit-grade fractal dimension estimation for graphs.**

Zero runtime dependencies. Refuses to emit a dimension without positive evidence.

[Get Started](getting-started/quickstart.md){ .md-button .md-button--primary }
[API Reference](reference/api.md){ .md-button }

</div>

---

## Measure in five lines

```python
from navi_fractal import make_grid_graph, estimate_sandbox_dimension

grid = make_grid_graph(30, 30)
result = estimate_sandbox_dimension(grid, seed=42)
print(f"D = {result.dimension:.3f}")  # D = 1.620
```

## The refusal is the feature

If your network doesn't have fractal structure, you don't get a number — you get a machine-readable refusal with the exact reason why.

```
Complete graph K50    → Refused: trivial_graph
Barabasi-Albert       → Refused: no_window_passes_r2
Erdos-Renyi random    → Refused: no_window_passes_r2
(1,2)-flower          → Refused: aicc_prefers_exponential
30×30 grid            → D = 1.620, R² = 0.9991
(2,2)-flower gen 8    → D = 1.812, R² = 0.9994
```

## Quality gates, not warnings

Every result passes through a chain of statistical gates before emission:

| Gate | What it checks |
|------|---------------|
| **R² threshold** | Power-law fit must actually fit |
| **AICc model selection** | Power-law must beat exponential decisively |
| **Curvature guard** | Reject windows where quadratic fits better |
| **Slope stability** | Reject windows with high local slope dispersion |

If any gate fails: `dimension=None`, `reason=<why>`. Every result — accepted or refused — is a frozen dataclass with the full audit trail.

## Calibrated against ground truth

Sandbox estimates are validated against (u,v)-flower networks with exact analytical dimensions, proved in Lean 4 by [fd-formalization](https://github.com/Project-Navi/fd-formalization).

[See the calibration table →](explanation/calibration-regime.md)
