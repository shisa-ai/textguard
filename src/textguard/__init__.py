from __future__ import annotations

from .clean import clean_text
from .config import resolve_config
from .scan import scan_text
from .types import Change, CleanResult, Finding, FindingContext, ScanResult, SemanticResult

__version__ = "0.0.0"


class TextGuard:
    """Configured entry point for the textguard scan and clean pipelines."""

    def __init__(self, **kwargs: object) -> None:
        self._config = resolve_config(dict(kwargs))

    def scan(self, text: str, *, include_context: bool = False) -> ScanResult:
        return scan_text(text, config=self._config, include_context=include_context)

    def clean(self, text: str, *, include_context: bool = False) -> CleanResult:
        return clean_text(text, config=self._config, include_context=include_context)

    def score_semantic(self, text: str) -> SemanticResult:
        raise RuntimeError("PromptGuard backend is not configured yet.")

    def match_yara(self, text: str) -> list[Finding]:
        raise RuntimeError("YARA backend is not configured yet.")


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
