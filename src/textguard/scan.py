from __future__ import annotations

from dataclasses import replace

from .config import TextGuardConfig
from .decode import decode_text_layers
from .detect import detect_encoded_payloads, detect_homoglyphs, detect_invisible_text
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
    )
    decoded = decode_text_layers(normalized_text, findings=findings)
    findings.extend(detect_invisible_text(text))
    findings.extend(detect_homoglyphs(text, confusables=config.confusables))
    findings.extend(detect_encoded_payloads(text))
    if decoded.text != normalized_text:
        findings.extend(detect_invisible_text(decoded.text, in_decoded_text=True))
        findings.extend(
            detect_homoglyphs(
                decoded.text,
                confusables=config.confusables,
                in_decoded_text=True,
            )
        )
        findings.extend(detect_encoded_payloads(decoded.text, in_decoded_text=True))

    findings = _dedupe_findings(findings)

    if include_context:
        findings = _attach_context(text, findings)

    return ScanResult(
        findings=findings,
        normalized_text=normalized_text,
        decoded_text=decoded.text,
        decode_depth=decoded.decode_depth,
        decode_reason_codes=list(decoded.reason_codes),
    )


def _dedupe_findings(findings: list[Finding]) -> list[Finding]:
    deduped: list[Finding] = []
    seen: set[tuple[str, str, str, str, int | None]] = set()
    for finding in findings:
        key = (
            finding.kind,
            finding.severity,
            finding.detail,
            finding.codepoint,
            finding.offset,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped


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
