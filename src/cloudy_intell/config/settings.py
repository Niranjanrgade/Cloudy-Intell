"""Application settings and provider namespacing.

The settings object centralizes all runtime configuration so modules do not
instantiate environment-dependent values directly.  It uses pydantic-settings
to automatically read values from environment variables and ``.env`` files,
providing a single source of truth for the entire application.

Key design decisions:
- Two LLM model fields (reasoning vs execution) allow independent model
  selection for supervisors/synthesizers (high capability) vs domain agents
  (cost-efficient).
- Provider-specific paths (AWS/Azure) enable per-provider ChromaDB vector
  stores without conditional logic scattered across modules.
- LangSmith settings are typed here and pushed to env vars by the service
  layer, ensuring consistent tracing configuration.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Typed settings loaded from environment variables and ``.env``.

    Detailed inline fields are intentionally explicit to support future
    expansion to Azure and UI integrations without changing current runtime
    behavior.

    Environment variables take precedence over ``.env`` file values, following
    the standard 12-factor app convention.  The ``extra = "ignore"`` config
    means unrecognized env vars are silently skipped rather than raising errors,
    which keeps the settings object compatible with shared ``.env`` files that
    may contain keys for other services (e.g. ``OPENAI_API_KEY``).
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Core runtime defaults ───────────────────────────────────────────
    app_name: str = "cloudy-intell"   # Application identifier used in logging and metadata.
    log_level: str = "INFO"           # Root logging level (DEBUG, INFO, WARNING, ERROR).

    # ── LLM models ──────────────────────────────────────────────────────
    # Split by role so supervisor (reasoning) and execution (domain agent)
    # paths can evolve independently.  Reasoning model handles complex
    # decomposition and synthesis; execution model handles tool-calling loops.
    llm_reasoning_model: str = "gpt-5"
    llm_execution_model: str = "gpt-4o-mini"

    # ── Tool and retry behavior ─────────────────────────────────────────
    tool_timeout_seconds: float = 60.0     # Max wall-clock time for a single tool-calling loop.
    tool_max_iterations: int = 3           # Max tool-call rounds before forcing a final answer.
    llm_retry_attempts: int = 2            # Retries per individual LLM invocation on transient failures.

    # ── Iteration defaults ──────────────────────────────────────────────
    # These control how many architect→validate cycles the graph executes.
    min_iterations_default: int = 1        # Minimum iterations regardless of validation outcome.
    max_iterations_default: int = 3        # Hard upper bound to prevent runaway cost.

    # ── Provider namespacing ────────────────────────────────────────────
    # Each cloud provider has its own ChromaDB collection and persist path.
    # AWS is active by default; Azure can be enabled for side-by-side or
    # comparison runs via ``provider_mode``.
    providers_aws_enabled: bool = True
    providers_aws_collection_name: str = "AWSDocs"      # ChromaDB collection containing AWS documentation embeddings.
    providers_aws_vector_path: str = "./chroma_db_AWSDocs"  # Local directory for the AWS ChromaDB on-disk store.

    providers_azure_enabled: bool = False
    providers_azure_collection_name: str = "AzureDocs"   # ChromaDB collection containing Azure documentation embeddings.
    providers_azure_vector_path: str = "./chroma_db_AzureDocs"  # Local directory for the Azure ChromaDB on-disk store.

    # ── Embedding model ─────────────────────────────────────────────────
    # Currently Ollama-based.  The embedding model is used to encode queries
    # for similarity search against the provider documentation vector stores.
    embedding_model: str = "nomic-embed-text"

    # ── Provider mode ───────────────────────────────────────────────────
    # Controls which cloud provider pipeline(s) to execute:
    #   "aws"   — Run only the AWS architecture pipeline (default).
    #   "azure" — Run only the Azure architecture pipeline.
    #   "both"  — Run both pipelines independently and return a comparison.
    provider_mode: Literal["aws", "azure", "both"] = "aws"

    # ── Operational metadata ────────────────────────────────────────────
    default_thread_id_prefix: str = "cloudy-intell"  # Prefix for auto-generated thread IDs used in checkpointing.
    run_label: str = Field(default="local-run", description="Human-readable run label for LangSmith filtering.")

    # LangSmith tracing configuration (off by default).
    langsmith_tracing: bool = Field(default=False, description="Enable LangSmith tracing.")
    langsmith_project: str = Field(default="cloudy-intell", description="LangSmith project name.")
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com",
        description="LangSmith API endpoint.",
    )
    langsmith_api_key: str = Field(default="", description="LangSmith API key.")

    # ── Provider helpers ────────────────────────────────────────────────

    def vector_path_for(self, provider: str) -> str:
        """Return the ChromaDB persist directory for the given provider."""
        if provider == "azure":
            return self.providers_azure_vector_path
        return self.providers_aws_vector_path

    def collection_name_for(self, provider: str) -> str:
        """Return the ChromaDB collection name for the given provider."""
        if provider == "azure":
            return self.providers_azure_collection_name
        return self.providers_aws_collection_name


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return cached settings instance.

    Caching ensures all modules resolve one consistent settings object during
    process lifetime.
    """

    return AppSettings()
