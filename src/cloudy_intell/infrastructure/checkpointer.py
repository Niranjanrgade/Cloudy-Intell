"""Checkpointer factory wrappers.

Checkpointers enable LangGraph to persist state between node executions,
making the workflow resumable and observable.  The ``MemorySaver`` stores
state in memory (suitable for development and single-process runs).  This
factory method exists as an extensibility seam for swapping in a persistent
backend (e.g. SQLite, PostgreSQL) without changing the graph builder code.
"""

from langgraph.checkpoint.memory import MemorySaver


def create_checkpointer() -> MemorySaver:
    """Create in-memory checkpointer.

    We keep MemorySaver as the default to match current behavior; this factory
    is a seam for future persistent checkpoint backends.
    """

    return MemorySaver()
