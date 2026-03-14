"""Repository-root LangGraph entrypoint for ``langgraph dev``.

This shim imports from the installed ``cloudy_intell`` package.
Run ``uv sync`` (or ``pip install -e .") to ensure the package is importable.
"""

from cloudy_intell.langgraph_app import build_runtime_graph


graph = build_runtime_graph()
