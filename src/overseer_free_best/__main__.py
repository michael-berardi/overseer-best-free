"""Command-line interface: print the current best free OpenRouter models.

Usage:
    python -m overseer_free_best [--top N] [--json] [--no-cache]
"""

from __future__ import annotations

import argparse
import json
import sys

from .core import CachedResolver


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="overseer-free-best",
        description="Print the current best free models on OpenRouter, best first.",
    )
    parser.add_argument("--top", type=int, default=3, help="How many models to list (default 3)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output JSON")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Bypass the cache and refetch the catalog",
    )
    args = parser.parse_args(argv)

    try:
        resolver = CachedResolver()
        models = resolver.get(limit=args.top, refresh=args.refresh)
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps([m.as_dict() for m in models], indent=2))
    else:
        for index, model in enumerate(models, start=1):
            print(f"{index}. {model.id}  (context={model.context_length})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
