"""Repository-root LangGraph entrypoint for `langgraph dev`.

This shim ensures the `src/` layout is importable in environments where the
project is not installed as an editable package.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cloudy_intell.langgraph_app import build_runtime_graph


graph = build_runtime_graph()
