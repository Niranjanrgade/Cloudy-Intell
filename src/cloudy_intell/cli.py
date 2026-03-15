"""CLI entrypoint for Cloudy-Intell.

This module provides the command-line interface for running the cloud
architecture generation workflow.  It parses arguments, constructs an
``AppSettings`` instance with the requested provider mode, initializes
the ``ArchitectureService``, and runs the workflow.

Heavy imports (``ArchitectureService``) are deferred until after argument
parsing so that ``--help`` responds instantly without loading LangChain,
OpenAI clients, or ChromaDB.

Usage examples:
    cloudy-intell --problem "Design a web app" --provider aws
    cloudy-intell --problem "Design a web app" --provider both
    cloudy-intell --problem "Design a web app" --min-iterations 2 --max-iterations 5
"""

from __future__ import annotations

import argparse
import json
import sys

from cloudy_intell.config.settings import AppSettings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="cloudy-intell",
        description="Multi-agent cloud architecture generation and validation.",
    )
    parser.add_argument(
        "--problem",
        required=True,
        help="Cloud architecture problem statement to solve.",
    )
    parser.add_argument(
        "--provider",
        choices=["aws", "azure", "both"],
        default="aws",
        help="Cloud provider to target (default: aws).",
    )
    parser.add_argument(
        "--min-iterations",
        type=int,
        default=None,
        help="Minimum iterations (default from settings).",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum iterations (default from settings).",
    )
    parser.add_argument(
        "--thread-id",
        default=None,
        help="Optional thread ID for checkpointing / LangSmith.",
    )

    args = parser.parse_args(argv)

    settings = AppSettings(provider_mode=args.provider)  # type: ignore[arg-type]
    min_iter = args.min_iterations or settings.min_iterations_default
    max_iter = args.max_iterations or settings.max_iterations_default

    # Lazy import to keep CLI startup snappy when showing --help.
    from cloudy_intell.services.architecture_service import ArchitectureService  # noqa: E402

    service = ArchitectureService(settings)
    result = service.run(
        user_problem=args.problem,
        min_iterations=min_iter,
        max_iterations=max_iter,
        thread_id=args.thread_id,
    )

    # Emit result as JSON for downstream tooling; fallback to repr.
    try:
        print(json.dumps(result, indent=2, default=str))
    except TypeError:
        print(result)


if __name__ == "__main__":
    main()
