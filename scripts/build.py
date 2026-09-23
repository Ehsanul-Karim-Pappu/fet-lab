"""Regenerate reviewed scene data and all current viewer bundles from any directory."""
import subprocess
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
for name in ('build_geometry','build_devices','build_inverters','build_showcase','build_story','build_parasitics','build_process','verify','build_web'):
    subprocess.run([sys.executable,'-B',str(HERE / (name+'.py'))],check=True)
