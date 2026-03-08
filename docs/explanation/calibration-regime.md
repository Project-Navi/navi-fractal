# Calibration Regime

navi-fractal's sandbox method systematically underestimates fractal dimension
on finite graphs. Rather than hiding this, we calibrate against networks with
exact analytical dimensions and document the gap openly. This page explains
why calibration matters, what the numbers show, and what they mean.

## Why calibrate

Every measurement instrument has systematic error. A thermometer might read
half a degree low; a bathroom scale might add a pound. The responsible thing
is to characterize that error against known standards, not to pretend it
doesn't exist.

The sandbox method's systematic underestimation has a clear geometric origin:
on a finite graph, BFS balls near the boundary are truncated -- they run out
of graph before they run out of radius. This pulls the average ball mass down
at large radii, which flattens the log-log slope, which depresses the
estimated dimension. The effect is worse on small graphs (more boundary
relative to interior) and diminishes as graphs grow.

Calibrating against networks with known analytical dimensions lets us quantify
this effect precisely. We use (u,v)-flower networks because their fractal
dimension \( d_B = \frac{\log(u+v)}{\log u} \) is known exactly from the construction, and
this formula has been formally proved in Lean 4 (see
[Theory Bridge](theory-bridge.md)).

## The calibration table

| Family | Gen | Nodes | Analytical \( d_B \) | Sandbox \( D \) | Gap |
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

All measurements use default parameters: seed=42, 256 centers, geometric mean,
WLS, curvature guard on, slope stability guard off.

## Convergence behavior

The gap generally shrinks with network size. This is consistent with the
\( O(1/g) \) convergence rate established by the Lean squeeze bounds in
fd-formalization. As the generation increases, the graph grows exponentially
(each generation multiplies the edge count by \( u+v \)), and the boundary effects
that cause underestimation become proportionally smaller.

Fitting \( \text{gap}(g) = a/g + b \) per flower family gives:

- **Empirical rate constant**: the fitted \( |a| \) values are 2--4x the theoretical
  bound from the Lean squeeze \( \frac{100 \log 2}{\log(u+v)} \).
- **Amplification factor**: this ratio \( |a_{\text{empirical}}| / a_{\text{theoretical}} \) is
  consistently greater than 1 across all families. This is expected because
  the theoretical bound applies to the global log-ratio (total vertex count
  divided by hub distance), while the sandbox measures a different geometric
  quantity (average local ball-mass scaling) that converges more slowly.

The amplification is not a deficiency of the sandbox method. It is a
quantitative characterization of how much harder it is to estimate dimension
from local measurements than from global counts.

## The gen 7 to 8 reversal

The (2,2)-flower calibration shows a gap that goes from -6.0% at gen 7 to
-9.5% at gen 8. This non-monotonic behavior deserves explanation because it
looks like the measurement is getting worse even as the graph gets bigger.

This is a legitimate measurement characteristic, not a bug. Here is what
happens:

1. At gen 7 (10,924 nodes), the window search finds a wide scaling window
   where the log-log plot is approximately linear. The curvature guard
   passes, the \( R^2 \) is high, and the slope lands at 1.881.

2. At gen 8 (43,692 nodes), the graph is larger and the potential radius
   range is wider. But the wider range also reveals curvature that wasn't
   visible at gen 7 -- the scaling behavior bends at large radii due to
   saturation effects that scale differently from the hub structure. The
   curvature guard correctly rejects the widest windows. The scoring function
   then selects the widest surviving window, which happens to have a slightly
   lower slope (1.812).

3. The scoring function's lexicographic preference for wide windows is
   working as designed. At gen 8, the widest curvature-clean window is
   different from the one that would minimize the gap to the analytical
   dimension. The algorithm doesn't know the analytical dimension -- it
   is optimizing for measurement quality (wide window, high \( R^2 \), low
   stderr), not for proximity to a number it doesn't have access to.

This reversal illustrates why the sandbox measures *local ball-mass scaling*,
not the *global log-ratio* that fd-formalization proves. The two quantities
converge in the limit but can diverge at any finite generation.

## Convergence rate analysis

The `scripts/convergence_analysis.py` script performs a structured comparison
of empirical convergence against the theoretical bound:

- Reads the calibration report (`scripts/calibration-report.json`)
- Groups results by flower family
- Fits \( \text{gap}(g) = a/g + b \) via least squares for each family
- Computes the theoretical rate constant: \( \frac{100 \log 2}{\log(u+v)} \)
- Reports the amplification factor and flags non-monotonic convergence

The theoretical bound comes from the Lean squeeze in `FlowerLog.lean`:

\[
\log N_g - g \log w \le \log 2
\]

Dividing by \( g \log u \) and expressing as a percentage of \( d_B \) gives the rate
constant. The empirical rate constant from the sandbox is larger because the
sandbox gap includes contributions from window selection, center sampling,
saturation filtering, and the fundamental geometric difference between global
counts and local ball masses.

## Non-fractal refusals

The calibration regime also validates the refusal behavior. Networks that
should not have a finite fractal dimension are correctly refused:

- **Barabási-Albert** (preferential attachment): refused with
  `no_valid_radii`. Ball-mass growth saturates so quickly that too few
  non-degenerate radii survive filtering.
- **Erdős-Rényi** (random graphs): refused with `no_valid_radii`.
  The small-world property means ball mass saturates within a few hops,
  leaving insufficient radii for window construction.
- **Complete graphs**: refused with `trivial_graph`. Diameter is 1.
- **(1,2)-flower** (transfractal, \( u = 1 \)): refused with `no_valid_radii`.
  With \( u = 1 \), the hub distance is \( L_g = 1 \) for all generations -- the network
  grows but doesn't stretch. Ball-mass growth saturates too rapidly for any
  meaningful radius sequence.

These refusals are as important as the acceptances. A fractal dimension tool
that reports \( D = 2.3 \) for a Barabási-Albert network is worse than useless -- it
gives false confidence. The refusal is the feature.
