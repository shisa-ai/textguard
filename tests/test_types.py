from __future__ import annotations

from textguard.types import Change, CleanResult, DecodedText, Finding, FindingContext, ScanResult


def test_type_defaults_match_plan_contract() -> None:
    finding = Finding(kind="invisible_char", severity="warn")
    assert finding.detail == ""
    assert finding.codepoint == ""
    assert finding.offset is None
    assert finding.context is None

    decoded = DecodedText(text="decoded")
    assert decoded.reason_codes == ()
    assert decoded.decode_depth == 0

    scan_result = ScanResult()
    clean_result = CleanResult()
    assert scan_result.findings == []
    assert scan_result.decode_reason_codes == []
    assert clean_result.changes == []
    assert clean_result.findings == []


def test_mutable_defaults_are_not_shared() -> None:
    first = ScanResult()
    second = ScanResult()
    first.findings.append(Finding(kind="encoded_payload", severity="error"))
    first.decode_reason_codes.append("encoding:base64_decoded")
    assert second.findings == []
    assert second.decode_reason_codes == []


def test_context_and_change_types_round_trip() -> None:
    context = FindingContext(excerpt="visible text")
    finding = Finding(kind="invisible_char", severity="warn", context=context)
    change = Change(kind="normalized", detail="Applied placeholder normalization.")
    clean_result = CleanResult(changes=[change], findings=[finding])
    assert clean_result.findings[0].context == context
    assert clean_result.changes[0].kind == "normalized"
