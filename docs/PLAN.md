# textguard Plan

## Status

Planning only.

This document is the working plan for turning the extracted `shisad` text-defense work into a standalone PyPI package.

## Goals

- Build a standalone package for hostile-text normalization, inspection, and cleaning.
- Preserve legitimate multilingual text by default.
- Make the heavy detectors optional so the default install stays small.
- Reuse the useful `shisad` firewall primitives without importing daemon, policy, or trust-store complexity into the base package.
- Provide both a Python API and a simple CLI.

## Non-Goals

- Rebuilding `shisad` as a second product.
- ASCII-only sanitization as the default behavior.
- Shipping PromptGuard or YARA in the core install path.
- Requiring network access for the core package.

## Package Shape

Initial target layout:

```text
textguard/
|- src/textguard/
|  |- __init__.py
|  |- normalize.py
|  |- decode.py
|  |- findings.py
|  |- clean.py
|  |- scan.py
|  |- cli.py
|  |- detect/
|  |  |- unicode.py
|  |  |- encoded.py
|  |  |- patterns.py
|  |  `- homoglyphs.py
|  `- backends/
|     |- yara_backend.py
|     `- promptguard.py
|- tests/
|- README.md
|- pyproject.toml
`- docs/
   `- PLAN.md
```

## User-Facing Surface

### Python API

Target shape:

```python
from textguard import scan, clean, TextGuard
```

### CLI

Target verbs:

- `textguard scan`
- `textguard clean`

The core idea from the original design conversation still holds: one read-only verb and one sanitizing verb are enough.

## Core Technical Scope

### 1. Normalization

Implement in-house:

- Unicode normalization
- removal of zero-width and invisible formatting characters
- removal of bidi controls
- soft hyphen stripping
- tag character stripping
- variation selector stripping
- whitespace collapsing
- bounded handling for combining-mark abuse

Recommendation:

- normalize for detection with `NFKC`
- keep destructive cleaning behavior explicit
- preserve separate "normalized for analysis" and "cleaned for output" stages

### 2. Decoding

Implement in-house:

- URL decode
- HTML entity decode
- bounded ROT13 decode
- bounded base64 inspection/detection

Hard requirement:

- all decode paths must have depth and expansion limits

### 3. Detection

Implement in-house:

- invisible/bidi/tag/variation-selector findings
- prompt-injection pattern matching
- encoded payload findings
- risk aggregation

Likely worth pulling from existing libraries:

- `regex` for script-aware matching and mixed-script heuristics
- `confusable-homoglyphs` for confusable lookups instead of maintaining our own Unicode confusables table

Recommendation:

- use `regex` in core
- use `confusable-homoglyphs` in core
- keep the rest of the risk pipeline in-house

## Dependency Strategy

### Core

Recommended initial direct dependencies:

- `regex==2026.4.4`
- `confusable-homoglyphs==3.3.1`

Recommendation:

- keep the CLI on stdlib `argparse` initially
- do not add `click` unless the CLI complexity proves it necessary
- pin direct dependencies exactly in `pyproject.toml`
- generate and commit `uv.lock`

### Optional: YARA

Recommended extra:

- `yara-python==4.5.4`

Reason:

- worth pulling rather than re-implementing a signature engine
- compiled dependency, so it should stay out of the default install

### Optional: PromptGuard

Recommended extra:

- `onnxruntime==1.24.4`
- `transformers==5.5.3`
- `huggingface-hub==1.10.1`

Not recommended initially:

- `safetensors`
- `sentencepiece`

Reason:

- the current `shisa-ai/promptguard2-onnx` pack exposes `model.onnx`, `model.onnx.data`, and `tokenizer.json`
- there is no reason to carry additional model-format dependencies unless the tokenizer load proves they are actually needed

Follow-up optimization:

- start with `transformers` for bring-up speed
- keep the backend isolated so we can later swap to a lighter `tokenizers`-only path if startup cost matters

## PromptGuard Plan

Model source:

- Hugging Face: `shisa-ai/promptguard2-onnx`

Approximate size as of 2026-04-10:

- `payload/model.onnx`: `2.5 MB`
- `payload/model.onnx.data`: `283.3 MB`
- `payload/tokenizer.json`: `8.7 MB`
- total model payload: about `294.5 MB`

Primary wheel downloads as of 2026-04-10:

- `onnxruntime`: about `17.3 MB`
- `transformers`: about `10.2 MB`
- `huggingface-hub`: about `0.64 MB`
- transitive dependencies come on top of that

Recommendation:

- `textguard[promptguard]` should enable the backend
- default behavior should use a local path or existing Hugging Face cache
- do not silently auto-download a ~295 MB model pack in the default path
- if we support download-on-demand, make it explicit via a subcommand, flag, or environment variable

Suggested interface:

- `TEXTGUARD_PROMPTGUARD_MODEL=/path/to/model-pack`
- optional future command: `textguard models fetch promptguard2`

## Reuse From shisad

Re-use:

- normalization ideas
- bounded decode strategy
- prompt-injection detection concepts
- PromptGuard ONNX backend shape

Do not import directly into core package design:

- daemon/runtime wiring
- policy engine concepts
- signed model-pack enforcement as a core package requirement

Note:

- the signed-pack logic in `shisad` is useful reference material, but `textguard` should first ship a simpler optional PromptGuard backend that works with an explicit local path or Hugging Face cache

## Delivery Phases

### Phase 1: Scaffold

- add `pyproject.toml`
- add `src/textguard/`
- add `tests/`
- add package metadata and initial lockfile

### Phase 2: Core normalize/decode

- port and improve the normalization primitives
- add bounded decode helpers
- add tests for benign Unicode and adversarial Unicode

### Phase 3: Scan/clean API

- define result dataclasses
- implement `scan()` and `clean()`
- wire risk findings

### Phase 4: CLI

- add `textguard scan`
- add `textguard clean`
- add `--json` and output-path support

### Phase 5: YARA backend

- add optional rule loading
- add YARA-backed findings and tests

### Phase 6: PromptGuard backend

- add optional ONNX runtime integration
- add local-path and cached-model support
- decide whether explicit fetch support is worth including in v1

## Testing Requirements

At minimum:

- benign multilingual text stays readable
- zero-width, bidi, tag characters, soft hyphen, and variation selectors are detected correctly
- bounded decode limits are enforced
- mixed-script and confusable findings are tested
- clean output is explicit about lossy behavior
- optional backends fail clearly when extras are not installed

## Immediate Next Step

Next implementation task after planning:

- scaffold `pyproject.toml`, `src/textguard/`, and `tests/`
- wire the core dependency split with optional extras
- start with normalization and hostile-Unicode tests
