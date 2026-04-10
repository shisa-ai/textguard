from __future__ import annotations

import textguard
from textguard import Change, CleanResult, Finding, FindingContext, ScanResult, SemanticResult


def test_top_level_import_surface_exposes_phase_one_api() -> None:
    assert textguard.__version__ == "0.0.0"
    assert textguard.TextGuard().__class__.__name__ == "TextGuard"
    assert callable(textguard.scan)
    assert callable(textguard.clean)
    assert Change is not None
    assert CleanResult is not None
    assert Finding is not None
    assert FindingContext is not None
    assert ScanResult is not None
    assert SemanticResult is not None
