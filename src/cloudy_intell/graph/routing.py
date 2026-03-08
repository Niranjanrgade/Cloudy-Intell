"""Routing helpers for graph iteration decisions."""


def iteration_condition(state: dict) -> str:
	"""Decide whether graph should iterate again or finish.

	The function mirrors runtime logic used in synthesizer module while keeping
	this module dependency-light for testing and reuse.
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
