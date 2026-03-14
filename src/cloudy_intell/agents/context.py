"""Runtime context passed to node factories.

This keeps module functions pure-ish and prevents hidden global coupling.
"""

from dataclasses import dataclass

from langchain_openai import ChatOpenAI

from cloudy_intell.config.provider_meta import ProviderMeta
from cloudy_intell.config.settings import AppSettings
from cloudy_intell.infrastructure.tools import ToolBundle


@dataclass(frozen=True)
class RuntimeContext:
    """Immutable runtime dependencies shared across graph node closures."""

    settings: AppSettings
    mini_llm: ChatOpenAI
    reasoning_llm: ChatOpenAI
    tools: ToolBundle
    provider: ProviderMeta
