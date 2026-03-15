"""Logging setup helpers.

Centralizing logging setup keeps consistent formatting across CLI and tests,
while allowing future structured logging upgrades in one place.

All modules obtain their logger via ``get_logger(__name__)`` which ensures
log messages include the fully qualified module path for easy filtering.
The root logging format is configured once at process startup by
``configure_logging`` (called from ``ArchitectureService.__init__``).
"""

import logging


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging format and level once per process.

    We intentionally keep formatter readable for local development. This can be
    replaced later with JSON logging for observability pipelines.
    """

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    """Return module-level logger with consistent naming."""

    return logging.getLogger(name)
