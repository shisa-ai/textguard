# textguard Work Log

Chronological development log. Append new entries at the bottom. Do not rewrite or reorder earlier entries — line-number stability matters for cross-referencing.

## Entry Format

```
### YYYY-MM-DD — Short Title

**Context**: What prompted this work or decision.
**Decision/Change**: What was decided or done.
**Rationale**: Why, especially if non-obvious or if alternatives were considered.
**Open questions**: Anything unresolved that future work should revisit.
```

---

### 2026-04-10 — Initial repo guidance, package plan, and shisad migration planning

**Context**: Started the `textguard` repo as a standalone extraction target for `shisad` text scanning and filtering logic. Needed to establish repo instructions, decide how much to inherit from nearby package repos versus `shisad`, and turn the initial design conversation into stable docs before scaffolding code.
**Decision/Change**: Added `AGENTS.md` and `CLAUDE.md` symlink for shared agent instructions. Created `README.md` as the public package overview and `docs/PLAN.md` as the working implementation plan. Added `docs/shisad-migration.md` to define how `shisad` should adopt `textguard` through an adapter instead of duplicating scanning logic. Removed the initial `textguard-conversation.md` seed file after its content was absorbed into repo docs. Settled on a stdlib-first core plan: use `unicodedata`, generated vendored Unicode tables for scripts and trimmed confusables, and keep `yara-python`, `onnxruntime`, and `transformers` as optional extras. Documented PromptGuard as optional, using the Hugging Face model `shisa-ai/promptguard2-onnx`, with an approximate model payload of about 294.5 MB and runtime wheel downloads of about 27.5 MB before transitive dependencies. Clarified that `textguard` should expose primitives and result surfaces `shisad` needs, but does not need to copy `shisad` internal shapes verbatim.
**Rationale**: `textguard` should become the single home for hostile-text normalization, bounded decode, scanning, and optional semantic backends, while `shisad` keeps its own policy, taint, secret-redaction, and firewall adapter behavior. A lightweight package-oriented workflow fits this repo better than copying `shisad`'s heavier framework process. Keeping the core runtime stdlib-only reduces install size and maintenance risk, while optional extras preserve room for stronger detectors without bloating the default package.
**Open questions**: Exact native `textguard` result types and finding model are still to be defined. Need to decide the generated Unicode data format and update workflow. Need to confirm whether PromptGuard model fetch support should exist at all, or whether `textguard` should only consume a local path / existing Hugging Face cache in v1. Need to scaffold `pyproject.toml`, `src/textguard/`, and `tests/` next.

### 2026-04-10 — Commit policy wording tightened

**Context**: Reviewed whether this repo's `AGENTS.md` was explicit enough about commit timing. The previous wording said to commit completed logical units promptly, but it was weaker than the preferred wording used in `shisad-dev`.
**Decision/Change**: Tightened `AGENTS.md` so it now states that commit-on-completion applies to docs, planning, and repo-setup work as well as code; that a task is a complete logical unit rather than every file edit; that commits should happen without waiting to be asked; and that smaller finished commits are preferred to reduce churn and loss of context.
**Rationale**: This repo is still in the planning and scaffolding stage, so a lot of meaningful work is docs-first. The commit policy needs to be explicit that those changes are first-class committable units. Stronger wording also reduces drift, lowers the chance of losing context, and matches the team's preferred working style more closely.
**Open questions**: None for the policy itself. The next question is whether the repo should also add `CHANGELOG.md` conventions now or defer that until the package is closer to its first release.

### 2026-04-10 — Commit policy wording narrowed to logical-unit completion only

**Context**: Re-reviewed the commit-policy wording after adding "prefer smaller finished commits over large batches". That phrase created ambiguity against the stronger primary rule of committing on logical-unit completion.
**Decision/Change**: Removed the "prefer smaller finished commits" line from `AGENTS.md` and kept the clearer rules only: commit on logical-unit completion, treat docs/planning/repo-setup work as committable units, and do not wait to be asked.
**Rationale**: The repo should optimize for coherent logical-unit commits, not for smaller commits as a separate goal. Keeping both rules invites misinterpretation and unnecessary oversplitting.
**Open questions**: None. The commit policy is clearer without the extra size-oriented guidance.

### 2026-04-10 — Design review: 10 decisions finalized, docs restructured

**Context**: Reviewed README.md, docs/PLAN.md, and docs/shisad-migration.md against the original design conversation (shisad-dev/research/textguard-conversation.md). Identified gaps where the earlier conversation's clarity had been diluted or where key design decisions were left implicit. Walked through each open item to reach a decision.

**Decisions made**:

1. **Two return types, not one.** `ScanResult` for `scan()`, `CleanResult` for `clean()`. Each type is focused — scan returns findings and decode metadata, clean returns the safe text plus a change log. Avoids a god-object that grows fields for both use cases.

2. **`clean()` pipeline: composable steps with presets.** Individual cleaning operations (strip invisibles, normalize, decode, etc.) are standalone composable functions. `clean()` applies a preset — a curated bundle of steps. Three presets: default (NFC, tag chars, soft hyphens, whitespace, combining cap — safe for all multilingual text including Japanese), strict (NFKC, all invisibles, bidi, decoding — for skill files and prompts), ascii (nuclear ASCII-only). **NFC is the default, not NFKC** — NFKC destroys semantic content in Japanese and other CJK scripts.

3. **Severity levels on findings: info/warn/error.** Findings always carry severity. `scan()` flags things even when `clean()` in default mode wouldn't act on them. No opaque aggregate risk score — the earlier conversation's `risk_score: float` was model-generated noise, not a principled design. Consumers (shisad, CI scripts) decide their own thresholds from the raw findings.

4. **Top-level functions wrap `TextGuard`.** `scan(text, **kwargs)` and `clean(text, **kwargs)` instantiate `TextGuard` internally with defaults. `TextGuard` holds config (preset, backend paths, YARA rules). Manual XDG config paths, no `platformdirs` dependency.

5. **`detect/` layout: invisible.py, homoglyphs.py, encoded.py.** No `patterns.py` — prompt injection phrase detection is YARA's job, not a hand-rolled regex engine. No `unicode.py` — vague catchall module names are banned. Zalgo detection folds into `invisible.py` since both produce "this character/sequence shouldn't be here" findings.

6. **No core pattern engine. YARA for all phrase detection.** Core detectors handle structural/character-level analysis only (invisibles, homoglyphs, encoding abuse). Pattern/phrase matching (instruction override, tool spoofing, role hijacking) lives entirely in YARA rules. YARA runs against both raw and decoded text — the decode pipeline is the force multiplier that makes YARA effective against obfuscated attacks. A bundled YARA ruleset ships with the package but is not loaded by default.

7. **Public `types.py` for all data types.** `ScanResult`, `CleanResult`, `Finding`, `Change`, `SemanticResult`, `DecodedText` all live in `types.py`. Key types re-exported from `__init__.py`. `findings.py` was rejected — the name implies detection logic, not type definitions.

8. **`SemanticResult` as nested optional.** `ScanResult.semantic: SemanticResult | None` instead of three nullable top-level fields. Keeps the core result clean when PromptGuard is not enabled.

9. **Floor pins in pyproject.toml, lockfile as authority.** `>=` version floors for optional extras. Exact resolution via committed `uv.lock` with hashes. Follows shisa-ai/supply-chain-security Python policy: "fully pinned via lockfile, not via manual == specs." CI uses `uv sync --frozen`.

10. **CLI clean: stdout default, -i for in-place.** `textguard clean FILE` outputs to stdout (Unix filter convention). `-i` overwrites in place (explicit opt-in). `-o PATH` for file output. `--report` prints human-readable change report to stderr (for use with -i or -o). `--json` for structured output. Safe default — a security tool should not be destructive by default.

11. **Model download: direct HTTP + SSH signature verification.** `textguard models fetch promptguard2` downloads from HF raw URLs via stdlib `urllib.request`, verifies SSH ed25519 signature via `ssh-keygen -Y verify` against a bundled `allowed_signers` public key, checks SHA-256 hashes from the manifest. Places in XDG data dir. No `huggingface-hub` dependency. shisad users pass their own verified local path.

12. **Doc restructuring.** README.md is user-facing: what it does, protection tiers with dependency sizes, install, API/CLI examples, presets, design constraints. docs/PLAN.md is the implementation blueprint: API contract, module layout, pipelines, dependency strategy, delivery phases. docs/shisad-migration.md is the shisad adoption path: adapter design, compatibility surface, validation gates. PromptGuard detail moved out of README (kept only the size summary), result type definitions moved from migration doc to PLAN, "reuse from shisad" moved from PLAN to migration doc.

**Rationale**: The original design conversation had good instincts (two verbs, composable API, optional backends) but the planning docs had drifted from that clarity. Key design gaps — what clean() does, how types relate, whether patterns.py should exist — needed explicit decisions before implementation could start cleanly. The supply-chain-security repo's Python policy resolved the version pinning question.

**Open questions**: Metadata injection concern — findings/results passed to LLMs need to be safe from becoming a secondary injection vector. Need to think about how Finding.detail strings are constructed. Decode pipeline scope needs detailed design during Phase 2 (what layers, what order, how to handle split-token and mixed encoding). Confusables table trimming criteria (which cross-script pairs are "high-risk") needs definition during Phase 3.

### 2026-04-10 — Implementation review: open questions resolved, phases updated

**Context**: Reviewed the delivery phases and remaining open questions from the design review. Walked through 9 items to close all open questions and refine the implementation plan before handing off to the coder.

**Decisions made**:

1. **Finding safety: safe by default, context opt-in.** `Finding.detail` never echoes original text content — only metadata (codepoints, offsets, classification). This makes findings safe to pass to LLMs without secondary injection risk. `--include-context` / `include_context=True` adds a structurally separate `context.excerpt` block per finding for human debugging. Consumers can strip or ignore it. If excerpts need sanitizing, pipe through `textguard clean`.

2. **Seven decode layers, all in core.** URL, HTML entity, ROT13 (signal-gated), base64, Unicode escapes (`\uXXXX`), hex escapes (`\xXX`), Punycode. All are fast (sub-ms), low false-positive, and common attack vectors. Each pass runs all layers in sequence (URL → HTML → ROT13 → base64 → Unicode → hex → Punycode), looping until stable or depth limit. Split-token / fragmented encoding detection is available as opt-in finding (FP risk when on by default).

3. **PromptGuard receives raw text, not decoded.** This is a critical correction — the earlier PLAN said "run PromptGuard against decoded text" which was wrong. PromptGuard is a classifier trained on injection attempts. The encoding (ROT13-wrapped instructions, base64 payloads, Unicode tricks) IS adversarial signal. Decoding first removes what the classifier is trained to detect. YARA still gets both raw and decoded text — pattern matching benefits from seeing through encoding layers.

4. **Confusables: trimmed default + full opt-in.** Default `confusables.json` covers Latin↔Cyrillic and Latin↔Greek (~150-200 entries). Full `confusables_full.json` covers all cross-script pairs (~1000+ entries), opt-in for exhaustive coverage. Both are generated artifacts from Unicode `confusables.txt`. The full table is useful for skill file checking where adversaries are thorough with homoglyph substitution.

5. **Phase boundary: types in Phase 1, pipeline before detectors.** `types.py` with all public dataclasses moves into Phase 1 scaffold so normalize and decode can emit `Finding` objects from day one. Phase ordering changed: scaffold → normalize+decode → **scan+clean API** → detection → CLI → YARA → PromptGuard. The pipeline wires up early so every detector added later plugs into a testable flow immediately.

6. **Generated Unicode data: single script, hash-verified upstream.** `scripts/generate_unicode_data.py` generates all artifacts. Fetches upstream from Unicode Consortium with a pinned version. Upstream file hashes verified against expected values (provenance tracking). Generated output includes metadata (Unicode version, timestamp, source hashes). Manual process — run generator, review diff, commit. Documented in `scripts/README.md`.

7. **Bundled YARA rules in `data/rules/`.** Ships with the package. YARA backend accepts `bundled=True` to load shipped rules, a directory path for user rules, or both. Users can combine or replace defaults entirely.

8. **TOML config, Python 3.11+.** Config file at `~/.config/textguard/config.toml` parsed with stdlib `tomllib`. Precedence: constructor kwargs > env vars > config file > defaults. Python 3.11+ minimum required (for `tomllib`).

9. **Clean public API surface.** Top-level `__init__.py` exports: `scan`, `clean`, `TextGuard`, `ScanResult`, `CleanResult`, `Finding`, `Change`, `SemanticResult`. Primitives (`normalize_text`, `decode_text_layers`, `DecodedText`) accessible via submodule imports (`textguard.normalize`, `textguard.decode`) but not re-exported at top level. Documented for power users.

**Rationale**: All open questions from the design review are now resolved. The PromptGuard raw-text correction is the most important change — it affects the scan pipeline architecture. The phase reordering (pipeline before detectors) means the integration shape is testable from Phase 3 onward. Finding safety and context opt-in prevent textguard from becoming a secondary injection vector in LLM pipelines. The seven decode layers cover the real-world encoding attack surface comprehensively without adding dependencies.

**Open questions**: None blocking implementation. The coder can start Phase 1 scaffold.

### 2026-04-10 — Implementation punchlist rewritten to match authoritative plan

**Context**: `docs/IMPLEMENTATION.md` had been created from an earlier version of `docs/PLAN.md` and no longer matched the resolved architecture. The later planning commits finalized the phase order, fixed the `include_context` type mismatch, and corrected the PromptGuard input rule.
**Decision/Change**: Rewrote `docs/IMPLEMENTATION.md` so it now matches the current authoritative `docs/PLAN.md`. The punchlist now follows the resolved phase order: scaffold -> normalize+decode -> scan+clean API -> core detection/generated Unicode data -> CLI -> YARA -> PromptGuard/model fetch. It includes `FindingContext`, per-call `include_context`, all seven decode layers and reason codes, PromptGuard-on-raw-text only, bundled YARA rules not auto-loaded by default, and the current direct-backend surfaces. Reviewed the recent planning commits (`bf3666b`, `1c7243f`, `57b9a0d`) against the rewritten punchlist to confirm those planning updates were captured.
**Rationale**: `docs/PLAN.md` is the source of truth, but the implementation punchlist is what a coder will execute against. If it lags behind the plan, it creates avoidable implementation drift and rework. Keeping it aligned with the resolved plan makes the first implementation pass coherent and lowers the chance of building against stale assumptions.
**Open questions**: None newly introduced by the rewrite. The next step is implementation starting at Phase 1.

### 2026-04-10 — Follow-up doc alignment after review

**Context**: A later review compared `docs/IMPLEMENTATION.md`, `docs/shisad-migration.md`, `README.md`, and this work log against the authoritative `docs/PLAN.md` and found a few remaining drifts. The biggest gaps were in the execution punchlist, but there were also stale wording fragments in the migration doc and one outdated worklog summary of the top-level export surface.
**Decision/Change**: Tightened `docs/IMPLEMENTATION.md` so Phase 2 now explicitly keeps ROT13 signal-gated, requires normalize/decode finding emission, and restores Arabic/Persian test coverage alongside Japanese. Restored the missing Phase 3 pipeline-flow and config-precedence tests, added confusable skeleton normalization back to Phase 4, and made the CLI exit-code item explicitly severity-based for CI use. Updated `docs/shisad-migration.md` to reflect the resolved ownership boundary: `textguard` owns its standalone PromptGuard fetch/verify path, while `shisad` can continue passing a resolved local model path during migration. Cleaned up stale "pattern detection" wording so it points to YARA-backed rule matching instead of implying a separate core phrase engine. Updated `README.md` only where it materially drifted from the plan, while leaving the planning-only status note intact as requested. This entry also corrects the stale worklog summary of the public export surface: `FindingContext` is part of the intended top-level export set.
**Rationale**: The plan is authoritative, but the punchlist and migration notes are operational documents. Small omissions there are enough to create implementation drift, especially around decode behavior, test obligations, and PromptGuard ownership. Updating the supporting docs keeps the repo coherent without rewriting earlier historical entries.
**Open questions**: None introduced by this alignment pass.
