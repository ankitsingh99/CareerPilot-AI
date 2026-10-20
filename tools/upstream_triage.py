#!/usr/bin/env python3
"""Forwarding shim for utils/upstream_triage.py."""
import runpy
from pathlib import Path

target = Path(__file__).resolve().parent.parent / "utils" / "upstream_triage.py"
runpy.run_path(str(target), run_name="__main__")
