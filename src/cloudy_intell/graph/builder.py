"""Graph construction for the architecture workflow."""

from typing import Any

from langgraph.graph import END, START, StateGraph

from cloudy_intell.agents.context import RuntimeContext
from cloudy_intell.agents.synthesizers import final_architecture_generator
from cloudy_intell.graph.routing import iteration_condition
from cloudy_intell.graph.subgraphs import build_architect_subgraph, build_validator_subgraph
from cloudy_intell.schemas.models import State

__all__ = ["build_graph"]


def build_graph(ctx: RuntimeContext, checkpointer: Any | None = None):
    """Build and compile LangGraph using subgraph-based architecture.

    Top-level graph:
        START → architect_phase → validator_phase → [conditional] →
            iterate: architect_phase | finish: final_architecture_generator → END
    """

    graph_builder = StateGraph(State)

    # Compose subgraphs as nodes
    graph_builder.add_node("architect_phase", build_architect_subgraph(ctx).compile())
    graph_builder.add_node("validator_phase", build_validator_subgraph(ctx).compile())
    graph_builder.add_node("final_architecture_generator", final_architecture_generator(ctx))

    # Edges
    graph_builder.add_edge(START, "architect_phase")
    graph_builder.add_edge("architect_phase", "validator_phase")

    # Iteration routing
    graph_builder.add_conditional_edges(
        "validator_phase",
        iteration_condition,
        {"iterate": "architect_phase", "finish": "final_architecture_generator"},
    )
    graph_builder.add_edge("final_architecture_generator", END)

    if checkpointer is None:
        return graph_builder.compile()
    return graph_builder.compile(checkpointer=checkpointer)
