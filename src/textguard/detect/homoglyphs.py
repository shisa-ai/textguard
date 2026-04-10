from __future__ import annotations

import json
import re
from bisect import bisect_right
from functools import lru_cache
from importlib import resources
from typing import Literal, TypedDict, cast

from ..types import Finding

ConfusablesMode = Literal["trimmed", "full"]

_IGNORED_SCRIPTS = {"Common", "Inherited", "Unknown"}
_MIXED_SCRIPT_BASELINE = {"Latin", "Greek", "Cyrillic"}
_EAST_ASIAN_ALLOWED = {"Han", "Hiragana", "Katakana"}
_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


class _ScriptRange(TypedDict):
    start: int
    end: int
    script: str


class _ConfusableEntry(TypedDict):
    mapping_type: str
    source_script: str
    target: str
    target_scripts: list[str]


def detect_homoglyphs(
    text: str,
    *,
    confusables: ConfusablesMode = "trimmed",
    in_decoded_text: bool = False,
) -> list[Finding]:
    findings: list[Finding] = []
    mappings = _load_confusable_map(confusables)

    for match in _TOKEN_RE.finditer(text):
        token = match.group(0)
        scripts = _token_scripts(token)
        if len(scripts) > 1 and _is_suspicious_script_mix(scripts, confusables):
            detail = f"Mixed scripts detected ({', '.join(scripts)})"
            if in_decoded_text:
                detail = f"{detail} in decoded text"
            findings.append(
                Finding(
                    kind="mixed_script",
                    severity="warn" if "Latin" in scripts else "info",
                    detail=detail,
                    offset=None if in_decoded_text else match.start(),
                )
            )

        skeleton = confusable_skeleton(token, confusables=confusables)
        if skeleton == token:
            continue

        matched_entries = [
            mappings[f"{ord(char):04X}"]
            for char in token
            if f"{ord(char):04X}" in mappings
        ]
        if not matched_entries or not _should_flag_confusable(
            scripts,
            matched_entries,
            confusables,
        ):
            continue

        source_scripts = sorted({entry["source_script"] for entry in matched_entries})
        target_scripts = sorted(
            {
                target_script
                for entry in matched_entries
                for target_script in entry["target_scripts"]
            }
        )
        detail = (
            f"Confusable skeleton differs under {confusables} table "
            f"({', '.join(source_scripts)}→{', '.join(target_scripts)})"
        )
        if in_decoded_text:
            detail = f"{detail} in decoded text"
        findings.append(
            Finding(
                kind="confusable_homoglyph",
                severity="error" if "Latin" in target_scripts else "warn",
                detail=detail,
                offset=None if in_decoded_text else match.start(),
            )
        )

    return findings


def confusable_skeleton(text: str, *, confusables: ConfusablesMode = "trimmed") -> str:
    mappings = _load_confusable_map(confusables)
    return "".join(
        mappings.get(f"{ord(char):04X}", {"target": char})["target"] for char in text
    )


def _should_flag_confusable(
    scripts: list[str],
    matched_entries: list[_ConfusableEntry],
    confusables: ConfusablesMode,
) -> bool:
    if len(scripts) <= 1:
        return False
    if confusables == "trimmed":
        return "Latin" in scripts and any(
            entry["source_script"] in {"Greek", "Cyrillic"} and "Latin" in entry["target_scripts"]
            for entry in matched_entries
        )
    return any(
        entry["source_script"] not in _IGNORED_SCRIPTS and entry["target_scripts"]
        for entry in matched_entries
    )


def _is_suspicious_script_mix(scripts: list[str], confusables: ConfusablesMode) -> bool:
    script_set = set(scripts)
    if script_set <= _EAST_ASIAN_ALLOWED:
        return False
    if len(script_set & _MIXED_SCRIPT_BASELINE) > 1:
        return True
    return confusables == "full" and len(script_set) > 1


def _token_scripts(token: str) -> list[str]:
    scripts = sorted(
        {
            _lookup_script(ord(char))
            for char in token
            if char.isalpha() and _lookup_script(ord(char)) not in _IGNORED_SCRIPTS
        }
    )
    return scripts


@lru_cache(maxsize=1)
def _load_script_ranges() -> tuple[tuple[int, int, str], ...]:
    payload = json.loads(
        resources.files("textguard").joinpath("data/scripts.json").read_text(encoding="utf-8")
    )
    ranges = payload["ranges"]
    return tuple((item["start"], item["end"], item["script"]) for item in ranges)


@lru_cache(maxsize=2)
def _load_confusable_map(mode: ConfusablesMode) -> dict[str, _ConfusableEntry]:
    filename = "confusables.json" if mode == "trimmed" else "confusables_full.json"
    payload = json.loads(
        resources.files("textguard").joinpath(f"data/{filename}").read_text(encoding="utf-8")
    )
    return cast(dict[str, _ConfusableEntry], payload["mappings"])


@lru_cache(maxsize=1)
def _load_script_starts() -> tuple[int, ...]:
    return tuple(item[0] for item in _load_script_ranges())


def _lookup_script(codepoint: int) -> str:
    ranges = _load_script_ranges()
    index = bisect_right(_load_script_starts(), codepoint) - 1
    if index >= 0:
        start, end, script = ranges[index]
        if start <= codepoint <= end:
            return script
    return "Unknown"
