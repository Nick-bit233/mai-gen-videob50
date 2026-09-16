"""Isolated real-kernel probe. A failed or hung driver never initializes the UI."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == '__main__':
    from utils.TaichiAccel import _probe_main
    _probe_main(sys.argv[1])
