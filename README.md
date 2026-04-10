# textguard

Hostile-text normalization, inspection, and cleaning for LLM-adjacent systems.

`textguard` extracts the reusable text-defense work from [`shisad`](https://github.com/shisa-ai/shisad) into a standalone Python package that can scan and clean untrusted text inputs — prompts, Markdown, skill files, and other content — without dragging in daemon or framework dependencies.

- Legitimate multilingual Unicode text is a first-class use case, so we do **NOT** convert everything to ASCII by default.
- Lossy transforms are always explicit opt-in.
- All decode paths have bounded depth and expansion limits.
- Findings carry severity levels (`info`, `warn`, `error`) — there is no opaque aggregate risk score.
- The package does not silently download models or make network requests.

## Install

```bash
pip install textguard            # core only, zero dependencies
pip install 'textguard[yara]'    # + pattern-based detection
pip install 'textguard[all]'     # everything
```

Or with uv:

```bash
uv pip install textguard
uv tool install textguard        # CLI-only, isolated
uvx textguard scan SKILL.md      # one-shot, no install
```

## CLI

The CLI works like a UNIX text utility:  pipe text through it, use it in shell scripts, or point it at files. Default usage is comparable to `cat` or `sed`: read from stdin or files, write cleaned output to stdout.

Both the CLI and [Python API](#python-api) are designed for agentic workflows. Scan untrusted inputs before they reach your model, or clean them inline as part of a pipeline.

```bash
# Scan: read-only, report findings
textguard scan SKILL.md
textguard scan SKILL.md --json
textguard scan docs/*.md --json > report.json

# Clean: output sanitized text
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

Exit codes from `scan` reflect the strongest signal in the result: structural findings map to `0` none, `1` info, `2` warn, `3` error; semantic tiers map to `0` none, `1` medium, `2` high, `3` critical. Runtime failures across subcommands return `4`.

## Protection Tiers

textguard is organized into three tiers. Each adds detection capability on top of the previous.

| Tier | Install | What it detects | Footprint |
|------|---------|----------------|-----------|
| **Core** | `textguard` | Invisible chars, bidi abuse, tag chars, soft hyphens, variation selectors, zalgo, homoglyphs/mixed-script, encoding layer abuse (URL, HTML entity, ROT13, base64, Unicode escapes, hex escapes, Punycode) | stdlib-only, small |
| **YARA** | `textguard[yara]` | Pattern-based detection: prompt injection phrases, tool spoofing tags, custom signatures. Runs against both raw and decoded text. | +~6 MB (`yara-python`) |
| **PromptGuard** | `textguard[promptguard]` | Semantic prompt injection / jailbreak classification via ONNX model. | +~27 MB wheels (`onnxruntime`, `transformers`) + ~295 MB model on first fetch |

Core has zero runtime dependencies. Heavy backends are always optional extras.

## Model Management

PromptGuard requires a ~295 MB ONNX model pack ([shisa-ai/promptguard2-onnx](https://huggingface.co/shisa-ai/promptguard2-onnx)). textguard never downloads models silently.

```bash
# Fetch, verify, and install to the XDG data dir
textguard models fetch promptguard2

# Point textguard to it
export TEXTGUARD_PROMPTGUARD_MODEL=~/.local/share/textguard/models/promptguard2

# Or pass directly
textguard scan --promptguard ~/.local/share/textguard/models/promptguard2 SKILL.md
```

`textguard models fetch promptguard2` downloads from Hugging Face via stdlib HTTP, verifies the SSH ed25519 signature against the bundled public key, and checks SHA-256 file hashes from the manifest before installing under `~/.local/share/textguard/models/promptguard2/` (or `XDG_DATA_HOME` if set).

## Python API

The two primary calls are `scan()` and `clean()` — they do what you'd expect. `scan()` inspects text and returns findings; `clean()` rewrites the text with hostile content removed.

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


## Dependencies & Supply Chain

- **Core runtime**: The core is stdlib-only and has **no runtime dependencies**.
- **Unicode data**: vendored Unicode data for script ranges and confusables is generated by manual script run.
- **Optional YARA**: `yara-python>=4.5.4`
- **Optional PromptGuard**: `onnxruntime>=1.24.4`, `transformers>=5.5.3`
- Pinned via floor versions in `pyproject.toml`. Exact resolution through committed `uv.lock` with hashes.

The [pypi package](https://pypi.org/project/textguard) is published through Github CI with OIDC and SBOM.

## Related Projects

Our work depends most on these public contributions:

- [Unicode 17.0 Scripts](https://www.unicode.org/Public/17.0.0/ucd/Scripts.txt)
- [Unicode 17.0 Confusables](https://www.unicode.org/Public/security/17.0.0/confusables.txt)
- [YARA](https://virustotal.github.io/yara/) / [yara-python](https://github.com/VirusTotal/yara-python)
- [Llama Prompt Guard 2](https://github.com/meta-llama/PurpleLlama/tree/main/Llama-Prompt-Guard-2)

While textguard fills a somewhat unique niche (hostile Unicode + encoding smuggling for LLM inputs), there are some foundational and related projects:

- Unicode security references:
  - https://www.unicode.org/reports/tr36/ — the foundational doc on Unicode attack surfaces
  - https://www.unicode.org/reports/tr39/ — where confusables and mixed-script detection are formally specified
- Unicode / text normalization:
  - https://github.com/rspeer/python-ftfy — fixes mojibake and encoding problems
  - https://github.com/vhf/confusable_homoglyphs — Python lib built on the same Unicode confusables data
  - https://github.com/avian2/unidecode — ASCII transliteration
