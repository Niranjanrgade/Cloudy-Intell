"""Checkpointer factory wrappers."""

from langgraph.checkpoint.memory import MemorySaver


def create_checkpointer() -> MemorySaver:
    """Create in-memory checkpointer.

    We keep MemorySaver as the default to match current behavior; this factory
    is a seam for future persistent checkpoint backends.
    """

    return MemorySaver()
