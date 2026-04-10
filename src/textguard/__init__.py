from __future__ import annotations

from .backends import YaraBackend, load_yara_backend
from .clean import clean_text
from .config import resolve_config
from .decode import decode_text_layers
from .normalize import normalize_text
from .scan import dedupe_findings, scan_text
from .types import Change, CleanResult, Finding, FindingContext, ScanResult, SemanticResult

__version__ = "0.0.0"


class TextGuard:
    """Configured entry point for the textguard scan and clean pipelines."""

    def __init__(self, **kwargs: object) -> None:
        self._config = resolve_config(dict(kwargs))
        self._yara_backend: YaraBackend | None = None
        self._yara_backend_loaded = False

    def scan(self, text: str, *, include_context: bool = False) -> ScanResult:
        result = scan_text(text, config=self._config, include_context=include_context)
        backend = self._maybe_yara_backend()
        if backend is not None:
            result.findings.extend(backend.match(text, decoded_text=result.decoded_text))
            result.findings = dedupe_findings(result.findings)
        return result

    def clean(self, text: str, *, include_context: bool = False) -> CleanResult:
        scan_result = self.scan(text, include_context=include_context)
        return clean_text(
            text,
            config=self._config,
            include_context=include_context,
            scan_result=scan_result,
        )

    def score_semantic(self, text: str) -> SemanticResult:
        raise RuntimeError("PromptGuard backend is not configured yet.")

    def match_yara(self, text: str) -> list[Finding]:
        backend = self._require_yara_backend()
        normalized_text = normalize_text(
            text,
            form=self._config.preset_settings.normalization_form,
            strip_ansi=True,
            strip_invisible=True,
            strip_bidi=True,
            strip_variation_selectors=True,
            strip_tag_chars=True,
            strip_soft_hyphens=True,
            collapse_whitespace=True,
        )
        decoded = decode_text_layers(normalized_text)
        return backend.match(text, decoded_text=decoded.text)

    def _maybe_yara_backend(self) -> YaraBackend | None:
        if not (self._config.yara_bundled or self._config.yara_rules_dir is not None):
            return None
        return self._require_yara_backend()

    def _require_yara_backend(self) -> YaraBackend:
        if self._yara_backend_loaded:
            if self._yara_backend is None:
                raise RuntimeError("YARA backend is not available for this TextGuard instance.")
            return self._yara_backend

        self._yara_backend_loaded = True
        self._yara_backend = load_yara_backend(
            rules_dir=self._config.yara_rules_dir,
            bundled=self._config.yara_bundled,
        )
        return self._yara_backend


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
