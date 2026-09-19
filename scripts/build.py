#!/usr/bin/env python3
"""Rebuild all scene data and shipped viewers; run from any directory."""
import subprocess
import sys
from paths import ROOT

for script in ("build_devices", "build_inverters", "build_showcase",
               "build_story", "build_parasitics", "verify", "build_web"):
    subprocess.run([sys.executable, str(ROOT / "scripts" / f"{script}.py")], check=True)
