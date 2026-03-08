"""Application settings and provider namespacing.

The settings object centralizes all runtime configuration so modules do not
instantiate environment-dependent values directly.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Typed settings loaded from environment variables and `.env`.

    Detailed inline fields are intentionally explicit to support future
    expansion to Azure and UI integrations without changing current runtime
    behavior.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core runtime defaults
    app_name: str = "cloudy-intell"
    log_level: str = "INFO"

    # LLM models split by role so supervisor and execution paths can evolve independently.
    llm_reasoning_model: str = "gpt-5"
    llm_execution_model: str = "gpt-4o-mini"

    # Tool and retry behavior defaults.
    tool_timeout_seconds: float = 60.0
    tool_max_iterations: int = 3
    llm_retry_attempts: int = 2

    # Iteration defaults used by CLI/service.
    min_iterations_default: int = 1
    max_iterations_default: int = 3

    # Provider namespacing: AWS active now; Azure reserved for future implementation.
    providers_aws_enabled: bool = True
    providers_aws_collection_name: str = "AWSDocs"
    providers_aws_vector_path: str = "./chroma_db_AWSDocs"

    providers_azure_enabled: bool = False
    providers_azure_collection_name: str = "AzureDocs"
    providers_azure_vector_path: str = "./chroma_db_AzureDocs"

    # Embedding runtime (currently Ollama-based).
    embedding_model: str = "nomic-embed-text"

    # Optional operational metadata for future UI/session wiring.
    default_thread_id_prefix: str = "cloudy-intell"
    run_label: str = Field(default="local-run", description="Human-readable run label.")

    # LangSmith tracing configuration (off by default).
    langsmith_tracing: bool = Field(default=False, description="Enable LangSmith tracing.")
    langsmith_project: str = Field(default="cloudy-intell", description="LangSmith project name.")
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com",
        description="LangSmith API endpoint.",
    )
    langsmith_api_key: str = Field(default="", description="LangSmith API key.")


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return cached settings instance.

    Caching ensures all modules resolve one consistent settings object during
    process lifetime.
    """

    return AppSettings()
