# -*- coding: utf-8 -*-
"""
utils/lazy_bootstrap.py
-----------------------
Enables Python 3.15 native lazy imports (PEP 690 / PEP 810) across the framework.
When running on Python 3.15+, sets lazy import mode to 'all' so imports are evaluated
on-demand only when module attributes are first accessed.
"""

import sys

def enable_lazy_imports() -> bool:
    """Activate native Python 3.15 lazy imports if supported by the runtime."""
    if hasattr(sys, "set_lazy_imports"):
        try:
            sys.set_lazy_imports("all")
            return True
        except Exception:
            pass
    return False

# Automatically activate when imported on Python 3.15+
IS_LAZY_ACTIVE = enable_lazy_imports()
