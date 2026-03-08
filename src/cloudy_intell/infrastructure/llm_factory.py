"""LLM factory functions.

These helpers isolate model configuration and make node modules agnostic to
how model clients are instantiated.
"""

from langchain_openai import ChatOpenAI

from cloudy_intell.config.settings import AppSettings


def create_reasoning_llm(settings: AppSettings) -> ChatOpenAI:
    """Create the high-reasoning model used by supervisors and synthesizers."""

    return ChatOpenAI(model=settings.llm_reasoning_model)


def create_execution_llm(settings: AppSettings) -> ChatOpenAI:
    """Create the lighter execution model used by domain node calls."""

    return ChatOpenAI(model=settings.llm_execution_model)
