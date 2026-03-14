"""Subgraph builders for architect and validator phases.

Each subgraph encapsulates a supervisor → parallel domain agents → synthesizer
fan-out/fan-in pattern, keeping the top-level graph concise.
"""

from typing import Any

from langgraph.graph import END, START, StateGraph

from cloudy_intell.agents.context import RuntimeContext
from cloudy_intell.agents.domain_nodes import (
    compute_architect,
    compute_validator,
    database_architect,
    database_validator,
    network_architect,
    network_validator,
    storage_architect,
    storage_validator,
)
from cloudy_intell.agents.supervisors import architect_supervisor, validator_supervisor
from cloudy_intell.agents.synthesizers import (
    architect_synthesizer,
    final_architecture_generator,
    validation_synthesizer,
)
from cloudy_intell.schemas.models import State

__all__ = ["build_architect_subgraph", "build_validator_subgraph"]


def build_architect_subgraph(ctx: RuntimeContext) -> StateGraph:
    """Build subgraph: architect_supervisor → 4 domain architects → architect_synthesizer."""

    sg = StateGraph(State)

    sg.add_node("architect_supervisor", architect_supervisor(ctx))
    sg.add_node("compute_architect", compute_architect(ctx))
    sg.add_node("network_architect", network_architect(ctx))
    sg.add_node("storage_architect", storage_architect(ctx))
    sg.add_node("database_architect", database_architect(ctx))
    sg.add_node("architect_synthesizer", architect_synthesizer(ctx))

    sg.add_edge(START, "architect_supervisor")

    sg.add_edge("architect_supervisor", "compute_architect")
    sg.add_edge("architect_supervisor", "network_architect")
    sg.add_edge("architect_supervisor", "storage_architect")
    sg.add_edge("architect_supervisor", "database_architect")

    sg.add_edge("compute_architect", "architect_synthesizer")
    sg.add_edge("network_architect", "architect_synthesizer")
    sg.add_edge("storage_architect", "architect_synthesizer")
    sg.add_edge("database_architect", "architect_synthesizer")

    sg.add_edge("architect_synthesizer", END)

    return sg


def build_validator_subgraph(ctx: RuntimeContext) -> StateGraph:
    """Build subgraph: validator_supervisor → 4 domain validators → validation_synthesizer."""

    sg = StateGraph(State)

    sg.add_node("validator_supervisor", validator_supervisor(ctx))
    sg.add_node("compute_validator", compute_validator(ctx))
    sg.add_node("network_validator", network_validator(ctx))
    sg.add_node("storage_validator", storage_validator(ctx))
    sg.add_node("database_validator", database_validator(ctx))
    sg.add_node("validation_synthesizer", validation_synthesizer(ctx))

    sg.add_edge(START, "validator_supervisor")

    sg.add_edge("validator_supervisor", "compute_validator")
    sg.add_edge("validator_supervisor", "network_validator")
    sg.add_edge("validator_supervisor", "storage_validator")
    sg.add_edge("validator_supervisor", "database_validator")

    sg.add_edge("compute_validator", "validation_synthesizer")
    sg.add_edge("network_validator", "validation_synthesizer")
    sg.add_edge("storage_validator", "validation_synthesizer")
    sg.add_edge("database_validator", "validation_synthesizer")

    sg.add_edge("validation_synthesizer", END)

    return sg
