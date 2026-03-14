"""Pydantic and state schemas used by graph nodes.

These models were extracted from the notebook-style implementation and kept
intentionally close to existing behavior to reduce migration risk.
"""

from operator import add
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langgraph.graph import add_messages
from pydantic import BaseModel, Field

__all__ = [
    "DomainTask",
    "TaskDecomposition",
    "ValidationTask",
    "ValidationDecomposition",
    "State",
]


class DomainTask(BaseModel):
    """Schema for a single architecture domain task assignment."""

    domain: str = Field(description="The domain name (compute, network, storage, database, etc)")
    task_description: str = Field(description="Clear description of the task for this domain")
    requirements: List[str] = Field(description="Key requirements and constraints for this domain")
    deliverables: List[str] = Field(description="Expected deliverables for this domain")


class TaskDecomposition(BaseModel):
    """Schema returned by architect supervisor decomposition."""

    user_problem: str = Field(description="The original user problem")
    decomposed_tasks: List[DomainTask] = Field(description="List of domain-specific tasks")
    overall_architecture_goals: List[str] = Field(description="High-level architecture goals")
    constraints: List[str] = Field(description="Global constraints that apply to all domains")


class ValidationTask(BaseModel):
    """Schema for a single domain validation assignment."""

    domain: str = Field(description="The domain name (compute, network, storage, database, etc)")
    components_to_validate: List[str] = Field(description="List of AWS services/components to validate")
    validation_focus: str = Field(
        description="Specific aspects to validate (configuration, best practices, compatibility, etc)"
    )


class ValidationDecomposition(BaseModel):
    """Schema returned by validator supervisor decomposition."""

    validation_tasks: List[ValidationTask] = Field(description="List of domain-specific validation tasks")


def merge_dicts(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge nested dictionaries while giving precedence to right-side values."""

    result = left.copy()
    for key, value in right.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def last_value(left: Any, right: Any) -> Any:
    """Reducer that always keeps the newest value."""

    return right


def or_reducer(left: bool, right: bool) -> bool:
    """Reducer that aggregates flags by logical OR."""

    return left or right


def overwrite_bool(left: bool, right: bool) -> bool:
    """Reducer that permits explicit flag reset across iterations."""

    return right


def append_list(left: List[Any], right: List[Any]) -> List[Any]:
    """Append with domain-aware deduplication semantics for validator outputs."""

    if not right:
        return left
    if not left:
        return right

    combined = left.copy()
    for item in right:
        if isinstance(item, dict) and "domain" in item:
            domain = item["domain"]
            combined = [x for x in combined if not (isinstance(x, dict) and x.get("domain") == domain)]
            combined.append(item)
        else:
            if item not in combined:
                combined.append(item)
    return combined


def validation_feedback_reducer(left: List[Any], right: List[Any]) -> List[Any]:
    """Reducer supporting explicit reset plus accumulation for validation feedback.

    An empty list emitted mid-run by supervisor means "clear previous feedback"
    before new validator results are appended.
    """

    if right == [] and left != []:
        return []
    return append_list(left, right)


class State(TypedDict):
    """Complete LangGraph state contract for architecture generation workflow."""

    messages: Annotated[List, add_messages]
    user_problem: Annotated[str, last_value]
    iteration_count: Annotated[int, last_value]
    min_iterations: Annotated[int, last_value]
    max_iterations: Annotated[int, last_value]

    architecture_domain_tasks: Annotated[Dict[str, Dict[str, Any]], merge_dicts]
    architecture_components: Annotated[Dict[str, Dict[str, Any]], merge_dicts]
    proposed_architecture: Annotated[Dict[str, Any], merge_dicts]

    validation_feedback: Annotated[List[Dict[str, Any]], validation_feedback_reducer]
    validation_summary: Annotated[Optional[str], last_value]
    audit_feedback: Annotated[List[Dict[str, Any]], add]

    factual_errors_exist: Annotated[bool, overwrite_bool]
    design_flaws_exist: Annotated[bool, or_reducer]

    final_architecture: Annotated[Optional[Dict[str, Any]], last_value]
    architecture_summary: Annotated[Optional[str], last_value]
