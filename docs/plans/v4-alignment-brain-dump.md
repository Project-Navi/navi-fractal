# v4 Alignment Brain Dump — Context Preservation

## Status
- Brainstorming skill active, checklist tasks 49-53
- Task 49 (explore): DONE
- Task 50 (clarify): DONE — v4 is ground truth, sandbox only, keep enums
- Task 51 (approaches): DONE — Approach 1 chosen (threshold-first)
- Task 52 (present design): IN PROGRESS — presented Section 1, awaiting approval
- Task 53 (write doc + invoke writing-plans): PENDING

## User Decisions
1. **v4 is ground truth** — adopt its defaults, algorithms, factoring. Our enums are additive improvements on top.
2. **Sandbox alignment only** — no multifractal, no Creative Determinant (stay v0.2.0)
3. **Keep Reason/QualityGateReason enums** — better than v4's free-form strings
4. **Approach 1: threshold-first** — fix defaults that cause D=1.61, validate, then align rest

## Design Sections to Present (Section 1 already shown, awaiting approval)

### Section 1: Threshold & Algorithm Fixes (D=1.61 root cause)
- `max_saturation_frac`: 0.2 → 0.95 (v4 default)
- `variance_floor` → `var_floor`: 1e-12 → 1e-6 (v4 default + rename)
- Curvature guard: hardcoded -6.0 → parameterized `delta_quadratic_win=3.0`
- Center selection: `rng.sample` (no replacement) → `rng.randrange` loop (with replacement, v4 style)
- **Expected outcome**: Grid 30x30 D should move from 1.61 toward 2.0

### Section 2: auto_radii Alignment
- Add parameters: `r_cap=32`, `dense_prefix=6`, `log_points=10`, `diam_frac=0.3`, `min_r_max=12`
- Match v4 signature exactly
- Current scaffold: dense_end=10, no r_cap. V4: dense_prefix=6, r_cap=32, min_r_max=12
- Pass `r_cap` through from `estimate_sandbox_dimension`

### Section 3: Bootstrap Improvements
- Add `_percentile()` function with linear interpolation (from v4 lines 1282-1299)
- Add minimum validity threshold: `boot_ok >= max(10, int(0.2 * bootstrap_reps))`
- Add `delta_aicc_ci` field to SandboxResult (bootstrap CI on AICc margin)
- Add `bootstrap_valid_reps` field to SandboxResult
- Replace `_radius_index_for_log` round-trip with direct index slicing (v4 style: `b_y[wi:wj+1]`)
- Factor bootstrap moment aggregation through `_moments_from_center_masses` / `_y_and_weights`
- Add `bootstrap_seed` parameter (separate from main seed)

### Section 4: Regression Module Alignment
- Add `aicc_for_wls()` — separate WLS AICc using chi2 directly (v4 lines 967-976)
- Keep single `aicc()` for OLS, add `aicc_wls()` for WLS
- Add `quadratic_fit_residual_wls()` — WLS quadratic SSE for curvature guard
- Add standalone `slope_range_over_subwindows()` function (v4 lines 1158-1181)
- LinFit: consider adding `weighted` field? Or keep as-is since we track fit type elsewhere

### Section 5: Quality Gate Alignment
- Add `min_log_span` check (v4 has it, scaffold doesn't)
- Adjust `stderr_max` inclusive default: 0.50 → 0.25 (match v4)
- Keep scaffold's `radius_ratio_min` check (additive, v4 doesn't have it)
- Keep scaffold's `aicc_min` check
- Result: gate checks R², stderr, log_span, radius_ratio, AICc (superset of v4)

### Section 6: Missing Parameters
- Add `radii` parameter (user-provided radii, Optional[Sequence[int]])
- Add `bootstrap_seed` parameter
- Add `r_cap` parameter (passed to auto_radii)
- Add `delta_quadratic_win` parameter (curvature guard threshold)
- Add `notes` parameter (str = "", not str | None)

### Section 7: Moment Aggregation Factoring
- Extract `_moments_from_center_masses()` as standalone function
- Extract `_y_and_weights()` as standalone function
- Both reused in bootstrap loop (DRY, matches v4 factoring)
- Move to `_sandbox.py` as private helpers

### Section 8: SandboxResult Field Additions
- Add: `delta_aicc_ci: tuple[float, float] | None`
- Add: `bootstrap_valid_reps: int` (default 0)
- Total fields: 23 → 25
- Update `_make_empty_result`, all construction sites, tests

### Section 9: Test Updates
- Tighten grid 30x30 bounds from [1.5, 2.3] to [1.8, 2.2] after threshold fix
- Add tests for new parameters (delta_quadratic_win, r_cap, user radii, bootstrap_seed)
- Update test_quality_gates for log_span check
- Update determinism tests for new fields

## Key Deltas from Explorer Agent (full reference)

### max_saturation_frac
- Scaffold: 0.2 (rejects at 20% of N)
- V4: 0.95 (rejects at 95% of N)
- Impact: Scaffold aggressively cuts large-radius data, shortening scaling window

### var_floor / variance_floor
- Scaffold: 1e-12
- V4: 1e-6
- Impact: Scaffold gives near-infinite WLS weight to low-variance points

### Curvature guard
- Scaffold: `if aicc_quad < aicc_pw - 6.0:` (hardcoded, very permissive)
- V4: `if aicc_quad + delta_quadratic_win < aicc_pow:` with default 3.0
- Equivalent: scaffold rejects when quad is 6.0 better; v4 rejects when quad is 3.0 better
- Impact: Scaffold more permissive to curvature (needs bigger quadratic win to reject)

### Center selection
- Scaffold: `rng.sample(range(cg.n), min(n_centers, cg.n))` — WITHOUT replacement, capped at n
- V4: `[rng.randrange(n_measured) for _ in range(max(1, n_centers))]` — WITH replacement, NOT capped
- Impact: Different center distributions, especially visible on small graphs

### auto_radii
- Scaffold: dense_end=10, cap=floor(0.3*diam), no r_cap, no min_r_max
- V4: dense_prefix=6, r_cap=32, min_r_max=12, diam_frac=0.3
- Impact: Different radius distributions

### AICc
- Scaffold: single `aicc()` used for everything (OLS formula)
- V4: `aicc_for_ols()` + `aicc_for_wls()` (different formulas)
- WLS AICc: `chi2 + 2k + correction` vs OLS AICc: `n*log(sse/n) + 2k + correction`
- Impact: Scaffold can't properly compare WLS fits across windows

### Bootstrap
- Scaffold: no min reps, `int()` truncation percentile, no delta_aicc_ci
- V4: min 10 or 20% reps, linear interpolation percentile, delta_aicc_ci

### Quality gate
- Scaffold inclusive: (r2=0.85, stderr=0.50, ratio=3.0, aicc=1.5)
- V4 inclusive: (r2=0.85, stderr=0.25, span=log(3), aicc=1.5)
- V4 has log_span check; scaffold has radius_ratio check

### Degenerate filtering
- Scaffold: `if all(m <= 1 for m in col)` — skips if ALL masses <=1
- V4: checks `mean_mass_eff <= 1.0` — skips if MEAN mass <=1
- Scaffold: `if all(m >= sat_threshold for m in col)` — skips if ALL saturated
- V4: checks `mean_mass_eff >= sat_thresh` — skips if MEAN saturated
- Impact: Scaffold is more permissive on individual radii (needs ALL to be degenerate)

### Window search
- Scaffold: iterates over contiguous radii_eval slices directly
- V4: iterates over `keep_idx` array with explicit hole check
- Both achieve same thing since scaffold filters inline (always contiguous)

## Reasoning Trace

The D=1.61 issue is almost certainly caused by `max_saturation_frac=0.2`:
- 30x30 grid has 900 nodes
- 0.2 * 900 = 180
- Any radius where mean M(r) >= 180 is filtered out
- On a 30x30 grid with diameter ~58, radii beyond ~7-8 easily reach 180 nodes
- This cuts the scaling window to only small radii, biasing D downward
- V4 uses 0.95 * 900 = 855, keeping data up to near-saturation

Secondary contributors:
- `var_floor=1e-12` gives extreme WLS weights to low-variance small-radius points
- Center selection with/without replacement changes mean mass statistics
- dense_prefix=10 vs 6 changes radius distribution

Plan: fix max_saturation_frac first, run 30x30 grid, see if D moves toward 2.0.
If it does, proceed with remaining alignment. If not, investigate further.

## Files to Modify (anticipated)
- `src/navi_fractal/_sandbox.py` — most changes (thresholds, params, bootstrap, aggregation)
- `src/navi_fractal/_regression.py` — aicc_wls, quadratic WLS, slope_range_over_subwindows
- `src/navi_fractal/_radii.py` — auto_radii parameter alignment
- `src/navi_fractal/_quality_gate.py` — add log_span check, adjust stderr default
- `src/navi_fractal/_types.py` — possibly add fields
- `tests/test_sandbox.py` — update thresholds, add new param tests
- `tests/test_known_dimensions.py` — tighten grid bounds
- `tests/test_quality_gates.py` — add log_span tests
- `tests/test_regression.py` — add aicc_wls, quadratic WLS tests

## What Was Already Presented to User
Section 1 (thresholds) was presented in detail:
- 1a: max_saturation_frac 0.2→0.95
- 1b: variance_floor→var_floor, 1e-12→1e-6
- 1c: curvature guard hardcoded→parameterized delta_quadratic_win=3.0
- 1d: center selection sample→randrange (with replacement)
User had not yet responded to "Does this section look right so far?"
