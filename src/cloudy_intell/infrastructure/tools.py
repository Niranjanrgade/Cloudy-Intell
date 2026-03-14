"""Tool construction and tool-bound LLM helper bundle."""

from dataclasses import dataclass
from functools import partial

from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI

from cloudy_intell.config.provider_meta import ProviderMeta
from cloudy_intell.infrastructure.vector_store import rag_search_function


@dataclass(frozen=True)
class ToolBundle:
    """Container with tools and frequently-used LLM bindings."""

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
