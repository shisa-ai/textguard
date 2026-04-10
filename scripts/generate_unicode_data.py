from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

PINNED_UNICODE_VERSION = "17.0.0"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "src" / "textguard" / "data"

_SCRIPTS_SOURCE = (
    "Scripts.txt",
    "https://www.unicode.org/Public/17.0.0/ucd/Scripts.txt",
    "9f5e50d3abaee7d6ce09480f325c706f485ae3240912527e651954d2d6b035bf",
)
_CONFUSABLES_SOURCE = (
    "confusables.txt",
    "https://www.unicode.org/Public/security/latest/confusables.txt",
    "091c7f82fc39ef208faf8f94d29c244de99254675e09de163160c810d13ef22a",
)

_IGNORED_SCRIPTS = {"Common", "Inherited", "Unknown"}
_TRIMMED_SCRIPTS = {"Latin", "Greek", "Cyrillic"}


@dataclass(frozen=True, slots=True)
class SourceFile:
    name: str
    url: str
    expected_sha256: str


@dataclass(frozen=True, slots=True)
class ScriptRange:
    start: int
    end: int
    script: str


@dataclass(frozen=True, slots=True)
class ScriptIndex:
    starts: tuple[int, ...]
    ends: tuple[int, ...]
    scripts: tuple[str, ...]

    def lookup(self, codepoint: int) -> str:
        index = bisect_right(self.starts, codepoint) - 1
        if index >= 0 and codepoint <= self.ends[index]:
            return self.scripts[index]
        return "Unknown"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_unicode_data.py",
        description="Generate vendored Unicode script and confusable data for textguard.",
    )
    parser.add_argument(
        "--unicode-version",
        default=PINNED_UNICODE_VERSION,
        help=f"Pinned Unicode version to generate (must be {PINNED_UNICODE_VERSION}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where scripts.json and confusable maps will be written.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.unicode_version != PINNED_UNICODE_VERSION:
        raise SystemExit(
            f"Only the pinned Unicode version {PINNED_UNICODE_VERSION} is supported. "
            "Update the source URLs and expected hashes before changing it."
        )

    scripts_source = SourceFile(*_SCRIPTS_SOURCE)
    confusables_source = SourceFile(*_CONFUSABLES_SOURCE)

    scripts_text, scripts_hash = _fetch_source(scripts_source)
    confusables_text, confusables_hash = _fetch_source(confusables_source)
    declared_version = _extract_confusables_version(confusables_text)
    if declared_version != args.unicode_version:
        raise SystemExit(
            "confusables.txt version mismatch: "
            f"expected {args.unicode_version}, upstream declares {declared_version}"
        )

    script_ranges = _parse_scripts(scripts_text)
    script_index = _build_script_index(script_ranges)
    trimmed_map, full_map = _parse_confusables(confusables_text, script_index)
    generated_at = _timestamp_now()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        args.output_dir / "scripts.json",
        _scripts_payload(
            unicode_version=args.unicode_version,
            generated_at=generated_at,
            source=scripts_source,
            source_sha256=scripts_hash,
            script_ranges=script_ranges,
        ),
    )
    _write_json(
        args.output_dir / "confusables.json",
        _confusables_payload(
            unicode_version=args.unicode_version,
            generated_at=generated_at,
            source=confusables_source,
            source_sha256=confusables_hash,
            declared_version=declared_version,
            mode="trimmed",
            mappings=trimmed_map,
        ),
    )
    _write_json(
        args.output_dir / "confusables_full.json",
        _confusables_payload(
            unicode_version=args.unicode_version,
            generated_at=generated_at,
            source=confusables_source,
            source_sha256=confusables_hash,
            declared_version=declared_version,
            mode="full",
            mappings=full_map,
        ),
    )
    return 0


def _fetch_source(source: SourceFile) -> tuple[str, str]:
    request = urllib.request.Request(
        source.url,
        headers={"User-Agent": "textguard-unicode-data-generator/0.0.0"},
    )
    with urllib.request.urlopen(request) as response:
        payload = response.read()
    payload_hash = hashlib.sha256(payload).hexdigest()
    if payload_hash != source.expected_sha256:
        raise SystemExit(
            f"{source.name} sha256 mismatch: expected {source.expected_sha256}, got {payload_hash}"
        )
    return payload.decode("utf-8"), payload_hash


def _parse_scripts(text: str) -> list[ScriptRange]:
    ranges: list[ScriptRange] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        codepoint_text, script = [part.strip() for part in line.split(";")]
        if ".." in codepoint_text:
            start_text, end_text = codepoint_text.split("..", 1)
        else:
            start_text = end_text = codepoint_text
        ranges.append(
            ScriptRange(
                start=int(start_text, 16),
                end=int(end_text, 16),
                script=script,
            )
        )
    return sorted(ranges, key=lambda item: item.start)


def _build_script_index(script_ranges: list[ScriptRange]) -> ScriptIndex:
    return ScriptIndex(
        starts=tuple(item.start for item in script_ranges),
        ends=tuple(item.end for item in script_ranges),
        scripts=tuple(item.script for item in script_ranges),
    )


def _parse_confusables(
    text: str,
    script_index: ScriptIndex,
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    trimmed: dict[str, dict[str, object]] = {}
    full: dict[str, dict[str, object]] = {}

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        source_text, target_text, mapping_type = [part.strip() for part in line.split(";")[:3]]
        source_codepoints = [int(item, 16) for item in source_text.split()]
        if len(source_codepoints) != 1:
            continue
        source_codepoint = source_codepoints[0]
        source_script = script_index.lookup(source_codepoint)
        target = "".join(chr(int(item, 16)) for item in target_text.split())
        target_scripts = sorted(
            {
                script_index.lookup(ord(char))
                for char in target
                if script_index.lookup(ord(char)) not in _IGNORED_SCRIPTS
            }
        )
        if source_script in _IGNORED_SCRIPTS or not target_scripts:
            continue
        if all(script == source_script for script in target_scripts):
            continue

        entry: dict[str, object] = {
            "mapping_type": mapping_type,
            "source_script": source_script,
            "target": target,
            "target_scripts": target_scripts,
        }
        key = f"{source_codepoint:04X}"
        full[key] = entry
        if _keep_trimmed_mapping(source_script, target_scripts):
            trimmed[key] = entry

    return trimmed, full


def _keep_trimmed_mapping(source_script: str, target_scripts: list[str]) -> bool:
    involved_scripts = {source_script, *target_scripts}
    return (
        involved_scripts <= _TRIMMED_SCRIPTS
        and "Latin" in involved_scripts
        and len(involved_scripts) > 1
    )


def _extract_confusables_version(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# Version:"):
            return line.partition(":")[2].strip()
    raise SystemExit("Unable to find '# Version:' header in confusables.txt")


def _scripts_payload(
    *,
    unicode_version: str,
    generated_at: str,
    source: SourceFile,
    source_sha256: str,
    script_ranges: list[ScriptRange],
) -> dict[str, object]:
    return {
        "metadata": {
            "generated_at": generated_at,
            "unicode_version": unicode_version,
            "sources": [
                {
                    "name": source.name,
                    "url": source.url,
                    "sha256": source_sha256,
                }
            ],
        },
        "ranges": [
            {"start": item.start, "end": item.end, "script": item.script} for item in script_ranges
        ],
    }


def _confusables_payload(
    *,
    unicode_version: str,
    generated_at: str,
    source: SourceFile,
    source_sha256: str,
    declared_version: str,
    mode: str,
    mappings: dict[str, dict[str, object]],
) -> dict[str, object]:
    return {
        "metadata": {
            "generated_at": generated_at,
            "unicode_version": unicode_version,
            "declared_source_version": declared_version,
            "mode": mode,
            "mapping_count": len(mappings),
            "sources": [
                {
                    "name": source.name,
                    "url": source.url,
                    "sha256": source_sha256,
                }
            ],
        },
        "mappings": mappings,
    }


def _timestamp_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
