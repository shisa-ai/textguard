from __future__ import annotations

from .backends import PromptGuardBackend as _PromptGuardBackend
from .backends import YaraBackend as _YaraBackend
from .backends import load_promptguard_backend as _load_promptguard_backend
from .backends import load_yara_backend as _load_yara_backend
from .backends import scores_to_semantic_result as _scores_to_semantic_result
from .clean import clean_text as _clean_text
from .config import resolve_config as _resolve_config
from .decode import decode_text_layers as _decode_text_layers
from .normalize import normalize_text as _normalize_text
from .scan import dedupe_findings as _dedupe_findings
from .scan import scan_text as _scan_text
from .types import Change, CleanResult, Finding, FindingContext, ScanResult, SemanticResult

__version__ = "1.0.0"


class TextGuard:
    """Configured entry point for the textguard scan and clean pipelines."""

    def __init__(self, **kwargs: object) -> None:
        self._config = _resolve_config(dict(kwargs))
        self._yara_backend: _YaraBackend | None = None
        self._yara_backend_loaded = False
        self._promptguard_backend: _PromptGuardBackend | None = None
        self._promptguard_backend_loaded = False

    def scan(self, text: str, *, include_context: bool = False) -> ScanResult:
        return self._scan(text, include_context=include_context, include_semantic=True)

    def _scan(
        self,
        text: str,
        *,
        include_context: bool,
        include_semantic: bool,
    ) -> ScanResult:
        result = _scan_text(text, config=self._config, include_context=include_context)
        backend = self._maybe_yara_backend()
        if backend is not None:
            result.findings.extend(backend.match(text, decoded_text=result.decoded_text))
            result.findings = _dedupe_findings(result.findings)
        if include_semantic:
            promptguard_backend = self._maybe_promptguard_backend()
            if promptguard_backend is not None:
                score, tier, classifier_id = _scores_to_semantic_result(
                    promptguard_backend.score_text(text)
                )
                result.semantic = SemanticResult(
                    score=score,
                    tier=tier,
                    classifier_id=classifier_id,
                )
        return result

    def clean(self, text: str, *, include_context: bool = False) -> CleanResult:
        scan_result = self._scan(text, include_context=include_context, include_semantic=False)
        return _clean_text(
            text,
            config=self._config,
            include_context=include_context,
            scan_result=scan_result,
        )

    def score_semantic(self, text: str) -> SemanticResult:
        backend = self._require_promptguard_backend()
        score, tier, classifier_id = _scores_to_semantic_result(backend.score_text(text))
        return SemanticResult(score=score, tier=tier, classifier_id=classifier_id)

    def match_yara(self, text: str) -> list[Finding]:
        backend = self._require_yara_backend()
        normalized_text = _normalize_text(
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
        decoded = _decode_text_layers(normalized_text)
        return backend.match(text, decoded_text=decoded.text)

    def _maybe_yara_backend(self) -> _YaraBackend | None:
        if not (self._config.yara_bundled or self._config.yara_rules_dir is not None):
            return None
        return self._require_yara_backend()

    def _maybe_promptguard_backend(self) -> _PromptGuardBackend | None:
        if self._config.promptguard_model_path is None:
            return None
        return self._require_promptguard_backend()

    def _require_yara_backend(self) -> _YaraBackend:
        if self._yara_backend_loaded:
            if self._yara_backend is None:
                raise RuntimeError("YARA backend is not available for this TextGuard instance.")
            return self._yara_backend

        backend = _load_yara_backend(
            rules_dir=self._config.yara_rules_dir,
            bundled=self._config.yara_bundled,
        )
        self._yara_backend = backend
        self._yara_backend_loaded = True
        return self._yara_backend

    def _require_promptguard_backend(self) -> _PromptGuardBackend:
        if self._config.promptguard_model_path is None:
            raise RuntimeError("PromptGuard backend is not enabled for this TextGuard instance.")
        if self._promptguard_backend_loaded:
            if self._promptguard_backend is None:
                raise RuntimeError(
                    "PromptGuard backend is not available for this TextGuard instance."
                )
            return self._promptguard_backend

        backend = _load_promptguard_backend(
            self._config.promptguard_model_path,
        )
        self._promptguard_backend = backend
        self._promptguard_backend_loaded = True
        return self._promptguard_backend


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
