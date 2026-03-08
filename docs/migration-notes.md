# Migration Notes

## Objective

Move from notebook-style single-file implementation (`Development/CloudyIntel.py`) to a modular package while preserving behavior.

## Mapping: Legacy -> New Modules

- State + schemas:
  - `Development/CloudyIntel.py` -> `src/cloudy_intell/schemas/models.py`
  - `create_initial_state` -> `src/cloudy_intell/graph/state_reducers.py`
- Infrastructure singletons:
  - LLMs/tools/vector store/checkpointer -> `src/cloudy_intell/infrastructure/*`
- Architect and validator supervisors:
  - -> `src/cloudy_intell/agents/supervisors.py`
- Domain architect/validator logic:
  - -> `src/cloudy_intell/agents/domain_nodes.py`
- Tool execution and error detection:
  - -> `src/cloudy_intell/agents/tool_execution.py`
- Synthesis, iteration routing, final generation:
  - -> `src/cloudy_intell/agents/synthesizers.py`
- Graph assembly:
  - -> `src/cloudy_intell/graph/builder.py`
- Runtime entrypoint:
  - -> `src/cloudy_intell/services/architecture_service.py` and `src/cloudy_intell/cli.py`

## Validation Checklist

- Compare iteration behavior (`min_iterations`, `max_iterations`, error-driven loop).
- Confirm final state includes `final_architecture` and `architecture_summary`.
- Confirm `validation_feedback` reset/accumulation semantics remain stable.

## Deferred Work

- Azure provider implementation.
- UI integration via LangSmith Studio and CopilotKit.
- Persistent checkpoint backends beyond MemorySaver.
