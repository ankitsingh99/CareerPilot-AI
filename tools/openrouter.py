#!/usr/bin/env python
# AUTO-GENERATED WRAPPER for backward compatibility
import sys
import runpy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from intelligence.llm_clients.openrouter import *
except ImportError:
    pass

if __name__ == '__main__':
    runpy.run_module('intelligence.llm_clients.openrouter', run_name='__main__')
