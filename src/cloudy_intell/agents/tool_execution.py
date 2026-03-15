"""Shared tool execution and formatting helpers for node modules.

This module provides the core tool-calling loop used by all domain architect
and validator agents.  When an LLM response contains tool calls (e.g. to
web_search or RAG_search), ``execute_tool_calls`` handles the full cycle:

1. Invoke the LLM and check the response for tool_calls.
2. For each tool call, look up the tool by name, invoke it, and append the
   result as a ``ToolMessage`` to the conversation.
3. Re-invoke the LLM with the updated conversation so it can use the tool
   results to generate a final answer.
4. Repeat until the LLM produces a response without tool calls, or the
   iteration/timeout limit is reached.

This loop is bounded by ``max_iterations`` and ``timeout`` to prevent runaway
cost.  Individual LLM invocations are retried with exponential backoff via
``retry_attempts``.

Also provides ``detect_errors_llm`` which uses a lightweight LLM call to
classify whether a validation result contains actionable errors, with a
keyword-based fallback if the LLM call fails.
"""

import time
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import Tool

from cloudy_intell.infrastructure.logging_utils import get_logger

logger = get_logger(__name__)


def format_component_recommendations(domain_name: str, task_info: Dict[str, Any], generated_text: Optional[str]) -> str:
    """Return architect output or a deterministic fallback skeleton.

    This avoids empty component sections propagating through synthesis when the
    model produces empty content due to tool failures or retries.  If the LLM
    returned valid text, it is returned as-is.  Otherwise, a structured fallback
    is generated from the task_info (requirements and deliverables) so downstream
    nodes always have something meaningful to work with.
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

    Execution flow:
    1. Invoke the LLM (with retry on failure).
    2. If the response contains tool_calls, execute each tool and add results
       as ToolMessages to the conversation history.
    3. Re-invoke the LLM with the updated history.
    4. Repeat until: (a) the LLM responds without tool calls (final answer),
       (b) max_iterations reached, or (c) timeout exceeded.

    If tools fail, a SystemMessage warning is injected so the LLM can adapt
    its response based on available information.  The function always returns
    an AIMessage, even on complete failure, to prevent graph crashes.

    Args:
        messages: Conversation history (system prompt + user message).
        llm_with_tools: LLM instance pre-bound with tool definitions.
        tools: Dict mapping tool names to callable Tool instances.
        max_iterations: Maximum number of tool-call rounds.
        timeout: Wall-clock timeout in seconds for the entire loop.
        retry_attempts: Retries per individual LLM invocation.

    Returns:
        The final AIMessage containing the LLM's answer.
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
    """Use model-based classification for YES/NO validation-error detection.

    This function determines whether a validation result contains actionable
    errors that should trigger another architect→validate iteration.

    Strategy:
    1. Truncate the validation result to ~1000 chars to avoid prompt bloat.
    2. Ask the lightweight LLM (gpt-4o-mini) a simple YES/NO question.
    3. Parse the response for YES or NO.
    4. If the LLM response is ambiguous, fall back to keyword counting:
       - Strong error indicators: "error", "incorrect", "invalid", etc.
       - Weak indicators: "problem", "should be", "issue", etc.
       - Returns True if ≥1 strong match or ≥2 weak matches.
    5. If the LLM call fails entirely, use the same keyword fallback.

    Args:
        validation_result: The full text output from a domain validator.
        mini_llm: Lightweight LLM instance for classification.

    Returns:
        True if errors/issues requiring fixes were detected, False otherwise.
    """

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
