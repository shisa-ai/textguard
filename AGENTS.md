# textguard Agent Guide

`textguard` is a greenfield Python package being extracted from `shisad` work on hostile-text normalization and detection. Keep the security ideas strong, keep the package reusable, and avoid importing daemon/framework complexity that does not belong in a standalone library.

Instruction precedence: if this file conflicts with platform, system, or developer instructions, follow those first.

## Current Source Of Truth

- `README.md` is the public package overview and usage surface.
- `docs/PLAN.md` is the working implementation plan.
- Use `shisad` as a reference source for reusable text-defense logic, not as an architecture template.

## First Principles

- Preserve legitimate text by default. Normal multilingual Unicode input is a first-class use case, not collateral damage.
- Do not make "convert everything to ASCII" the default behavior. Lossy or destructive transforms must be explicit opt-in.
- Security features must improve safety without turning the package into a blunt text shredder.
- Keep the package focused on text normalization, decoding, inspection, and sanitization primitives for LLM-adjacent systems.
- Prefer pure, testable library code over framework coupling, background services, policy engines, or repo-specific runtime assumptions.
- Bound all decoding and expansion behavior. No unbounded recursion, no unbounded size blowups, no regexes with obvious pathological behavior.

## Intended Project Shape

Build toward a small public-package layout like this:

```text
textguard/
|- src/textguard/        # library code
|- tests/                # unit and integration tests
|- pyproject.toml        # packaging metadata
|- README.md             # public install and usage docs
|- docs/PLAN.md          # optional implementation plan for non-trivial work
`- docs/PUBLISH.md       # optional release checklist
```

If the repo is still sparse, create only the files required for the current task. Do not add process scaffolding just to satisfy the diagram.

## Working Rules

- Run `git status -sb` before editing and before committing.
- Assume the worktree may be shared. Leave unrelated dirty or untracked files alone.
- Do not overwrite, revert, or delete work you did not create unless the user explicitly instructs it.
- Keep the public package generic. Do not hardcode org-specific URLs, secrets, local paths, or internal infrastructure assumptions.
- Do not commit virtualenvs, caches, build artifacts, local databases, or credentials.
- Prefer minimal runtime dependencies. Every added dependency needs a clear benefit.
- If dependency versions are pinned in `pyproject.toml`, keep them synchronized with `uv.lock`.

## Development Workflow

- Follow a light `spec -> test -> implement` loop.
- For non-trivial features, capture the scope briefly in `README.md` or `docs/PLAN.md` before expanding the code.
- Write tests before or alongside implementation. For security-sensitive logic, tests are part of the spec.
- Keep changes small and composable. Extract reusable primitives before adding wrappers or CLI surfaces.
- When behavior changes, update the public docs in the same change.

## Security-Specific Rules

- Separate normalization, detection, and sanitization concerns where practical. Callers should be able to choose how destructive a pipeline is.
- Treat benign multilingual text as a required success path in tests.
- Treat adversarial Unicode, hidden formatting, bidi controls, ANSI escapes, encoded payloads, and split-token smuggling as required threat cases in tests.
- If a heuristic blocks or mangles valid user text too aggressively, redesign it. False positives and silent data loss are bugs.
- If you extract logic from `shisad`, keep the reusable core and drop daemon-specific wiring, policy plumbing, and unrelated enforcement layers unless the task explicitly requires them.
- Be explicit about lossy behavior in function names, docs, and tests.

## Testing Expectations

Run the smallest relevant checks for the files you changed.

Minimum expectations:

- Python code changes: `python3 -m py_compile src/textguard/*.py tests/*.py`
- Library behavior changes: `uv run pytest -q`
- Focused work: run the narrowest relevant test file first, for example `uv run pytest tests/test_normalize.py -q`
- Packaging changes: `python3 -m build`
- Dependency changes: `uv lock` and rerun the relevant tests

If a needed check cannot be run, say so explicitly.

## CLI And API Surface

- If this repo gains a CLI, every user-facing flag needs explicit help text.
- Keep the library API small, composable, and public-package safe.
- Avoid surprise behavior. If a function strips, rewrites, or decodes content, document that clearly.
- Keep examples in `README.md` aligned with the actual import paths and CLI entry points.

## Release And Packaging

- Do not claim the package is PyPI-ready unless build metadata, versioning, install instructions, and import paths all work.
- Keep version strings synchronized anywhere they are user-visible.
- Prefer `pip`, `pipx`, `uv tool install`, and `uvx` friendly packaging if a CLI is added.
- Avoid shipping optional heavyweight detectors by default unless they materially improve the package and the install story stays clean.

## Git

- Commit completed logical units promptly after the relevant checks pass.
- Never use `git add .`, `git add -A`, or `git commit -a`.
- Stage only the files for the current task.
- Review staged changes with `git diff --staged --name-only` and `git diff --staged`.
- Use conventional commit prefixes such as `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, or `chore:`.

## Meta

- Update this file when the workflow or repo shape becomes more concrete.
- Keep this file focused on process and guardrails. Put package behavior, API details, and examples in `README.md` or `docs/`.
