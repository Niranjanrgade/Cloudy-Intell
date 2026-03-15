"""Graph node implementations split by responsibility.

This package exports all agent node factories organized by role:

- ``RuntimeContext``: Immutable dependency container passed to all factories.
- ``architect_supervisor`` / ``validator_supervisor``: Orchestration agents that
  decompose tasks into domain-specific assignments.
- ``compute_architect``, ``network_architect``, etc.: Domain-specific architect
  agents that generate infrastructure recommendations.
- ``compute_validator``, ``network_validator``, etc.: Domain-specific validator
  agents that check recommendations against documentation.
- ``architect_synthesizer``, ``validation_synthesizer``: Fan-in agents that
  merge parallel domain outputs.
- ``final_architecture_generator``: Terminal node that produces the final document.
"""

from .context import RuntimeContext
from .domain_nodes import (
    compute_architect,
    database_architect,
    network_architect,
    storage_architect,
    compute_validator,
    network_validator,
    storage_validator,
    database_validator,
)
from .supervisors import architect_supervisor, validator_supervisor
from .synthesizers import (
    architect_synthesizer,
    final_architecture_generator,
    validation_synthesizer,
)

__all__ = [
    "RuntimeContext",
    "architect_supervisor",
    "validator_supervisor",
    "compute_architect",
    "network_architect",
    "storage_architect",
    "database_architect",
    "compute_validator",
    "network_validator",
    "storage_validator",
    "database_validator",
    "architect_synthesizer",
    "validation_synthesizer",
    "final_architecture_generator",
]
