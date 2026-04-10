from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Literal

from .types import Finding

_ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

_INVISIBLE_CODEPOINTS = {
    0x034F,  # COMBINING GRAPHEME JOINER
    0x061C,  # ARABIC LETTER MARK
    0x180E,  # MONGOLIAN VOWEL SEPARATOR
    0x200B,  # ZERO WIDTH SPACE
    0x200C,  # ZERO WIDTH NON-JOINER
    0x200D,  # ZERO WIDTH JOINER
    0x2060,  # WORD JOINER
    0xFEFF,  # ZERO WIDTH NO-BREAK SPACE / BOM
}
_BIDI_CODEPOINTS = set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A))
_TAG_CODEPOINTS = set(range(0xE0000, 0xE0080))
_VARIATION_SELECTOR_CODEPOINTS = set(range(0xFE00, 0xFE10)) | set(range(0xE0100, 0xE01F0))
_SOFT_HYPHEN = 0x00AD

DEFAULT_COMBINING_MARK_CAP = 3


def normalize_text(
    text: str,
    *,
    form: Literal["NFC", "NFKC"] = "NFC",
    strip_ansi: bool = True,
    strip_invisible: bool = True,
    strip_bidi: bool = True,
    strip_variation_selectors: bool = True,
    strip_tag_chars: bool = True,
    strip_soft_hyphens: bool = True,
    collapse_whitespace: bool = True,
    max_combining_marks: int | None = DEFAULT_COMBINING_MARK_CAP,
    findings: list[Finding] | None = None,
) -> str:
    """Normalize text for hostile-content analysis.

    The public primitive returns normalized text and optionally appends machine-readable
    findings into ``findings`` as suspicious characters or sequences are removed.
    """

    if form not in {"NFC", "NFKC"}:
        raise ValueError("form must be 'NFC' or 'NFKC'")

    stripped = _strip_ansi_sequences(text, findings=findings) if strip_ansi else text

    filtered_parts: list[str] = []
    previous_was_space = False
    for offset, char in enumerate(stripped):
        codepoint = ord(char)

        if strip_invisible and codepoint in _INVISIBLE_CODEPOINTS:
            _append_char_finding(
                findings,
                kind="invisible_char",
                severity="warn",
                codepoint=codepoint,
                offset=offset,
            )
            continue
        if strip_bidi and codepoint in _BIDI_CODEPOINTS:
            _append_char_finding(
                findings,
                kind="bidi_control",
                severity="error",
                codepoint=codepoint,
                offset=offset,
            )
            continue
        if strip_variation_selectors and codepoint in _VARIATION_SELECTOR_CODEPOINTS:
            _append_char_finding(
                findings,
                kind="variation_selector",
                severity="warn",
                codepoint=codepoint,
                offset=offset,
            )
            continue
        if strip_tag_chars and codepoint in _TAG_CODEPOINTS:
            _append_char_finding(
                findings,
                kind="tag_character",
                severity="error",
                codepoint=codepoint,
                offset=offset,
            )
            continue
        if strip_soft_hyphens and codepoint == _SOFT_HYPHEN:
            _append_char_finding(
                findings,
                kind="soft_hyphen",
                severity="warn",
                codepoint=codepoint,
                offset=offset,
            )
            continue

        if collapse_whitespace and char.isspace():
            if not previous_was_space:
                filtered_parts.append(" ")
            previous_was_space = True
            continue

        filtered_parts.append(char)
        previous_was_space = False

    normalized = unicodedata.normalize(form, "".join(filtered_parts))
    if collapse_whitespace:
        normalized = normalized.strip()

    return _cap_combining_marks(
        normalized,
        max_combining_marks=max_combining_marks,
        findings=findings,
    )


def strip_non_ascii(text: str) -> str:
    """Lossy ASCII transliteration used by the ascii preset."""

    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", errors="ignore").decode("ascii")


def _strip_ansi_sequences(text: str, *, findings: list[Finding] | None) -> str:
    if findings is None:
        return _ANSI_ESCAPE_RE.sub("", text)

    stripped_parts: list[str] = []
    last_end = 0
    for match in _ANSI_ESCAPE_RE.finditer(text):
        stripped_parts.append(text[last_end : match.start()])
        findings.append(
            Finding(
                kind="ansi_escape",
                severity="warn",
                detail="ANSI escape sequence stripped",
                offset=match.start(),
            )
        )
        last_end = match.end()
    stripped_parts.append(text[last_end:])
    return "".join(stripped_parts)


def _cap_combining_marks(
    text: str,
    *,
    max_combining_marks: int | None,
    findings: list[Finding] | None,
) -> str:
    if max_combining_marks is None:
        return text
    if max_combining_marks < 0:
        raise ValueError("max_combining_marks must be >= 0 or None")

    capped_parts: list[str] = []
    run_length = 0
    for offset, char in enumerate(text):
        if unicodedata.combining(char):
            run_length += 1
            if run_length > max_combining_marks:
                _append_char_finding(
                    findings,
                    kind="combining_abuse",
                    severity="warn",
                    codepoint=ord(char),
                    offset=offset,
                    detail=f"Combining mark cap exceeded ({max_combining_marks})",
                )
                continue
        else:
            run_length = 0
        capped_parts.append(char)
    return "".join(capped_parts)


def _append_char_finding(
    findings: list[Finding] | None,
    *,
    kind: str,
    severity: str,
    codepoint: int,
    offset: int | None,
    detail: str | None = None,
) -> None:
    if findings is None:
        return
    codepoint_text = _format_codepoint(codepoint)
    findings.append(
        Finding(
            kind=kind,
            severity=severity,
            detail=detail or f"{kind.replace('_', ' ').title()} {codepoint_text}",
            codepoint=codepoint_text,
            offset=offset,
        )
    )


def _format_codepoint(codepoint: int) -> str:
    width = 6 if codepoint > 0xFFFF else 4
    return f"U+{codepoint:0{width}X}"


def format_codepoints(chars: Iterable[str]) -> tuple[str, ...]:
    return tuple(_format_codepoint(ord(char)) for char in chars)
