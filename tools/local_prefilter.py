#!/usr/bin/env python3
# WRAPPER for backward compatibility and local compute offloading
import sys
import runpy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from intelligence.prefilter import *
except ImportError:
    pass

if __name__ == '__main__':
    runpy.run_module('intelligence.prefilter', run_name='__main__')
