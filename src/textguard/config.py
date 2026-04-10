from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from .detect.invisible import DEFAULT_COMBINING_MARK_CAP

NormalizationForm = Literal["NFC", "NFKC"]
PresetName = Literal["default", "strict", "ascii"]
ConfusablesMode = Literal["trimmed", "full"]


@dataclass(frozen=True, slots=True)
class Preset:
    name: PresetName
    normalization_form: NormalizationForm
    decode_on_clean: bool
    ascii_transliterate: bool
    strip_ansi: bool
    strip_invisible: bool
    strip_bidi: bool
    strip_variation_selectors: bool
    strip_tag_chars: bool
    strip_soft_hyphens: bool
    collapse_whitespace: bool
    max_combining_marks: int | None


PRESETS: dict[PresetName, Preset] = {
    "default": Preset(
        name="default",
        normalization_form="NFC",
        decode_on_clean=False,
        ascii_transliterate=False,
        strip_ansi=False,
        strip_invisible=False,
        strip_bidi=False,
        strip_variation_selectors=False,
        strip_tag_chars=True,
        strip_soft_hyphens=True,
        collapse_whitespace=True,
        max_combining_marks=DEFAULT_COMBINING_MARK_CAP,
    ),
    "strict": Preset(
        name="strict",
        normalization_form="NFKC",
        decode_on_clean=True,
        ascii_transliterate=False,
        strip_ansi=True,
        strip_invisible=True,
        strip_bidi=True,
        strip_variation_selectors=True,
        strip_tag_chars=True,
        strip_soft_hyphens=True,
        collapse_whitespace=True,
        max_combining_marks=DEFAULT_COMBINING_MARK_CAP,
    ),
    "ascii": Preset(
        name="ascii",
        normalization_form="NFKC",
        decode_on_clean=True,
        ascii_transliterate=True,
        strip_ansi=True,
        strip_invisible=True,
        strip_bidi=True,
        strip_variation_selectors=True,
        strip_tag_chars=True,
        strip_soft_hyphens=True,
        collapse_whitespace=True,
        max_combining_marks=DEFAULT_COMBINING_MARK_CAP,
    ),
}


@dataclass(frozen=True, slots=True)
class TextGuardConfig:
    preset: PresetName = "default"
    confusables: ConfusablesMode = "trimmed"
    yara_rules_dir: Path | None = None
    yara_bundled: bool = False
    promptguard_model_path: Path | None = None

    @property
    def preset_settings(self) -> Preset:
        return PRESETS[self.preset]


def config_file_path() -> Path:
    return Path.home() / ".config" / "textguard" / "config.toml"


def resolve_config(overrides: dict[str, object] | None = None) -> TextGuardConfig:
    overrides = overrides or {}
    _validate_override_keys(overrides)

    merged: dict[str, object] = {}
    merged.update(_config_file_values())
    merged.update(_environment_values())
    merged.update({key: value for key, value in overrides.items() if value is not None})

    return TextGuardConfig(
        preset=_coerce_preset(merged.get("preset", "default")),
        confusables=_coerce_confusables(merged.get("confusables", "trimmed")),
        yara_rules_dir=_coerce_optional_path(merged.get("yara_rules_dir")),
        yara_bundled=_coerce_bool(merged.get("yara_bundled", False), field_name="yara_bundled"),
        promptguard_model_path=_coerce_optional_path(merged.get("promptguard_model_path")),
    )


def _validate_override_keys(overrides: dict[str, object]) -> None:
    valid_keys = {
        "preset",
        "confusables",
        "yara_rules_dir",
        "yara_bundled",
        "promptguard_model_path",
    }
    invalid = sorted(set(overrides) - valid_keys)
    if invalid:
        joined = ", ".join(invalid)
        raise TypeError(f"Unexpected TextGuard config keys: {joined}")


def _config_file_values() -> dict[str, object]:
    path = config_file_path()
    if not path.is_file():
        return {}

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    values: dict[str, object] = {}
    if "preset" in data:
        values["preset"] = data["preset"]
    if "confusables" in data:
        values["confusables"] = data["confusables"]
    if "promptguard_model" in data:
        values["promptguard_model_path"] = data["promptguard_model"]

    yara = data.get("yara")
    if isinstance(yara, dict):
        if "rules_dir" in yara:
            values["yara_rules_dir"] = yara["rules_dir"]
        if "bundled" in yara:
            values["yara_bundled"] = yara["bundled"]
    return values


def _environment_values() -> dict[str, object]:
    values: dict[str, object] = {}
    if preset := os.environ.get("TEXTGUARD_PRESET"):
        values["preset"] = preset
    if confusables := os.environ.get("TEXTGUARD_CONFUSABLES"):
        values["confusables"] = confusables
    if model_path := os.environ.get("TEXTGUARD_PROMPTGUARD_MODEL"):
        values["promptguard_model_path"] = model_path
    if rules_dir := os.environ.get("TEXTGUARD_YARA_RULES_DIR"):
        values["yara_rules_dir"] = rules_dir
    return values


def _coerce_preset(value: object) -> PresetName:
    if value not in PRESETS:
        raise ValueError(f"Unsupported preset: {value!r}")
    return value


def _coerce_confusables(value: object) -> ConfusablesMode:
    if value not in {"trimmed", "full"}:
        raise ValueError(f"Unsupported confusables mode: {value!r}")
    return cast(ConfusablesMode, value)


def _coerce_optional_path(value: object) -> Path | None:
    if value in {None, ""}:
        return None
    if isinstance(value, Path):
        return value.expanduser()
    if isinstance(value, str):
        return Path(value).expanduser()
    raise TypeError(f"Expected path-like value, got {type(value).__name__}")


def _coerce_bool(value: object, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise TypeError(f"{field_name} must be a bool")
