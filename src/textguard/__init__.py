from __future__ import annotations

from .types import Change, CleanResult, Finding, FindingContext, ScanResult, SemanticResult

__version__ = "0.0.0"


class TextGuard:
    """Scaffold-only API surface until the scan and clean pipeline lands."""

    def __init__(self, **kwargs: object) -> None:
        self._config = dict(kwargs)

    def scan(self, text: str, *, include_context: bool = False) -> ScanResult:
        raise NotImplementedError("textguard.scan() is not implemented yet.")

    def clean(self, text: str, *, include_context: bool = False) -> CleanResult:
        raise NotImplementedError("textguard.clean() is not implemented yet.")

    def score_semantic(self, text: str) -> SemanticResult:
        raise NotImplementedError("PromptGuard integration is not implemented yet.")

    def match_yara(self, text: str) -> list[Finding]:
        raise NotImplementedError("YARA integration is not implemented yet.")


def scan(text: str, *, include_context: bool = False, **kwargs: object) -> ScanResult:
    return TextGuard(**kwargs).scan(text, include_context=include_context)


def clean(text: str, *, include_context: bool = False, **kwargs: object) -> CleanResult:
    return TextGuard(**kwargs).clean(text, include_context=include_context)


__all__ = [
    "Change",
    "CleanResult",
    "Finding",
    "FindingContext",
    "ScanResult",
    "SemanticResult",
    "TextGuard",
    "__version__",
    "clean",
    "scan",
]
