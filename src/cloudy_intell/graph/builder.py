"""Graph construction for the architecture workflow.

This module assembles the top-level LangGraph ``StateGraph`` by composing two
pre-compiled subgraphs (architect_phase and validator_phase) with a conditional
iteration edge and a final output node.

The resulting graph topology is:

    START
      │
      ▼
    architect_phase (subgraph: supervisor → 4 parallel domain architects → synthesizer)
      │
      ▼
    validator_phase (subgraph: supervisor → 4 parallel domain validators → synthesizer)
      │
      ▼
    ┌─────────────────────┐
    │ iteration_condition │─── "iterate" ──▶ architect_phase  (loops back)
    └─────────────────────┘
      │ "finish"
      ▼
    final_architecture_generator
      │
      ▼
    END

Subgraph composition keeps the top-level graph concise while encapsulating
the fan-out/fan-in parallelism within each phase.
"""

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

    Args:
        ctx: Runtime context containing LLMs, tools, settings, and provider metadata.
             Passed to subgraph builders so every nested node shares the same
             dependencies.
        checkpointer: Optional LangGraph checkpointer (e.g. MemorySaver) for
                      persisting state across invocations.  When None the graph
                      runs without checkpointing (used by ``langgraph dev``).

    Returns:
        A compiled LangGraph ``CompiledGraph`` ready to be invoked with an
        initial state dictionary.
    """

    graph_builder = StateGraph(State)

    # ── Compose subgraphs as nodes ───────────────────────────────────────
    # Each subgraph is built as a StateGraph and then compiled into a
    # standalone CompiledGraph.  Adding a compiled graph as a node makes it
    # execute as a nested sub-workflow within the parent graph.
    graph_builder.add_node("architect_phase", build_architect_subgraph(ctx).compile())
    graph_builder.add_node("validator_phase", build_validator_subgraph(ctx).compile())
    graph_builder.add_node("final_architecture_generator", final_architecture_generator(ctx))

    # ── Linear edges ──────────────────────────────────────────────────
    graph_builder.add_edge(START, "architect_phase")
    graph_builder.add_edge("architect_phase", "validator_phase")

    # ── Conditional iteration routing ─────────────────────────────────
    # After the validator phase completes, ``iteration_condition`` inspects
    # the state to decide whether to loop back to architect_phase (if errors
    # exist and iterations are below max) or proceed to final output.
    graph_builder.add_conditional_edges(
        "validator_phase",
        iteration_condition,
        {"iterate": "architect_phase", "finish": "final_architecture_generator"},
    )
    graph_builder.add_edge("final_architecture_generator", END)

    if checkpointer is None:
        return graph_builder.compile()
    return graph_builder.compile(checkpointer=checkpointer)
