"""LangGraph dev/studio entrypoint.

This module exposes a compiled graph object so `langgraph dev` can discover
and run the workflow directly from repository configuration.
"""

from dotenv import load_dotenv

from cloudy_intell.agents.context import RuntimeContext
from cloudy_intell.config.provider_meta import AWS_META
from cloudy_intell.config.settings import get_settings
from cloudy_intell.graph.builder import build_graph
from cloudy_intell.infrastructure.llm_factory import create_execution_llm, create_reasoning_llm
from cloudy_intell.infrastructure.logging_utils import configure_logging
from cloudy_intell.infrastructure.tools import create_tool_bundle
from cloudy_intell.infrastructure.vector_store import create_vector_store
from cloudy_intell.services.architecture_service import configure_langsmith_environment


def build_runtime_graph():
    """Build compiled graph for LangGraph Studio and local dev server."""

    # Keep env precedence aligned with service runtime behavior.
    load_dotenv(override=False)
    settings = get_settings()
    configure_langsmith_environment(settings)
    configure_logging(settings.log_level)

    mini_llm = create_execution_llm(settings)
    reasoning_llm = create_reasoning_llm(settings)
    vector_store = create_vector_store(settings, provider="aws")
    tools = create_tool_bundle(mini_llm, vector_store, provider_meta=AWS_META)

    ctx = RuntimeContext(
        settings=settings,
        mini_llm=mini_llm,
        reasoning_llm=reasoning_llm,
        tools=tools,
        provider=AWS_META,
    )
    # LangGraph API dev mode manages persistence automatically.
    return build_graph(ctx)


# LangGraph CLI loads this symbol from langgraph.json.
graph = build_runtime_graph()
