import sys

from pathlib import Path

_ROOT_DIR = str(Path(__file__).parents[2].resolve())
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)
