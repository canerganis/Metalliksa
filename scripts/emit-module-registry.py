"""Emit src/generated/moduleRegistry.{json,ts} from python/module_registry.py.

Usage (from the repo root):
    python scripts/emit-module-registry.py                 # write generated files
    python scripts/emit-module-registry.py --check         # exit 1 when out of date
    python scripts/emit-module-registry.py --refresh-seed  # re-snapshot workspaces.ts + App.tsx, then emit
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

import module_registry  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(module_registry.main(sys.argv[1:]))
