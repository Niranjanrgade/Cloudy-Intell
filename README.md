# Cloudy-Intell

Cloudy-Intell is a multi-agent cloud architecture generation and validation system built on [LangGraph](https://langchain-ai.github.io/langgraph/).  It uses an **Evaluator-Optimizer** pattern where specialized AI agents decompose a cloud design problem into domain-specific tasks, generate architecture recommendations, validate them against official cloud documentation, and iteratively refine the design until convergence.

## Overview

Given a user's cloud architecture problem (e.g. *"Design a secure, scalable three-tier web app on AWS"*), the system:

1. **Decomposes** the problem into four domain-specific tasks (compute, network, storage, database) via an architect supervisor agent.
2. **Generates** detailed infrastructure recommendations for each domain in parallel using domain architect agents equipped with web search and RAG tools.
3. **Synthesizes** the four domain outputs into a unified architecture proposal.
4. **Validates** each domain's recommendations against official cloud provider documentation via RAG-powered validator agents.
5. **Iterates** if validation errors are found, looping back to step 1 with feedback, up to a configurable maximum number of iterations.
6. **Produces** a polished, production-ready architecture document once validation converges.

The system supports **AWS**, **Azure**, or **both** providers simultaneously, with automatic side-by-side comparison when running in dual-provider mode.

## Architecture

### Backend (Python / LangGraph)

```
src/cloudy_intell/
├── agents/                 # Agent node factories
│   ├── context.py          # RuntimeContext — immutable dependency container
│   ├── domain_nodes.py     # Domain architect and validator node factories
│   ├── supervisors.py      # Architect and validator supervisor nodes
│   ├── synthesizers.py     # Fan-in synthesis nodes (architect, validation, final)
│   └── tool_execution.py   # Tool-calling loop with retry logic and error detection
├── config/                 # Configuration
│   ├── provider_meta.py    # Cloud provider metadata (AWS/Azure services, validation checks)
│   └── settings.py         # Typed application settings from env vars / .env file
├── graph/                  # LangGraph assembly
│   ├── builder.py          # Top-level graph: architect_phase → validator_phase → conditional → END
│   ├── routing.py          # Iteration decision logic (iterate vs finish)
│   ├── state_init.py       # Initial state factory with all field defaults
│   └── subgraphs.py        # Subgraph builders (supervisor → 4 parallel agents → synthesizer)
├── infrastructure/         # External integrations
│   ├── checkpointer.py     # LangGraph MemorySaver checkpointer factory
│   ├── llm_factory.py      # ChatOpenAI factory (reasoning model + execution model)
│   ├── logging_utils.py    # Centralized logging configuration
│   ├── tools.py            # Web search (Google Serper) + RAG tool bundle
│   └── vector_store.py     # ChromaDB vector store for RAG document retrieval
├── schemas/                # Data contracts
│   └── models.py           # Pydantic models + LangGraph State TypedDict with reducers
├── services/               # High-level orchestration
│   └── architecture_service.py  # ArchitectureService facade (CLI/API entrypoint)
├── cli.py                  # Command-line interface
└── langgraph_app.py        # LangGraph dev/studio entrypoint
```

### Frontend (Next.js / React)

```
UI/
├── app/
│   ├── page.tsx                    # Main layout (sidebar + workflow graph + chat)
│   └── api/
│       ├── threads/route.ts        # POST — create LangGraph thread
│       ├── threads/[threadId]/state/route.ts  # GET — fetch final graph state
│       └── runs/stream/route.ts    # POST — stream run via SSE
├── components/
│   ├── WorkflowGraph.tsx           # React Flow visualization of the agent pipeline
│   ├── CopilotSidebar.tsx          # Chat interface with real-time status updates
│   ├── CompareView.tsx             # Side-by-side AWS vs Azure comparison
│   ├── SidebarNavigator.tsx        # Left navigation (AWS / Azure / Compare)
│   ├── nodes/                      # Custom React Flow node types
│   │   ├── AgentNode.tsx           # Purple agent nodes with status indicators
│   │   ├── ToolNode.tsx            # Dashed-border tool nodes
│   │   ├── DecisionNode.tsx        # Diamond validation decision node
│   │   └── StartEndNode.tsx        # Rounded start/end nodes
│   └── edges/
│       └── FarRightEdge.tsx        # Custom edge for iteration loop routing
├── hooks/
│   └── useRunOrchestration.ts      # Orchestrates thread → stream → state lifecycle
└── lib/
    ├── graph.config.ts             # Node positions, edge definitions, layout helpers
    ├── node-mapping.ts             # Backend → UI node ID resolution
    ├── langgraph-client.ts         # LangGraph SDK client factory
    ├── types.ts                    # TypeScript interfaces mirroring backend State
    ├── compare.config.ts           # Domain icons and default fallback descriptions
    └── utils.ts                    # Tailwind CSS utility (cn)
```

### Workflow Graph Topology

```
START
  │
  ▼
architect_phase (subgraph)
  ├─ architect_supervisor ──► decomposes problem into domain tasks
  ├─ compute_architect ─┐
  ├─ network_architect  ├──► 4 domain agents run in parallel (web search + RAG tools)
  ├─ storage_architect  │
  ├─ database_architect ┘
  └─ architect_synthesizer ──► merges domain outputs into unified proposal
  │
  ▼
validator_phase (subgraph)
  ├─ validator_supervisor ──► creates validation assignments per domain
  ├─ compute_validator ─┐
  ├─ network_validator  ├──► 4 validators run in parallel (RAG tool for doc-checking)
  ├─ storage_validator  │
  ├─ database_validator ┘
  └─ validation_synthesizer ──► consolidates feedback, sets error flags
  │
  ▼
iteration_condition
  ├─ "iterate" ──► architect_phase  (if errors exist AND iteration < max)
  └─ "finish"  ──► final_architecture_generator ──► END
```

## Prerequisites

- **Python 3.11+** with [uv](https://docs.astral.sh/uv/) package manager
- **Node.js 18+** with npm (for the UI)
- **Ollama** running locally with the `nomic-embed-text` embedding model
- **OpenAI API key** for LLM calls (GPT-5 reasoning, GPT-4o-mini execution)
- **Google Serper API key** for web search tool
- **ChromaDB vector stores** pre-built with AWS/Azure documentation embeddings

## Quick Start

### 1. Install dependencies

```bash
# Backend
uv sync --extra dev

# Frontend
cd UI && npm install
```

### 2. Configure environment

Create a `.env` file in the project root:

```bash
# Required
OPENAI_API_KEY=<your-openai-api-key>
SERPER_API_KEY=<your-serper-api-key>

# Optional — LangSmith tracing
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<your-langsmith-api-key>
LANGSMITH_PROJECT=cloudy-intell

# Optional — provider mode
PROVIDER_MODE=aws   # "aws" | "azure" | "both"
```

### 3. Run via CLI

```bash
# Basic run (AWS, default iterations)
uv run cloudy-intell --problem "Design a containerized web app on AWS" --provider aws

# With iteration control
uv run cloudy-intell --problem "Design a secure three-tier web app" --min-iterations 2 --max-iterations 5

# Both providers with comparison
uv run cloudy-intell --problem "Design a data pipeline" --provider both
```

### 4. Run via UI

Start the LangGraph backend server and the Next.js frontend:

```bash
# Terminal 1: LangGraph backend
langgraph dev

# Terminal 2: Next.js frontend
cd UI && npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.  Use the chat interface to describe your architecture problem and watch the agent workflow execute in real time.

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
uv run cloudy-intell --problem "Design a secure VPC and Kubernetes platform" --langsmith-project cloudy-intell-dev
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
uv run ruff check .       # Lint
uv run mypy src           # Type check
uv run pytest             # Run tests
```

## Key Design Decisions

- **Subgraph composition**: Architect and validator phases are self-contained `StateGraph` instances compiled and nested as nodes in the parent graph, keeping the top-level topology simple.
- **Provider-agnostic agents**: All prompt content is driven by `ProviderMeta` dataclasses, so adding a new cloud provider requires only defining new metadata — no agent code changes.
- **Immutable RuntimeContext**: A frozen dataclass passed to all node factories ensures thread-safe sharing during parallel fan-out execution.
- **Custom state reducers**: LangGraph reducers (`merge_dicts`, `validation_feedback_reducer`, `overwrite_bool`) handle parallel writes from domain agents and support explicit state reset between iterations.
- **Pre-bound tool LLMs**: Tools are bound to LLM instances once at startup via `ToolBundle`, avoiding repeated binding overhead during execution.
- **Bounded execution**: Tool-calling loops, LLM invocations, and iteration counts all have configurable upper bounds to prevent runaway cost.

## Migration Notes

- The source of truth for old behavior is still `Development/CloudyIntel.py`.
- New implementation is modularized under `src/cloudy_intell/`.
- See [docs/migration-notes.md](docs/migration-notes.md) for detailed migration mapping and validation checklist.