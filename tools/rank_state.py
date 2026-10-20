#!/usr/bin/env python3
# AUTO-GENERATED WRAPPER for backward compatibility
import sys
import runpy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from intelligence.ranker import *
except ImportError:
    pass

if __name__ == '__main__':
    runpy.run_module('intelligence.ranker', run_name='__main__')
