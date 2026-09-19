"""Repository paths, independent of the shell's current directory."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "devices.json"
