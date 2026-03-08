"""Tests for state initialization and reducer behavior."""

from cloudy_intell.graph.state_reducers import create_initial_state
from cloudy_intell.schemas.models import validation_feedback_reducer


def test_create_initial_state_defaults() -> None:
    state = create_initial_state("test problem", min_iterations=2, max_iterations=4)
    assert state["user_problem"] == "test problem"
    assert state["iteration_count"] == 0
    assert state["min_iterations"] == 2
    assert state["max_iterations"] == 4
    assert state["validation_feedback"] == []


def test_validation_feedback_reducer_reset_signal() -> None:
    left = [{"domain": "compute", "has_errors": True}]
    assert validation_feedback_reducer(left, []) == []


def test_validation_feedback_reducer_deduplicates_domain() -> None:
    left = [{"domain": "compute", "has_errors": True, "validation_result": "old"}]
    right = [{"domain": "compute", "has_errors": False, "validation_result": "new"}]
    merged = validation_feedback_reducer(left, right)
    assert len(merged) == 1
    assert merged[0]["validation_result"] == "new"
