"""
cli.py
------
Command-line entry point for the fairify package.

Usage
-----
    python -m fairify path/to/dataset --out metadata_excite.json

    # or after pip install:
    fairify path/to/dataset --out metadata_excite.json
"""

import argparse
import json
from pathlib import Path

from . import fairify


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Extract and translate CT metadata to EXCITE schema JSON."
    )
    ap.add_argument(
        "dataset",
        type=str,
        help="Path to the dataset root folder.",
    )
    ap.add_argument(
        "--out",
        type=str,
        default="metadata_excite.json",
        help="Output JSON file path (default: metadata_excite.json).",
    )
    args = ap.parse_args()

    try:
        structured = fairify(args.dataset)
    except FileNotFoundError as e:
        raise SystemExit(str(e))

    out_path = Path(args.out).resolve()
    out_path.write_text(json.dumps(structured, indent=2), encoding="utf-8")
    print(f"Wrote structured metadata: {out_path}")


if __name__ == "__main__":
    main()
