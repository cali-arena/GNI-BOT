#!/usr/bin/env python3
"""
Lightweight sanity check: import apps.api.main (no server start).
Use in CI or locally: python scripts/test_imports.py
Requires repo root on PYTHONPATH (e.g. run from repo root, or set PYTHONPATH=/app in Docker).
Exits 0 on success, 1 on import error (traceback printed).
"""
import importlib
import sys
import traceback
from pathlib import Path

# Ensure repo root is on path when run as script from repo root or from /app in container
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))


def main() -> int:
    try:
        importlib.import_module("apps.api.main")
        print("OK")
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
