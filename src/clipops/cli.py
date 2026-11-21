"""Command-line entry point. Only implemented commands are registered."""
from __future__ import annotations

import argparse
import sys

from . import __version__, health


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="clipops")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("health", help="check repository and host state")
    h.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "health":
        return health.main(as_json=args.json)
    return 2


if __name__ == "__main__":
    sys.exit(main())
