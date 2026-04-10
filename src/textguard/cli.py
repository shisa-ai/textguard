from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import cast

from . import clean, scan
from .backends import fetch_promptguard_model
from .config import PRESETS
from .types import CleanResult, ScanResult

Handler = Callable[[argparse.Namespace], int]

_SCAN_EXIT_CODES = {
    "info": 1,
    "warn": 2,
    "error": 3,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="textguard",
        description=(
            "Hostile-text normalization, inspection, and cleaning for "
            "LLM-adjacent systems."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan input for hostile-text findings.",
        description="Scan files or stdin and report hostile-text findings.",
    )
    scan_parser.add_argument(
        "paths",
        nargs="+",
        help="Input path(s) to scan, or '-' to read from stdin.",
    )
    _add_common_scan_flags(scan_parser)
    scan_parser.set_defaults(handler=_handle_scan)

    clean_parser = subparsers.add_parser(
        "clean",
        help="Clean hostile or ambiguous text input.",
        description="Clean one file or stdin and emit cleaned text or a structured report.",
    )
    clean_parser.add_argument(
        "path",
        help="Input path to clean, or '-' to read from stdin.",
    )
    clean_parser.add_argument(
        "-i",
        "--in-place",
        action="store_true",
        help="Overwrite the input file in place. Not allowed with stdin or -o/--output.",
    )
    clean_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write cleaned text to this output path instead of stdout.",
    )
    clean_parser.add_argument(
        "--report",
        action="store_true",
        help="Print a human-readable change report to stderr.",
    )
    _add_common_scan_flags(clean_parser)
    clean_parser.set_defaults(handler=_handle_clean)

    models_parser = subparsers.add_parser(
        "models",
        help="Manage optional model assets.",
        description="Manage optional model assets used by backend integrations.",
    )
    models_subparsers = models_parser.add_subparsers(dest="models_command")
    fetch_parser = models_subparsers.add_parser(
        "fetch",
        help="Fetch a named model pack.",
        description="Fetch and verify a named model pack.",
    )
    fetch_parser.add_argument("model_name", help="Model name to fetch.")
    fetch_parser.set_defaults(handler=_handle_models_fetch)

    return parser


def _add_common_scan_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON output instead of the default human-readable format.",
    )
    parser.add_argument(
        "--preset",
        choices=tuple(PRESETS),
        default="default",
        help="Cleaning preset to use for normalization and clean behavior.",
    )
    parser.add_argument(
        "--include-context",
        action="store_true",
        help="Include original-text excerpts around findings. Not safe for LLM-bound output.",
    )
    parser.add_argument(
        "--confusables",
        choices=("trimmed", "full"),
        default="trimmed",
        help="Confusable table scope: 'trimmed' by default or 'full' for broader coverage.",
    )
    parser.add_argument(
        "--yara-rules",
        type=Path,
        help="Directory containing YARA rules to load alongside or instead of bundled rules.",
    )
    parser.add_argument(
        "--yara-bundled",
        action="store_true",
        help="Enable the bundled YARA ruleset.",
    )
    parser.add_argument(
        "--promptguard",
        type=Path,
        help="Local PromptGuard model pack or artifact directory.",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return cast(Handler, handler)(args)


def _handle_scan(args: argparse.Namespace) -> int:
    payloads = [_read_input(path_text) for path_text in cast(list[str], args.paths)]
    try:
        results = [
            (
                label,
                scan(
                    text,
                    include_context=args.include_context,
                    preset=args.preset,
                    confusables=args.confusables,
                    yara_rules_dir=args.yara_rules,
                    yara_bundled=args.yara_bundled,
                    promptguard_model_path=args.promptguard,
                ),
            )
            for label, text in payloads
        ]
    except RuntimeError as exc:
        _print_error(str(exc))
        return 2

    if args.json:
        serialized = [
            {
                "path": label,
                "result": asdict(result),
            }
            for label, result in results
        ]
        print(_json_dump(serialized[0] if len(serialized) == 1 else serialized))
    else:
        _print_scan_report(results)

    return max(_scan_exit_code(result) for _, result in results)


def _handle_clean(args: argparse.Namespace) -> int:
    if args.in_place and args.path == "-":
        _print_error("--in-place cannot be used when reading from stdin.")
        return 2
    if args.in_place and args.output is not None:
        _print_error("--in-place cannot be combined with -o/--output.")
        return 2

    label, text = _read_input(cast(str, args.path))
    try:
        result = clean(
            text,
            include_context=args.include_context,
            preset=args.preset,
            confusables=args.confusables,
            yara_rules_dir=args.yara_rules,
            yara_bundled=args.yara_bundled,
            promptguard_model_path=args.promptguard,
        )
    except RuntimeError as exc:
        _print_error(str(exc))
        return 2

    if args.in_place:
        Path(args.path).write_text(result.text, encoding="utf-8")
    elif args.output is not None:
        args.output.write_text(result.text, encoding="utf-8")
    elif not args.json:
        sys.stdout.write(result.text)

    if args.json:
        print(_json_dump({"path": label, "result": asdict(result)}))
    if args.report:
        _print_clean_report(label, result)
    return 0


def _handle_models_fetch(args: argparse.Namespace) -> int:
    try:
        destination = fetch_promptguard_model(args.model_name)
    except (RuntimeError, ValueError) as exc:
        _print_error(str(exc))
        return 2
    print(destination)
    return 0


def _read_input(path_text: str) -> tuple[str, str]:
    if path_text == "-":
        return "stdin", sys.stdin.read()
    path = Path(path_text)
    return path_text, path.read_text(encoding="utf-8")


def _scan_exit_code(result: ScanResult) -> int:
    code = 0
    for finding in result.findings:
        code = max(code, _SCAN_EXIT_CODES.get(finding.severity, 0))
    return code


def _print_scan_report(results: list[tuple[str, ScanResult]]) -> None:
    for label, result in results:
        if not result.findings:
            print(f"{label}: no findings")
        else:
            print(f"{label}: {len(result.findings)} finding(s)")
            for finding in result.findings:
                location = "" if finding.offset is None else f" @ {finding.offset}"
                context = ""
                if finding.context is not None:
                    context = f" [{finding.context.excerpt!r}]"
                print(
                    f"{finding.severity.upper()} {finding.kind}{location}: "
                    f"{finding.detail}{context}"
                )
        if result.semantic is not None:
            print(
                f"SEMANTIC {result.semantic.tier.upper()} {result.semantic.classifier_id}: "
                f"score={result.semantic.score:.3f}"
            )


def _print_clean_report(label: str, result: CleanResult) -> None:
    print(
        f"{label}: {len(result.changes)} change(s), {len(result.findings)} finding(s)",
        file=sys.stderr,
    )
    for change in result.changes:
        print(f"CHANGE {change.kind}: {change.detail}", file=sys.stderr)
    for finding in result.findings:
        location = "" if finding.offset is None else f" @ {finding.offset}"
        print(
            f"FINDING {finding.severity.upper()} {finding.kind}{location}: {finding.detail}",
            file=sys.stderr,
        )


def _json_dump(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _print_error(message: str) -> None:
    print(message, file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
