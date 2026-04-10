# textguard

Hostile-text normalization, inspection, and cleaning for LLM-adjacent systems.

`textguard` extracts the reusable text-defense work from `shisad` into a standalone Python package that can scan and clean untrusted text inputs — prompts, Markdown, `SKILL.md` files, and other content — without dragging in daemon or framework dependencies.

## Status

Working implementation in repo. The Python API, CLI, optional YARA backend, optional PromptGuard backend, and signed model fetch flow are all present. See [docs/PLAN.md](docs/PLAN.md) for the architecture and [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) for the completed execution checklist.

## Protection Tiers

textguard is organized into three tiers. Each adds detection capability on top of the previous.

| Tier | Install | What it detects | Footprint |
|------|---------|----------------|-----------|
| **Core** | `pip install textguard` | Invisible chars, bidi abuse, tag chars, soft hyphens, variation selectors, zalgo, homoglyphs/mixed-script, encoding layer abuse (URL, HTML entity, ROT13, base64, Unicode escapes, hex escapes, Punycode) | stdlib-only, small |
| **YARA** | `pip install 'textguard[yara]'` | Pattern-based detection: prompt injection phrases, tool spoofing tags, custom signatures. Runs against both raw and decoded text. | +~6 MB (`yara-python`) |
| **PromptGuard** | `pip install 'textguard[promptguard]'` | Semantic prompt injection / jailbreak classification via ONNX model. | +~27 MB wheels (`onnxruntime`, `transformers`) + ~295 MB model on first fetch |

Core has zero runtime dependencies. Heavy backends are always optional extras.

## Design Constraints

- Legitimate multilingual Unicode text is a first-class use case.
- Lossy transforms are always explicit opt-in.
- "Convert everything to ASCII" is not an acceptable default.
- All decode paths have bounded depth and expansion limits.
- Findings carry severity levels (`info`, `warn`, `error`) — there is no opaque aggregate risk score.
- The package does not silently download models or make network requests.

## Python API

```python
from textguard import scan, clean, TextGuard

# Quick functional API — uses defaults, zero config
result = scan(text)          # ScanResult
cleaned = clean(text)        # CleanResult

# Configured instance — reusable, carries backend state
guard = TextGuard(
    preset="strict",
    split_tokens=True,
    yara_rules_dir="./rules/",
    promptguard_model_path="~/.local/share/textguard/models/promptguard2/",
)
result = guard.scan(text)    # ScanResult
cleaned = guard.clean(text)  # CleanResult
semantic = guard.score_semantic(text)  # SemanticResult
```

Top-level `scan()` and `clean()` are thin wrappers around `TextGuard` with default settings. For repeated calls or backend-enabled scanning, create a `TextGuard` instance.

### Results

`scan()` returns a `ScanResult` — findings, decode metadata, and optional semantic classification:

```python
result = scan(text)
for f in result.findings:
    print(f"{f.severity}: {f.kind} at offset {f.offset} — {f.detail}")
```

`clean()` returns a `CleanResult` — the cleaned text plus a report of what changed:

```python
cleaned = clean(text)
print(cleaned.text)          # the safe output
for c in cleaned.changes:
    print(f"  {c.kind}: {c.detail}")
```

### Presets

Presets control how aggressive cleaning is:

| Preset | Normalization | Strips | Decodes | Use case |
|--------|--------------|--------|---------|----------|
| **default** | NFC | Tag chars, soft hyphens, whitespace collapse, combining mark cap | No | Safe for all multilingual text including CJK |
| **strict** | NFKC | All invisibles, bidi, variation selectors, tag chars, soft hyphens | All seven layers | Skill files, prompts, contexts where hidden content is suspect |
| **ascii** | NFKC + ASCII transliteration | Everything non-ASCII | All seven layers | When you explicitly want ASCII-only output |

The default preset preserves legitimate multilingual text. NFKC is not the default because it destroys semantic content in Japanese and other scripts. Strict and ascii presets opt into progressively more aggressive cleaning.

Scan-time analysis is intentionally more aggressive than clean-time rewriting. `scan()` always strips hostile formatting and unwinds bounded encodings for analysis; presets control what `clean()` rewrites into the returned output.

Split-token smuggling detection is opt-in. Enable it with `TextGuard(split_tokens=True)`, `TEXTGUARD_SPLIT_TOKENS=1`, config file `split_tokens = true`, or CLI `--split-tokens`.

## CLI

```bash
# Scan — read-only, report findings
textguard scan SKILL.md
textguard scan SKILL.md --json
textguard scan docs/*.md --json > report.json

# Clean — output sanitized text
textguard clean SKILL.md              # cleaned text to stdout
textguard clean SKILL.md -i           # overwrite in place
textguard clean SKILL.md -o out.md    # write to file
textguard clean SKILL.md -i --report  # overwrite, human-readable report to stderr
cat untrusted.txt | textguard clean - # pipe from stdin

# Presets
textguard clean SKILL.md --preset strict
textguard clean SKILL.md --preset ascii

# Optional backends
textguard scan --yara-rules ./rules/ SKILL.md
textguard scan --no-yara-bundled SKILL.md
textguard scan --split-tokens SKILL.md
textguard scan --promptguard ~/.local/share/textguard/models/promptguard2/ SKILL.md
```

Exit codes from `scan` reflect the strongest signal in the result: structural findings map to `0` none, `1` info, `2` warn, `3` error; semantic tiers map to `0` none, `1` medium, `2` high, `3` critical. Runtime failures across subcommands return `4`.

## Model Management

PromptGuard requires a ~295 MB ONNX model pack (`shisa-ai/promptguard2-onnx`). textguard never downloads models silently.

```bash
# Fetch, verify, and install to the XDG data dir
textguard models fetch promptguard2

# Point textguard to it
export TEXTGUARD_PROMPTGUARD_MODEL=~/.local/share/textguard/models/promptguard2

# Or pass directly
textguard scan --promptguard ~/.local/share/textguard/models/promptguard2 SKILL.md
```

`textguard models fetch promptguard2` downloads from Hugging Face via stdlib HTTP, verifies the SSH ed25519 signature against the bundled public key, and checks SHA-256 file hashes from the manifest before installing under `~/.local/share/textguard/models/promptguard2/` (or `XDG_DATA_HOME` if set).

## Dependency Direction

- **Core runtime**: stdlib-only. Uses `unicodedata`, `argparse`, `hashlib`, `urllib.request`, and vendored generated Unicode data for script ranges and confusables.
- **Optional YARA**: `yara-python>=4.5.4`
- **Optional PromptGuard**: `onnxruntime>=1.24.4`, `transformers>=5.5.3`
- Pinned via floor versions in `pyproject.toml`. Exact resolution through committed `uv.lock` with hashes.
