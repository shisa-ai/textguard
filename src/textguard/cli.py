from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from typing import cast

Handler = Callable[[argparse.Namespace], int]


def _not_implemented(_: argparse.Namespace) -> int:
    raise SystemExit("textguard CLI is scaffolded, but command behavior is not implemented yet.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="textguard",
        description=(
            "Hostile-text normalization, inspection, and cleaning for "
            "LLM-adjacent systems."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    scan_parser = subparsers.add_parser("scan", help="Scan input for hostile-text findings.")
    scan_parser.set_defaults(handler=_not_implemented)

    clean_parser = subparsers.add_parser("clean", help="Clean hostile or ambiguous text input.")
    clean_parser.set_defaults(handler=_not_implemented)

    models_parser = subparsers.add_parser("models", help="Manage optional model assets.")
    models_subparsers = models_parser.add_subparsers(dest="models_command")
    fetch_parser = models_subparsers.add_parser("fetch", help="Fetch a named model pack.")
    fetch_parser.add_argument("model_name", help="Model name to fetch.")
    fetch_parser.set_defaults(handler=_not_implemented)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return cast(Handler, handler)(args)


if __name__ == "__main__":
    raise SystemExit(main())
