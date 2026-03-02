# navi-fractal

**Audit-grade fractal dimension estimation for graphs.** Zero dependencies. Refuses to emit without evidence.

```python
from navi_fractal import make_grid_graph, estimate_sandbox_dimension

grid = make_grid_graph(30, 30)
result = estimate_sandbox_dimension(grid, seed=42)

if result.dimension is not None:
    print(f"D = {result.dimension:.3f}, R² = {result.powerlaw_fit.r2:.4f}")
else:
    print(f"Refused: {result.reason}")
```

Most fractal dimension tools will always give you a number. This one won't. If the evidence doesn't support a dimension estimate, navi-fractal tells you *refused* and shows you exactly why.

## Features

- **Sandbox (mass-radius) dimension** with full quality gate chain
- **Refuses without evidence** — no R², no AICc preference, no dimension
- **Deterministic** — seeded RNG, compiled graph with sorted adjacency, reproducible results
- **Zero runtime dependencies** — Python 3.12+ stdlib only
- **Full audit trail** — every result is a frozen dataclass with all intermediate data
- **Null model** — degree-preserving rewiring to validate genuine structure
- **Bootstrap confidence intervals** — resample centers for uncertainty quantification

## Installation

```bash
pip install navi-fractal
```

## How It Works

| Step | What happens |
|------|-------------|
| 1. Compile | Input graph compiled to deterministic undirected metric graph |
| 2. Component | Optionally restrict to giant connected component |
| 3. Diameter | Two-sweep BFS heuristic |
| 4. Radii | Dense prefix + log-spaced tail, capped at 30% of diameter |
| 5. BFS mass | Seeded random centers, ball sizes M(r) at each radius |
| 6. Aggregate | Geometric or arithmetic mean across centers |
| 7. Window search | Exhaustive search with R², AICc, curvature, slope stability gates |
| 8. Bootstrap | Resample centers for confidence intervals |
| 9. Result | Full diagnostic dataclass or refusal with reason |

## Quality Gates

A dimension is only emitted when **all** gates pass:

- **R² threshold** — minimum coefficient of determination (default 0.85)
- **AICc discrimination** — power-law must beat exponential by margin (default 1.5)
- **Curvature guard** — reject windows where quadratic log-log fits significantly better
- **Slope stability** — reject windows with high local slope dispersion

## Known Geometries

| Graph | Expected D | Behavior |
|-------|-----------|----------|
| Grid (m x n) | ~2.0 | Emits D in [1.55, 1.75] |
| Path | ~1.0 | Emits D in [0.8, 1.2] |
| Complete | N/A | **Refused** — no scaling regime |

## Measurement Characteristics

Sandbox dimension estimates are measurements of mass-radius scaling, not box-counting dimension. On finite networks the two converge in the infinite-size limit, but the sandbox algorithm systematically underestimates due to boundary and saturation effects.

**Calibration against (u,v)-flower networks** (Rozenfeld et al. 2007, NJP 9:175) with exact analytical box-counting dimension d_B = ln(u+v)/ln(u):

| Network | Nodes | Analytical d_B | Sandbox D | Gap |
|---------|-------|----------------|-----------|-----|
| (2,2)-flower gen 8 | 43,692 | 2.000 | 1.812 | -9.4% |
| (3,3)-flower gen 5 | 6,222 | 1.631 | 1.495 | -8.3% |
| (4,4)-flower gen 4 | 3,512 | 1.500 | 1.398 | -6.8% |
| (2,3)-flower gen 6 | 11,720 | 2.322 | 1.991 | -14.3% |

The bias follows a predictable pattern: symmetric flowers with larger path lengths show smaller gaps because the diameter grows faster relative to node count, giving more scaling regime before saturation. Asymmetric flowers show larger gaps because heterogeneous local structure reduces the effectiveness of center-averaging. This is consistent with published results — Song et al. (2015, Sci. Rep. 5:17628) report similar underestimation for Sierpinski weighted fractal networks.

Non-fractal networks (Barabasi-Albert, Erdos-Renyi, complete graphs) are correctly refused by the quality gates. The (1,2)-flower — a transfractal network with infinite analytical d_B — is also correctly rejected.

See `tests/v4_smoke/` for the full calibration test suite with literature references.

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Citation

If you use this software in research, please cite:

```bibtex
@software{spence2026navifractal,
  author = {Spence, Nelson},
  title = {navi-fractal: Audit-grade fractal dimension estimation for graphs},
  year = {2026},
  url = {https://github.com/Project-Navi/navi-fractal}
}
```
