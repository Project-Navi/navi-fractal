# Theory Bridge: fd-formalization

navi-fractal measures fractal dimension empirically. A companion project,
[fd-formalization](https://github.com/ndspence/fd-formalization), proves the
analytical dimension formula in Lean 4. This page explains what each project
does, how they relate, and where they differ.

## What fd-formalization proves

For the (u,v)-flower network family (Rozenfeld, Havlin & ben-Avraham, NJP
9:175, 2007), the log-ratio of vertex count to hub distance converges:

```
lim   log |V_g| / log L_g  =  log(u + v) / log(u)    for 1 < u <= v
g->inf
```

This limit is the fractal dimension d_B of the flower family. The proof is
written in Lean 4 with Mathlib, compiled against Lean 4.28.0, and contains
zero `sorry` stubs (unproved obligations) and zero custom axioms. The Lean
compiler is the final arbiter -- the proof type-checks or it doesn't. There
is no gap between "we believe this is true" and "this is true": the statement
follows from the axioms of the type theory by mechanical verification.

The proof works by establishing:

1. **Vertex count recurrence**: the closed form (w-1)N_g = (w-2)w^g + w,
   where w = u + v.
2. **Hub distance**: the distance between hub0 and hub1 in the generation-g
   flower graph is exactly u^g.
3. **Squeeze bounds**: log(N_g) is squeezed between g*log(w) and
   g*log(w) + log(2), yielding a residual that decays as O(1/g) when
   divided by log(L_g) = g*log(u).
4. **Limit**: the squeeze theorem closes the deal.

## Symbol mapping

The following table maps Lean declarations in fd-formalization to their Python
counterparts in navi-fractal:

| Lean declaration | Python equivalent | Meaning |
|-----------------|------------------|---------|
| `flowerVertCount_eq` | Node count in `make_uv_flower` | (w-1)N_g = (w-2)w^g + w |
| `flowerHubDist_eq_pow` | BFS distance hub0 to hub1 | L_g = u^g |
| `flowerDimension` | `analytical_d` in calibration | lim log(N_g)/log(L_g) = log(w)/log(u) |
| `flowerGraph_dist_hubs` | Graph distance assertion | SimpleGraph.dist hub0 hub1 = u^g |

The Lean side works with `SimpleGraph` (Mathlib's type for simple undirected
graphs) and proves exact equalities about graph distance. The Python side
constructs the same graphs as adjacency lists and runs BFS to measure
distances empirically. On every test case, the BFS distances match the proved
formulas exactly.

## What they measure differently

The two projects are answering related but distinct questions about the same
family of graphs.

**fd-formalization** proves the *global* log-ratio: the ratio of log(total
vertex count) to log(hub-to-hub distance) converges to log(w)/log(u) as the
generation grows. This is a statement about two specific scalars -- the total
size of the graph and the diameter of its backbone. The proof is exact and
holds for every generation simultaneously (via the squeeze bounds).

**navi-fractal** measures *local* mass-radius scaling: the slope of log(ball
mass) vs log(radius), averaged over random centers, in the best scaling
window. This is a statistical estimate derived from many BFS measurements at
many radii, filtered through quality gates.

In the infinite-size limit, these two quantities converge -- both equal the
box-counting dimension d_B. This is a theorem in the fractal networks
literature (Song, Havlin & Makse, Nature 433:392, 2005), though not one that
fd-formalization has formalized (the proof requires metric space machinery
beyond what the current formalization covers).

On finite graphs, they differ. The sandbox systematically underestimates.
This is not a flaw in either method -- it is a consequence of measuring
different geometric quantities on a finite object. The global log-ratio
converges from above (the vertex count slightly exceeds what pure power-law
scaling would predict), while the local mass-radius slope is pulled down by
boundary effects (centers near the periphery see truncated balls).

## The convergence rate

The Lean squeeze bounds give a precise convergence rate for the global
log-ratio:

```
| log(N_g)/log(L_g) - d_B |  <=  log(2) / (g * log(u))
```

This means the global log-ratio converges to d_B at rate O(1/g), with a rate
constant of log(2)/log(u). Expressing this as a percentage of d_B:

```
rate_pct = 100 * log(2) / log(u + v)
```

The sandbox gap (the percentage difference between the sandbox estimate and
the analytical dimension) also decays roughly as 1/g, but with a rate
constant that is 2--4x larger than the theoretical bound. This amplification
is expected and is not a deficiency of either method:

- The proved bound applies to the global log-ratio, a single deterministic
  quantity.
- The sandbox gap includes contributions from window selection, center
  sampling, saturation filtering, and the geometric difference between "total
  count at a fixed distance" and "average ball mass across random centers."
- Each of these contributions adds variance and bias that the theoretical
  bound does not account for (and should not -- it describes a different
  quantity).

The convergence analysis script (`scripts/convergence_analysis.py`) fits
gap(g) = a/g + b per flower family, computes the amplification factor
|a_empirical| / a_theoretical, and flags non-monotonic convergence. It reads
the calibration report and produces a structured comparison.

## The role of calibration

The calibration table (see [Calibration Regime](calibration-regime.md)) is
where the two projects meet concretely. The analytical dimension d_B comes
from the formula that fd-formalization proves. The sandbox dimension D comes
from navi-fractal's measurement pipeline. The gap between them -- documented
openly, not hidden -- is the empirical cost of measuring a local quantity on
a finite graph.

The calibration is not a correction factor. navi-fractal does not adjust its
output to match the analytical dimension. The gap is reported as-is, and
users can decide how to interpret it for their own networks. The point is
transparency: here is what the instrument reports, here is what the true
answer is, and here is the discrepancy.

## References

- Rozenfeld, H. D., Havlin, S. & ben-Avraham, D. "Fractal and transfractal
  recursive scale-free nets." *New Journal of Physics* 9:175 (2007).
- Song, C., Havlin, S. & Makse, H. A. "Self-similarity of complex networks."
  *Nature* 433:392--395 (2005).
