"""Domain architect and validator node factories.

All prompt text is driven by ``RuntimeContext.provider`` metadata, making
these factories provider-agnostic (AWS, Azure, GCP, etc.).

This module defines the core domain-level agents:

- **Domain Architects** (compute, network, storage, database): Each architect
  receives a task assignment from the architect supervisor, uses web search
  and/or RAG tools to gather information, and produces detailed infrastructure
  recommendations for its specific domain.

- **Domain Validators** (compute, network, storage, database): Each validator
  checks the proposed architecture for its domain against official cloud
  provider documentation (via RAG tool) and produces a structured validation
  report with errors, warnings, and improvement suggestions.

Both architect and validator functions are implemented as closures: the outer
function (e.g. ``_domain_architect``) captures the ``RuntimeContext`` and domain
name, while the inner ``_node`` function matches the LangGraph node signature
``(state: State) -> State``.
"""

from typing import Any, Dict, cast

from langchain_core.messages import HumanMessage, SystemMessage

from cloudy_intell.agents.context import RuntimeContext
from cloudy_intell.agents.tool_execution import detect_errors_llm, execute_tool_calls, format_component_recommendations
from cloudy_intell.infrastructure.logging_utils import get_logger
from cloudy_intell.schemas.models import State

logger = get_logger(__name__)


def _domain_architect(ctx: RuntimeContext, domain: str):
    """Create one domain architect node using provider metadata for services.

    The architect node performs the following steps:
    1. Reads its task assignment from ``state["architecture_domain_tasks"][domain]``.
    2. Checks for prior validation feedback to incorporate in refinement iterations.
    3. Constructs a system prompt with the task details, constraints, and provider context.
    4. Calls the LLM with tool access (web search + RAG) to generate recommendations.
    5. Formats the output via ``format_component_recommendations`` and returns a
       partial state update that writes to ``state["architecture_components"][domain]``.

    Args:
        ctx: Runtime context with LLMs, tools, and provider metadata.
        domain: The architecture domain ("compute", "network", "storage", or "database").

    Returns:
        A LangGraph node function ``(State) -> State``.
    """

    provider = ctx.provider
    domain_services = provider.domain_services.get(domain, f"{domain} services")

    def _node(state: State) -> State:
        domain_task = state["architecture_domain_tasks"].get(domain, {})
        overall_goals = state["architecture_domain_tasks"].get("overall_goals", [])
        constraints = state["architecture_domain_tasks"].get("constraints", [])

        if not domain_task or not domain_task.get("task_description"):
            error_msg = f"No task assignment found for {domain} domain. Cannot generate architecture recommendations."
            return cast(
                State,
                {
                    "architecture_components": {
                        domain: {
                            "recommendations": error_msg,
                            "agent": f"{domain}_architect",
                            "task_info": domain_task,
                            "error": "No task assignment",
                        }
                    }
                },
            )

        validation_feedback = state.get("validation_feedback", [])
        domain_feedback = [
            fb
            for fb in validation_feedback
            if isinstance(fb, dict) and fb.get("domain", "").lower() == domain.lower()
        ]

        validation_context = ""
        if domain_feedback:
            validation_context = "\n\nPrevious Validation Feedback for this Domain:\n"
            for feedback in domain_feedback:
                result = feedback.get("validation_result", "")
                has_errors = feedback.get("has_errors", False)
                status = "HAS ERRORS" if has_errors else "PASSED"
                validation_context += f"\n[{status}]: {result[:300]}...\n"

        system_prompt = f"""
        You are an {provider.display_name} {domain.capitalize()} Domain Architect.
        Design the {domain} infrastructure based on the task.

        Original Problem: {state['user_problem']}
        Current Iteration: {state['iteration_count']}

        Your Specific Task:
        - Description: {domain_task.get('task_description', f'Design {domain} infrastructure')}
        - Requirements: {domain_task.get('requirements', [])}
        - Expected Deliverables: {domain_task.get('deliverables', [])}

        Overall Architecture Goals: {overall_goals}
        Global Constraints: {constraints}
        {validation_context}

        Design {domain} components ({domain_services}).
        Use web search if you need specific, up-to-date information.
        Provide detailed configuration recommendations.
        Focus only on the {domain} domain.

        If this is a refinement iteration, address any issues identified in the validation feedback.
        """

        messages = [SystemMessage(content=system_prompt), HumanMessage(content=state["user_problem"])]

        try:
            response = execute_tool_calls(
                messages,
                ctx.tools.llm_with_all_tools,
                {"web_search": ctx.tools.web_search, "RAG_search": ctx.tools.rag_search},
                max_iterations=ctx.settings.tool_max_iterations,
                timeout=ctx.settings.tool_timeout_seconds,
                retry_attempts=ctx.settings.llm_retry_attempts,
            )
            content = getattr(response, "content", "")
            if not content or not content.strip():
                raise ValueError(f"[{domain}_architect] Empty response from LLM")
            recommendations = format_component_recommendations(domain, domain_task, content)
        except Exception as exc:  # noqa: BLE001
            logger.error("[%s_architect] Error generating recommendations: %s", domain, exc, exc_info=True)
            recommendations = format_component_recommendations(
                domain,
                domain_task,
                f"[{domain}_architect] Error generating recommendations: {exc}",
            )

        return cast(
            State,
            {
                "architecture_components": {
                    domain: {
                        "recommendations": recommendations,
                        "agent": f"{domain}_architect",
                        "task_info": domain_task,
                    }
                }
            },
        )

    return _node


def _domain_validator(ctx: RuntimeContext, domain: str):
    """Create one domain validator node using provider metadata for checks.

    The validator node performs the following steps:
    1. Reads validation task details from ``state["architecture_domain_tasks"]["validation_tasks"][domain]``.
    2. Reads the proposed architecture components for its domain.
    3. Constructs a system prompt referencing official provider documentation checks.
    4. Calls the LLM with RAG tool access to validate against documentation.
    5. Uses ``detect_errors_llm`` to classify whether the validation result
       indicates actionable errors.
    6. Returns a partial state update with validation feedback and error flags.

    Args:
        ctx: Runtime context with LLMs, tools, and provider metadata.
        domain: The architecture domain ("compute", "network", "storage", or "database").

    Returns:
        A LangGraph node function ``(State) -> State``.
    """

    provider = ctx.provider
    validation_checks = provider.validation_checks.get(
        domain,
        "1. Service names and configurations are correct\n"
        "    2. Best practices are followed\n"
        "    3. Any factual errors or misconfigurations",
    )

    def _node(state: State) -> State:
        validation_tasks = state.get("architecture_domain_tasks", {}).get("validation_tasks", {})
        domain_validation = validation_tasks.get(domain, {})
        domain_components = state.get("architecture_components", {}).get(domain, {})

        if not domain_validation:
            return cast(
                State,
                {
                    "validation_feedback": [
                        {
                            "domain": domain,
                            "status": "skipped",
                            "reason": "No validation tasks assigned",
                            "validation_result": f"No validation tasks assigned for {domain} domain.",
                            "components_validated": [],
                            "has_errors": False,
                        }
                    ],
                    "factual_errors_exist": False,
                },
            )

        components_to_validate = domain_validation.get("components_to_validate", [])
        validation_focus = domain_validation.get("validation_focus", "general validation")
        recommendations = domain_components.get("recommendations", "")

        system_prompt = f"""
        You are a {domain} domain validator for {provider.display_name} cloud architecture.
        Your role is to validate {domain} architecture recommendations against official {provider.display_name} documentation.

        Original Problem: {state['user_problem']}

        Components to Validate: {components_to_validate}
        Validation Focus: {validation_focus}

        Proposed {domain.capitalize()} Architecture:
        {recommendations}

        Use the RAG_search tool to retrieve relevant {provider.display_name} documentation for each component.
        Validate:
        {validation_checks}

        Provide a structured validation report with:
        - Valid components (correctly configured)
        - Issues found (errors, misconfigurations, or improvements needed)
        - Recommendations for fixes or improvements
        - Confidence level in the validation
        """

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Validate these {domain} components: {', '.join(components_to_validate)}"),
        ]

        try:
            response = execute_tool_calls(
                messages,
                ctx.tools.llm_with_rag_tools,
                {"RAG_search": ctx.tools.rag_search},
                max_iterations=ctx.settings.tool_max_iterations,
                timeout=ctx.settings.tool_timeout_seconds,
                retry_attempts=ctx.settings.llm_retry_attempts,
            )
            validation_result = getattr(response, "content", "Validation completed.")
            if not validation_result or not validation_result.strip():
                validation_result = f"[{domain}_validator] Validation completed but no detailed results provided."
        except Exception as exc:  # noqa: BLE001
            validation_result = f"[{domain}_validator] Error during validation: {exc}"
            logger.error(validation_result, exc_info=True)

        has_errors = detect_errors_llm(validation_result, ctx.mini_llm)
        feedback: Dict[str, Any] = {
            "domain": domain,
            "validation_result": validation_result,
            "components_validated": components_to_validate,
            "has_errors": has_errors,
        }

        return cast(State, {"validation_feedback": [feedback], "factual_errors_exist": has_errors})

    return _node


def compute_architect(ctx: RuntimeContext):
    return _domain_architect(ctx, "compute")


def network_architect(ctx: RuntimeContext):
    return _domain_architect(ctx, "network")


def storage_architect(ctx: RuntimeContext):
    return _domain_architect(ctx, "storage")


def database_architect(ctx: RuntimeContext):
    return _domain_architect(ctx, "database")


def compute_validator(ctx: RuntimeContext):
    return _domain_validator(ctx, "compute")


def network_validator(ctx: RuntimeContext):
    return _domain_validator(ctx, "network")


def storage_validator(ctx: RuntimeContext):
    return _domain_validator(ctx, "storage")


def database_validator(ctx: RuntimeContext):
    return _domain_validator(ctx, "database")
