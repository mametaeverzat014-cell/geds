"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from app.core.graph import CompiledGraph, compile_graph
from app.core.propagation import PropagationEngine
from app.core.scenarios import taiwan_semiconductor_shock
from app.core.types import GraphSnapshot
from app.data.seed import load_graph


@pytest.fixture(scope="session")
def snapshot() -> GraphSnapshot:
    return load_graph()


@pytest.fixture(scope="session")
def graph(snapshot: GraphSnapshot) -> CompiledGraph:
    return compile_graph(snapshot, rerouting_efficiency=0.5)


@pytest.fixture
def engine(graph: CompiledGraph) -> PropagationEngine:
    return PropagationEngine(graph)


@pytest.fixture
def taiwan_scenario():
    return taiwan_semiconductor_shock(magnitude=0.75, duration_weeks=20, horizon_weeks=52)
