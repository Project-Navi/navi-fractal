# SPDX-License-Identifier: Apache-2.0
"""Audit-grade fractal dimension estimation for graphs.

Refuses to emit a dimension unless positive evidence of power-law scaling exists.
"""

from __future__ import annotations

import logging

from navi_fractal._graph import (
    CompiledGraph,
    Graph,
    compile_to_undirected_metric_graph,
)
from navi_fractal._helpers import make_grid_graph, make_path_graph
from navi_fractal._null_model import degree_preserving_rewire_undirected
from navi_fractal._quality_gate import sandbox_quality_gate
from navi_fractal._sandbox import SandboxResult, estimate_sandbox_dimension
from navi_fractal._types import DimensionSummary, LinFit, QualityGateReason, Reason

logging.getLogger("navi_fractal").addHandler(logging.NullHandler())

__all__ = [
    "CompiledGraph",
    "DimensionSummary",
    "Graph",
    "LinFit",
    "QualityGateReason",
    "Reason",
    "SandboxResult",
    "compile_to_undirected_metric_graph",
    "degree_preserving_rewire_undirected",
    "estimate_sandbox_dimension",
    "make_grid_graph",
    "make_path_graph",
    "sandbox_quality_gate",
]
