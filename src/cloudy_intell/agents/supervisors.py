"""Supervisor node factories.

All prompt text is driven by ``RuntimeContext.provider`` metadata, making
these factories provider-agnostic (AWS, Azure, GCP, etc.).
"""

import time
from typing import cast

from langchain_core.messages import SystemMessage

from cloudy_intell.agents.context import RuntimeContext
from cloudy_intell.infrastructure.logging_utils import get_logger
from cloudy_intell.schemas.models import State, TaskDecomposition, ValidationDecomposition

logger = get_logger(__name__)


def architect_supervisor(ctx: RuntimeContext):
    """Create architect supervisor node bound to runtime context."""

    provider = ctx.provider

    def _node(state: State) -> State:
        iteration = state["iteration_count"] + 1
        previous_validation_feedback = state.get("validation_feedback", [])
        previous_validation_summary = state.get("validation_summary")

        feedback_context = ""
        if previous_validation_feedback:
            feedback_context += "\n\nPrevious Validation Feedback:\n"
            for feedback in previous_validation_feedback:
                domain = feedback.get("domain", "unknown")
                result = feedback.get("validation_result", "")
                feedback_context += f"\n{domain.upper()} Domain: {result[:200]}...\n"

        if previous_validation_summary:
            feedback_context += f"\n\nValidation Summary: {previous_validation_summary}\n"

        domain_lines = "\n        ".join(
            f"{i}. {domain} ({services})"
            for i, (domain, services) in enumerate(provider.domain_services.items(), 1)
        )

        system_prompt = f"""
        You are an architect supervisor for {provider.display_name} cloud architecture.
        Your role is to decompose the user's problem into structured domain-specific tasks and assign them to different architect domain agents.

        User Problem: {state['user_problem']}
        Current Iteration: {iteration} of {state.get('max_iterations', 3)}

        {feedback_context}

        Decompose the problem into structured tasks for these domains:
        {domain_lines}

        For each domain, provide a clear task description, key requirements, constraints and expected deliverables.
        Also provide overall architecture goals and global constraints.

        If this is a refinement iteration (iteration > 1), incorporate the validation feedback to address identified issues.
        Ensure your output matches the TaskDecomposition schema perfectly.
        """

        try:
            structured_llm = ctx.reasoning_llm.with_structured_output(TaskDecomposition)
            messages = [SystemMessage(content=system_prompt)]

            task_decomposition = None
            last_error = None
            for attempt in range(3):
                try:
                    response = structured_llm.invoke(messages)
                    task_decomposition = cast(TaskDecomposition, response)
                    if not task_decomposition or not task_decomposition.decomposed_tasks:
                        raise ValueError("Empty task decomposition received from LLM")
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    if attempt < 2:
                        time.sleep(2**attempt)
                    else:
                        raise

            if task_decomposition is None:
                raise ValueError(f"Failed to get task decomposition after retries: {last_error}")
        except Exception as exc:  # noqa: BLE001
            logger.error("Error in architect_supervisor LLM call: %s", exc, exc_info=True)
            error_msg = f"Error in task decomposition: {exc}"
            return cast(
                State,
                {
                    "user_problem": state["user_problem"],
                    "iteration_count": iteration,
                    "min_iterations": state.get("min_iterations", 1),
                    "max_iterations": state.get("max_iterations", 3),
                    "architecture_domain_tasks": {},
                    "architecture_components": {},
                    "proposed_architecture": {},
                    "validation_feedback": [],
                    "validation_summary": None,
                    "audit_feedback": [],
                    "factual_errors_exist": True,
                    "design_flaws_exist": False,
                    "final_architecture": None,
                    "architecture_summary": error_msg,
                },
            )

        domain_tasks_update = {
            "decomposition": task_decomposition.model_dump(),
            "overall_goals": task_decomposition.overall_architecture_goals,
            "constraints": task_decomposition.constraints,
        }

        for task in task_decomposition.decomposed_tasks:
            domain_key = task.domain.lower()
            domain_tasks_update[domain_key] = {
                "task_description": task.task_description,
                "requirements": task.requirements,
                "deliverables": task.deliverables,
            }

        return cast(
            State,
            {
                "architecture_domain_tasks": domain_tasks_update,
                "iteration_count": iteration,
                "validation_feedback": [],
                "architecture_components": {},
                "proposed_architecture": {},
                "factual_errors_exist": False,
                "validation_summary": None,
            },
        )

    return _node


def validator_supervisor(ctx: RuntimeContext):
    """Create validator supervisor node bound to runtime context."""

    provider = ctx.provider

    def _node(state: State) -> State:
        architecture_components = state.get("architecture_components", {})
        proposed_architecture = state.get("proposed_architecture", {})

        domain_lines = "\n        ".join(
            f"{i}. {domain} ({services})"
            for i, (domain, services) in enumerate(provider.domain_services.items(), 1)
        )

        system_prompt = f"""
        You are a validator supervisor for {provider.display_name} cloud architecture validation.
        Your role is to decompose the validation task into domain-specific validation assignments.

        Original Problem: {state['user_problem']}

        Architecture Components to Validate:
        {architecture_components}

        Proposed Architecture Summary:
        {proposed_architecture.get('architecture_summary', 'No summary available')}

        Analyze the architecture components and create validation tasks for these domains:
        {domain_lines}

        For each domain that has components in the architecture:
        - List the specific {provider.display_name} services/components that need validation
        - Specify what aspects to validate (configuration correctness, best practices, service compatibility, etc.)

        Only create validation tasks for domains that actually have components in the architecture.
        Ensure your output matches the ValidationDecomposition schema perfectly.
        """

        try:
            structured_llm = ctx.reasoning_llm.with_structured_output(ValidationDecomposition)
            messages = [SystemMessage(content=system_prompt)]

            validation_decomposition = None
            last_error = None
            for attempt in range(3):
                try:
                    response = structured_llm.invoke(messages)
                    validation_decomposition = cast(ValidationDecomposition, response)
                    if not validation_decomposition or not validation_decomposition.validation_tasks:
                        raise ValueError("Empty validation decomposition received")
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    if attempt < 2:
                        time.sleep(2**attempt)
                    else:
                        raise

            if validation_decomposition is None:
                raise ValueError(f"Failed to get validation decomposition after retries: {last_error}")
        except Exception as exc:  # noqa: BLE001
            logger.error("Error in validator_supervisor: %s", exc, exc_info=True)
            validation_decomposition = ValidationDecomposition(validation_tasks=[])

        validation_tasks_update = {}
        for task in validation_decomposition.validation_tasks:
            validation_tasks_update[task.domain.lower()] = {
                "components_to_validate": task.components_to_validate,
                "validation_focus": task.validation_focus,
            }

        existing = state.get("architecture_domain_tasks", {})
        merged = {**existing, "validation_tasks": validation_tasks_update}
        return cast(State, {"architecture_domain_tasks": merged})

    return _node
