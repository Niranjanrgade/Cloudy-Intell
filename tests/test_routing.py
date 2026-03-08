"""Tests for iteration routing conditions."""

from cloudy_intell.graph.routing import iteration_condition


def test_iteration_condition_min_iterations_forces_iterate() -> None:
    state = {
        "iteration_count": 0,
        "min_iterations": 2,
        "max_iterations": 3,
        "factual_errors_exist": False,
    }
    assert iteration_condition(state) == "iterate"


def test_iteration_condition_errors_below_max_iterates() -> None:
    state = {
        "iteration_count": 2,
        "min_iterations": 1,
        "max_iterations": 3,
        "factual_errors_exist": True,
    }
    assert iteration_condition(state) == "iterate"


def test_iteration_condition_max_reached_finishes() -> None:
    state = {
        "iteration_count": 3,
        "min_iterations": 1,
        "max_iterations": 3,
        "factual_errors_exist": True,
    }
    assert iteration_condition(state) == "finish"
