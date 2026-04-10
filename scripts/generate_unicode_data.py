from __future__ import annotations

import argparse
from collections.abc import Sequence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_unicode_data.py",
        description="Generate vendored Unicode data for textguard.",
    )
    parser.add_argument(
        "--unicode-version",
        help="Pinned Unicode version to fetch when the generator is implemented.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    raise SystemExit("Unicode data generation is scaffolded but not implemented yet.")


if __name__ == "__main__":
    raise SystemExit(main())
