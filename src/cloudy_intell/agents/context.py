"""Runtime context passed to node factories.

This keeps module functions pure-ish and prevents hidden global coupling.
Every graph node factory receives a ``RuntimeContext`` instance and closes
over it, so all dependencies (LLMs, tools, settings, provider metadata) are
explicit rather than imported from global singletons.

The frozen dataclass ensures the context is immutable after construction,
which is critical because multiple domain nodes read it concurrently during
parallel fan-out execution.
"""

from dataclasses import dataclass

from langchain_openai import ChatOpenAI

from cloudy_intell.config.provider_meta import ProviderMeta
from cloudy_intell.config.settings import AppSettings
from cloudy_intell.infrastructure.tools import ToolBundle


@dataclass(frozen=True)
class RuntimeContext:
    """Immutable runtime dependencies shared across graph node closures.

    Attributes:
        settings: Application configuration (iteration bounds, model names, etc.).
        mini_llm: Lightweight LLM instance (gpt-4o-mini) used for tool-calling
                  loops in domain agents and error detection classification.
        reasoning_llm: High-capability LLM instance (gpt-5) used by supervisors
                       for task decomposition and by synthesizers for merging outputs.
        tools: Pre-built ``ToolBundle`` containing web search, RAG search, and
               LLM instances pre-bound to those tools for immediate invocation.
        provider: Cloud provider metadata (AWS_META or AZURE_META) that drives
                  all provider-specific prompt content.
    """

    settings: AppSettings
    mini_llm: ChatOpenAI
    reasoning_llm: ChatOpenAI
    tools: ToolBundle
    provider: ProviderMeta
