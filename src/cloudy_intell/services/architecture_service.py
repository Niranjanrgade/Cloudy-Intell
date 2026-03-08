"""High-level orchestration service used by CLI and future APIs."""

from datetime import datetime
import os
from typing import Any

from dotenv import load_dotenv

from cloudy_intell.agents.context import RuntimeContext
from cloudy_intell.config.settings import AppSettings
from cloudy_intell.graph.builder import build_graph
from cloudy_intell.graph.state_reducers import create_initial_state
from cloudy_intell.infrastructure.checkpointer import create_checkpointer
from cloudy_intell.infrastructure.llm_factory import create_execution_llm, create_reasoning_llm
from cloudy_intell.infrastructure.logging_utils import configure_logging
from cloudy_intell.infrastructure.tools import create_tool_bundle
from cloudy_intell.infrastructure.vector_store import create_vector_store


class ArchitectureService:
    """Facade that builds runtime dependencies and executes the LangGraph run."""

    def __init__(self, settings: AppSettings):
        self.settings = settings
        # Preserve shell-provided values; `.env` is used as local fallback.
        load_dotenv(override=False)
        configure_langsmith_environment(self.settings)
        configure_logging(settings.log_level)

        mini_llm = create_execution_llm(settings)
        reasoning_llm = create_reasoning_llm(settings)
        vector_store = create_vector_store(settings)
        tools = create_tool_bundle(mini_llm, vector_store)

        self.ctx = RuntimeContext(
            settings=settings,
            mini_llm=mini_llm,
            reasoning_llm=reasoning_llm,
            tools=tools,
        )
        self.graph = build_graph(self.ctx, create_checkpointer())

    def run(
        self,
        user_problem: str,
        min_iterations: int,
        max_iterations: int,
        thread_id: str | None = None,
        langsmith_project: str | None = None,
    ):
        """Run architecture generation workflow and return resulting state."""

        chosen_thread_id = thread_id or (
            f"{self.settings.default_thread_id_prefix}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        )
        resolved_project = langsmith_project or self.settings.langsmith_project
        if resolved_project:
            os.environ["LANGSMITH_PROJECT"] = resolved_project

        config = build_graph_run_config(
            thread_id=chosen_thread_id,
            run_label=self.settings.run_label,
            langsmith_project=resolved_project,
        )
        initial_state = create_initial_state(
            user_problem=user_problem,
            min_iterations=min_iterations,
            max_iterations=max_iterations,
        )
        return self.graph.invoke(initial_state, config=config)  # type: ignore[arg-type]

def build_graph_run_config(thread_id: str, run_label: str, langsmith_project: str) -> dict[str, Any]:
    """Create invoke config with stable metadata for LangSmith Studio filtering."""

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return {
        "configurable": {"thread_id": thread_id},
        "run_name": f"{run_label}-{timestamp}",
        "tags": ["cloudy-intell", run_label],
        "metadata": {
            "thread_id": thread_id,
            "run_label": run_label,
            "langsmith_project": langsmith_project,
        },
    }


def configure_langsmith_environment(settings: AppSettings) -> None:
    """Set LangSmith env vars from typed settings for consistent runtime behavior."""

    os.environ["LANGSMITH_TRACING"] = "true" if settings.langsmith_tracing else "false"
    if settings.langsmith_project:
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    if settings.langsmith_endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        # Keep compatibility for stacks expecting LANGCHAIN_API_KEY.
        os.environ.setdefault("LANGCHAIN_API_KEY", settings.langsmith_api_key)
