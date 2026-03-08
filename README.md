<p align="center">
  <img src="docs/assets/logo.png" alt="navi-fractal" width="120">
</p>

<h1 align="center">navi-fractal</h1>

<p align="center">
  <strong>Audit-grade fractal dimension estimation for graphs.</strong><br>
  Refuses to emit a dimension without positive evidence of power-law scaling.
</p>

<p align="center">
  <a href="https://github.com/Project-Navi/navi-fractal/actions"><img src="https://github.com/Project-Navi/navi-fractal/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/navi-fractal/"><img src="https://img.shields.io/badge/PyPI-coming%20soon-lightgrey" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/dependencies-0-brightgreen" alt="Zero deps">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache_2.0-orange" alt="License"></a>
  <a href="https://project-navi.github.io/navi-fractal"><img src="https://img.shields.io/badge/docs-zensical-7eb8a8" alt="Docs"></a>
</p>

---

```python
from navi_fractal import make_grid_graph, estimate_sandbox_dimension

grid = make_grid_graph(30, 30)
result = estimate_sandbox_dimension(grid, seed=42)
print(f"D = {result.dimension:.3f}")  # D = 1.620
```

If your network has fractal structure, navi-fractal finds it and shows you the evidence. If it doesn't, you get a refusal with the exact reason why.

```
Complete graph K50    → Refused: trivial_graph
Barabási-Albert       → Refused: no_valid_radii
Erdős-Rényi random    → Refused: no_valid_radii
(1,2)-flower          → Refused: no_valid_radii
30×30 grid            → D = 1.620, R² = 0.9999
(2,2)-flower gen 8    → D = 1.810, R² = 0.9994
```

**The refusal is the feature.**

## Install

```bash
pip install navi-fractal
```

Python 3.12+. Zero runtime dependencies.

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

Deterministic given the same seed and Python version.

**[Full documentation →](https://project-navi.github.io/navi-fractal)**

## Calibration

Sandbox dimension is validated against (u,v)-flower networks with exact analytical dimensions from [fd-formalization](https://github.com/Project-Navi/fd-formalization) (Lean 4, zero sorry, zero custom axioms).

| Family | Gen | Nodes | Analytical d_B | Sandbox D | Gap |
|--------|-----|-------|----------------|-----------|-----|
| (2,2)-flower | 4 | 172 | 2.000 | 1.380 | -31.0% |
| (2,2)-flower | 5 | 684 | 2.000 | 1.635 | -18.2% |
| (2,2)-flower | 6 | 2,732 | 2.000 | 1.690 | -15.5% |
| (2,2)-flower | 7 | 10,924 | 2.000 | 1.880 | -6.0% |
| (2,2)-flower | 8 | 43,692 | 2.000 | 1.810 | -9.5% |
| (3,3)-flower | 3 | 174 | 1.631 | 1.313 | -19.5% |
| (3,3)-flower | 4 | 1,038 | 1.631 | 1.418 | -13.1% |
| (3,3)-flower | 5 | 6,222 | 1.631 | 1.495 | -8.3% |
| (4,4)-flower | 3 | 440 | 1.500 | 1.294 | -13.7% |
| (4,4)-flower | 4 | 3,512 | 1.500 | 1.398 | -6.8% |
| (2,3)-flower | 4 | 470 | 2.322 | 1.670 | -28.1% |
| (2,3)-flower | 5 | 2,345 | 2.322 | 1.881 | -19.0% |
| (2,3)-flower | 6 | 11,720 | 2.322 | 1.992 | -14.2% |

The gap generally shrinks with network size. See [calibration regime](https://project-navi.github.io/navi-fractal/explanation/calibration-regime/) for convergence analysis and the gen 7-to-8 reversal.

## Design Philosophy

navi-fractal applies a chain of quality gates before emitting a dimension. A result is only produced when **all** of these pass:

- **R² threshold** — the power-law fit must actually fit
- **AICc model selection** — power-law must beat exponential decisively
- **Curvature guard** — reject windows where quadratic fits better in log-log
- **Slope stability** — reject windows with high local slope dispersion

If any gate fails, you get `dimension=None` and a machine-readable reason. Every result — accepted or refused — is a frozen dataclass with the full intermediate data. You can inspect exactly what happened and why.

We calibrate against networks with exact analytical dimensions rather than hiding the gap. Sandbox dimension measures mass-radius scaling, not box-counting dimension. On finite networks these converge in the infinite-size limit, but the sandbox algorithm systematically underestimates due to boundary and saturation effects. We document this rather than explaining it away.

## Citation

```bibtex
@software{spence2026navifractal,
  author = {Spence, Nelson},
  title = {navi-fractal: Audit-grade fractal dimension estimation for graphs},
  year = {2026},
  url = {https://github.com/Project-Navi/navi-fractal}
}
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
