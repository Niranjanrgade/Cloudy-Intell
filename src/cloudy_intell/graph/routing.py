"""Routing helpers for graph iteration decisions.

This module contains the conditional routing function used by the top-level
graph to decide whether to loop back for another architect→validate iteration
or proceed to final output generation.

The routing logic implements an Evaluator-Optimizer pattern:
- Run at least ``min_iterations`` regardless of validation outcome.
- Continue iterating if ``factual_errors_exist`` is True and iteration count
  is below ``max_iterations``.
- Finish immediately once ``max_iterations`` is reached.
"""


def iteration_condition(state: dict) -> str:
    """Decide whether graph should iterate again or finish.

    The function mirrors runtime logic used in synthesizer module while keeping
    this module dependency-light for testing and reuse.

    Decision logic:
    - If iteration_count < min_iterations: always iterate (force minimum passes).
    - If factual_errors_exist and iteration_count < max_iterations: iterate to fix.
    - If iteration_count >= max_iterations: always finish (hard stop).
    - Otherwise: finish (no errors found, minimum met).

    Args:
        state: Current graph state dict.

    Returns:
        "iterate" to loop back to architect_phase, or "finish" to proceed
        to final_architecture_generator.
    """

    iteration = state.get("iteration_count", 0)
    min_iterations = state.get("min_iterations", 1)
    max_iterations = state.get("max_iterations", 3)
    has_errors = state.get("factual_errors_exist", False)

    if iteration < min_iterations:
        return "iterate"
    if has_errors and iteration < max_iterations:
        return "iterate"
    if iteration >= max_iterations:
        return "finish"
    return "finish"


__all__ = ["iteration_condition"]
