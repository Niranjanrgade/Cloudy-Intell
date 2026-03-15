"""Cloudy-Intell package.

This package contains the modularized backend implementation for the
multi-agent cloud architecture generation workflow.  The package is organized
into the following sub-packages:

- ``agents``: Graph node implementations (supervisors, domain architects/
  validators, synthesizers, and tool execution helpers).
- ``config``: Application settings and cloud provider metadata definitions.
- ``graph``: LangGraph assembly (graph builder, subgraphs, routing, state init).
- ``infrastructure``: External integrations (LLM factory, tool construction,
  vector store, checkpointer, logging).
- ``schemas``: Pydantic models and the LangGraph State TypedDict contract.
- ``services``: High-level orchestration facade used by CLI and APIs.
"""

__all__: list[str] = []
