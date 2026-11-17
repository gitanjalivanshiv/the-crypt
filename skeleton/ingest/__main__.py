"""CLI: python -m skeleton.ingest [--retained] <url>"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from skeleton.ingest import ingest_url
from skeleton.ingest.models import IngestError


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m skeleton.ingest")
    p.add_argument("url")
    p.add_argument("--retained", action="store_true", help="retain the snapshot (licence-gated)")
    p.add_argument("--ref", default=None)
    p.add_argument("--sha", default=None)
    p.add_argument("--store", default=os.environ.get("SKELETON_STORE", "snapshots"))
    args = p.parse_args(argv)
    try:
        snap = ingest_url(
            args.url,
            ref=args.ref,
            sha=args.sha,
            intent="retained" if args.retained else "ephemeral",
            store=Path(args.store),
        )
    except IngestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(snap.root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
