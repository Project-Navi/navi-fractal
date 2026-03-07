# Changelog

All notable changes to navi-fractal will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## 0.1.0 (Unreleased)

Initial release.

### Added

- Sandbox (mass-radius) dimension estimation via `estimate_sandbox_dimension`
- Quality gate chain: R², AICc model selection, curvature guard, slope stability
- Machine-readable refusal codes via `Reason` enum
- Post-hoc quality gate via `sandbox_quality_gate` with `inclusive` and `strict` presets
- Bootstrap confidence intervals for dimension and delta AICc
- `Graph` type with `add_node`/`add_edge` API (zero dependencies)
- `CompiledGraph` frozen dataclass for deterministic BFS
- Helper constructors: `make_grid_graph`, `make_path_graph`
- Degree-preserving rewiring null model
- Calibration against (u,v)-flower networks with exact analytical dimensions
- Full audit trail in `SandboxResult` frozen dataclass (25 fields)
- Zero runtime dependencies, Python 3.12+
