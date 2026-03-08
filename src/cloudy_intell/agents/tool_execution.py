"""Shared tool execution and formatting helpers for node modules."""

import time
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import Tool

from cloudy_intell.infrastructure.logging_utils import get_logger

logger = get_logger(__name__)


def format_component_recommendations(domain_name: str, task_info: Dict[str, Any], generated_text: Optional[str]) -> str:
    """Return architect output or a deterministic fallback skeleton.

    This avoids empty component sections propagating through synthesis when the
    model produces empty content due to tool failures or retries.
    """

    if generated_text and generated_text.strip():
        return generated_text.strip()

    requirements = task_info.get("requirements", []) or []
    deliverables = task_info.get("deliverables", []) or []
    sections = [
        f"### {domain_name.capitalize()} Domain Recommendations",
        f"Task focus: {task_info.get('task_description', 'No task description provided.')}",
    ]

    if requirements:
        sections.append("Key requirements covered:")
        sections.extend(f"- {item}" for item in requirements)

    if deliverables:
        sections.append("Planned deliverables:")
        sections.extend(f"- {item}" for item in deliverables)

    sections.append("(Generated text unavailable; using structured fallback.)")
    return "\n".join(sections)


def execute_tool_calls(
    messages: List,
    llm_with_tools,
    tools: Dict[str, Tool],
    max_iterations: int = 3,
    timeout: Optional[float] = 60.0,
    retry_attempts: int = 2,
) -> AIMessage:
    """Execute iterative tool-calling loop with bounded retries.

    The loop is intentionally defensive because either model invocation or tool
    invocation can fail transiently (network/API/tool runtime issues).
    """

    tool_iterations = 0
    final_response = None
    start_time = time.time()
    failed_tools: List[str] = []

    try:
        while tool_iterations < max_iterations:
            if timeout and (time.time() - start_time) > timeout:
                logger.warning("Tool execution timeout after %ss", timeout)
                break

            response = None
            last_error = None
            for attempt in range(retry_attempts + 1):
                try:
                    response = llm_with_tools.invoke(messages)
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    if attempt < retry_attempts:
                        wait_time = 2**attempt
                        logger.warning(
                            "LLM invocation failed (attempt %s/%s), retrying in %ss: %s",
                            attempt + 1,
                            retry_attempts + 1,
                            wait_time,
                            exc,
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error("LLM invocation failed after retries: %s", exc)

            if response is None:
                error_msg = f"Failed to get LLM response after {retry_attempts + 1} attempts"
                if last_error:
                    error_msg += f": {last_error}"
                return AIMessage(content=f"Error: {error_msg}")

            if not response or not hasattr(response, "content"):
                logger.warning("Empty or invalid LLM response at iteration %s", tool_iterations)
                break

            if hasattr(response, "tool_calls") and response.tool_calls:
                messages.append(response)
                tool_failures_in_iteration: List[str] = []

                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    if tool_name not in tools:
                        messages.append(
                            ToolMessage(content=f"Unknown tool: {tool_name}", tool_call_id=tool_call["id"])
                        )
                        continue

                    try:
                        tool_args = tool_call.get("args", {})
                        if not isinstance(tool_args, dict):
                            tool_args = {"query": str(tool_args)} if tool_args else {}
                        tool_result = tools[tool_name].invoke(tool_args)
                        messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_call["id"]))
                    except Exception as exc:  # noqa: BLE001
                        error_msg = f"Error executing tool {tool_name}: {exc}"
                        logger.error(error_msg)
                        failed_tools.append(tool_name)
                        tool_failures_in_iteration.append(tool_name)
                        messages.append(ToolMessage(content=error_msg, tool_call_id=tool_call["id"]))

                if tool_failures_in_iteration:
                    messages.append(
                        SystemMessage(
                            content=(
                                "Warning: The following tools failed: "
                                f"{', '.join(tool_failures_in_iteration)}. "
                                "Please proceed with available information."
                            )
                        )
                    )

                tool_iterations += 1
            else:
                final_response = response
                break

        if final_response is None:
            if messages and isinstance(messages[-1], AIMessage):
                final_response = messages[-1]
            else:
                details = f"Tool execution incomplete after {tool_iterations} iterations."
                if failed_tools:
                    details += f" Failed tools: {', '.join(sorted(set(failed_tools)))}"
                final_response = AIMessage(content=details)

        return final_response
    except Exception as exc:  # noqa: BLE001
        logger.error("Critical error in execute_tool_calls: %s", exc, exc_info=True)
        return AIMessage(content=f"Error: Tool execution failed: {exc}")


def detect_errors_llm(validation_result: str, mini_llm) -> bool:
    """Use model-based classification for YES/NO validation-error detection."""

    try:
        max_length = 1000
        if len(validation_result) > max_length:
            first_part = validation_result[:700]
            last_part = validation_result[-300:]
            truncated_result = (
                f"{first_part}\n\n[... {len(validation_result) - max_length} characters omitted ...]\n\n{last_part}"
            )
        else:
            truncated_result = validation_result

        prompt = f"""
        Analyze this validation result and determine if it indicates any errors, issues, or problems that need to be fixed.

        Validation Result:
        {truncated_result}

        Respond with ONLY the word "YES" if there are errors/issues that need fixing, or ONLY the word "NO" if everything is valid.
        Do not include any other text in your response.
        """

        response = mini_llm.invoke([SystemMessage(content=prompt)])
        result_text = str(getattr(response, "content", "")).strip().upper()

        if result_text.startswith("YES"):
            return True
        if result_text.startswith("NO"):
            return False

        strong = ["error", "incorrect", "invalid", "misconfiguration", "wrong", "needs fix"]
        weak = ["problem", "should be", "issue", "fix", "improve"]
        strong_count = sum(1 for keyword in strong if keyword in validation_result.lower())
        weak_count = sum(1 for keyword in weak if keyword in validation_result.lower())
        return strong_count >= 1 or weak_count >= 2
    except Exception as exc:  # noqa: BLE001
        logger.warning("Error in LLM-based error detection, fallback to keyword matching: %s", exc)
        strong = ["error", "incorrect", "invalid", "misconfiguration", "wrong", "needs fix"]
        weak = ["problem", "should be", "issue", "fix", "improve"]
        strong_count = sum(1 for keyword in strong if keyword in validation_result.lower())
        weak_count = sum(1 for keyword in weak if keyword in validation_result.lower())
        return strong_count >= 1 or weak_count >= 2
