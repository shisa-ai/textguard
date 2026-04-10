from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class FindingContext:
    excerpt: str


@dataclass(slots=True)
class Finding:
    kind: str
    severity: str
    detail: str = ""
    codepoint: str = ""
    offset: int | None = None
    context: FindingContext | None = None


@dataclass(slots=True)
class Change:
    kind: str
    detail: str = ""


@dataclass(slots=True)
class SemanticResult:
    score: float
    tier: str
    classifier_id: str


@dataclass(slots=True)
class DecodedText:
    text: str
    reason_codes: tuple[str, ...] = ()
    decode_depth: int = 0


@dataclass(slots=True)
class ScanResult:
    findings: list[Finding] = field(default_factory=list)
    normalized_text: str = ""
    decoded_text: str = ""
    decode_depth: int = 0
    decode_reason_codes: list[str] = field(default_factory=list)
    semantic: SemanticResult | None = None


@dataclass(slots=True)
class CleanResult:
    text: str = ""
    original_text: str = ""
    changes: list[Change] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
