# Copyright 2024-2026 Nelson Spence
# SPDX-License-Identifier: Apache-2.0
"""Performance benchmarks for sandbox dimension estimation."""

from __future__ import annotations

import pytest

from navi_fractal import (
    compile_to_undirected_metric_graph,
    estimate_sandbox_dimension,
    make_grid_graph,
)


@pytest.fixture
def grid_30x30_compiled():  # type: ignore[no-untyped-def]
    g = make_grid_graph(30, 30)
    return compile_to_undirected_metric_graph(g)


class TestBenchmarks:
    def test_sandbox_30x30(self, benchmark, grid_30x30_compiled) -> None:  # type: ignore[no-untyped-def]
        benchmark.pedantic(
            estimate_sandbox_dimension,
            args=(grid_30x30_compiled,),
            kwargs={"seed": 42, "n_centers": 64, "bootstrap_reps": 0},
            rounds=3,
            iterations=1,
        )


@pytest.fixture
def grid_100x100_compiled():  # type: ignore[no-untyped-def]
    g = make_grid_graph(100, 100)
    return compile_to_undirected_metric_graph(g)


@pytest.fixture
def grid_300x300_compiled():  # type: ignore[no-untyped-def]
    g = make_grid_graph(300, 300)
    return compile_to_undirected_metric_graph(g)


class TestLargeBenchmarks:
    def test_sandbox_100x100(self, benchmark, grid_100x100_compiled) -> None:  # type: ignore[no-untyped-def]
        benchmark.pedantic(
            estimate_sandbox_dimension,
            args=(grid_100x100_compiled,),
            kwargs={"seed": 42, "n_centers": 64, "bootstrap_reps": 0},
            rounds=3,
            iterations=1,
        )

    def test_sandbox_300x300(self, benchmark, grid_300x300_compiled) -> None:  # type: ignore[no-untyped-def]
        benchmark.pedantic(
            estimate_sandbox_dimension,
            args=(grid_300x300_compiled,),
            kwargs={"seed": 42, "n_centers": 64, "bootstrap_reps": 0},
            rounds=1,
            iterations=1,
        )
