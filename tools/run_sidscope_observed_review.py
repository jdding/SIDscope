#!/usr/bin/env python3
"""Thin CLI wrapper over `sidscope.observed_review` (single observed workflow).

The implementation lives in the installed package; this entry keeps the
historical argument surface for source-tree callers.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from sidscope.observed_review import run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run(args.input, args.metadata, args.output)
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(json.dumps({'status': 'fail', 'code': getattr(error, 'code', type(error).__name__), 'detail': str(error)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
