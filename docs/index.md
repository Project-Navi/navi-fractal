---
hide:
  - navigation
  - toc
---

# navi-fractal

**Audit-grade fractal dimension estimation for graphs.**

Zero runtime dependencies. Refuses to emit a dimension without positive evidence.

[Get Started](getting-started/quickstart.md){ .md-button .md-button--primary }
[API Reference](reference/api.md){ .md-button }

---

## Measure in five lines

```python
from navi_fractal import make_grid_graph, estimate_sandbox_dimension

grid = make_grid_graph(30, 30)
result = estimate_sandbox_dimension(grid, seed=42)
print(f"D = {result.dimension:.3f}")  # D = 1.620
```

## The refusal is the feature

If your network doesn't have fractal structure, you don't get a number --- you get a machine-readable refusal with the exact reason why.

```
Complete graph K50    → Refused: trivial_graph
Barabási-Albert       → Refused: no_valid_radii
Erdős-Rényi random    → Refused: no_valid_radii
(1,2)-flower          → Refused: no_valid_radii
30×30 grid            → D = 1.620, R² = 0.9999
(2,2)-flower gen 8    → D = 1.810, R² = 0.9994
```

## Quality gates, not warnings

Every result passes through a chain of statistical gates before emission:

| Gate | What it checks |
|------|---------------|
| **\( R^2 \) threshold** | Power-law fit must actually fit |
| **AICc model selection** | Power-law must beat exponential decisively |
| **Curvature guard** | Reject windows where quadratic fits better |
| **Slope stability** | Reject windows with high local slope dispersion |

If any gate fails: `dimension=None`, `reason=<why>`. Every result --- accepted or refused --- is a frozen dataclass with the full audit trail.

## Formally verified foundations

The analytical dimension formula that navi-fractal calibrates against has been
formally proved in Lean 4 --- machine-checked from axioms, with zero unproved
obligations and zero custom axioms. The proof is maintained by a companion
project, [fd-formalization](https://github.com/Project-Navi/fd-formalization),
and is being [upstreamed into Mathlib](https://github.com/leanprover-community/mathlib4/pull/36443).

This is not "we believe the formula is correct." The Lean compiler verified it.

| What's proved | Status |
|--------------|--------|
| Flower dimension \( \lim_{g \to \infty} \frac{\log |V_g|}{\log L_g} = \frac{\log(u+v)}{\log u} \) | Verified |
| Hub distance \( \text{dist}(\text{hub}_0, \text{hub}_1) = u^g \) | Verified |
| Vertex count recurrence | Verified |
| Squeeze convergence bounds | Verified |
| `SimpleGraph.ball` (graph metric ball) | [PR #36443](https://github.com/leanprover-community/mathlib4/pull/36443) in Mathlib review |

[How the formal proofs connect to the code →](explanation/theory-bridge.md) · [Calibration table →](explanation/calibration-regime.md)

## Citing this project

```bibtex
@software{spence2026navifractal,
  author = {Spence, Nelson},
  title = {navi-fractal: Audit-grade fractal dimension estimation for graphs},
  year = {2026},
  url = {https://github.com/Project-Navi/navi-fractal}
}
```

## License

navi-fractal is released under the [Apache 2.0 License](https://github.com/Project-Navi/navi-fractal/blob/main/LICENSE).
