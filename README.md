# navi-fractal

Most fractal dimension tools will always give you a number. This one won't.

```python
from navi_fractal import Graph, estimate_sandbox_dimension

G = Graph()
# ... build your network ...

result = estimate_sandbox_dimension(G, seed=42)

if result.dimension is not None:
    print(f"D = {result.dimension:.3f}, R² = {result.powerlaw_fit.r2:.4f}")
else:
    print(f"Refused: {result.reason.value}")
    # "no_window_passes_r2", "aicc_prefers_exponential", ...
```

If your network has fractal structure, navi-fractal finds it and shows you the evidence — dimension estimate, R², model selection, confidence intervals, the full audit trail. If it doesn't, you get a refusal with the exact reason why. Not a meaningless number. Not a warning you can ignore. A refusal.

```
Complete graph K50    → Refused: trivial_graph
Barabasi-Albert       → Refused: no_window_passes_r2
Erdos-Renyi random    → Refused: no_window_passes_r2
(1,2)-flower          → Refused: aicc_prefers_exponential
30×30 grid            → D = 1.620, R² = 0.9991
(2,2)-flower gen 8    → D = 1.812, R² = 0.9994
```

The refusal is the feature.

## Install

```bash
pip install navi-fractal
```

Python 3.12+. Zero runtime dependencies.

## Why This Exists

Every fractal dimension tool we could find will happily estimate D on a random graph, a complete graph, or pure noise. You get a number, maybe an R², and no indication that the result is meaningless. If you're a researcher relying on that number, you're building on sand.

navi-fractal applies a chain of quality gates before emitting a dimension. A result is only produced when **all** of these pass:

- **R² threshold** — the power-law fit must actually fit (default 0.85)
- **AICc model selection** — power-law must beat exponential by a margin, not just edge it out
- **Curvature guard** — reject windows where a quadratic fits significantly better in log-log
- **Slope stability** — reject windows with high local slope dispersion

If any gate fails, you get `dimension=None` and a machine-readable reason. Every result — accepted or refused — is a frozen dataclass with the full intermediate data: radii, masses, fits, window bounds, AICc scores. You can inspect exactly what happened and why.

## How It Works

The sandbox (mass-radius) method: pick random center nodes, run BFS to measure ball mass M(r) at increasing radii, fit log M(r) ~ D log r over the best scaling window.

| Step | What happens |
|------|-------------|
| Compile | Input graph → deterministic undirected metric graph |
| Component | Optionally restrict to giant connected component |
| Diameter | Two-sweep BFS heuristic |
| Radii | Dense prefix + log-spaced tail, capped at 30% of diameter |
| BFS mass | Seeded random centers, ball sizes M(r) at each radius |
| Aggregate | Geometric or arithmetic mean across centers |
| Window search | Exhaustive search with R², AICc, curvature, slope stability gates |
| Bootstrap | Resample centers for confidence intervals |
| Result | Full diagnostic dataclass or refusal with reason |

Deterministic given the same seed and Python version. Seeded RNG, compiled graph with sorted adjacency, reproducible results.

## Measurement Characteristics

Sandbox dimension measures mass-radius scaling, not box-counting dimension. On finite networks these converge in the infinite-size limit, but the sandbox algorithm systematically underestimates on finite graphs due to boundary and saturation effects. We calibrate against networks with exact analytical dimensions rather than hiding the gap.

**Finite-size convergence** on (u,v)-flower networks (Rozenfeld et al. 2007, NJP 9:175), where d_B = ln(u+v)/ln(u) is known exactly:

| Family | Gen | Nodes | Analytical d_B | Sandbox D | Gap |
|--------|-----|-------|----------------|-----------|-----|
| (2,2)-flower | 4 | 172 | 2.000 | 1.379 | -31.1% |
| (2,2)-flower | 5 | 684 | 2.000 | 1.633 | -18.4% |
| (2,2)-flower | 6 | 2,732 | 2.000 | 1.686 | -15.7% |
| (2,2)-flower | 7 | 10,924 | 2.000 | 1.881 | -6.0% |
| (2,2)-flower | 8 | 43,692 | 2.000 | 1.812 | -9.4% |
| (3,3)-flower | 3 | 174 | 1.631 | 1.314 | -19.5% |
| (3,3)-flower | 4 | 1,038 | 1.631 | 1.418 | -13.1% |
| (3,3)-flower | 5 | 6,222 | 1.631 | 1.495 | -8.3% |
| (4,4)-flower | 3 | 440 | 1.500 | 1.295 | -13.7% |
| (4,4)-flower | 4 | 3,512 | 1.500 | 1.398 | -6.8% |
| (2,3)-flower | 4 | 470 | 2.322 | 1.669 | -28.1% |
| (2,3)-flower | 5 | 2,345 | 2.322 | 1.882 | -19.0% |
| (2,3)-flower | 6 | 11,720 | 2.322 | 1.991 | -14.2% |

The gap generally shrinks with network size. The (2,2)-flower gen 7→8 reversal (-6.0% → -9.4%) is not a bug — the window search selects different optimal windows at different scales, and this objective can diverge from convergence toward the analytical dimension when hub structure and saturation effects scale at different rates. We document this as a measurement characteristic rather than explaining it away.

Non-fractal networks (Barabasi-Albert, Erdos-Renyi, complete graphs) are correctly refused. The (1,2)-flower — a transfractal network with infinite analytical d_B — is also rejected.

See `scripts/calibrate.py` for the full calibration instrument and `scripts/calibration-report.json` for the structured baseline.

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
