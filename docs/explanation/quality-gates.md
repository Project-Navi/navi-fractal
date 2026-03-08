# Quality Gates

navi-fractal applies a chain of quality gates before reporting a fractal
dimension. A result is only produced when every gate passes. This page
explains each gate: what it checks, why it exists, and what kinds of graphs
trigger it.

The gates are applied in order during the exhaustive window search. A
candidate window must survive every gate to be considered. If no window
survives, the result is a refusal with the reason code of the highest-priority
gate that rejected the best candidate.

## \( R^2 \) threshold

**Parameter**: `r2_min` (default 0.85)

**What it checks**: The coefficient of determination (\( R^2 \)) for the
power-law fit within the candidate window. \( R^2 \) measures what fraction
of the variance in \( \log M \) is explained by the linear relationship with \( \log r \).

**Why it exists**: A low \( R^2 \) means the data points in the window don't
follow a straight line in log-log space. If \( \log M \) vs \( \log r \) isn't linear,
the "dimension" extracted from the slope is not meaningful -- you're fitting a
line to something that isn't a line. The 0.85 default is deliberately
permissive; most genuine fractal networks produce \( R^2 \) above 0.99 in
their best windows. The threshold exists to catch clear non-power-law
behavior, not to enforce perfection.

**Example triggers**: Random graphs (Erdős-Rényi, Barabási-Albert) typically
fail this gate because their ball-mass growth follows an exponential or
sigmoidal curve in log-log space, not a straight line.

**Reason code**: `NO_WINDOW_PASSES_R2`

## AICc model selection

**Parameter**: `delta_power_win` (default 1.5)

**What it checks**: The Akaike Information Criterion (corrected for small
samples) is computed for two competing models fit to the same window data:

- **Power-law** (linear in log-log):

\[
\log M = D \log r + c
\]

- **Exponential** (linear in \( r \)):

\[
\log M = a \cdot r + b
\]

The power-law model must have an AICc at least `delta_power_win` lower than
the exponential model. Lower AICc means better fit after penalizing for model
complexity (both models have the same number of parameters here, so the
comparison reduces to which functional form fits the data better).

**Why it exists**: Some networks show ball-mass growth that looks vaguely
power-law over a narrow window but is actually better described by exponential
growth. Reporting a "dimension" for such networks would be misleading.
The AICc comparison is a principled way to ask: "is power-law scaling actually
the right model, or does exponential fit just as well?"

**Example triggers**: Networks where ball-mass growth is exponential rather
than power-law. The (1,2)-flower is a transfractal network with u=1 where
mass growth saturates too rapidly to construct valid radii (it is refused
earlier with `no_valid_radii`). The AICc gate catches networks that do
produce enough radii for window construction but where exponential growth
fits better than power-law.

**Reason code**: `AICC_PREFERS_EXPONENTIAL`

## Curvature guard

**Parameters**: `curvature_guard` (default `True`), `delta_quadratic_win`
(default 3.0)

**What it checks**: Within the candidate window, fit a quadratic model in
log-log space:

\[
\log M = a (\log r)^2 + b \log r + c
\]

If the quadratic model's AICc is more than `delta_quadratic_win` lower than
the linear model's AICc, the window is rejected. The quadratic has one extra
parameter, so AICc already penalizes it for complexity -- if it still wins
convincingly, there is genuine curvature in the data.

**Why it exists**: True power-law scaling produces a straight line in log-log
space. Curvature (a bend) indicates that the scaling exponent is changing
across the window -- you're not in a single scaling regime. This happens
naturally at the boundaries of the fractal scaling range: at small radii the
discrete lattice structure dominates, and at large radii saturation effects
(running out of graph) flatten the curve. The curvature guard forces the
window search to find the regime where scaling is genuinely linear, rather
than averaging over a curved region and calling the average slope a
"dimension."

**Example triggers**: Large-generation flower networks at wide windows. At
gen 8 of the (2,2)-flower, the widest windows that pass \( R^2 \) still show
detectable curvature from boundary effects. The curvature guard correctly
rejects these, forcing the algorithm to select a narrower (but straighter)
window. This is one mechanism behind the gen 7 to 8 reversal in the
calibration table.

**Reason code**: `CURVATURE_GUARD`

## Slope stability guard

**Parameters**: `slope_stability_guard` (default `False`),
`slope_stability_sub_len` (default `None`, falls back to `min_points`),
`max_slope_range` (default 0.5)

**What it checks**: Divide the candidate window into overlapping sub-windows
of length `slope_stability_sub_len`, fit each sub-window independently, and
compute the range (max - min) of the resulting slopes. If this range exceeds
`max_slope_range`, the window is rejected.

**Why it exists**: A stable fractal dimension should look roughly the same
regardless of which part of the scaling window you examine. If the slope
changes dramatically from the left half to the right half of the window, the
"dimension" is not a stable property of the network -- it's an artifact of
which radii you happened to include. This gate catches networks with multiple
scaling regimes (different dimensions at different length scales) and windows
that straddle two regimes.

**Why it's off by default**: The curvature guard already catches the most
common case (smoothly varying slope), and the slope stability guard can be
overly aggressive on small networks where statistical noise in sub-windows
is large. It is available for users who want an extra layer of scrutiny.

**Example triggers**: Networks with hierarchical community structure sometimes
show one dimension within communities and a different dimension between
communities. The slope stability guard would reject windows that span both
regimes.

**Reason code**: `SLOPE_STABILITY_GUARD`

## Negative slope guard

**Parameter**: `require_positive_slope` (default `True`)

**What it checks**: After the best window is found and all other gates have
passed, this gate rejects windows where the best-fit slope is zero or
negative.

**Why it exists**: In a connected graph, ball mass is a monotonically
non-decreasing function of radius -- you can only reach more nodes by
looking farther. A negative slope in log-log space would mean mass
*decreases* with radius, which is geometrically impossible in a single
connected component. If the aggregated data shows a negative slope, something
has gone wrong with the aggregation (e.g., the geometric mean was pulled down
by centers with anomalously low mass at large radii), and the result should
not be trusted.

**Why it's a post-search gate**: Unlike the other gates, this one is applied
after the window search completes, to the single best window. This is because
negative slopes are rare enough that checking inside the inner loop would add
complexity without practical benefit.

**Reason code**: `NEGATIVE_SLOPE`

## Minimum delta-y guard

**Parameter**: `min_delta_y` (default 0.5)

**What it checks**: The vertical span of the candidate window in log-log
space: \( \max(\log M) - \min(\log M) \) across the radii in the window. If this
span is less than `min_delta_y`, the window is skipped.

**Why it exists**: When ball mass barely changes across a range of radii --
a nearly flat region in log-log space -- the slope estimate becomes
unreliable. A tiny vertical span means the signal-to-noise ratio is poor:
small perturbations in mass produce large changes in the fitted slope. The
`min_delta_y` threshold ensures that the window contains enough "dynamic
range" in mass growth for the slope to be meaningful.

The default of 0.5 corresponds to a mass ratio of about \( e^{0.5} \approx 1.65\times \) from
the smallest to largest radius in the window. This is conservative -- most
genuine scaling windows show mass changing by orders of magnitude.

**How it interacts with other gates**: The delta-y check is applied early in
the window search loop, before regression. This is an optimization: windows
with tiny vertical span are almost certain to fail \( R^2 \) or produce
unstable slopes, so rejecting them early saves computation.
