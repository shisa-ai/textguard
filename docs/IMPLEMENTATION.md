# textguard Implementation Punchlist

## Status

Implementation complete. All seven planned phases are now landed in the repo.

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

- [x] Implement `src/textguard/config.py`
  - config file path: `~/.config/textguard/config.toml`
  - stdlib `tomllib`
  - precedence:
    - constructor kwargs
    - env vars
    - config file
    - defaults
- [x] Implement preset definitions:
  - `default`
  - `strict`
  - `ascii`
- [x] Implement `src/textguard/scan.py`
  - scan pipeline per `docs/PLAN.md`
  - returns `ScanResult`
- [x] Implement `src/textguard/clean.py`
  - scan first
  - apply preset transformations
  - record `Change` entries
  - returns `CleanResult`
- [x] Implement `TextGuard`
  - holds preset/config/backend state
  - exposes:
    - `scan(...)`
    - `clean(...)`
    - placeholder/backend hook surface for later:
      - `score_semantic(...)`
      - `match_yara(...)`
- [x] Implement top-level wrappers
  - `scan(text, *, include_context=False, **kwargs)`
  - `clean(text, *, include_context=False, **kwargs)`
  - per-call output options stay per-call, not constructor config
- [x] Ensure `include_context` behavior matches the type contract
  - `Finding.context: FindingContext | None`
  - no context unless explicitly requested
- [x] Enforce finding safety
  - `Finding.detail` contains only safe metadata
  - never echo raw text content in `detail`
- [x] Add tests for:
  - pipeline flow
  - top-level wrapper parity
  - `decoded_text` propagation
  - `CleanResult.changes`
  - `include_context`
  - safe-by-default findings metadata
  - config precedence
  - preset semantics

## Phase 4 — Core detection + generated Unicode data

- [x] Add `scripts/generate_unicode_data.py`
- [x] Add `scripts/README.md`
- [x] Generate and vendor:
  - `src/textguard/data/scripts.json`
  - `src/textguard/data/confusables.json`
  - `src/textguard/data/confusables_full.json`
- [x] Include generated metadata:
  - Unicode version
  - source file identifiers
  - source hashes
- [x] Implement `src/textguard/detect/invisible.py`
  - invisibles
  - bidi
  - tag chars
  - soft hyphens
  - variation selectors
  - combining abuse
- [x] Implement `src/textguard/detect/homoglyphs.py`
  - mixed-script detection
  - confusable skeleton normalization
  - trimmed confusables path (default)
  - full confusables opt-in path (e.g., `TextGuard(confusables="full")` or config option)
- [x] Implement `src/textguard/detect/encoded.py`
  - encoded payload analysis
  - split-token detection as opt-in
- [x] Wire detectors into the existing scan pipeline
- [x] Add tests for:
  - script-range behavior
  - Latin/Cyrillic and Latin/Greek confusables
  - full-confusables opt-in path
  - split-token off by default
  - severity assignments across detector outputs

## Phase 5 — CLI

- [x] Implement `src/textguard/cli.py` with stdlib `argparse`
- [x] Implement `textguard scan`
  - default human-readable output
  - `--json`
  - `--preset`
  - `--include-context`
  - `--confusables` (trimmed default, full opt-in)
  - `--split-tokens`
  - backend flags:
    - `--yara-rules DIR`
    - `--yara-bundled`
    - `--no-yara-bundled`
    - `--promptguard PATH`
- [x] Implement `textguard clean`
  - stdout default
  - `-i`
  - `-o`
  - `--report`
  - `--json`
  - `--preset`
  - `--include-context`
  - `--confusables`
  - `--split-tokens`
  - backend flags (same config surfaces as scan)
- [x] Implement `textguard models fetch` command surface
  - Phase 5 landed the surface
  - Phase 7 completed the fetch/verify/install behavior
- [x] Define and implement `scan` exit-code behavior that reflects finding severity for CI use
- [x] Add CLI tests for:
  - help text
  - stdin/stdout flow
  - file output
  - in-place mode
  - context flag behavior
  - exit codes

## Phase 6 — YARA backend

- [x] Implement `src/textguard/backends/yara_backend.py`
- [x] Add bundled rules under `src/textguard/data/rules/`
- [x] Support bundled-rule loading behavior from the resolved plan
  - bundled rules ship with the package
  - not auto-loaded by default
  - explicit enable path via config/flag/API
- [x] Implement direct backend access:
  - `guard.match_yara(text)`
- [x] Ensure YARA runs against:
  - raw text
  - decoded text
- [x] Add tests for:
  - missing extra
  - bundled rules
  - custom rules
  - raw + decoded matching

## Phase 7 — PromptGuard backend + model fetch

- [x] Implement `src/textguard/backends/promptguard.py`
- [x] Implement PromptGuard integration into `ScanResult.semantic`
- [x] Ensure PromptGuard receives raw text only
- [x] Implement direct backend access:
  - `guard.score_semantic(text)`
- [x] Implement model fetch and verification
  - stdlib download via `urllib.request`
  - SSH signature verification via `ssh-keygen -Y verify`
  - SHA-256 manifest verification
  - install path under XDG data dir
- [x] Add tests for:
  - missing extra
  - local model path handling
  - raw-text semantic scoring
  - tampered manifest rejection
  - hash mismatch rejection
  - happy-path fetch/install

## Docs parity and downstream readiness

- [x] Sync `README.md` examples with the implemented package surface
- [x] Keep `docs/PLAN.md` and `docs/IMPLEMENTATION.md` aligned as phases complete
- [x] Reconcile finding names with `shisad` migration/adoption expectations
- [x] Confirm the resulting surface is sufficient for later `shisad` adapter work

## Validation checklist

- [x] `python3 -m py_compile src/textguard/*.py tests/*.py`
- [x] Focused `uv run pytest` during development
- [x] `uv run pytest -q` once the initial scaffold and core runtime are in place
- [x] `python3 -m build` once packaging metadata exists

## Historical implementation recommendation

- The work was completed in the documented phase order
- YARA and PromptGuard landed only after the core scan/clean pipeline stabilized
- `shisad` adapter work remains intentionally separate from this package implementation
