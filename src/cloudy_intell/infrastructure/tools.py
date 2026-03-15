"""Tool construction and tool-bound LLM helper bundle.

This module creates the two tools used by domain agents:

1. **web_search** — Google Serper API wrapper for real-time web information
   about cloud services, pricing, and configurations.
2. **RAG_search** — Retrieval-Augmented Generation tool backed by a ChromaDB
   vector store containing pre-embedded official cloud documentation.

The ``ToolBundle`` pre-binds LLMs with tool definitions once at startup,
avoiding repeated binding per invocation.  Three LLM variants are created:
- ``llm_with_all_tools``: Both web_search + RAG (used by domain architects).
- ``llm_with_web_tools``: Web search only.
- ``llm_with_rag_tools``: RAG only (used by domain validators for
  documentation-verified checking).
"""

from dataclasses import dataclass
from functools import partial

from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI

from cloudy_intell.config.provider_meta import ProviderMeta
from cloudy_intell.infrastructure.vector_store import rag_search_function


@dataclass(frozen=True)
class ToolBundle:
    """Container with tools and frequently-used LLM bindings.

    Frozen dataclass ensures immutability since this bundle is shared across
    all nodes via RuntimeContext during parallel execution.
    """

    web_search: Tool
    rag_search: Tool
    llm_with_all_tools: ChatOpenAI
    llm_with_web_tools: ChatOpenAI
    llm_with_rag_tools: ChatOpenAI


def create_tool_bundle(
    base_llm: ChatOpenAI,
    vector_store,
    provider_meta: ProviderMeta | None = None,
) -> ToolBundle:
    """Create all tools and pre-bound LLM variants.

    We pre-bind once so node execution only depends on this immutable bundle
    instead of repeatedly creating dynamic tool wrappers.

    Args:
        base_llm: The execution-tier LLM (gpt-4o-mini) to bind tools to.
        vector_store: ChromaDB vector store instance for RAG search.
        provider_meta: Optional provider metadata; when provided, the RAG
                       tool description is customized for that provider.

    Returns:
        An immutable ``ToolBundle`` with tools and pre-bound LLM instances.
    """

    serper = GoogleSerperAPIWrapper()
    tool_web_search = Tool(
        name="web_search",
        func=serper.run,
        description="Useful when you need additional web information about a query.",
    )

    rag_description = (
        provider_meta.rag_tool_description
        if provider_meta
        else (
            "Search AWS documentation vector database for accurate, up-to-date "
            "information about AWS services, configurations, and best practices."
        )
    )

    tool_rag_search = Tool(
        name="RAG_search",
        func=partial(rag_search_function, vector_store=vector_store),
        description=rag_description,
    )

    return ToolBundle(
        web_search=tool_web_search,
        rag_search=tool_rag_search,
        llm_with_all_tools=base_llm.bind_tools([tool_web_search, tool_rag_search]),
        llm_with_web_tools=base_llm.bind_tools([tool_web_search]),
        llm_with_rag_tools=base_llm.bind_tools([tool_rag_search]),
    )
