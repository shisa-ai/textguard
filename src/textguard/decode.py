from __future__ import annotations

import base64
import binascii
import html
import re
from collections.abc import Callable
from urllib.parse import unquote

from .types import DecodedText, Finding

_BASE64_RE = re.compile(r"[A-Za-z0-9+/=\s]{24,}")
_BASE64_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{24,}={0,2}(?![A-Za-z0-9+/=])"
)
_UNICODE_ESCAPE_RE = re.compile(r"\\u([0-9a-fA-F]{4})|\\U([0-9a-fA-F]{8})")
_HEX_ESCAPE_RE = re.compile(r"\\x([0-9a-fA-F]{2})")
_PUNYCODE_LABEL_RE = re.compile(r"\bxn--[a-z0-9-]+\b", re.IGNORECASE)
_ROT13_SIGNAL_TOKENS = (
    "api key",
    "curl",
    "developer message",
    "disregard",
    "exfiltrate",
    "http://",
    "https://",
    "ignore",
    "instruction",
    "password",
    "reveal",
    "secret",
    "system prompt",
    "token",
    "wget",
)


def decode_text_layers(
    text: str,
    *,
    max_depth: int = 3,
    max_expansion_ratio: float = 4.0,
    max_total_chars: int = 32768,
    findings: list[Finding] | None = None,
) -> DecodedText:
    """Unwind supported encodings with explicit recursion and size bounds."""

    if max_depth <= 0:
        return DecodedText(text=text)
    if max_expansion_ratio <= 0:
        raise ValueError("max_expansion_ratio must be > 0")
    if max_total_chars <= 0:
        raise ValueError("max_total_chars must be > 0")

    current = text
    reason_codes: set[str] = set()
    emitted_findings: set[str] = set()
    depth = 0

    for _ in range(max_depth):
        changed = False
        for decoder, reason in _decoder_steps():
            candidate = decoder(current)
            current, applied = _apply_bounded_decode(
                current=current,
                candidate=candidate,
                reason=reason,
                reason_codes=reason_codes,
                emitted_findings=emitted_findings,
                findings=findings,
                max_expansion_ratio=max_expansion_ratio,
                max_total_chars=max_total_chars,
            )
            changed = changed or applied
        if not changed:
            break
        depth += 1

    if depth >= max_depth and _has_additional_layer(current):
        _record_reason(
            "encoding:decode_depth_limited",
            severity="warn",
            reason_codes=reason_codes,
            findings=findings,
            emitted_findings=emitted_findings,
            detail="Maximum decode depth reached while encodings remained",
        )

    return DecodedText(
        text=current,
        reason_codes=tuple(sorted(reason_codes)),
        decode_depth=depth,
    )


def _decoder_steps() -> tuple[tuple[Callable[[str], str | None], str], ...]:
    return (
        (_url_decode_candidate, "encoding:url_decoded"),
        (_html_decode_candidate, "encoding:html_entity_decoded"),
        (_rot13_decode_candidate, "encoding:rot13_decoded"),
        (_base64_decode_candidate, "encoding:base64_decoded"),
        (_unicode_escape_decode_candidate, "encoding:unicode_escape_decoded"),
        (_hex_escape_decode_candidate, "encoding:hex_escape_decoded"),
        (_punycode_decode_candidate, "encoding:punycode_decoded"),
    )


def _apply_bounded_decode(
    *,
    current: str,
    candidate: str | None,
    reason: str,
    reason_codes: set[str],
    emitted_findings: set[str],
    findings: list[Finding] | None,
    max_expansion_ratio: float,
    max_total_chars: int,
) -> tuple[str, bool]:
    if candidate is None or candidate == current:
        return current, False
    if len(candidate) > max_total_chars:
        _record_reason(
            "encoding:decode_bound_hit",
            severity="warn",
            reason_codes=reason_codes,
            findings=findings,
            emitted_findings=emitted_findings,
            detail="Decode candidate exceeded max_total_chars",
        )
        return current, False
    expansion_limit = max(1, int(len(current) * max_expansion_ratio))
    if len(candidate) > expansion_limit:
        _record_reason(
            "encoding:decode_bound_hit",
            severity="warn",
            reason_codes=reason_codes,
            findings=findings,
            emitted_findings=emitted_findings,
            detail="Decode candidate exceeded max_expansion_ratio",
        )
        return current, False
    _record_reason(
        reason,
        severity="info",
        reason_codes=reason_codes,
        findings=findings,
        emitted_findings=emitted_findings,
        detail=f"Applied {reason.removeprefix('encoding:').replace('_', ' ')}",
    )
    return candidate, True


def _record_reason(
    reason: str,
    *,
    severity: str,
    reason_codes: set[str],
    findings: list[Finding] | None,
    emitted_findings: set[str],
    detail: str,
) -> None:
    reason_codes.add(reason)
    if findings is None or reason in emitted_findings:
        return
    findings.append(Finding(kind=reason, severity=severity, detail=detail))
    emitted_findings.add(reason)


def _url_decode_candidate(text: str) -> str | None:
    if "%" not in text:
        return None
    candidate = unquote(text)
    return candidate if candidate != text else None


def _html_decode_candidate(text: str) -> str | None:
    if "&" not in text:
        return None
    candidate = html.unescape(text)
    return candidate if candidate != text else None


def _rot13_decode_candidate(text: str) -> str | None:
    translated = text.translate(
        str.maketrans(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
            "NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm",
        )
    )
    if translated == text:
        return None
    lowered_raw = text.lower()
    lowered_decoded = translated.lower()
    decoded_hits = {token for token in _ROT13_SIGNAL_TOKENS if token in lowered_decoded}
    if not decoded_hits:
        return None
    raw_hits = {token for token in _ROT13_SIGNAL_TOKENS if token in lowered_raw}
    if not (decoded_hits - raw_hits):
        return None
    return translated


def _base64_decode_candidate(text: str) -> str | None:
    try:
        candidate = _base64_decode_string(text, allow_whitespace=True)
    except (ValueError, binascii.Error, UnicodeDecodeError):
        candidate = None

    if candidate is not None:
        if candidate == text or not _looks_like_text(candidate):
            return None
        return candidate

    return _base64_decode_inline_candidate(text)


def _base64_decode_inline_candidate(text: str) -> str | None:
    matches = list(_BASE64_TOKEN_RE.finditer(text))
    if not matches:
        return None

    pieces: list[str] = []
    cursor = 0
    changed = False
    for match in matches:
        pieces.append(text[cursor : match.start()])
        token = match.group(0)
        try:
            decoded = _base64_decode_string(token, allow_whitespace=False)
        except (ValueError, binascii.Error, UnicodeDecodeError):
            decoded = None
        if decoded is not None and decoded != token and _looks_like_text(decoded):
            pieces.append(decoded)
            changed = True
        else:
            pieces.append(token)
        cursor = match.end()
    pieces.append(text[cursor:])
    if not changed:
        return None
    return "".join(pieces)


def _base64_decode_string(text: str, *, allow_whitespace: bool) -> str | None:
    compact = re.sub(r"\s+", "", text) if allow_whitespace else text
    if len(compact) < 24:
        return None
    if allow_whitespace:
        if not _BASE64_RE.fullmatch(text):
            return None
    else:
        if not _BASE64_TOKEN_RE.fullmatch(text):
            return None
    padding = "=" * ((4 - (len(compact) % 4)) % 4)
    decoded = base64.b64decode(compact + padding, validate=True)
    return decoded.decode("utf-8")


def _unicode_escape_decode_candidate(text: str) -> str | None:
    if not _UNICODE_ESCAPE_RE.search(text):
        return None
    candidate = _UNICODE_ESCAPE_RE.sub(_replace_unicode_escape, text)
    return candidate if candidate != text else None


def _hex_escape_decode_candidate(text: str) -> str | None:
    if not _HEX_ESCAPE_RE.search(text):
        return None
    candidate = _HEX_ESCAPE_RE.sub(_replace_hex_escape, text)
    return candidate if candidate != text else None


def _punycode_decode_candidate(text: str) -> str | None:
    if "xn--" not in text.lower():
        return None
    changed = False

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        label = match.group(0)
        try:
            decoded = label.encode("ascii").decode("idna")
        except UnicodeError:
            return label
        if decoded != label:
            changed = True
        return decoded

    candidate = _PUNYCODE_LABEL_RE.sub(replace, text)
    return candidate if changed else None


def _replace_unicode_escape(match: re.Match[str]) -> str:
    hex_text = match.group(1) or match.group(2)
    return chr(int(hex_text, 16))


def _replace_hex_escape(match: re.Match[str]) -> str:
    return chr(int(match.group(1), 16))


def _has_additional_layer(text: str) -> bool:
    return any(decoder(text) is not None for decoder, _ in _decoder_steps())


def _looks_like_text(candidate: str) -> bool:
    if not candidate or "\x00" in candidate:
        return False
    printable = sum(1 for char in candidate if char.isprintable() or char.isspace())
    ratio = printable / len(candidate)
    if ratio < 0.85:
        return False
    return any(char.isalpha() for char in candidate)
