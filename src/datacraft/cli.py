"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from decimal import Decimal
from pathlib import Path

from .pipeline import PipelineError, run


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate, filter and aggregate file data")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING, format="%(message)s"
    )
    try:
        config = (
            json.loads(args.config.read_text(encoding="utf-8"), parse_float=Decimal)
            if args.config
            else {}
        )
        print(json.dumps(run(args.source, args.destination, config)))
    except (PipelineError, OSError, ValueError) as error:
        print(json.dumps({"event": "pipeline_failed", "error": str(error)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
