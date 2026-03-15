"""Compatibility launcher.

This file remains at repository root for convenience so users can run
``python main.py`` without installing the package.  The primary runtime
entrypoint is ``cloudy_intell.cli:main``, registered as the ``cloudy-intell``
console script in ``pyproject.toml``.

Run ``uv sync`` (or ``pip install -e .") to ensure the package is importable.
"""

from cloudy_intell.cli import main


if __name__ == "__main__":
    main()
