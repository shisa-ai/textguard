# textguard

`textguard` is a planned standalone Python package for hostile-text normalization, inspection, and cleaning.

The goal is to extract the reusable text-defense work from `shisad` into a small public package that can scan untrusted text inputs such as prompts, Markdown, `SKILL.md` files, and other LLM-adjacent content without dragging in the rest of the daemon/framework stack.

## Status

Work in progress.

This repo currently contains planning docs only. The package scaffold and runtime code are not implemented yet.

See [docs/PLAN.md](docs/PLAN.md) for the current implementation plan.

## Intended Scope

`textguard` is intended to cover:

- Unicode normalization for hostile or hidden text
- invisible and bidi control detection
- encoded-layer inspection and bounded decoding
- prompt-injection-oriented pattern detection
- optional YARA-backed signatures
- optional PromptGuard semantic scoring
- two main surfaces:
  - `scan`: inspect text and report findings
  - `clean`: sanitize text while preserving meaning where practical

## Design Constraints

- Legitimate multilingual Unicode text is a first-class use case.
- Lossy transforms must be explicit.
- "Convert everything to ASCII" is not an acceptable default.
- The core package should stay lightweight and reusable.
- Heavy detectors must remain optional extras.

## Planned Install Surface

Not implemented yet, but the intended extras split is:

```bash
pip install textguard
pip install 'textguard[yara]'
pip install 'textguard[promptguard]'
```

## Planned Optional PromptGuard Backend

PromptGuard should be optional, not part of the default install.

The initial PromptGuard runtime extra is planned to include:

- `onnxruntime`
- `transformers`

If we later add an explicit model-fetch command, that can pull in `huggingface-hub` separately.

The model source is:

- Hugging Face: `shisa-ai/promptguard2-onnx`

Approximate first-time PromptGuard footprint as of 2026-04-10:

- Python wheels:
  - `onnxruntime` `1.24.4`: about `17.3 MB`
  - `transformers` `5.5.3`: about `10.2 MB`
  - plus transitive dependencies
- Model pack from Hugging Face:
  - `payload/model.onnx`: about `2.5 MB`
  - `payload/model.onnx.data`: about `283.3 MB`
  - `payload/tokenizer.json`: about `8.7 MB`
  - total payload: about `294.5 MB`

Recommendation:

- support PromptGuard only when the extra is installed
- use the local model path or existing Hugging Face cache by default
- allow an explicit fetch path for the model pack
- avoid silent background model downloads in the default path

## Dependency Direction

Current recommendation:

- Keep the core runtime stdlib-only if possible.
- Use stdlib `unicodedata` for normalization, category checks, and combining-mark handling.
- Vendor generated Unicode data for:
  - script-range lookup
  - a trimmed confusables mapping focused on high-risk cross-script pairs
- Prefer generated data over runtime dependencies such as `regex` or `confusable-homoglyphs`.
- Keep heavy integrations optional:
  - `yara-python`
  - `onnxruntime`
  - `transformers`

## Planned CLI

The intended CLI shape is:

```bash
textguard scan <path-or-stdin>
textguard clean <path-or-stdin>
```

Examples:

```bash
textguard scan SKILL.md
textguard scan --json SKILL.md
textguard clean SKILL.md -o SKILL.clean.md
cat untrusted.txt | textguard clean -
```

The repo does not implement these commands yet.

Implementation note:

- start with stdlib `argparse`
- add `click` only if the CLI grows beyond what the stdlib path handles cleanly
