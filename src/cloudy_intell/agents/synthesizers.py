"""Synthesis node factories for architecture and validation stages.

All prompt text is driven by ``RuntimeContext.provider`` metadata, making
these factories provider-agnostic (AWS, Azure, GCP, etc.).
"""

import time
from typing import Any, Dict, cast

from langchain_core.messages import SystemMessage

from cloudy_intell.agents.context import RuntimeContext
from cloudy_intell.infrastructure.logging_utils import get_logger
from cloudy_intell.schemas.models import State

logger = get_logger(__name__)


def _invoke_with_retries(llm, prompt: str, node_name: str, retries: int = 3) -> str:
    """Invoke an LLM prompt with bounded retries and validated text output."""

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = llm.invoke([SystemMessage(content=prompt)])
            content = getattr(response, "content", "")
            if not isinstance(content, str) or not content.strip():
                raise ValueError(f"[{node_name}] Empty response from LLM")
            return content
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retries - 1:
                wait_time = 2**attempt
                logger.warning(
                    "%s LLM call failed (attempt %s/%s), retrying in %ss: %s",
                    node_name,
                    attempt + 1,
                    retries,
                    wait_time,
                    exc,
                )
                time.sleep(wait_time)
            else:
                logger.error("%s failed after retries: %s", node_name, exc, exc_info=True)

    return f"[{node_name}] Error: {last_error}"


def architect_synthesizer(ctx: RuntimeContext):
    """Create synthesizer that merges domain architect outputs into one proposal."""

    provider = ctx.provider

    def _node(state: State) -> State:
        all_components = state.get("architecture_components", {})
        domain_tasks = state.get("architecture_domain_tasks", {})

        special_keys = {"decomposition", "overall_goals", "constraints", "validation_tasks"}
        required_domains = sorted(k for k in domain_tasks.keys() if k not in special_keys)
        if not required_domains:
            required_domains = ["compute", "network", "storage", "database"]

        completed_domains = list(all_components.keys())
        missing_domains = [domain for domain in required_domains if domain not in completed_domains]
        if missing_domains:
            logger.warning("Missing domains in architect synthesizer: %s", missing_domains)

        component_summaries = []
        for domain, info in all_components.items():
            recommendation = str(info.get("recommendations", "No recommendations provided.")).strip()
            if not recommendation:
                recommendation = "No recommendations provided for this domain."
            component_summaries.append(f"**{domain.capitalize()} Domain:**\n{recommendation}\n")

        prompt = f"""
        You are an {provider.architect_role}.
        Synthesize specialist domain outputs into one coherent architecture proposal.

        Original Problem: {state['user_problem']}
        Current Iteration: {state['iteration_count']}
        Overall Goals: {domain_tasks.get('overall_goals', [])}
        Global Constraints: {domain_tasks.get('constraints', [])}

        Component Designs from Domain Architects:
        {"---".join(component_summaries)}

        Provide a unified architecture with:
        1. High-level architecture summary
        2. Integrated component design
        3. Key design decisions and tradeoffs
        """

        architecture_summary = _invoke_with_retries(ctx.reasoning_llm, prompt, "architect_synthesizer")
        return cast(
            State,
            {
                "proposed_architecture": {
                    "architecture_summary": architecture_summary,
                    "source_components": all_components,
                }
            },
        )

    return _node


def validation_synthesizer(ctx: RuntimeContext):
    """Create synthesizer that consolidates validator results across domains."""

    provider = ctx.provider

    def _node(state: State) -> State:
        all_validation_feedback = state.get("validation_feedback", [])
        if not all_validation_feedback:
            return cast(State, {"validation_summary": "No validation was performed."})

        validation_summaries = []
        total_errors = 0
        for feedback in all_validation_feedback:
            domain = feedback.get("domain", "unknown")
            has_errors = bool(feedback.get("has_errors", False))
            result = str(feedback.get("validation_result", ""))
            if has_errors:
                total_errors += 1
            validation_summaries.append(f"**{str(domain).capitalize()} Domain:**\n{result[:300]}...\n")

        prompt = f"""
        You are a validation synthesizer for {provider.display_name} cloud architecture.
        Consolidate all domain validation feedback into an actionable summary.

        Original Problem: {state['user_problem']}
        Current Iteration: {state['iteration_count']}

        Validation Feedback:
        {"---".join(validation_summaries)}

        Total domains with errors: {total_errors}
        Factual errors flag: {state.get('factual_errors_exist', False)}

        Include:
        1. Overall validation status
        2. Key issues across domains
        3. Priority fixes
        4. Recommendation: iterate or finalize
        """

        validation_summary = _invoke_with_retries(ctx.reasoning_llm, prompt, "validation_synthesizer")
        return cast(State, {"validation_summary": validation_summary})

    return _node


def final_architecture_generator(ctx: RuntimeContext):
    """Create node that emits the final architecture document."""

    provider = ctx.provider

    def _node(state: State) -> State:
        proposed_architecture = state.get("proposed_architecture", {})
        architecture_components = state.get("architecture_components", {})
        validation_summary = state.get("validation_summary", "")

        prompt = f"""
        You are a {provider.architect_role} finalizing a {provider.display_name} cloud architecture.
        Create a concise but production-ready final architecture document.

        Original Problem: {state['user_problem']}
        Total Iterations: {state['iteration_count']}

        Proposed Architecture:
        {proposed_architecture.get('architecture_summary', 'No summary available')}

        Architecture Components:
        {architecture_components}

        Validation Summary:
        {validation_summary}

        Structure output with:
        1. Executive summary
        2. Architecture overview
        3. Component details
        4. Security and operations
        5. Deployment guidance
        """

        final_doc = _invoke_with_retries(ctx.reasoning_llm, prompt, "final_architecture_generator")
        final_state: Dict[str, Any] = {
            "document": final_doc,
            "components": architecture_components,
            "proposed_architecture": proposed_architecture,
            "validation_summary": validation_summary,
            "iterations": state["iteration_count"],
        }

        return cast(
            State,
            {
                "final_architecture": final_state,
                "architecture_summary": final_doc,
            },
        )

    return _node


__all__ = [
    "architect_synthesizer",
    "validation_synthesizer",
    "final_architecture_generator",
]
