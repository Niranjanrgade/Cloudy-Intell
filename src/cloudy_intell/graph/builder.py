"""Graph construction for the architecture workflow."""

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
from cloudy_intell.graph.routing import iteration_condition
from cloudy_intell.schemas.models import State


def build_graph(ctx: RuntimeContext, checkpointer):
    """Build and compile LangGraph using modularized node factories."""

    graph_builder = StateGraph(State)

    # Architect nodes
    graph_builder.add_node("architect_supervisor", architect_supervisor(ctx))
    graph_builder.add_node("compute_architect", compute_architect(ctx))
    graph_builder.add_node("network_architect", network_architect(ctx))
    graph_builder.add_node("storage_architect", storage_architect(ctx))
    graph_builder.add_node("database_architect", database_architect(ctx))
    graph_builder.add_node("architect_synthesizer", architect_synthesizer(ctx))

    # Validator nodes
    graph_builder.add_node("validator_supervisor", validator_supervisor(ctx))
    graph_builder.add_node("compute_validator", compute_validator(ctx))
    graph_builder.add_node("network_validator", network_validator(ctx))
    graph_builder.add_node("storage_validator", storage_validator(ctx))
    graph_builder.add_node("database_validator", database_validator(ctx))
    graph_builder.add_node("validation_synthesizer", validation_synthesizer(ctx))
    graph_builder.add_node("final_architecture_generator", final_architecture_generator(ctx))

    # Architecture generation flow.
    graph_builder.add_edge(START, "architect_supervisor")
    graph_builder.add_edge("architect_supervisor", "compute_architect")
    graph_builder.add_edge("architect_supervisor", "network_architect")
    graph_builder.add_edge("architect_supervisor", "storage_architect")
    graph_builder.add_edge("architect_supervisor", "database_architect")

    graph_builder.add_edge("compute_architect", "architect_synthesizer")
    graph_builder.add_edge("network_architect", "architect_synthesizer")
    graph_builder.add_edge("storage_architect", "architect_synthesizer")
    graph_builder.add_edge("database_architect", "architect_synthesizer")

    # Validation flow.
    graph_builder.add_edge("architect_synthesizer", "validator_supervisor")
    graph_builder.add_edge("validator_supervisor", "compute_validator")
    graph_builder.add_edge("validator_supervisor", "network_validator")
    graph_builder.add_edge("validator_supervisor", "storage_validator")
    graph_builder.add_edge("validator_supervisor", "database_validator")

    graph_builder.add_edge("compute_validator", "validation_synthesizer")
    graph_builder.add_edge("network_validator", "validation_synthesizer")
    graph_builder.add_edge("storage_validator", "validation_synthesizer")
    graph_builder.add_edge("database_validator", "validation_synthesizer")

    # Iteration routing.
    graph_builder.add_conditional_edges(
        "validation_synthesizer",
        iteration_condition,
        {"iterate": "architect_supervisor", "finish": "final_architecture_generator"},
    )
    graph_builder.add_edge("final_architecture_generator", END)

    return graph_builder.compile(checkpointer=checkpointer)
