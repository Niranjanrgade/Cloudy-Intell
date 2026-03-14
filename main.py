"""Compatibility launcher.

This file remains at repository root for convenience.
Primary runtime entrypoint is now ``cloudy_intell.cli:main``.
Run ``uv sync`` (or ``pip install -e .") to ensure the package is importable.
"""

from cloudy_intell.cli import main


if __name__ == "__main__":
    main()
