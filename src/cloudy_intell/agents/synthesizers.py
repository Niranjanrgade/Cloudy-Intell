"""Synthesizer and iteration-control node factories."""

import time
from typing import cast

from langchain_core.messages import SystemMessage

from cloudy_intell.agents.context import RuntimeContext
from cloudy_intell.infrastructure.logging_utils import get_logger
from cloudy_intell.schemas.models import State

logger = get_logger(__name__)


def architect_synthesizer(ctx: RuntimeContext):
    """Create architecture synthesis node."""

    def _node(state: State) -> State:
        all_components = state.get("architecture_components", {})
        domain_tasks = state.get("architecture_domain_tasks", {})
        special_keys = {"decomposition", "overall_goals", "constraints", "validation_tasks"}
        required_domains = sorted([k for k in domain_tasks.keys() if k not in special_keys])
        if not required_domains:
            required_domains = ["compute", "network", "storage", "database"]

        completed_domains = list(all_components.keys())
        missing_domains = [domain for domain in required_domains if domain not in completed_domains]
        if missing_domains:
            logger.warning("Missing domains in synthesizer: %s", missing_domains)

        summaries = []
        for domain, info in all_components.items():
            recommendation = info.get("recommendations", "No recommendations provided.")
            if not recommendation.strip():
                recommendation = "No recommendations provided for this domain."
            summaries.append(f"**{domain.capitalize()} Domain:**\\n{recommendation}\\n")

        system_prompt = f"""
        You are an AWS Principal Solutions Architect.
        You have received architecture designs from your domain specialist architects.
        Your job is to synthesize these components into a single, coherent, and final architecture proposal.

        Original Problem: {state['user_problem']}
        Overall Goals: {state['architecture_domain_tasks'].get('overall_goals', [])}
        Global Constraints: {state['architecture_domain_tasks'].get('constraints', [])}

        Component Designs from Domain Architects:
        {'---'.join(summaries)}

        Synthesize all these pieces into a final, unified architecture.
        Ensure the components work together.
        Provide a high-level summary and then the detailed, integrated design.
        """

        try:
            response = None
            for attempt in range(3):
                try:
                    response = ctx.reasoning_llm.invoke([SystemMessage(content=system_prompt)])
                    break
                except Exception as exc:  # noqa: BLE001
                    if attempt < 2:
                        time.sleep(2**attempt)
                    else:
                        raise exc

            if not response or not getattr(response, "content", ""):
                raise ValueError("Empty response from architect synthesizer")
            architecture_summary = response.content
        except Exception as exc:  # noqa: BLE001
            architecture_summary = f"[architect_synthesizer] Error synthesizing architecture: {exc}"
            logger.error(architecture_summary, exc_info=True)

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
    """Create validation synthesis node."""

    def _node(state: State) -> State:
        all_feedback = state.get("validation_feedback", [])
        if not all_feedback:
            return cast(State, {"validation_summary": "No validation was performed."})

        summaries = []
        total_errors = 0
        for feedback in all_feedback:
            domain = feedback.get("domain", "unknown")
            has_errors = feedback.get("has_errors", False)
            result = feedback.get("validation_result", "")
            if has_errors:
                total_errors += 1
            summaries.append(f"**{domain.capitalize()} Domain:**\\n{result[:300]}...\\n")

        system_prompt = f"""
        You are a validation synthesizer for AWS cloud architecture.
        Your role is to synthesize validation feedback from all domain validators into a comprehensive summary.

        Original Problem: {state['user_problem']}
        Current Iteration: {state['iteration_count']}

        Validation Feedback from All Domains:
        {'---'.join(summaries)}

        Total Domains with Errors: {total_errors}
        Factual Errors Detected: {state.get('factual_errors_exist', False)}

        Synthesize all validation feedback into a clear, actionable summary that includes:
        1. Overall validation status
        2. Key issues found across all domains
        3. Priority of fixes needed
        4. Recommendations for the next iteration (if errors exist)
        5. Confidence in the architecture (if no errors)
        """

        try:
            response = None
            for attempt in range(3):
                try:
                    response = ctx.reasoning_llm.invoke([SystemMessage(content=system_prompt)])
                    break
                except Exception as exc:  # noqa: BLE001
                    if attempt < 2:
                        time.sleep(2**attempt)
                    else:
                        raise exc

            if not response or not getattr(response, "content", ""):
                raise ValueError("Empty response from validation synthesizer")
            summary = response.content
        except Exception as exc:  # noqa: BLE001
            summary = f"[validation_synthesizer] Error synthesizing validation: {exc}"
            logger.error(summary, exc_info=True)

        return cast(State, {"validation_summary": summary})

    return _node


def iteration_condition(state: State) -> str:
    """Route to either another iteration or final generation.

    Routing is intentionally strict and easy to test because iteration logic is
    the primary control mechanism for quality refinement.
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


def final_architecture_generator(ctx: RuntimeContext):
    """Create final architecture document generation node."""

    def _node(state: State) -> State:
        proposed_architecture = state.get("proposed_architecture", {})
        architecture_components = state.get("architecture_components", {})
        validation_summary = state.get("validation_summary", "")

        system_prompt = f"""
        You are a Principal Solutions Architect finalizing an AWS cloud architecture.
        Your role is to create a comprehensive, production-ready architecture document.

        Original Problem: {state['user_problem']}
        Total Iterations: {state['iteration_count']}

        Final Proposed Architecture:
        {proposed_architecture.get('architecture_summary', 'No summary available')}

        Architecture Components:
        {architecture_components}

        Validation Summary:
        {validation_summary}

        Create a final, comprehensive architecture document that includes:
        1. Executive Summary
        2. Architecture Overview
        3. Detailed Component Specifications
        4. Integration Points
        5. Security Considerations
        6. Cost Optimization Recommendations
        7. Deployment Strategy
        8. Monitoring and Operations

        Ensure the document is production-ready and actionable.
        """

        try:
            response = None
            for attempt in range(3):
                try:
                    response = ctx.reasoning_llm.invoke([SystemMessage(content=system_prompt)])
                    break
                except Exception as exc:  # noqa: BLE001
                    if attempt < 2:
                        time.sleep(2**attempt)
                    else:
                        raise exc

            if not response or not getattr(response, "content", ""):
                raise ValueError("Empty response from final architecture generator")
            final_doc = response.content
        except Exception as exc:  # noqa: BLE001
            final_doc = f"[final_architecture_generator] Error generating final architecture: {exc}"
            logger.error(final_doc, exc_info=True)

        return cast(
            State,
            {
                "final_architecture": {
                    "document": final_doc,
                    "components": architecture_components,
                    "proposed_architecture": proposed_architecture,
                    "validation_summary": validation_summary,
                    "iterations": state["iteration_count"],
                },
                "architecture_summary": final_doc,
            },
        )

    return _node
