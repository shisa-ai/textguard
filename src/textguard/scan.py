from __future__ import annotations

from dataclasses import replace

from .config import TextGuardConfig
from .decode import decode_text_layers
from .normalize import normalize_text
from .types import Finding, FindingContext, ScanResult

_CONTEXT_RADIUS = 24


def scan_text(
    text: str,
    *,
    config: TextGuardConfig,
    include_context: bool = False,
) -> ScanResult:
    findings: list[Finding] = []

    normalized_text = normalize_text(
        text,
        form=config.preset_settings.normalization_form,
        strip_ansi=True,
        strip_invisible=True,
        strip_bidi=True,
        strip_variation_selectors=True,
        strip_tag_chars=True,
        strip_soft_hyphens=True,
        collapse_whitespace=True,
        findings=findings,
    )
    decoded = decode_text_layers(normalized_text, findings=findings)

    if include_context:
        findings = _attach_context(text, findings)

    return ScanResult(
        findings=findings,
        normalized_text=normalized_text,
        decoded_text=decoded.text,
        decode_depth=decoded.decode_depth,
        decode_reason_codes=list(decoded.reason_codes),
    )


def _attach_context(original_text: str, findings: list[Finding]) -> list[Finding]:
    contextualized: list[Finding] = []
    for finding in findings:
        if finding.offset is None:
            contextualized.append(finding)
            continue
        start = max(0, finding.offset - _CONTEXT_RADIUS)
        end = min(len(original_text), finding.offset + _CONTEXT_RADIUS)
        contextualized.append(
            replace(
                finding,
                context=FindingContext(excerpt=original_text[start:end]),
            )
        )
    return contextualized
