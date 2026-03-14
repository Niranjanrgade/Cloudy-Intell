"""State initialization helpers.

Reducer functions live in `schemas.models` to keep one source of truth for
LangGraph annotations; this module provides initialization helpers and shared
state constants used by graph/service code.
"""

from langchain_core.messages import HumanMessage

from cloudy_intell.schemas.models import State

__all__ = ["create_initial_state"]


def create_initial_state(user_problem: str, min_iterations: int = 1, max_iterations: int = 3) -> State:
    """Create graph state with explicit defaults for every tracked field.

    Keeping full defaults in one place avoids subtle state key omissions when
    individual nodes return partial updates.
    """

    return {
        "messages": [HumanMessage(content=user_problem)],
        "user_problem": user_problem,
        "iteration_count": 0,
        "min_iterations": min_iterations,
        "max_iterations": max_iterations,
        "architecture_domain_tasks": {},
        "architecture_components": {},
        "proposed_architecture": {},
        "validation_feedback": [],
        "validation_summary": None,
        "audit_feedback": [],
        "factual_errors_exist": False,
        "design_flaws_exist": False,
        "final_architecture": None,
        "architecture_summary": None,
    }
