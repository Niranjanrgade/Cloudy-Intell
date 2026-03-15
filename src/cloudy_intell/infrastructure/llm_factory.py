"""LLM factory functions.

These helpers isolate model configuration and make node modules agnostic to
how model clients are instantiated.  Two distinct LLM instances are created:

- **Reasoning LLM** (gpt-5): Used by supervisors for task decomposition and
  by synthesizers for merging domain outputs.  These tasks require strong
  reasoning and structured output capabilities.

- **Execution LLM** (gpt-4o-mini): Used by domain architects and validators
  for tool-calling loops.  This model is cost-efficient for the high-volume
  tool-call interactions that domain agents perform.

Both models are configured via ``AppSettings`` so the model names can be
overridden via environment variables without code changes.
"""

from langchain_openai import ChatOpenAI

from cloudy_intell.config.settings import AppSettings


def create_reasoning_llm(settings: AppSettings) -> ChatOpenAI:
    """Create the high-reasoning model used by supervisors and synthesizers."""

    return ChatOpenAI(model=settings.llm_reasoning_model)


def create_execution_llm(settings: AppSettings) -> ChatOpenAI:
    """Create the lighter execution model used by domain node calls."""

    return ChatOpenAI(model=settings.llm_execution_model)
