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
    """Read-only analysis output from scan().

    normalized_text and decoded_text are analysis artifacts: scan() normalizes and decodes
    aggressively so downstream detectors and backends inspect the strongest available signal.
    """

    findings: list[Finding] = field(default_factory=list)
    normalized_text: str = ""
    decoded_text: str = ""
    decode_depth: int = 0
    decode_reason_codes: list[str] = field(default_factory=list)
    semantic: SemanticResult | None = None


@dataclass(slots=True)
class CleanResult:
    """Cleaned output plus the findings that informed it.

    findings reflect what scan() observed in the original and decoded analysis pipeline, not
    just the subset of issues the active preset rewrote out of the final text.
    """

    text: str = ""
    original_text: str = ""
    changes: list[Change] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
