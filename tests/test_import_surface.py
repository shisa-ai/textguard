from __future__ import annotations

import textguard
from textguard import Change, CleanResult, Finding, FindingContext, ScanResult, SemanticResult


def test_top_level_import_surface_exposes_only_public_api() -> None:
    assert textguard.__version__ == "0.9.0"
    assert textguard.TextGuard().__class__.__name__ == "TextGuard"
    assert callable(textguard.scan)
    assert callable(textguard.clean)
    assert Change is not None
    assert CleanResult is not None
    assert Finding is not None
    assert FindingContext is not None
    assert ScanResult is not None
    assert SemanticResult is not None
    for hidden in (
        "clean_text",
        "decode_text_layers",
        "PromptGuardBackend",
        "YaraBackend",
        "load_promptguard_backend",
        "load_yara_backend",
        "normalize_text",
        "scan_text",
        "scores_to_semantic_result",
    ):
        assert not hasattr(textguard, hidden)
