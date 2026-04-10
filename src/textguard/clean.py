from __future__ import annotations

import unicodedata

from .config import PRESETS, TextGuardConfig
from .decode import decode_text_layers
from .normalize import normalize_text, strip_non_ascii
from .scan import scan_text
from .types import Change, CleanResult, ScanResult


def clean_text(
    text: str,
    *,
    config: TextGuardConfig,
    include_context: bool = False,
    scan_result: ScanResult | None = None,
) -> CleanResult:
    if scan_result is None:
        scan_result = scan_text(text, config=config, include_context=include_context)
    preset = config.preset_settings

    cleaned = text
    changes: list[Change] = []

    normalized_only = unicodedata.normalize(preset.normalization_form, cleaned)
    if normalized_only != cleaned:
        cleaned = normalized_only
        changes.append(
            Change(
                kind="normalized",
                detail=f"Applied {preset.normalization_form} normalization",
            )
        )

    cleaned_after_stripping = normalize_text(
        cleaned,
        form=preset.normalization_form,
        strip_ansi=preset.strip_ansi,
        strip_invisible=preset.strip_invisible,
        strip_bidi=preset.strip_bidi,
        strip_variation_selectors=preset.strip_variation_selectors,
        strip_tag_chars=preset.strip_tag_chars,
        strip_soft_hyphens=preset.strip_soft_hyphens,
        collapse_whitespace=preset.collapse_whitespace,
        max_combining_marks=preset.max_combining_marks,
    )
    if cleaned_after_stripping != cleaned:
        cleaned = cleaned_after_stripping
        changes.append(
            Change(
                kind="stripped",
                detail=f"Applied {preset.name} cleanup rules",
            )
        )

    if preset.decode_on_clean:
        decoded = decode_text_layers(cleaned)
        if decoded.text != cleaned:
            cleaned = decoded.text
            changes.append(
                Change(
                    kind="decoded",
                    detail=f"Decoded {len(decoded.reason_codes)} encoding layer markers",
                )
            )

    if preset.ascii_transliterate:
        ascii_text = strip_non_ascii(cleaned)
        if ascii_text != cleaned:
            cleaned = ascii_text
            changes.append(
                Change(
                    kind="normalized",
                    detail="Applied ASCII transliteration",
                )
            )

    return CleanResult(
        text=cleaned,
        original_text=text,
        changes=changes,
        findings=scan_result.findings,
    )


def preset_names() -> tuple[str, ...]:
    return tuple(PRESETS)
