# v4 Alignment Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align navi-fractal's sandbox estimator algorithms and defaults to v4 ground truth (`fractal_analysis_v4_mfa.py`), keeping our enum-based API as an additive improvement.

**Architecture:** Nine sections of changes across 9 files. Threshold-first approach: fix defaults that differ from v4, then align algorithms, then add missing parameters and fields. v4 is ground truth for all defaults and algorithms. Our `Reason`/`QualityGateReason` enums and frozen-dataclass API are kept (additive over v4's free-form strings).

**Tech Stack:** Python 3.12+, stdlib only, existing module layout.

---

## User Decisions (locked)

1. **v4 is ground truth** — adopt its defaults, algorithms, factoring
2. **Sandbox alignment only** — no multifractal, no Creative Determinant (stay v0.2.0)
3. **Keep Reason/QualityGateReason enums** — better than v4's free-form strings
4. **Approach: threshold-first** — fix defaults, validate, then align rest

## Empirical Baseline

Both implementations produce D~1.62 on a 30x30 open grid (v4: 1.622, scaffold: 1.613).
This is mathematically correct — `M(r) = 2r^2 + 2r + 1` on a discrete L1 lattice
gives slope < 2 at finite radii. The 0.009 gap comes from minor algorithmic differences.

**Expected outcome of alignment:** scaffold 30x30 grid D moves from 1.613 to ~1.622 (matching v4).

---

### Task 1: Threshold & Algorithm Fixes

The core defaults and algorithms that differ from v4.

**Files:**
- Modify: `src/navi_fractal/_sandbox.py:81-103` (signature defaults)
- Modify: `src/navi_fractal/_sandbox.py:190-191` (center selection)
- Modify: `src/navi_fractal/_sandbox.py:200-216` (degenerate/saturation filtering)
- Modify: `src/navi_fractal/_sandbox.py:335` (curvature guard)

**1a: `max_saturation_frac` default: 0.2 → 0.95**

Scaffold line 93: `max_saturation_frac: float = 0.2`
V4 line 1319: `max_saturation_frac: float = 0.95`

Change the default. 0.95 means "keep data unless 95% of nodes are in the ball" vs scaffold's aggressive 20% cutoff.

**1b: `variance_floor` → `var_floor`, default 1e-12 → 1e-6**

Scaffold line 102: `variance_floor: float = 1e-12`
V4 line 1328: `var_floor: float = 1e-6`

Rename parameter and update default. 1e-12 gives near-infinite WLS weight to low-variance points; 1e-6 is more reasonable. Update all internal references from `variance_floor` to `var_floor`.

**1c: Curvature guard: hardcoded -6.0 → parameterized `delta_quadratic_win=3.0`**

Scaffold line 335: `if aicc_quad < aicc_pw - 6.0:`
V4 line 1676: `if aicc_quad + delta_quadratic_win < aicc_pow:`

These are equivalent formulations but with different thresholds:
- Scaffold rejects when quadratic is 6.0 AICc better (very permissive)
- V4 rejects when quadratic is 3.0 AICc better (tighter)

Add `delta_quadratic_win: float = 3.0` parameter. Replace hardcoded check with:
```python
if aicc_quad + delta_quadratic_win < aicc_pw:
```

**Also**: v4 uses the correct AICc function per fit type (OLS or WLS) for curvature guard. The scaffold always uses OLS AICc. This will be fixed in Task 4 when `aicc_for_wls` is added; for now, note the dependency.

**1d: Center selection: `rng.sample` → `rng.randrange` loop (with replacement)**

Scaffold line 190-191:
```python
actual_n_centers = min(n_centers, cg.n)
centers = rng.sample(range(cg.n), actual_n_centers)
```

V4 line 1533:
```python
centers = [rng.randrange(n_measured) for _ in range(max(1, n_centers))]
```

Key differences:
- V4 samples WITH replacement (same center can appear twice)
- V4 does NOT cap at n_measured (can request more centers than nodes)
- V4 uses `max(1, n_centers)` instead of `min(n_centers, cg.n)`

Replace with v4 style. Remove `actual_n_centers` variable.

**1e: Degenerate/saturation filtering: all() → mean-based**

Scaffold lines 213-216:
```python
if all(m <= 1 for m in col):
    continue
if all(m >= saturation_threshold for m in col) and saturation_threshold > 1:
    continue
```

V4 lines 1564-1570:
```python
mean_mass_eff = math.exp(mean_logM[i]) if mean_mode == "geometric" else mean_M[i]
if mean_mass_eff <= 1.0:
    continue
if mean_mass_eff >= sat_thresh:
    continue
```

V4 filters on the MEAN mass (geometric or arithmetic), not whether ALL individual centers are degenerate. This is stricter — a radius is filtered if the typical center is degenerate, even if some individual centers are not.

This change depends on Task 7 (moment aggregation factoring) since v4 computes `mean_logM` via `_moments_from_center_masses()` before filtering. However, the filtering logic itself can be implemented using the already-computed `mean_mass_eval` and `y_eval` values from the aggregation loop. After Task 7 factors out moment aggregation, the filtering moves to after aggregation and uses the computed means directly.

---

### Task 2: auto_radii Alignment

**Files:**
- Modify: `src/navi_fractal/_radii.py` (full rewrite of function signature and body)
- Modify: `src/navi_fractal/_sandbox.py:176` (pass `r_cap` through)

Scaffold signature:
```python
def auto_radii(diameter: int, *, max_fraction: float = 0.3) -> list[int]:
```

V4 signature (lines 983-991):
```python
def auto_radii(
    diam_est: int,
    *,
    r_cap: int = 32,
    dense_prefix: int = 6,
    log_points: int = 10,
    diam_frac: float = 0.3,
    min_r_max: int = 12,
) -> List[int]:
```

Key algorithm differences:
- `dense_end=10` → `dense_prefix=6`
- No `r_cap` → `r_cap=32` (hard cap on radius)
- No `min_r_max` → `min_r_max=12` (floor on max radius)
- V4 caps by diameter AND r_cap: `r_max = min(r_cap, max(1, r_max))` then `r_max = min(r_max, max(1, diam_est))`
- V4 log-spacing uses `round()` vs scaffold's `floor()`

Rewrite `auto_radii` to match v4 lines 983-1012 exactly.

Update `_sandbox.py` line 176 to pass `r_cap`:
```python
radii = auto_radii(diam, r_cap=r_cap)
```

---

### Task 3: Bootstrap Improvements

**Files:**
- Modify: `src/navi_fractal/_sandbox.py:438-469` (bootstrap loop)
- Create helper: `_percentile()` in `_sandbox.py`

**3a: `_percentile()` with linear interpolation**

Scaffold lines 467-468 (truncating percentile):
```python
lo = boot_slopes[max(0, int(0.025 * len(boot_slopes)))]
hi = boot_slopes[min(len(boot_slopes) - 1, int(0.975 * len(boot_slopes)))]
```

V4 lines 1282-1299 (`_percentile` with linear interpolation):
```python
def _percentile(sorted_vals: List[float], q: float) -> float:
    if not sorted_vals:
        return float("nan")
    if q <= 0:
        return float(sorted_vals[0])
    if q >= 1:
        return float(sorted_vals[-1])
    n = len(sorted_vals)
    pos = (n - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_vals[lo])
    t = pos - lo
    return float((1 - t) * sorted_vals[lo] + t * sorted_vals[hi])
```

Add as private function in `_sandbox.py`.

**3b: Minimum validity threshold**

V4 line 1780: `if boot_ok >= max(10, int(0.2 * bootstrap_reps)):`

Scaffold has no minimum — any non-empty `boot_slopes` produces a CI. Add the same threshold.

**3c: Replace `_radius_index_for_log` round-trip with direct index slicing**

Scaffold lines 446: `j = _radius_index_for_log(log_radii[j_idx], radii)`

V4 lines 1761-1762: `xw = x_log_r[wi:wj + 1]` / `yw = b_y[wi:wj + 1]`

V4 slices directly from the recomputed bootstrap arrays using the window indices. No need for the log→exp→closest-index round-trip. Delete `_radius_index_for_log()`.

**3d: Factor bootstrap through `_moments_from_center_masses` / `_y_and_weights`**

V4 lines 1748-1759 show bootstrap recomputing moments from resampled centers:
```python
boot_masses = [center_masses[k] for k in idxs]
b_mean_M, b_var_M, b_mean_logM, b_var_logM = _moments_from_center_masses(boot_masses)
b_y, b_w = _y_and_weights(...)
```

This depends on Task 7 (extracting these helpers). After Task 7, refactor the bootstrap loop to use them.

**3e: Bootstrap also computes `delta_aicc_ci`**

V4 lines 1769-1773 compute bootstrap AICc delta:
```python
b_aicc_pow = aicc_fn(b_fit_pow.sse, b_fit_pow.n, k=2)
b_fit_exp = fit_fn(xr_w, yw, ww)
b_aicc_exp = aicc_fn(b_fit_exp.sse, b_fit_exp.n, k=2)
b_delta = b_aicc_exp - b_aicc_pow
```

Add `delta_aicc_ci` computation alongside `dimension_ci`.

**3f: `bootstrap_seed` parameter**

V4 line 1742: `brng = random.Random(seed if bootstrap_seed is None else bootstrap_seed)`

Add `bootstrap_seed: int | None = None` parameter to `estimate_sandbox_dimension`.

---

### Task 4: Regression Module Alignment

**Files:**
- Modify: `src/navi_fractal/_regression.py`
- Modify: `src/navi_fractal/_sandbox.py` (use correct AICc per fit type)

**4a: Add `aicc_for_wls()`**

V4 lines 967-976:
```python
def aicc_for_wls(chi2: float, n: int, k: int) -> float:
    if n <= k + 1:
        return float("inf")
    return float(chi2 + 2 * k + (2 * k * (k + 1)) / (n - k - 1))
```

WLS AICc uses chi2 (weighted residual sum) directly, NOT `n*log(sse/n)`. This is a different formula from OLS AICc.

Add to `_regression.py`. Rename existing `aicc()` to `aicc_for_ols()` for clarity.

**4b: Add `quadratic_fit_residual_wls()`**

V4 lines 1130-1155: WLS quadratic fit for curvature guard when `use_wls=True`.

Add to `_regression.py`. The scaffold currently always uses OLS for the quadratic check regardless of `use_wls`.

**4c: Add standalone `slope_range_over_subwindows()`**

V4 lines 1158-1181:
```python
def slope_range_over_subwindows(
    x, y, *, sub_len, use_wls, w=None
) -> float:
```

Currently the scaffold inlines this logic in `_sandbox.py` lines 343-360. Extract to `_regression.py` as a standalone function that supports both OLS and WLS subwindow fits.

**4d: Update `_sandbox.py` to use correct AICc per fit type**

V4 lines 1613-1615:
```python
fit_fn = (lambda xx, yy, ww: linear_fit_wls(xx, yy, ww)) if use_wls else (lambda xx, yy, ww: linear_fit_ols(xx, yy))
aicc_fn = aicc_for_wls if use_wls else aicc_for_ols
```

The scaffold always uses OLS AICc for model comparison (lines 315-316), even when `use_wls=True`. Update to use the matching AICc function:
- When `use_wls=True`: use `aicc_for_wls(fit.sse, n, 2)` (where `fit.sse` is the weighted chi2)
- When `use_wls=False`: use `aicc_for_ols(fit.sse, n, 2)`

Same for curvature guard and exponential alternative fits.

---

### Task 5: Quality Gate Alignment

**Files:**
- Modify: `src/navi_fractal/_quality_gate.py`
- Modify: `src/navi_fractal/_types.py` (add `LOG_SPAN_TOO_SMALL` enum member)

**5a: Add `min_log_span` check**

V4 line 1869-1870:
```python
if res.window_log_span is None or res.window_log_span < _span:
    return False, f"reject: window_log_span={res.window_log_span} < {_span:.3f}"
```

V4 inclusive default: `math.log(3.0)` (~1.099)
V4 strict default: `math.log(4.0)` (~1.386)

Add `min_log_span: float | None = None` parameter. Add `QualityGateReason.LOG_SPAN_TOO_SMALL` enum member.

**5b: `stderr_max` inclusive default: 0.50 → 0.25**

Scaffold line 35: `defaults = (0.85, 0.50, 3.0, 1.5)`
V4 line 1847: `_se = 0.25`

Change inclusive stderr default to 0.25.

**5c: Keep scaffold's additive checks**

Keep `radius_ratio_min` (v4 doesn't have it — our addition).
Keep `aicc_min` (v4 has this as `delta_aicc_min`).

Result: quality gate checks R^2, stderr, log_span, radius_ratio, AICc — superset of v4.

**5d: Check ordering**

V4 checks in order: R^2, stderr, log_span, AICc. Scaffold should match this ordering, with radius_ratio inserted after log_span (our addition).

---

### Task 6: Missing Parameters on `estimate_sandbox_dimension`

**Files:**
- Modify: `src/navi_fractal/_sandbox.py:81-103` (add to signature)

Add parameters matching v4 signature (lines 1306-1343):

```python
def estimate_sandbox_dimension(
    g: Graph | CompiledGraph,
    *,
    seed: int = 0,
    rng: random.Random | None = None,       # keep (scaffold addition)
    n_centers: int = 256,
    component_policy: str = "giant",
    mean_mode: str = "geometric",
    radii: Sequence[int] | None = None,      # NEW — user-provided radii
    min_points: int = 6,
    min_radius_ratio: float = 3.0,           # keep (scaffold addition)
    r2_min: float = 0.85,
    min_delta_y: float = 0.5,
    max_saturation_frac: float = 0.95,       # CHANGED from 0.2
    delta_power_win: float = 1.5,
    require_positive_slope: bool = True,
    use_wls: bool = True,
    var_floor: float = 1e-6,                 # RENAMED + CHANGED from 1e-12
    curvature_guard: bool = True,
    delta_quadratic_win: float = 3.0,        # NEW
    slope_stability_guard: bool = False,
    slope_stability_sub_len: int | None = None,
    max_slope_range: float = 0.5,
    bootstrap_reps: int = 0,
    bootstrap_seed: int | None = None,       # NEW
    r_cap: int = 32,                         # NEW
    notes: str = "",                         # CHANGED from str | None
) -> SandboxResult:
```

When `radii` is provided, skip `auto_radii()` and use the provided radii directly (sorted, deduplicated, >= 1). Match v4 lines 1490-1491:
```python
radii_eval = sorted(set(int(r) for r in radii if int(r) >= 1))
```

---

### Task 7: Moment Aggregation Factoring

**Files:**
- Modify: `src/navi_fractal/_sandbox.py`

Extract two private helpers from the inline aggregation loop (lines 202-244):

**`_moments_from_center_masses()`** — matches v4 lines 1188-1232:
```python
def _moments_from_center_masses(
    center_masses: Sequence[Sequence[int]],
) -> tuple[list[float], list[float], list[float], list[float]]:
    """Compute mean_M, var_M, mean_logM, var_logM across centers per radius."""
```

Key details:
- Uses sample variance (`/ (n_centers - 1)`) not population variance
- Clamps masses to `max(1, m)` before taking log (v4 line 1209)
- Returns 4 parallel lists of length n_radii

**`_y_and_weights()`** — matches v4 lines 1235-1279:
```python
def _y_and_weights(
    *,
    mean_mode: str,
    mean_M: Sequence[float],
    var_M: Sequence[float],
    mean_logM: Sequence[float],
    var_logM: Sequence[float],
    n_centers: int,
    use_wls: bool,
    var_floor: float,
) -> tuple[list[float], list[float] | None]:
    """Return y_eval and optional WLS weights per radius."""
```

Key details:
- Geometric: `y = mean_logM[i]`, `Var(y) = var_logM[i] / n_centers`
- Arithmetic: `y = log(mean_M[i])`, `Var(y) = (var_M[i] / n_centers) / mean_M[i]^2` (delta method)
- Weight = `1 / max(Var(y), var_floor)`

Replace the inline aggregation loop with calls to these helpers. The degenerate/saturation filtering then operates on the computed means (Task 1e).

Both helpers are reused in the bootstrap loop (Task 3d).

---

### Task 8: SandboxResult Field Additions

**Files:**
- Modify: `src/navi_fractal/_sandbox.py:24-68` (SandboxResult dataclass)
- Modify: `src/navi_fractal/_sandbox.py:508-543` (`_make_empty_result`)
- Modify: all SandboxResult construction sites in `_sandbox.py`

Add two fields matching v4's SandboxResult:

```python
# After dimension_ci field:
delta_aicc_ci: tuple[float, float] | None       # bootstrap CI on AICc margin
bootstrap_valid_reps: int                         # number of valid bootstrap replicates
```

- `delta_aicc_ci` defaults to `None` (populated by bootstrap, Task 3e)
- `bootstrap_valid_reps` defaults to `0` (populated by bootstrap)
- Total fields: 23 → 25
- Update `_make_empty_result` to include both new fields
- Update all 4 inline `SandboxResult(...)` constructors in `_sandbox.py`

---

### Task 9: Test Updates

**Files:**
- Modify: `tests/test_known_dimensions.py:25` (grid bounds)
- Modify: `tests/test_sandbox.py` (new parameter tests, updated field counts)
- Modify: `tests/test_quality_gates.py` (log_span test, updated helpers)
- Modify: `tests/test_regression.py` (aicc_for_wls, quadratic WLS tests)

**9a: Grid 30x30 bounds**

Current (line 25): `assert 1.5 <= result.dimension <= 2.3`

After alignment, scaffold should produce D~1.622 (matching v4). Tighten to:
```python
assert 1.55 <= result.dimension <= 1.75, f"D={result.dimension}"
```

**9b: New parameter tests in `test_sandbox.py`**

- `test_delta_quadratic_win_parameter`: verify parameterized curvature guard works
- `test_r_cap_parameter`: verify r_cap passes through to auto_radii
- `test_user_provided_radii`: verify custom radii bypass auto_radii
- `test_bootstrap_seed_separate`: verify bootstrap_seed differs from main seed
- `test_var_floor_parameter`: verify renamed parameter works (replaces variance_floor)
- `test_notes_default_empty_string`: verify notes="" not None

**9c: Quality gate log_span test**

Add to `tests/test_quality_gates.py`:
- `test_log_span_override`: verify `min_log_span` parameter rejects narrow windows
- Update `_make_accepted_result` helper with `delta_aicc_ci=None, bootstrap_valid_reps=0`

**9d: Regression tests**

Add to `tests/test_regression.py`:
- `test_aicc_for_wls_basic`: verify WLS AICc formula
- `test_aicc_for_ols_renamed`: verify renamed function works identically to old `aicc()`
- `test_quadratic_fit_residual_wls`: verify WLS quadratic fit
- `test_slope_range_over_subwindows`: verify standalone function

**9e: Determinism tests**

Update any tests that construct `SandboxResult` directly to include the two new fields (`delta_aicc_ci`, `bootstrap_valid_reps`).

---

## Dependency Graph

```
Task 7 (moment factoring) ──→ Task 1e (mean-based filtering)
                           ──→ Task 3d (bootstrap factoring)

Task 4a (aicc_for_wls)    ──→ Task 4d (correct AICc in sandbox)
                           ──→ Task 1c (curvature guard with correct AICc)

Task 8 (new fields)        ──→ Task 9e (test field updates)
Task 5a (log_span gate)    ──→ Task 9c (log_span test)

All tasks                  ──→ Task 9a (tighten grid bounds — run last)
```

**Suggested execution order:**
1. Task 8 (SandboxResult fields — unblocks test updates)
2. Task 4 (regression module — unblocks correct AICc usage)
3. Task 7 (moment factoring — unblocks filtering + bootstrap)
4. Task 2 (auto_radii — independent)
5. Task 1 (thresholds — depends on 4, 7)
6. Task 5 (quality gate — independent)
7. Task 6 (missing params — depends on 1, 2)
8. Task 3 (bootstrap — depends on 7)
9. Task 9 (tests — depends on all above)

## Files Changed Summary

| File | Changes |
|------|---------|
| `_sandbox.py` | Signature, defaults, center selection, filtering, bootstrap, moment helpers, new fields |
| `_regression.py` | `aicc_for_ols` (rename), `aicc_for_wls` (new), `quadratic_fit_residual_wls` (new), `slope_range_over_subwindows` (new) |
| `_radii.py` | Full `auto_radii` rewrite to match v4 signature |
| `_quality_gate.py` | Add `min_log_span` check, update stderr default |
| `_types.py` | Add `LOG_SPAN_TOO_SMALL` to `QualityGateReason` |
| `tests/test_known_dimensions.py` | Tighten 30x30 bounds |
| `tests/test_sandbox.py` | New param tests, field updates |
| `tests/test_quality_gates.py` | log_span test, helper updates |
| `tests/test_regression.py` | New function tests |
