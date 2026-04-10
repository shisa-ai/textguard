from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from ..types import Finding


@dataclass(slots=True)
class YaraBackend:
    compiled_rules: Any

    def match(self, raw_text: str, *, decoded_text: str | None = None) -> list[Finding]:
        findings = self._match_one(raw_text, source_label="raw")
        if decoded_text is not None and decoded_text != raw_text:
            findings.extend(self._match_one(decoded_text, source_label="decoded"))
        return findings

    def _match_one(self, text: str, *, source_label: str) -> list[Finding]:
        findings: list[Finding] = []
        for match in self.compiled_rules.match(data=text):
            detail = f"Matched YARA rule {match.rule} on {source_label} text"
            severity = _coerce_severity(match.meta.get("severity", "error"))
            findings.append(
                Finding(
                    kind=f"yara:{match.rule}",
                    severity=severity,
                    detail=detail,
                )
            )
        return findings


def load_yara_backend(*, rules_dir: Path | None, bundled: bool) -> YaraBackend:
    if not bundled and rules_dir is None:
        raise RuntimeError(
            "YARA backend is not enabled. Set yara_bundled=True or provide yara_rules_dir."
        )

    yara = _import_yara()
    rule_paths = _collect_rule_paths(rules_dir=rules_dir, bundled=bundled)
    if not rule_paths:
        raise RuntimeError("No YARA rules were found for the configured backend.")

    filepaths = {f"rule_{index:03d}": str(path) for index, path in enumerate(rule_paths, start=1)}
    try:
        compiled = yara.compile(filepaths=filepaths)
    except Exception as exc:
        raise RuntimeError(f"Failed to compile YARA rules: {exc}") from exc
    return YaraBackend(compiled_rules=compiled)


def _collect_rule_paths(*, rules_dir: Path | None, bundled: bool) -> list[Path]:
    paths: list[Path] = []
    if bundled:
        traversable = resources.files("textguard").joinpath("data").joinpath("rules")
        with resources.as_file(traversable) as bundled_dir:
            paths.extend(sorted(Path(bundled_dir).glob("*.yara")))
    if rules_dir is not None:
        paths.extend(sorted(rules_dir.glob("*.yara")))
    return paths


def _import_yara() -> Any:
    try:
        import yara  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "YARA backend requires the optional dependency. Install hint: textguard[yara]."
        ) from exc
    return yara


def _coerce_severity(value: object) -> str:
    if value in {"info", "warn", "error"}:
        return str(value)
    return "error"
