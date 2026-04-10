# textguard Implementation Punchlist

## Status

Phase 1 scaffold is the current focus. Core runtime implementation starts in Phase 2.

`docs/PLAN.md` is authoritative for architecture and public surface.
This file is the execution checklist for implementing that plan in the `textguard` repo.

Out of scope here:

- `shisad` adapter implementation
- release work
- changelog/release-note maintenance

## Implementation order

Follow the phase order from `docs/PLAN.md` and `WORKLOG.md`:

1. Scaffold
2. Normalize + decode
3. Scan + clean API
4. Core detection + generated Unicode data
5. CLI
6. YARA backend
7. PromptGuard backend + model fetch

Do not revert to the older ordering where detection comes before the scan/clean pipeline.

## Phase 1 — Scaffold

- [x] Add `pyproject.toml`
  - Python `>=3.11`
  - package metadata
  - console script entrypoint
  - optional extras:
    - `yara = ["yara-python>=4.5.4"]`
    - `promptguard = ["onnxruntime>=1.24.4", "transformers>=5.5.3"]`
    - `all = ["textguard[yara,promptguard]"]`
- [x] Add `src/textguard/`
- [x] Add `tests/`
- [x] Add `scripts/` stubs for generated-data tooling docs and implementation
- [x] Add `src/textguard/__init__.py`
- [x] Add `src/textguard/types.py`
- [x] Define the public dataclasses from `docs/PLAN.md`:
  - `Finding`
  - `FindingContext`
  - `Change`
  - `SemanticResult`
  - `DecodedText`
  - `ScanResult`
  - `CleanResult`
- [x] Re-export the intended top-level public surface from `__init__.py`:
  - `scan`
  - `clean`
  - `TextGuard`
  - `ScanResult`
  - `CleanResult`
  - `Finding`
  - `FindingContext`
  - `Change`
  - `SemanticResult`
- [x] Add `src/textguard/detect/__init__.py`
- [x] Add `src/textguard/backends/__init__.py`
- [x] Add `src/textguard/data/allowed_signers` (SSH ed25519 public key for model verification)
- [x] Add initial tests for type defaults and import surface
- [x] Generate and commit `uv.lock`

## Phase 2 — Normalize + decode

- [x] Implement `src/textguard/normalize.py`
  - NFC default path
  - NFKC support for strict/ascii presets
  - whitespace collapse
  - invisible stripping primitives
  - bidi stripping primitives
  - soft hyphen handling
  - variation selector handling
  - tag character handling
  - combining-mark cap / zalgo handling
  - ANSI escape sequence stripping
- [x] Implement `src/textguard/decode.py`
  - URL decoding
  - HTML entity decoding
  - ROT13 decoding (signal-token gated)
  - base64 decoding
  - Unicode escape decoding
  - hex escape decoding
  - punycode decoding
- [x] Ensure `normalize.py` and `decode.py` can emit `Finding` objects as they work
  - detect-as-side-effect for normalization/decode stages
- [x] Implement the bounded decode loop
  - layer order per pass:
    - URL
    - HTML
    - ROT13
    - base64
    - Unicode escapes
    - hex escapes
    - Punycode
  - configurable:
    - `max_depth`
    - `max_expansion_ratio`
    - `max_total_chars`
- [x] Emit decode findings / reason codes for:
  - `encoding:url_decoded`
  - `encoding:html_entity_decoded`
  - `encoding:rot13_decoded`
  - `encoding:base64_decoded`
  - `encoding:unicode_escape_decoded`
  - `encoding:hex_escape_decoded`
  - `encoding:punycode_decoded`
  - `encoding:decode_depth_limited`
  - `encoding:decode_bound_hit`
- [x] Keep PromptGuard input assumptions out of this phase
  - decode exists for structural analysis and YARA support
  - PromptGuard later consumes raw text only
- [x] Add tests for:
  - benign multilingual text, including Japanese, Arabic, and Persian
  - adversarial Unicode
  - decode-depth limiting
  - expansion bounds
  - each supported decode layer

## Phase 3 — Scan + clean API

- [ ] Implement `src/textguard/config.py`
  - config file path: `~/.config/textguard/config.toml`
  - stdlib `tomllib`
  - precedence:
    - constructor kwargs
    - env vars
    - config file
    - defaults
- [ ] Implement preset definitions:
  - `default`
  - `strict`
  - `ascii`
- [ ] Implement `src/textguard/scan.py`
  - scan pipeline per `docs/PLAN.md`
  - returns `ScanResult`
- [ ] Implement `src/textguard/clean.py`
  - scan first
  - apply preset transformations
  - record `Change` entries
  - returns `CleanResult`
- [ ] Implement `TextGuard`
  - holds preset/config/backend state
  - exposes:
    - `scan(...)`
    - `clean(...)`
    - placeholder/backend hook surface for later:
      - `score_semantic(...)`
      - `match_yara(...)`
- [ ] Implement top-level wrappers
  - `scan(text, *, include_context=False, **kwargs)`
  - `clean(text, *, include_context=False, **kwargs)`
  - per-call output options stay per-call, not constructor config
- [ ] Ensure `include_context` behavior matches the type contract
  - `Finding.context: FindingContext | None`
  - no context unless explicitly requested
- [ ] Enforce finding safety
  - `Finding.detail` contains only safe metadata
  - never echo raw text content in `detail`
- [ ] Add tests for:
  - pipeline flow
  - top-level wrapper parity
  - `decoded_text` propagation
  - `CleanResult.changes`
  - `include_context`
  - safe-by-default findings metadata
  - config precedence
  - preset semantics

## Phase 4 — Core detection + generated Unicode data

- [ ] Add `scripts/generate_unicode_data.py`
- [ ] Add `scripts/README.md`
- [ ] Generate and vendor:
  - `src/textguard/data/scripts.json`
  - `src/textguard/data/confusables.json`
  - `src/textguard/data/confusables_full.json`
- [ ] Include generated metadata:
  - Unicode version
  - source file identifiers
  - source hashes
- [ ] Implement `src/textguard/detect/invisible.py`
  - invisibles
  - bidi
  - tag chars
  - soft hyphens
  - variation selectors
  - combining abuse
- [ ] Implement `src/textguard/detect/homoglyphs.py`
  - mixed-script detection
  - confusable skeleton normalization
  - trimmed confusables path (default)
  - full confusables opt-in path (e.g., `TextGuard(confusables="full")` or config option)
- [ ] Implement `src/textguard/detect/encoded.py`
  - encoded payload analysis
  - split-token detection as opt-in
- [ ] Wire detectors into the existing scan pipeline
- [ ] Add tests for:
  - script-range behavior
  - Latin/Cyrillic and Latin/Greek confusables
  - full-confusables opt-in path
  - split-token off by default
  - severity assignments across detector outputs

## Phase 5 — CLI

- [ ] Implement `src/textguard/cli.py` with stdlib `argparse`
- [ ] Implement `textguard scan`
  - default human-readable output
  - `--json`
  - `--preset`
  - `--include-context`
  - `--confusables` (trimmed default, full opt-in)
  - backend flags (stub if backends not yet implemented, error with install hint):
    - `--yara-rules DIR`
    - `--yara-bundled`
    - `--promptguard PATH`
- [ ] Implement `textguard clean`
  - stdout default
  - `-i`
  - `-o`
  - `--report`
  - `--json`
  - `--preset`
  - `--include-context`
  - `--confusables`
  - backend flags (same stubs as scan)
- [ ] Implement `textguard models fetch` command surface
  - real implementation can land in Phase 7
  - CLI shape should exist by this phase if practical
- [ ] Define and implement `scan` exit-code behavior that reflects finding severity for CI use
- [ ] Add CLI tests for:
  - help text
  - stdin/stdout flow
  - file output
  - in-place mode
  - context flag behavior
  - exit codes

## Phase 6 — YARA backend

- [ ] Implement `src/textguard/backends/yara_backend.py`
- [ ] Add bundled rules under `src/textguard/data/rules/`
- [ ] Support bundled-rule loading behavior from the resolved plan
  - bundled rules ship with the package
  - not auto-loaded by default
  - explicit enable path via config/flag/API
- [ ] Implement direct backend access:
  - `guard.match_yara(text)`
- [ ] Ensure YARA runs against:
  - raw text
  - decoded text
- [ ] Add tests for:
  - missing extra
  - bundled rules
  - custom rules
  - raw + decoded matching

## Phase 7 — PromptGuard backend + model fetch

- [ ] Implement `src/textguard/backends/promptguard.py`
- [ ] Implement PromptGuard integration into `ScanResult.semantic`
- [ ] Ensure PromptGuard receives raw text only
- [ ] Implement direct backend access:
  - `guard.score_semantic(text)`
- [ ] Implement model fetch and verification
  - stdlib download via `urllib.request`
  - SSH signature verification via `ssh-keygen -Y verify`
  - SHA-256 manifest verification
  - install path under XDG data dir
- [ ] Add tests for:
  - missing extra
  - local model path handling
  - raw-text semantic scoring
  - tampered manifest rejection
  - hash mismatch rejection
  - happy-path fetch/install

## Docs parity and downstream readiness

- [ ] Sync `README.md` examples with the implemented package surface
- [ ] Keep `docs/PLAN.md` and `docs/IMPLEMENTATION.md` aligned as phases complete
- [ ] Reconcile finding names with `docs/shisad-migration.md`
- [ ] Confirm the resulting surface is sufficient for later `shisad` adapter work

## Validation checklist

- [ ] `python3 -m py_compile src/textguard/*.py tests/*.py`
- [ ] Focused `uv run pytest` during development
- [ ] `uv run pytest -q` once the initial scaffold and core runtime are in place
- [ ] `python3 -m build` once packaging metadata exists

## Current implementation recommendation

- Start with Phases 1 through 3
- Do not begin YARA or PromptGuard work until the core scan/clean pipeline is stable
- Keep `shisad` unchanged until `textguard` has stable normalize, decode, findings, and `decoded_text` semantics
