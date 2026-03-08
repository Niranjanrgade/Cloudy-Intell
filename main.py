"""Compatibility launcher.

This file remains at repository root for convenience during migration.
Primary runtime entrypoint is now `cloudy_intell.cli:main`.
"""

from pathlib import Path
import sys

# Add src path so `python main.py` works in local source checkout before install.
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cloudy_intell.cli import main


if __name__ == "__main__":
    main()
