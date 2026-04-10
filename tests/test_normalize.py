from __future__ import annotations

from textguard.normalize import DEFAULT_COMBINING_MARK_CAP, normalize_text, strip_non_ascii


def test_normalize_preserves_benign_multilingual_text() -> None:
    samples = (
        "こんにちは 世界",
        "مرحبا بالعالم",
        "سلام دنیا",
    )

    for sample in samples:
        findings = []
        normalized = normalize_text(sample, findings=findings)
        assert normalized == sample
        assert findings == []


def test_normalize_strips_invisible_and_bidi_controls() -> None:
    findings = []
    normalized = normalize_text("hello\u200b\u202eworld\u202c", findings=findings)

    assert normalized == "helloworld"
    assert {item.kind for item in findings} == {"bidi_control", "invisible_char"}


def test_normalize_strips_tag_soft_hyphen_and_variation_selector() -> None:
    findings = []
    raw = "A\U000E0041\u00adB\ufe0f"
    normalized = normalize_text(raw, findings=findings)

    assert normalized == "AB"
    assert {item.kind for item in findings} == {
        "soft_hyphen",
        "tag_character",
        "variation_selector",
    }


def test_normalize_strips_ansi_and_collapses_whitespace() -> None:
    findings = []
    raw = "\x1b[31mred\x1b[0m\t value\n\nnext"
    normalized = normalize_text(raw, findings=findings)

    assert normalized == "red value next"
    assert findings[0].kind == "ansi_escape"


def test_normalize_caps_combining_marks() -> None:
    findings = []
    raw = "q" + "\u0301" * (DEFAULT_COMBINING_MARK_CAP + 2)
    normalized = normalize_text(raw, findings=findings)

    assert normalized == "q" + "\u0301" * DEFAULT_COMBINING_MARK_CAP
    assert all(item.kind == "combining_abuse" for item in findings)
    assert len(findings) == 2


def test_strip_non_ascii_is_lossy_and_explicit() -> None:
    raw = "\uFF21\uFF22\uFF23 café 東京"
    assert strip_non_ascii(raw) == "ABC cafe "
