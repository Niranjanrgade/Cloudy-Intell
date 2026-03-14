"""High-level orchestration service used by CLI and future APIs."""

from __future__ import annotations

from datetime import datetime
import os
from typing import Any

from dotenv import load_dotenv

from cloudy_intell.agents.context import RuntimeContext
from cloudy_intell.config.provider_meta import AWS_META, AZURE_META, ProviderMeta, ProviderName
from cloudy_intell.config.settings import AppSettings
from cloudy_intell.graph.builder import build_graph
from cloudy_intell.graph.state_init import create_initial_state
from cloudy_intell.infrastructure.checkpointer import create_checkpointer
from cloudy_intell.infrastructure.llm_factory import create_execution_llm, create_reasoning_llm
from cloudy_intell.infrastructure.logging_utils import configure_logging, get_logger
from cloudy_intell.infrastructure.tools import create_tool_bundle
from cloudy_intell.infrastructure.vector_store import create_vector_store

logger = get_logger(__name__)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _build_provider_runtime(
    settings: AppSettings,
    provider_meta: ProviderMeta,
    mini_llm,
    reasoning_llm,
):
    """Build a RuntimeContext + compiled graph for a single provider."""

    vector_store = create_vector_store(settings, provider=provider_meta.name)
    tools = create_tool_bundle(mini_llm, vector_store, provider_meta=provider_meta)
    ctx = RuntimeContext(
        settings=settings,
        mini_llm=mini_llm,
        reasoning_llm=reasoning_llm,
        tools=tools,
        provider=provider_meta,
    )
    graph = build_graph(ctx, create_checkpointer())
    return ctx, graph


class ArchitectureService:
    """Facade that builds runtime dependencies and executes the LangGraph run.

    Supports three provider modes:
    - ``aws``  — run the original AWS pipeline (default).
    - ``azure`` — run the Azure pipeline.
    - ``both`` — run both pipelines independently and return a comparison.
    """

    def __init__(self, settings: AppSettings):
        self.settings = settings
        load_dotenv(override=False)
        configure_langsmith_environment(self.settings)
        configure_logging(settings.log_level)

        mini_llm = create_execution_llm(settings)
        reasoning_llm = create_reasoning_llm(settings)

        self._graphs: dict[ProviderName, Any] = {}
        self._contexts: dict[ProviderName, RuntimeContext] = {}

        providers_to_init = self._resolve_providers()
        for provider_meta in providers_to_init:
            ctx, graph = _build_provider_runtime(settings, provider_meta, mini_llm, reasoning_llm)
            self._contexts[provider_meta.name] = ctx
            self._graphs[provider_meta.name] = graph

        # Backward-compatible: expose .ctx and .graph for aws-only callers.
        if "aws" in self._contexts:
            self.ctx = self._contexts["aws"]
            self.graph = self._graphs["aws"]
        else:
            first = next(iter(self._contexts))
            self.ctx = self._contexts[first]
            self.graph = self._graphs[first]

    def _resolve_providers(self) -> list[ProviderMeta]:
        mode = self.settings.provider_mode
        if mode == "both":
            return [AWS_META, AZURE_META]
        if mode == "azure":
            return [AZURE_META]
        return [AWS_META]

    # ── Single-provider run ─────────────────────────────────────────────

    def _run_single(
        self,
        provider: ProviderName,
        user_problem: str,
        min_iterations: int,
        max_iterations: int,
        thread_id: str | None = None,
        langsmith_project: str | None = None,
    ) -> dict[str, Any]:
        graph = self._graphs[provider]
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        chosen_thread_id = thread_id or (
            f"{self.settings.default_thread_id_prefix}-{provider}-{timestamp}"
        )
        resolved_project = langsmith_project or self.settings.langsmith_project
        if resolved_project:
            os.environ["LANGSMITH_PROJECT"] = resolved_project

        config = build_graph_run_config(
            thread_id=chosen_thread_id,
            run_label=f"{self.settings.run_label}-{provider}",
            langsmith_project=resolved_project,
        )
        initial_state = create_initial_state(
            user_problem=user_problem,
            min_iterations=min_iterations,
            max_iterations=max_iterations,
        )
        return graph.invoke(initial_state, config=config)  # type: ignore[arg-type]

    # ── Public API ──────────────────────────────────────────────────────

    def run(
        self,
        user_problem: str,
        min_iterations: int,
        max_iterations: int,
        thread_id: str | None = None,
        langsmith_project: str | None = None,
    ):
        """Run architecture workflow for configured provider(s).

        Returns a single-provider result dict when mode is ``aws`` or
        ``azure``, or a comparison envelope ``{aws_result, azure_result,
        comparison_summary}`` when mode is ``both``.
        """

        mode = self.settings.provider_mode

        if mode in ("aws", "azure"):
            return self._run_single(
                provider=mode,  # type: ignore[arg-type]
                user_problem=user_problem,
                min_iterations=min_iterations,
                max_iterations=max_iterations,
                thread_id=thread_id,
                langsmith_project=langsmith_project,
            )

        # ── "both" mode ────────────────────────────────────────────────
        results: dict[str, Any] = {}
        for provider_name in ("aws", "azure"):
            if provider_name not in self._graphs:
                continue
            logger.info("Running %s pipeline…", provider_name.upper())
            results[f"{provider_name}_result"] = self._run_single(
                provider=provider_name,  # type: ignore[arg-type]
                user_problem=user_problem,
                min_iterations=min_iterations,
                max_iterations=max_iterations,
                thread_id=f"{thread_id or ''}-{provider_name}" if thread_id else None,
                langsmith_project=langsmith_project,
            )

        results["comparison_summary"] = _build_comparison_summary(results)
        return results


def _build_comparison_summary(results: dict[str, Any]) -> str:
    """Build a textual side-by-side comparison from two provider results."""

    sections: list[str] = ["# Cloud Architecture Comparison: AWS vs Azure\n"]

    for provider_key, label in [("aws_result", "AWS"), ("azure_result", "Azure")]:
        result = results.get(provider_key)
        if not result:
            sections.append(f"## {label}\n_No result available._\n")
            continue
        summary = (
            result.get("architecture_summary")
            or (result.get("final_architecture") or {}).get("document")
            or "No summary available."
        )
        iterations = result.get("iteration_count", "?")
        sections.append(f"## {label} (iterations: {iterations})\n{summary}\n")

    sections.append("---\n_Comparison generated automatically. Review each provider result for full details._")
    return "\n".join(sections)


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
