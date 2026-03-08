"""CLI entrypoint for Cloudy-Intell backend workflow."""

import argparse
import json
from typing import Any

from cloudy_intell.config.settings import get_settings
from cloudy_intell.services.architecture_service import ArchitectureService


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser with explicit workflow knobs.

    We keep these arguments intentionally close to runtime state fields so
    operators can reproduce behavior from development experiments.
    """

    parser = argparse.ArgumentParser(description="Cloudy-Intell architecture generation CLI")
    parser.add_argument("problem", help="User problem statement to architect")
    parser.add_argument("--min-iterations", type=int, default=None)
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--thread-id", type=str, default=None)
    parser.add_argument(
        "--print-final-only",
        action="store_true",
        help="Print only final architecture document instead of full state JSON",
    )
    return parser


def _json_default(value: Any) -> str:
    """JSON serialization fallback for complex objects in state output."""

    return str(value)


def main() -> None:
    """Execute CLI workflow using modular architecture service."""

    parser = build_parser()
    args = parser.parse_args()

    settings = get_settings()
    min_iterations = args.min_iterations if args.min_iterations is not None else settings.min_iterations_default
    max_iterations = args.max_iterations if args.max_iterations is not None else settings.max_iterations_default

    service = ArchitectureService(settings)
    result = service.run(
        user_problem=args.problem,
        min_iterations=min_iterations,
        max_iterations=max_iterations,
        thread_id=args.thread_id,
    )

    if args.print_final_only:
        final_doc = result.get("architecture_summary") or "No final architecture summary generated."
        print(final_doc)
        return

    print(json.dumps(result, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
