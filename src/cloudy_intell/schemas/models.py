"""Pydantic and state schemas used by graph nodes.

These models were extracted from the notebook-style implementation and kept
intentionally close to existing behavior to reduce migration risk.

This module defines two categories of contracts:

1. **Pydantic Models** (DomainTask, TaskDecomposition, ValidationTask,
   ValidationDecomposition) — These are used with ``with_structured_output()``
   so the LLM returns validated, typed JSON that supervisors and domain agents
   can consume without ad-hoc parsing.

2. **LangGraph State TypedDict** — A single ``State`` class annotated with
   custom reducer functions.  LangGraph merges partial dicts returned by each
   node into the shared state using these reducers, enabling fan-out/fan-in
   parallelism and iterative refinement without manual bookkeeping.

Reducer functions (``merge_dicts``, ``last_value``, ``or_reducer``, etc.) are
defined here rather than in a utility module so that the State class and its
semantics live in one self-contained file.
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
    """Schema for a single architecture domain task assignment.

    The architect supervisor decomposes the user's problem into one DomainTask
    per cloud domain (compute, network, storage, database).  Each DomainTask
    carries enough context for the corresponding domain architect agent to
    generate targeted infrastructure recommendations without re-reading the
    original problem statement.
    """

    domain: str = Field(description="The domain name (compute, network, storage, database, etc)")
    task_description: str = Field(description="Clear description of the task for this domain")
    requirements: List[str] = Field(description="Key requirements and constraints for this domain")
    deliverables: List[str] = Field(description="Expected deliverables for this domain")


class TaskDecomposition(BaseModel):
    """Schema returned by architect supervisor decomposition.

    This is the structured output that the architect supervisor LLM produces
    via ``with_structured_output(TaskDecomposition)``.  It captures the full
    decomposition of the user's problem into domain-level tasks along with
    cross-cutting goals and constraints that every domain architect should
    honour.
    """

    user_problem: str = Field(description="The original user problem")
    decomposed_tasks: List[DomainTask] = Field(description="List of domain-specific tasks")
    overall_architecture_goals: List[str] = Field(description="High-level architecture goals")
    constraints: List[str] = Field(description="Global constraints that apply to all domains")


class ValidationTask(BaseModel):
    """Schema for a single domain validation assignment.

    Produced by the validator supervisor after inspecting the proposed
    architecture.  Each ValidationTask tells the corresponding domain
    validator exactly which cloud services to check and what validation
    criteria to apply (e.g. configuration correctness, security best
    practices, cross-service compatibility).
    """

    domain: str = Field(description="The domain name (compute, network, storage, database, etc)")
    components_to_validate: List[str] = Field(description="List of AWS services/components to validate")
    validation_focus: str = Field(
        description="Specific aspects to validate (configuration, best practices, compatibility, etc)"
    )


class ValidationDecomposition(BaseModel):
    """Schema returned by validator supervisor decomposition.

    The validator supervisor analyses the proposed architecture components and
    produces one ValidationTask per domain that has active components.  Domains
    without components are intentionally omitted.
    """

    validation_tasks: List[ValidationTask] = Field(description="List of domain-specific validation tasks")


# ── Reducer Functions ────────────────────────────────────────────────────────
#
# LangGraph uses reducer functions to combine partial state updates from
# multiple nodes running in parallel (fan-out/fan-in).  Each field in the
# State TypedDict is annotated with a reducer via ``Annotated[T, reducer]``.
# When two nodes both write to ``architecture_components``, for example,
# LangGraph calls ``merge_dicts(existing, new)`` to combine them.
# ─────────────────────────────────────────────────────────────────────────────


def merge_dicts(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge nested dictionaries while giving precedence to right-side values.

    Used by ``architecture_components``, ``architecture_domain_tasks``, and
    ``proposed_architecture`` so that each domain architect can independently
    write its slice (e.g. ``{"compute": {...}}``) and the results are merged
    into a single dict without overwriting sibling domains.
    """

    result = left.copy()
    for key, value in right.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def last_value(left: Any, right: Any) -> Any:
    """Reducer that always keeps the newest value.

    Applied to scalar fields like ``user_problem``, ``iteration_count``, and
    ``architecture_summary`` where only the latest write matters.
    """

    return right


def or_reducer(left: bool, right: bool) -> bool:
    """Reducer that aggregates flags by logical OR.

    Used by ``design_flaws_exist`` — if *any* domain validator reports design
    flaws the flag remains True for the rest of the iteration.
    """

    return left or right


def overwrite_bool(left: bool, right: bool) -> bool:
    """Reducer that permits explicit flag reset across iterations.

    Unlike ``or_reducer``, this allows the architect supervisor to explicitly
    clear the ``factual_errors_exist`` flag at the start of a new iteration so
    validators can set it afresh.
    """

    return right


def append_list(left: List[Any], right: List[Any]) -> List[Any]:
    """Append with domain-aware deduplication semantics for validator outputs.

    When a validator re-runs for the same domain (e.g. after an iteration),
    the new feedback replaces stale feedback for that domain rather than
    duplicating it.  Non-domain items are deduplicated by equality.
    """

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
    """Complete LangGraph state contract for architecture generation workflow.

    Every node in the graph receives a snapshot of this state and returns a
    *partial* dict containing only the keys it wants to update.  LangGraph
    applies the annotated reducer for each key to merge the partial update
    into the shared state.

    The state is organized into logical sections:
    - **Messages**: Chat history consumed by LangGraph's built-in message handling.
    - **Iteration control**: Counters and bounds that drive the iterate-or-finish
      routing decision.
    - **Architecture artifacts**: Domain tasks, component designs, and the
      synthesized proposal produced during the architect phase.
    - **Validation artifacts**: Feedback from validators, summary, and error flags.
    - **Final output**: The polished architecture document emitted after convergence.
    """

    # Chat history — LangGraph's built-in ``add_messages`` reducer appends new
    # messages and handles deduplication by message ID.
    messages: Annotated[List, add_messages]

    # ── Iteration control ───────────────────────────────────────────────
    user_problem: Annotated[str, last_value]              # Original problem statement from the user.
    iteration_count: Annotated[int, last_value]           # Current architect-validate iteration (starts at 0, incremented by architect_supervisor).
    min_iterations: Annotated[int, last_value]            # Minimum iterations to run before allowing convergence.
    max_iterations: Annotated[int, last_value]            # Hard upper bound on iterations to prevent infinite loops.

    # ── Architecture artifacts ──────────────────────────────────────────
    # ``architecture_domain_tasks`` — Decomposed task assignments keyed by domain.
    #   Populated by architect_supervisor; consumed by domain architects.
    architecture_domain_tasks: Annotated[Dict[str, Dict[str, Any]], merge_dicts]
    # ``architecture_components`` — Per-domain recommendations produced by domain architects.
    #   Each architect writes its slice (e.g. {"compute": {...}}); merge_dicts combines them.
    architecture_components: Annotated[Dict[str, Dict[str, Any]], merge_dicts]
    # ``proposed_architecture`` — Unified architecture proposal built by architect_synthesizer.
    proposed_architecture: Annotated[Dict[str, Any], merge_dicts]

    # ── Validation artifacts ────────────────────────────────────────────
    # ``validation_feedback`` — List of per-domain validation reports from domain validators.
    #   Uses a custom reducer that supports explicit reset (empty list = clear) plus accumulation.
    validation_feedback: Annotated[List[Dict[str, Any]], validation_feedback_reducer]
    validation_summary: Annotated[Optional[str], last_value]  # Consolidated human-readable validation summary.
    audit_feedback: Annotated[List[Dict[str, Any]], add]      # Append-only audit trail (reserved for future use).

    # ── Error flags ─────────────────────────────────────────────────────
    # ``factual_errors_exist`` — Set True by validators when documentation-verified errors are found.
    #   Reset to False by architect_supervisor at the start of each new iteration.
    factual_errors_exist: Annotated[bool, overwrite_bool]
    # ``design_flaws_exist`` — Sticky flag (OR reducer); remains True once any validator detects flaws.
    design_flaws_exist: Annotated[bool, or_reducer]

    # ── Final output ────────────────────────────────────────────────────
    final_architecture: Annotated[Optional[Dict[str, Any]], last_value]  # Complete final architecture artifact dict.
    architecture_summary: Annotated[Optional[str], last_value]           # Polished text summary for display / CLI output.
