#!/usr/bin/env python3
"""Dump the live OpenAPI spec of the Lager FastAPI app to JSON.

Used by `frontend/` to regenerate typed API client stubs:

    python scripts/generate-openapi.py > openapi.json
    cd frontend && npm run gen:types

Run from the repo root.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from any CWD: insert the repo root (parent of /scripts/) on path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write the spec to this path instead of stdout.",
    )
    args = p.parse_args()

    # Import here so import errors don't block --help
    from app.main import app

    spec = app.openapi()
    rendered = json.dumps(spec, indent=2, ensure_ascii=False)

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
        print(f"Wrote {args.out} ({len(rendered)} bytes)", file=sys.stderr)
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
