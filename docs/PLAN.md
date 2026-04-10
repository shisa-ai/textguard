# textguard Plan

## Status

All seven planned phases are implemented in the repo. This document remains the architectural source of truth for the package surface and future changes.

For the `shisad` adoption path, see [docs/shisad-migration.md](shisad-migration.md).

## Goals

- Build a standalone package for hostile-text normalization, inspection, and cleaning.
- Preserve legitimate multilingual text by default.
- Make heavy detectors optional so the default install stays small.
- Reuse the useful `shisad` firewall primitives without importing daemon, policy, or trust-store complexity.
- Provide both a Python API and a simple CLI.
- Keep core runtime stdlib-only.
- Require Python 3.11+ (stdlib `tomllib` for config).

## Non-Goals

- Rebuilding `shisad` as a second product.
- ASCII-only sanitization as a default.
- Shipping PromptGuard or YARA in the core install path.
- Requiring network access for the core package.
- An opaque aggregate risk score. Findings with severity levels are the data.
- A built-in prompt-injection pattern engine. Pattern/phrase detection is YARA's job.

## Core API Contract

### Types

All public data types live in `src/textguard/types.py` and are re-exported from `__init__.py`.

```python
@dataclass
class FindingContext:
    excerpt: str           # short slice of original text around the finding offset

@dataclass
class Finding:
    kind: str              # "invisible_char", "mixed_script", "encoded_payload", etc.
    severity: str          # "info", "warn", "error"
    detail: str = ""       # human-readable description (never echoes original content)
    codepoint: str = ""    # "U+200B" (for unicode findings)
    offset: int | None = None  # character position in original text
    context: FindingContext | None = None  # only populated when include_context=True

@dataclass
class Change:
    kind: str              # "stripped", "normalized", "decoded", "capped"
    detail: str = ""       # what was changed and why

@dataclass
class SemanticResult:
    score: float           # classifier confidence
    tier: str              # "none", "medium", "high", "critical"
    classifier_id: str     # model identifier

@dataclass
class DecodedText:
    text: str
    reason_codes: tuple[str, ...] = ()
    decode_depth: int = 0

@dataclass
class ScanResult:
    findings: list[Finding]
    normalized_text: str
    decoded_text: str              # post-decode text — shisad uses this for secret redaction and rewrite
    decode_depth: int
    decode_reason_codes: list[str]
    semantic: SemanticResult | None = None

@dataclass
class CleanResult:
    text: str              # the cleaned output
    original_text: str     # what went in
    changes: list[Change]  # what was modified and why
    findings: list[Finding]  # same detections as scan, not just issues removed by the active preset
```

### TextGuard Class and Top-Level Functions

`TextGuard` holds configuration and optional backend state. Top-level `scan()` and `clean()` are thin wrappers that instantiate with defaults.

```python
# Top-level convenience (zero config, default preset, no backends)
from textguard import scan, clean

result = scan(text)      # ScanResult
cleaned = clean(text)    # CleanResult

# Configured instance (preset, backends, reusable)
from textguard import TextGuard

guard = TextGuard(
    preset="strict",
    confusables="full",           # "trimmed" (default) or "full" — controls confusable table scope
    yara_rules_dir="./rules/",
    promptguard_model_path="/path/to/model-pack",
)
result = guard.scan(text)
cleaned = guard.clean(text)

# Direct backend access — bypass the scan/clean pipeline
semantic = guard.score_semantic(text)   # SemanticResult
yara_findings = guard.match_yara(text)  # list[Finding]
```

Backends are accessible both through the `scan()` pipeline and independently. The pipeline is the recommended path, but direct access exists for consumers with their own pipelines (e.g., `shisad` scoring already-processed text).

Top-level functions separate per-call options from constructor config:

```python
def scan(text: str, *, include_context: bool = False, **kwargs) -> ScanResult:
    # include_context is per-call output control, not instance config — kept separate from **kwargs
    # which pass through to the TextGuard constructor (preset, backend paths, etc.)
    return TextGuard(**kwargs).scan(text, include_context=include_context)

def clean(text: str, *, include_context: bool = False, **kwargs) -> CleanResult:
    return TextGuard(**kwargs).clean(text, include_context=include_context)
```

Constructor kwargs (`preset`, `confusables`, `split_tokens`, `yara_rules_dir`, `promptguard_model_path`, etc.) configure the `TextGuard` instance. Per-call options (`include_context`) pass through to the method.

`confusables` is a constructor parameter (instance config), not a per-call option — the confusable table is loaded once and reused across calls. Values: `"trimmed"` (default, Latin↔Cyrillic and Latin↔Greek) or `"full"` (all cross-script pairs, higher false-positive rate). Also settable via `TEXTGUARD_CONFUSABLES` env var, config file, or `--confusables` CLI flag.

### Configuration

`TextGuard` reads config from XDG-compliant paths (`$XDG_CONFIG_HOME/textguard/config.toml`, defaulting to `~/.config/textguard/config.toml`), manually implemented without `platformdirs`. Config file parsed with stdlib `tomllib` (Python 3.11+).

Precedence (highest to lowest):
1. Constructor kwargs
2. Environment variables (`TEXTGUARD_PRESET`, `TEXTGUARD_CONFUSABLES`, `TEXTGUARD_SPLIT_TOKENS`, `TEXTGUARD_PROMPTGUARD_MODEL`, `TEXTGUARD_YARA_RULES_DIR`, `TEXTGUARD_YARA_BUNDLED`)
3. Config file (`~/.config/textguard/config.toml`)
4. Built-in defaults

Example config file:

```toml
preset = "strict"
split_tokens = true
promptguard_model = "~/.local/share/textguard/models/promptguard2"

[yara]
rules_dir = "~/.local/share/textguard/rules"
bundled = true
```

Unknown config keys fail closed with an explicit error instead of being ignored silently.

The package works fine with no config file — everything has CLI flag and env var equivalents.

### Public API Surface

Top-level `__init__.py` exports:

```python
# Functions
scan, clean

# Main class
TextGuard

# Result types (for type hints and inspection)
ScanResult, CleanResult, Finding, FindingContext, Change, SemanticResult
```

Internal types (`DecodedText`) and primitives (`normalize_text`, `decode_text_layers`) are importable from their submodules (`textguard.decode`, `textguard.normalize`) but not re-exported at the top level. This keeps the top-level namespace focused on the product surface while giving power users and library consumers (e.g., `shisad`) access to composable primitives.

## Package Layout

```text
src/textguard/
├── __init__.py          # scan(), clean(), TextGuard, re-export public types
├── types.py             # ScanResult, CleanResult, Finding, FindingContext, Change, SemanticResult, DecodedText
├── normalize.py         # NFC/NFKC, invisible stripping, ANSI escape stripping, whitespace collapse, combining cap
├── decode.py            # URL/HTML/ROT13/base64/unicode-escape/hex-escape/punycode bounded layer unwinding
├── clean.py             # cleaning pipeline, preset application
├── scan.py              # scan pipeline, finding aggregation
├── config.py            # XDG config loading, env var handling
├── cli.py               # argparse CLI (scan, clean, models)
├── detect/
│   ├── __init__.py
│   ├── invisible.py     # ZW, bidi, tags, variation selectors, soft hyphen, zalgo (combining abuse)
│   ├── homoglyphs.py    # mixed-script detection, confusable skeleton
│   └── encoded.py       # base64/split-token smuggling detection
├── backends/
│   ├── __init__.py
│   ├── yara_backend.py  # optional yara-python integration
│   └── promptguard.py   # optional ONNX PromptGuard2 backend
└── data/
    ├── allowed_signers      # SSH ed25519 public key for model verification
    ├── scripts.json         # generated Unicode script-range table
    ├── confusables.json     # generated trimmed confusables (Latin↔Cyrillic, Latin↔Greek)
    ├── confusables_full.json # generated full cross-script confusables (opt-in)
    └── rules/               # bundled YARA ruleset for common prompt injection patterns
```

Module naming rule: no vague catchall names. Every module name should describe what it does, not what domain it relates to. `invisible.py` not `unicode.py`.

## Pipelines

### scan() Pipeline

1. **Normalize** — NFC (or NFKC in strict/ascii presets), strip/detect invisibles, bidi, tags, variation selectors, soft hyphens, ANSI escapes, zalgo
2. **Decode** — bounded URL/HTML entity/ROT13/base64 layer unwinding with depth and expansion limits
3. **Detect** — run all core detectors on both raw and decoded text: invisible chars, homoglyphs/mixed-script, encoded payload analysis
4. **Backends** (optional) — run YARA rules against raw + decoded text, run PromptGuard against **raw text** (encoding is signal for the classifier, not noise to remove)
5. **Aggregate** — collect findings with severity levels, return `ScanResult`

Scan-time normalization is intentionally aggressive for analysis even when `clean()` is using a less destructive preset. Preset strip flags are clean-time rewrite settings; scan() always strips hostile formatting before detection.

### clean() Pipeline

1. **Scan** — run the full scan pipeline to identify findings
2. **Apply preset** — execute the cleaning steps defined by the active preset
3. **Record changes** — log each modification as a `Change` entry
4. **Return** `CleanResult` with cleaned text, changes, and findings

Cleaning is scan-then-transform. The scan runs first so findings are always available regardless of how much the preset actually modifies.

### Presets

| Preset | Normalization | Strips | Decodes |
|--------|--------------|--------|---------|
| **default** | NFC | Tag chars, soft hyphens, whitespace collapse, combining mark cap | No |
| **strict** | NFKC | All invisibles, bidi, variation selectors, tag chars, soft hyphens | All seven layers |
| **ascii** | NFKC + ASCII transliteration | Everything non-ASCII | All seven layers |

**NFC is the default, not NFKC.** NFKC destroys semantic content in Japanese (fullwidth katakana, certain kana forms) and other scripts. The default preset must be safe for multilingual text. NFKC is opt-in via strict and ascii presets.

Each preset enables a defined set of cleaning steps. Individual steps are also available as composable functions for callers who want custom pipelines.

### Severity Levels

Findings and scan reports use three severity levels:

| Level | Meaning | Examples |
|-------|---------|---------|
| `info` | Detected, not likely hostile | Mixed scripts in legitimately multilingual text |
| `warn` | Suspicious, could be hostile or legitimate | ZWJ in non-emoji context, soft hyphens mid-word |
| `error` | Almost certainly hostile or dangerous | Tag char sequences, bidi around instruction text, encoded prompt injection |

There is no aggregate risk score. Consumers decide their own thresholds based on findings.

### Finding Safety

`Finding.detail` is safe metadata only — codepoints, offsets, classification labels. It never echoes original text content. This makes findings safe to pass to LLMs without creating a secondary injection vector.

The `--include-context` flag (CLI) or `include_context=True` (per-call API option) populates `Finding.context` — a `FindingContext` with a short excerpt of the original text around the finding offset. This is opt-in for human debugging. When `include_context` is not set, `Finding.context` is `None`.

```json
{
  "kind": "invisible_char",
  "severity": "error",
  "detail": "Tag character U+E0041",
  "offset": 12,
  "context": {
    "excerpt": "safe text ..."
  }
}
```

Consumers can ignore or strip the `context` field. If the excerpt itself needs sanitizing, pipe it through `textguard clean`.

Note: `include_context` is a per-call option on `scan()` / `clean()`, not a `TextGuard` constructor parameter — it controls output shape, not instance configuration.

## Detection Scope

### Core Detects (no dependencies)

- Invisible characters: ZWS, ZWNJ, ZWJ, BOM, invisible formatting
- Bidi overrides and isolates
- Tag characters (ASCII smuggling vector)
- Soft hyphens
- Variation selectors
- Combining mark abuse (zalgo)
- Mixed-script / confusable homoglyphs
- Encoded payload analysis: base64 smuggling, split-token detection (opt-in)
- Decode reason codes for all seven decode layers plus depth/bound limits

### YARA Detects (optional `[yara]` extra)

- Pattern-based prompt injection phrase detection
- Tool/tag spoofing signatures
- Custom user-provided rules
- Runs against **both raw and decoded text** — the decode pipeline is the force multiplier

A bundled YARA ruleset ships in `data/rules/` for common prompt injection patterns. The YARA backend accepts `bundled=True` to load the shipped rules, a directory path for user rules, or both. Users can combine or replace the defaults entirely.

### PromptGuard Detects (optional `[promptguard]` extra)

- Semantic prompt injection / jailbreak classification
- Returns `SemanticResult` with score, tier, and classifier ID
- Results nested as `ScanResult.semantic: SemanticResult | None`

## Decode Pipeline

The decode module is the core value of the package. It is what makes YARA effective against obfuscated attacks — YARA matches against both raw and decoded text, so encoding layers don't hide payloads. (PromptGuard receives raw text only — see "What Gets Fed Where" below.)

Bounded layer unwinding — all layers are fast (sub-millisecond each) and low false-positive:

- URL decoding (`urllib.parse.unquote`)
- HTML entity decoding (`html.unescape`)
- ROT13 decoding (signal-token gated — only applied when decoded text reveals known signal words)
- Base64 decoding (within bounds)
- Unicode escape decoding (`\uXXXX` → character)
- Hex escape decoding (`\xXX` → character)
- Punycode decoding (`xn--` → Unicode)

Each pass runs all layers in sequence, looping until nothing changes or depth is hit. Order within a pass: URL → HTML → ROT13 → base64 → Unicode escapes → hex escapes → Punycode.

Split-token / fragmented encoding detection is available as an opt-in finding (not enabled by default due to false-positive risk). This flags patterns like fragmented base64 or partial URL encoding split across boundaries.

Hard requirements:
- Configurable `max_depth` (default 3)
- Configurable `max_expansion_ratio` (default 4.0)
- Configurable `max_total_chars` (default 32768)
- Reason codes emitted for every decode step applied
- `decode_depth_limited` emitted if max depth reached with more layers remaining

Reason codes: `encoding:url_decoded`, `encoding:html_entity_decoded`, `encoding:rot13_decoded`, `encoding:base64_decoded`, `encoding:unicode_escape_decoded`, `encoding:hex_escape_decoded`, `encoding:punycode_decoded`, `encoding:decode_depth_limited`, `encoding:decode_bound_hit`.

The decode pipeline must be referenceable from `shisad`'s adapter — `shisad` uses `decoded_text` (not `normalized_text`) as input to its secret redaction and rewrite stages.

### What Gets Fed Where

The decode pipeline is the force multiplier for downstream analysis, but different backends want different inputs:

- **YARA**: receives **both raw and decoded text**. Patterns match against both — raw catches byte-level signatures, decoded catches content hidden behind encoding layers.
- **PromptGuard**: receives **raw text only**. PromptGuard is a classifier trained on injection attempts. The encoding itself (ROT13-wrapped instructions, base64 payloads) is adversarial signal — decoding it first removes the signal the classifier is trained to detect.

## CLI Design

Two main verbs plus a model management subcommand:

```bash
textguard scan <path-or-stdin> [--json] [--preset PRESET] [--include-context] [--yara-rules DIR] [--promptguard PATH]
textguard clean <path-or-stdin> [-i] [-o PATH] [--preset PRESET] [--report] [--json] [--include-context]
textguard models fetch <model-name>
```

Output behavior:
- `scan` outputs a human-readable summary by default, `--json` for structured output
- `clean` outputs cleaned text to **stdout** by default
- `-i` overwrites the input file in place (explicit opt-in, never default)
- `-o PATH` writes cleaned text to a file
- `--report` prints a human-readable change report to stderr (useful with `-i` or `-o`)
- `--json` for structured output combining cleaned text and findings
- `--include-context` adds original text excerpts to findings (opt-in, not LLM-safe)
- `--split-tokens` / `--no-split-tokens` toggle opt-in split-token smuggling detection
- `--yara-bundled` / `--no-yara-bundled` explicitly enable or disable bundled YARA rules
- `scan` exit codes reflect the maximum of structural finding severity and semantic tier for CI use (`0` none, `1` info/medium, `2` warn/high, `3` error/critical)

Built on stdlib `argparse`. No `click` dependency.

## Generated Unicode Data

Generated by `scripts/generate_unicode_data.py`. See `scripts/README.md` for usage.

Artifacts:

- **`data/scripts.json`**: script-range table generated from Unicode `Scripts.txt`. Used by `detect/homoglyphs.py` for mixed-script detection.
- **`data/confusables.json`**: trimmed confusables mapping (Latin↔Cyrillic, Latin↔Greek) generated from Unicode `confusables.txt`. The default for scan/clean — low false-positive, covers the most-exploited attack surface.
- **`data/confusables_full.json`**: full cross-script confusables mapping. Opt-in for exhaustive coverage (useful for skill file checking where adversaries are thorough). Higher false-positive rate.

Generation workflow:

- Single script generates all artifacts: `python scripts/generate_unicode_data.py`
- Script fetches upstream files from `https://www.unicode.org/Public/` with a pinned Unicode version
- Upstream file hashes are verified against expected values stored in the script (provenance tracking, detects silent upstream changes)
- Generated output includes metadata: upstream Unicode version, generation timestamp, source file hashes
- Manual process — Unicode updates are annual. Run the generator, review the diff, commit the updated data files.

Prefer generated data over runtime dependencies like `regex` or `confusable-homoglyphs`.

## Model Download Strategy

PromptGuard model source: Hugging Face `shisa-ai/promptguard2-onnx`

`textguard models fetch promptguard2`:
1. Downloads files via stdlib `urllib.request` from known HF raw URLs
2. Verifies SSH ed25519 signature over `manifest.json` using `ssh-keygen -Y verify` against the bundled `allowed_signers` public key
3. Checks SHA-256 hashes from the manifest against downloaded files
4. Places the pack in the XDG data directory (`~/.local/share/textguard/models/promptguard2/`)

No `huggingface-hub` dependency. The download URLs point to the known HF repo. Users who already have the model (via `shisad`, manual download, or HF cache) point to it directly via `TEXTGUARD_PROMPTGUARD_MODEL` or the `--promptguard` flag.

`shisad` users never need the fetch command — `shisad` has its own signed-pack verification flow and passes the resolved local path to `TextGuard`.

## Dependency Strategy

### Core

Zero runtime dependencies. stdlib-only. Python 3.11+ required.

- `unicodedata` for normalization and category checks
- `argparse` for CLI
- `tomllib` for config file parsing (Python 3.11+)
- `hashlib` for model verification
- `urllib.request` for model fetch
- Vendored generated Unicode data for script ranges and confusables

### Optional Extras

Floor pins in `pyproject.toml`. Exact resolution via committed `uv.lock` with hashes.

```toml
[project.optional-dependencies]
yara = ["yara-python>=4.5.4"]
promptguard = ["onnxruntime>=1.24.4", "transformers>=5.5.3"]
all = ["textguard[yara,promptguard]"]
```

Bundled YARA rules (`data/rules/`) ship with the core package — the rule files are small data, not the YARA runtime. Installing `textguard[yara]` adds the `yara-python` engine needed to load and execute them. Users without the YARA extra can still inspect the rules or use them with an external YARA installation.

CI uses `uv sync --frozen`. The lockfile is the security boundary. See `shisa-ai/supply-chain-security` for policy.

## Delivery Phases

### Phase 1: Scaffold

- `pyproject.toml` with package metadata, optional extras, Python 3.11+ requirement
- `src/textguard/` with `__init__.py` and `types.py` (all public dataclasses)
- `tests/`
- `uv.lock`
- `scripts/generate_unicode_data.py` (stub or full)
- `scripts/README.md`

### Phase 2: Core normalize + decode

- `normalize.py` — NFC/NFKC, invisible/bidi/tag stripping, whitespace collapse, combining cap
- `decode.py` — bounded layer unwinding: URL, HTML, ROT13, base64, Unicode escapes, hex escapes, Punycode
- Both modules emit `Finding` objects as they work (detect-as-side-effect)
- Tests for benign multilingual text (including Japanese, Arabic, Persian) and adversarial Unicode

### Phase 3: scan + clean API

- `scan.py` — scan pipeline wiring, finding aggregation
- `clean.py` — cleaning pipeline, preset application, change recording
- `config.py` — XDG config loading (`tomllib`), env var handling
- `TextGuard` class with config, `scan()`, `clean()`, direct backend method stubs
- Top-level `scan()` and `clean()` wrapper functions in `__init__.py`
- Preset system (default, strict, ascii)
- Tests for pipeline flow, preset behavior, config precedence

### Phase 4: Core detection

- `detect/invisible.py` — invisible char and zalgo detection (standalone, beyond what normalize already catches)
- `detect/homoglyphs.py` — mixed-script detection, confusable skeleton normalization
- `detect/encoded.py` — base64/split-token smuggling structural detection
- `scripts/generate_unicode_data.py` — full implementation, generates `scripts.json`, `confusables.json`, `confusables_full.json`
- Tests for mixed-script, confusable, and encoded payload findings

### Phase 5: CLI

- `cli.py` — `argparse`-based CLI
- `textguard scan` with `--json`, `--preset`, `--include-context`, exit codes
- `textguard clean` with `-i`, `-o`, `--report`, `--json`, `--preset`, `--include-context`
- `textguard models fetch` (stub or full)

### Phase 6: YARA backend

- `backends/yara_backend.py` — optional YARA rule loading
- Run rules against raw + decoded text
- Bundled default ruleset in `data/rules/`
- `bundled=True` flag, user rules directory, or both
- `TextGuard.match_yara()` direct access method
- Tests with and without `[yara]` extra installed

### Phase 7: PromptGuard backend

- `backends/promptguard.py` — optional ONNX runtime integration
- Receives **raw text** (encoding is signal, not noise)
- Model fetch with SSH ed25519 signature verification and SHA-256 hash checking
- `SemanticResult` integration into `ScanResult`
- `TextGuard.score_semantic()` direct access method
- Tests with and without `[promptguard]` extra installed

## Testing Requirements

At minimum:

- Benign multilingual text (including Japanese, Arabic, Persian) stays readable through all presets
- Zero-width, bidi, tag characters, soft hyphens, and variation selectors are detected correctly
- All seven decode layers work and respect bounded limits
- Mixed-script and confusable findings are tested (both trimmed and full tables)
- Clean output is explicit about lossy behavior via `CleanResult.changes`
- Preset behavior matches specification (default preserves CJK, strict applies NFKC, ascii is lossy)
- Optional backends fail clearly when extras are not installed
- YARA receives both raw and decoded text
- PromptGuard receives raw text only
- Model fetch verifies signatures and rejects tampered payloads
- Severity levels are assigned correctly across finding types
- `Finding.detail` never contains original text content (unless `--include-context`)
- Config precedence: kwargs > env vars > config file > defaults
- Split-token detection only fires when explicitly opted in
