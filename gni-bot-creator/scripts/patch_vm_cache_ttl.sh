#!/usr/bin/env bash
# One-time patch for VM: fix CACHE_TTL_SECONDS empty-string crash in worker.
# Run from repo root: bash scripts/patch_vm_cache_ttl.sh
set -e
cd "$(dirname "$0")/.."

CACHE_PY="apps/worker/cache.py"
ENV_HELPERS="apps/shared/env_helpers.py"

# 1) Ensure env_helpers.py has env_int
if ! grep -q "def env_int" "$ENV_HELPERS" 2>/dev/null; then
  echo "Adding env_int to $ENV_HELPERS"
  python3 << 'PY'
from pathlib import Path
p = Path("apps/shared/env_helpers.py")
p.parent.mkdir(parents=True, exist_ok=True)
extra = r'''
def env_int(name, default, *, min_value=None, max_value=None):
    import os
    raw = os.environ.get(name, "")
    s = (raw or "").strip()
    if not s:
        return default
    try:
        n = int(s)
    except ValueError:
        raise ValueError(f"Invalid integer for {name!r}: {s!r}")
    if min_value is not None and n < min_value:
        raise ValueError(f"{name!r} must be >= {min_value}, got {n}")
    if max_value is not None and n > max_value:
        raise ValueError(f"{name!r} must be <= {max_value}, got {n}")
    return n
'''
text = p.read_text() if p.exists() else ""
if "def env_int" not in text:
    text = (text.rstrip() + "\n" + extra.lstrip() + "\n").strip() + "\n"
    p.write_text(text)
PY
fi

# 2) Patch cache.py
python3 << 'PY'
import re
from pathlib import Path
p = Path("apps/worker/cache.py")
text = p.read_text()
# Match the old line (with or without trailing comment)
old_pat = re.compile(r'CACHE_TTL_SECONDS = int\(os\.environ\.get\("CACHE_TTL_SECONDS", "86400"\)\).*')
new_line = 'CACHE_TTL_SECONDS = env_int("CACHE_TTL_SECONDS", 86400, min_value=1)'
if old_pat.search(text):
    text = old_pat.sub(new_line, text)
    if "from apps.shared.env_helpers import env_int" not in text:
        text = text.replace(
            "from typing import Any, Optional",
            "from typing import Any, Optional\n\nfrom apps.shared.env_helpers import env_int",
        1,
        )
    p.write_text(text)
    print("Patched cache.py")
else:
    print("cache.py already patched or format differs")
PY

echo ""
echo "Rebuild and restart: docker compose build --no-cache worker && docker compose up -d"
