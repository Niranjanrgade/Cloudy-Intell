# Cloudy-Intell

Cloudy-Intell is a multi-agent architecture generation workflow built on LangGraph.
It decomposes a cloud design problem into domain-specific architect/validator tasks,
synthesizes recommendations, and iterates until validation converges.

## Current Scope

- Backend restructuring from notebook-style monolith to standard `src/` package.
- AWS-oriented architecture generation and validation flow.
- Detailed inline code comments and modular separation for maintainability.

Deferred by design:

- Azure provider implementation.
- CopilotKit UI integration.

## Project Structure

```text
src/cloudy_intell/
	agents/            # Supervisor, domain, synthesis node factories
	config/            # Typed app settings and provider namespacing
	graph/             # Graph builder, routing, state initialization
	infrastructure/    # LLM/tools/vector-store/checkpointer factories
	schemas/           # Pydantic contracts + LangGraph state contract
	services/          # High-level orchestration facade
	cli.py             # Command-line entrypoint
Development/
	CloudyIntel.py     # Legacy notebook-style reference implementation
tests/
	...                # Reducer/routing/state tests
```

## Quick Start

1. Install dependencies:

```bash
uv sync --extra dev
```

2. Provide required environment variables in `.env`.

3. Run CLI:

```bash
uv run cloudy-intell "Guidance for Building a Containerized and Scalable Web Application on AWS" --min-iterations 2 --max-iterations 3
```

4. Print only final architecture section:

```bash
uv run cloudy-intell "Design a secure, scalable three-tier web app" --print-final-only
```

## LangSmith Studio Setup

Cloudy-Intell supports LangSmith tracing for LangGraph/LLM execution visibility.

1. Add these values to `.env` (or export them in your shell):

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<your-langsmith-api-key>
LANGSMITH_PROJECT=cloudy-intell
# Optional, default shown below:
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

2. Run the CLI normally, or override project per run:

```bash
uv run cloudy-intell "Design a secure VPC and Kubernetes platform" --langsmith-project cloudy-intell-dev
```

3. Open LangSmith Studio and verify:

- The run appears under the expected project.
- The run name is prefixed with your configured `run_label`.
- Node/tool/LLM spans are present for each iteration.

Notes:

- Shell environment variables take precedence over `.env` values.
- Tracing is disabled by default unless `LANGSMITH_TRACING=true`.

## LangGraph Dev Server

This repo includes `langgraph.json` and a graph entrypoint at `langgraph_app.py`
for local studio testing.

Run:

```bash
langgraph dev
```

If the command is not installed globally, use:

```bash
uvx --from langgraph-cli langgraph dev
```

Before launching, ensure `.env` has your OpenAI and LangSmith variables.

## Dev Commands

```bash
uv run ruff check .
uv run mypy src
uv run pytest
```

## Migration Notes

- The source of truth for old behavior is still `Development/CloudyIntel.py`.
- New implementation is modularized under `src/cloudy_intell/`.
- During migration validation, compare iteration behavior and final state fields.