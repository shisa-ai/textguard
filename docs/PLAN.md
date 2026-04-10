# textguard Plan

## Status

Planning only. No runtime code yet.

For the `shisad` adoption path, see [docs/shisad-migration.md](shisad-migration.md).

## Goals

- Build a standalone package for hostile-text normalization, inspection, and cleaning.
- Preserve legitimate multilingual text by default.
- Make heavy detectors optional so the default install stays small.
- Reuse the useful `shisad` firewall primitives without importing daemon, policy, or trust-store complexity.
- Provide both a Python API and a simple CLI.
- Keep core runtime stdlib-only.

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
class Finding:
    kind: str              # "invisible_char", "mixed_script", "encoded_payload", etc.
    severity: str          # "info", "warn", "error"
    detail: str = ""       # human-readable description
    codepoint: str = ""    # "U+200B" (for unicode findings)
    offset: int | None = None  # character position in original text

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
    decoded_text: str
    decode_depth: int
    decode_reason_codes: list[str]
    semantic: SemanticResult | None = None

@dataclass
class CleanResult:
    text: str              # the cleaned output
    original_text: str     # what went in
    changes: list[Change]  # what was modified and why
    findings: list[Finding]  # same detections as scan
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

Top-level functions accept the same kwargs as `TextGuard.__init__` and pass them through:

```python
def scan(text: str, **kwargs) -> ScanResult:
    return TextGuard(**kwargs).scan(text)
```

### Configuration

`TextGuard` reads config from XDG-compliant paths (`~/.config/textguard/`), manually implemented without `platformdirs`. Environment variables override file config. Constructor kwargs override everything.

## Package Layout

```text
src/textguard/
├── __init__.py          # scan(), clean(), TextGuard, re-export public types
├── types.py             # ScanResult, CleanResult, Finding, Change, SemanticResult, DecodedText
├── normalize.py         # NFC/NFKC, invisible stripping, whitespace collapse, combining cap
├── decode.py            # URL/HTML/ROT13/base64 bounded layer unwinding
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
    ├── allowed_signers  # SSH ed25519 public key for model verification
    ├── scripts.json     # generated Unicode script-range table
    └── confusables.json # generated trimmed confusables mapping
```

Module naming rule: no vague catchall names. Every module name should describe what it does, not what domain it relates to. `invisible.py` not `unicode.py`.

## Pipelines

### scan() Pipeline

1. **Normalize** — NFC (or NFKC in strict/ascii presets), strip/detect invisibles, bidi, tags, variation selectors, soft hyphens, zalgo
2. **Decode** — bounded URL/HTML entity/ROT13/base64 layer unwinding with depth and expansion limits
3. **Detect** — run all core detectors on both raw and decoded text: invisible chars, homoglyphs/mixed-script, encoded payload analysis
4. **Backends** (optional) — run YARA rules against raw + decoded text, run PromptGuard against decoded text
5. **Aggregate** — collect findings with severity levels, return `ScanResult`

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
| **strict** | NFKC | All invisibles, bidi, variation selectors, tag chars, soft hyphens | URL, HTML, ROT13 |
| **ascii** | NFKC + ASCII transliteration | Everything non-ASCII | All layers |

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

## Detection Scope

### Core Detects (no dependencies)

- Invisible characters: ZWS, ZWNJ, ZWJ, BOM, invisible formatting
- Bidi overrides and isolates
- Tag characters (ASCII smuggling vector)
- Soft hyphens
- Variation selectors
- Combining mark abuse (zalgo)
- Mixed-script / confusable homoglyphs
- Encoded payload analysis: base64, split-token smuggling
- Decode reason codes: `encoding:url_decoded`, `encoding:html_entity_decoded`, `encoding:rot13_decoded`, `encoding:decode_depth_limited`, `encoding:decode_bound_hit`

### YARA Detects (optional `[yara]` extra)

- Pattern-based prompt injection phrase detection
- Tool/tag spoofing signatures
- Custom user-provided rules
- Runs against **both raw and decoded text** — the decode pipeline is the force multiplier

A bundled YARA ruleset ships with the package for common prompt injection patterns. Users can load additional rules or replace the defaults entirely.

### PromptGuard Detects (optional `[promptguard]` extra)

- Semantic prompt injection / jailbreak classification
- Returns `SemanticResult` with score, tier, and classifier ID
- Results nested as `ScanResult.semantic: SemanticResult | None`

## Decode Pipeline

The decode module is the core value of the package. It is what makes YARA and PromptGuard effective against obfuscated attacks rather than only matching raw input.

Bounded layer unwinding:
- URL decoding (`urllib.parse.unquote`)
- HTML entity decoding (`html.unescape`)
- ROT13 decoding (signal-token gated — only applied when decoded text reveals known signal words)
- Base64 detection (contiguous and split-token)

Hard requirements:
- Configurable `max_depth` (default 3)
- Configurable `max_expansion_ratio` (default 4.0)
- Configurable `max_total_chars` (default 32768)
- Reason codes emitted for every decode step applied
- `decode_depth_limited` emitted if max depth reached with more layers remaining

The decode pipeline must be referenceable from `shisad`'s adapter — `shisad` uses `decoded_text` (not `normalized_text`) as input to its secret redaction and rewrite stages.

## CLI Design

Two main verbs plus a model management subcommand:

```bash
textguard scan <path-or-stdin> [--json] [--preset PRESET] [--yara-rules DIR] [--promptguard PATH]
textguard clean <path-or-stdin> [-i] [-o PATH] [--preset PRESET] [--report] [--json]
textguard models fetch <model-name>
```

Output behavior:
- `scan` outputs a human-readable summary by default, `--json` for structured output
- `clean` outputs cleaned text to **stdout** by default
- `-i` overwrites the input file in place (explicit opt-in, never default)
- `-o PATH` writes cleaned text to a file
- `--report` prints a human-readable change report to stderr (useful with `-i` or `-o`)
- `--json` for structured output combining cleaned text and findings
- `scan` exit codes reflect finding severity for CI use

Built on stdlib `argparse`. No `click` dependency.

## Generated Unicode Data

- **Script-range table**: generated from Unicode `Scripts.txt`, vendored as `data/scripts.json`. Used by `detect/homoglyphs.py` for mixed-script detection.
- **Confusables table**: generated from Unicode `confusables.txt`, trimmed to high-risk cross-script pairs, vendored as `data/confusables.json`. Used for confusable skeleton normalization.
- Record upstream Unicode version in generated artifact metadata.
- Prefer generated data over runtime dependencies like `regex` or `confusable-homoglyphs`.

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

Zero runtime dependencies. stdlib-only.

- `unicodedata` for normalization and category checks
- `argparse` for CLI
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

CI uses `uv sync --frozen`. The lockfile is the security boundary. See `shisa-ai/supply-chain-security` for policy.

## Delivery Phases

### Phase 1: Scaffold

- `pyproject.toml` with package metadata and optional extras
- `src/textguard/` with `__init__.py` and `types.py`
- `tests/`
- `uv.lock`

### Phase 2: Core normalize + decode

- Normalization primitives (NFC, invisible/bidi/tag stripping, whitespace collapse, combining cap)
- Bounded decode helpers (URL, HTML, ROT13, base64 detection)
- Tests for benign multilingual text and adversarial Unicode

### Phase 3: Core detection

- `detect/invisible.py` — invisible char and zalgo detection
- `detect/homoglyphs.py` — mixed-script and confusable detection
- `detect/encoded.py` — base64/split-token smuggling detection
- Generated Unicode data tables (scripts, confusables)

### Phase 4: scan + clean API

- `ScanResult` and `CleanResult` implementation
- `scan()` and `clean()` pipelines
- Preset system (default, strict, ascii)
- `TextGuard` class with config

### Phase 5: CLI

- `textguard scan` with `--json`, `--preset`, exit codes
- `textguard clean` with `-i`, `-o`, `--report`, `--json`, `--preset`
- `textguard models fetch` (stub or full)

### Phase 6: YARA backend

- Optional YARA rule loading
- Run rules against raw + decoded text
- Bundled default ruleset for common prompt injection patterns

### Phase 7: PromptGuard backend

- Optional ONNX runtime integration
- Model fetch with SSH signature verification
- `SemanticResult` integration into `ScanResult`

## Testing Requirements

At minimum:

- Benign multilingual text (including Japanese, Arabic, Persian) stays readable through all presets
- Zero-width, bidi, tag characters, soft hyphens, and variation selectors are detected correctly
- Bounded decode limits are enforced
- Mixed-script and confusable findings are tested
- Clean output is explicit about lossy behavior via `CleanResult.changes`
- Preset behavior matches specification
- Optional backends fail clearly when extras are not installed
- Model fetch verifies signatures and rejects tampered payloads
- Severity levels are assigned correctly across finding types
