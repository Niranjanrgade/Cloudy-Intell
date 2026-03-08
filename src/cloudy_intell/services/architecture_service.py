"""High-level orchestration service used by CLI and future APIs."""

from datetime import datetime

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
        load_dotenv(override=True)
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
    ):
        """Run architecture generation workflow and return resulting state."""

        chosen_thread_id = thread_id or (
            f"{self.settings.default_thread_id_prefix}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        )
        config = {"configurable": {"thread_id": chosen_thread_id}}
        initial_state = create_initial_state(
            user_problem=user_problem,
            min_iterations=min_iterations,
            max_iterations=max_iterations,
        )
        return self.graph.invoke(initial_state, config=config)  # type: ignore[arg-type]
