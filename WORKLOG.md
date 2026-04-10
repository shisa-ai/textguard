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
