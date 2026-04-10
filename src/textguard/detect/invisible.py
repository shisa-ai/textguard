from __future__ import annotations

import re
import unicodedata

from ..types import Finding

ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

INVISIBLE_CODEPOINTS = {
    0x034F,  # COMBINING GRAPHEME JOINER
    0x061C,  # ARABIC LETTER MARK
    0x180E,  # MONGOLIAN VOWEL SEPARATOR
    0x200B,  # ZERO WIDTH SPACE
    0x200C,  # ZERO WIDTH NON-JOINER
    0x200D,  # ZERO WIDTH JOINER
    0x2060,  # WORD JOINER
    0xFEFF,  # ZERO WIDTH NO-BREAK SPACE / BOM
}
BIDI_CODEPOINTS = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A))
TAG_CODEPOINTS = set(range(0xE0000, 0xE0080))
VARIATION_SELECTOR_CODEPOINTS = set(range(0xFE00, 0xFE10)) | set(range(0xE0100, 0xE01F0))
SOFT_HYPHEN = 0x00AD

DEFAULT_COMBINING_MARK_CAP = 3


def detect_invisible_text(
    text: str,
    *,
    max_combining_marks: int | None = DEFAULT_COMBINING_MARK_CAP,
    in_decoded_text: bool = False,
) -> list[Finding]:
    findings: list[Finding] = []
    offset_mode = None if in_decoded_text else 0
    detail_suffix = " in decoded text" if in_decoded_text else ""

    for match in ANSI_ESCAPE_RE.finditer(text):
        findings.append(
            Finding(
                kind="ansi_escape",
                severity="warn",
                detail=f"ANSI escape sequence detected{detail_suffix}",
                offset=None if offset_mode is None else match.start(),
            )
        )

    for offset, char in enumerate(text):
        codepoint = ord(char)
        finding_offset = None if offset_mode is None else offset
        if codepoint in INVISIBLE_CODEPOINTS:
            findings.append(
                _char_finding(
                    kind="invisible_char",
                    severity="warn",
                    codepoint=codepoint,
                    offset=finding_offset,
                    detail_suffix=detail_suffix,
                )
            )
        elif codepoint in BIDI_CODEPOINTS:
            findings.append(
                _char_finding(
                    kind="bidi_control",
                    severity="error",
                    codepoint=codepoint,
                    offset=finding_offset,
                    detail_suffix=detail_suffix,
                )
            )
        elif codepoint in TAG_CODEPOINTS:
            findings.append(
                _char_finding(
                    kind="tag_character",
                    severity="error",
                    codepoint=codepoint,
                    offset=finding_offset,
                    detail_suffix=detail_suffix,
                )
            )
        elif codepoint in VARIATION_SELECTOR_CODEPOINTS:
            findings.append(
                _char_finding(
                    kind="variation_selector",
                    severity="warn",
                    codepoint=codepoint,
                    offset=finding_offset,
                    detail_suffix=detail_suffix,
                )
            )
        elif codepoint == SOFT_HYPHEN:
            findings.append(
                _char_finding(
                    kind="soft_hyphen",
                    severity="warn",
                    codepoint=codepoint,
                    offset=finding_offset,
                    detail_suffix=detail_suffix,
                )
            )

    findings.extend(
        _detect_combining_abuse(
            text,
            max_combining_marks=max_combining_marks,
            in_decoded_text=in_decoded_text,
        )
    )
    return findings


def _detect_combining_abuse(
    text: str,
    *,
    max_combining_marks: int | None,
    in_decoded_text: bool,
) -> list[Finding]:
    if max_combining_marks is None:
        return []
    if max_combining_marks < 0:
        raise ValueError("max_combining_marks must be >= 0 or None")

    findings: list[Finding] = []
    run_length = 0
    detail = f"Combining mark cap exceeded ({max_combining_marks})"
    if in_decoded_text:
        detail = f"{detail} in decoded text"
    for offset, char in enumerate(text):
        if unicodedata.combining(char):
            run_length += 1
            if run_length > max_combining_marks:
                findings.append(
                    Finding(
                        kind="combining_abuse",
                        severity="warn",
                        detail=detail,
                        codepoint=_format_codepoint(ord(char)),
                        offset=None if in_decoded_text else offset,
                    )
                )
        else:
            run_length = 0
    return findings


def _char_finding(
    *,
    kind: str,
    severity: str,
    codepoint: int,
    offset: int | None,
    detail_suffix: str,
) -> Finding:
    codepoint_text = _format_codepoint(codepoint)
    return Finding(
        kind=kind,
        severity=severity,
        detail=f"{kind.replace('_', ' ').title()} {codepoint_text}{detail_suffix}",
        codepoint=codepoint_text,
        offset=offset,
    )


def _format_codepoint(codepoint: int) -> str:
    width = 6 if codepoint > 0xFFFF else 4
    return f"U+{codepoint:0{width}X}"
