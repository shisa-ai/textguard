from __future__ import annotations

import re
from typing import Final

from ..decode import _base64_decode_candidate
from ..types import Finding

_BASE64_TOKEN_RE = re.compile(r"\b[A-Za-z0-9+/]{24,}={0,2}\b")
_SPLIT_TOKEN_WORDS: Final[tuple[str, ...]] = (
    "ignore",
    "developer",
    "instruction",
    "instructions",
    "prompt",
    "system",
)
_SIGNAL_TOKENS: Final[tuple[str, ...]] = (
    "curl",
    "developer",
    "ignore",
    "instruction",
    "instructions",
    "password",
    "prompt",
    "secret",
    "system",
    "token",
    "wget",
    "http://",
    "https://",
)


def detect_encoded_payloads(
    text: str,
    *,
    split_tokens: bool = False,
    in_decoded_text: bool = False,
) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(_detect_base64_payloads(text, in_decoded_text=in_decoded_text))
    if split_tokens:
        findings.extend(_detect_split_tokens(text, in_decoded_text=in_decoded_text))
    return findings


def _detect_base64_payloads(text: str, *, in_decoded_text: bool) -> list[Finding]:
    findings: list[Finding] = []
    for match in _BASE64_TOKEN_RE.finditer(text):
        token = match.group(0)
        decoded = _base64_decode_candidate(token)
        if decoded is None:
            continue
        severity = "warn"
        detail = "Base64-like payload decodes to readable text"
        lowered = decoded.lower()
        if any(signal in lowered for signal in _SIGNAL_TOKENS):
            severity = "error"
            detail = "Base64-like payload decodes to instruction-like text"
        if in_decoded_text:
            detail = f"{detail} in decoded text"
        findings.append(
            Finding(
                kind="encoded_payload",
                severity=severity,
                detail=detail,
                offset=None if in_decoded_text else match.start(),
            )
        )
    return findings


def _detect_split_tokens(text: str, *, in_decoded_text: bool) -> list[Finding]:
    findings: list[Finding] = []
    for word in _SPLIT_TOKEN_WORDS:
        pattern = _split_token_pattern(word)
        for match in pattern.finditer(text):
            detail = f"Split-token pattern matched protected keyword '{word}'"
            if in_decoded_text:
                detail = f"{detail} in decoded text"
            findings.append(
                Finding(
                    kind="split_token",
                    severity="warn",
                    detail=detail,
                    offset=None if in_decoded_text else match.start(),
                )
            )
    return findings


def _split_token_pattern(word: str) -> re.Pattern[str]:
    separator = r"[\s._:/\\|,\-]*"
    return re.compile(separator.join(re.escape(char) for char in word), re.IGNORECASE)
