# textguard Supply Chain Audit

*Created: 2026-04-10*  
*Updated: 2026-04-10*  
*Status: Draft*  
*Snapshot basis: Phase 1 scaffold bootstrap on `main`*

## Scope And Intent

This document records the initial supply-chain posture of the `textguard`
scaffold. It covers the package manager, lockfile, CI install path, and release
workflow design added during Phase 1.

Goals:

1. Map the direct dependency surface for the initial scaffold.
2. Capture the hardening controls added from `docs/DEV.md`.
3. Track follow-up work needed before the first release.

## Repo Profile

| Item | Value |
| --- | --- |
| Primary ecosystem | Python |
| Package manager | uv |
| Lockfile | `uv.lock` |
| CI install path | `uv sync --exclude-newer P7D --frozen --dev` |
| Release path | GitHub Actions workflow (`publish.yml`) via OIDC trusted publishing |
| Current risk summary | Medium |

## Pre-Analysis Notes

- Behavioral contract impact: scaffold only; no implemented hostile-text runtime yet.
- Threat hotspots:
  - optional heavyweight extras (`yara`, `promptguard`) will expand the lockfile and release blast radius,
  - GitHub environment approval still needs to be configured in repository settings,
  - workflow linting is not yet wired into CI.
- Accepted risks carried into the audit:
  - package version remains `0.0.0` until the first real milestone,
  - release workflows exist before the package has meaningful runtime behavior.

## Evidence And Commands

```bash
git status -sb
uv lock --check
uv tree --all-groups
uv export --all-groups --frozen --format requirements.txt --no-header --no-annotate
rg -n "^requires =|build-system" pyproject.toml
rg -c "^\\[\\[package\\]\\]" uv.lock
rg -n "actions/checkout|setup-uv|dependency-review-action|gh-action-pypi-publish|sbom-action|attest-build-provenance" .github/workflows
```

## Immediate Hardening Applied

1. Pinned the build backend to `hatchling==1.29.0`.
2. Added a committed `uv.lock` baseline for reproducible installs.
3. Added CI and publish workflows with GitHub Actions pinned by commit SHA.
4. Enforced `uv sync --exclude-newer P7D --frozen` in CI and release validation.
5. Added dependency review, SBOM generation, attestations, and trusted publishing scaffolding.

## Dependency Map

### A. Direct dependencies

| Package | Declared in | Spec | Locked version | Lock quality | Notes |
| --- | --- | --- | --- | --- | --- |
| `build` | `pyproject.toml` (`dev`) | `>=1.4,<2` | See `uv.lock` | Locked | Release/build validation only |
| `mypy` | `pyproject.toml` (`dev`) | `>=1.18,<2` | See `uv.lock` | Locked | Strict typing in CI |
| `pytest` | `pyproject.toml` (`dev`) | `>=8.4,<9` | See `uv.lock` | Locked | Test runner |
| `ruff` | `pyproject.toml` (`dev`) | `>=0.12,<1` | See `uv.lock` | Locked | Linting |
| `twine` | `pyproject.toml` (`dev`) | `>=6.2,<7` | See `uv.lock` | Locked | Metadata validation |
| `yara-python` | `pyproject.toml` (`extra`) | `>=4.5.4` | See `uv.lock` | Locked | Optional end-user extra |
| `onnxruntime` | `pyproject.toml` (`extra`) | `>=1.24.4` | See `uv.lock` | Locked | Optional PromptGuard runtime |
| `transformers` | `pyproject.toml` (`extra`) | `>=5.5.3` | See `uv.lock` | Locked | Optional PromptGuard runtime |

### B. Transitive inventory

- Total locked packages: see `rg -c "^\\[\\[package\\]\\]" uv.lock`
- Non-registry sources: expected none in the initial scaffold
- Packages with install scripts: not yet reviewed in depth
- Git / URL / path dependencies: expected none beyond the editable root package

### C. Install And Release Surfaces

- Local development via `uv sync --dev`
- CI lint and test jobs via `.github/workflows/ci.yml`
- Release validation and build via `.github/workflows/publish.yml`
- Future optional runtime installs through `pip install 'textguard[...]'`

## Findings

1. Publish environment approval is not enforced by the repo alone.
   - Evidence: `.github/workflows/publish.yml` can target an environment, but reviewer rules live in GitHub settings.
   - Risk: trusted publishing is weaker if the environment is not protected before the first release.
   - Recommended action: configure the `pypi-publish` environment with required reviewers before any release tag is pushed.

2. Workflow linting is not yet part of CI.
   - Evidence: the scaffold includes dependency review but not `zizmor` or equivalent workflow analysis.
   - Risk: workflow-specific misconfigurations may slip through review.
   - Recommended action: add a workflow-lint lane once the basic scaffold stabilizes.

## Controls Review

| Control | Status | Notes |
| --- | --- | --- |
| Lockfile committed | Yes | `uv.lock` is tracked in git |
| Frozen install enforced | Yes | `uv sync --frozen` in CI and publish validation |
| Age gate enforced | Yes | `--exclude-newer P7D` in CI and publish validation |
| Hashes enforced at install surface | Yes | `uv.lock` drives installs and exports |
| Build scripts deny-by-default | Yes | No custom build hooks beyond pinned hatchling |
| GitHub Actions pinned by SHA | Yes | All external actions use commit SHAs |
| Release workflows avoid attacker-controlled triggers | Yes | Publish runs on tag push only |
| Workflow inputs sanitized before shell execution | Yes | No user-supplied workflow inputs in the publish path |
| Publish environment requires approval | No | GitHub environment rules still need configuration |
| Workflow linting (`zizmor` / equivalent) | No | Deferred after initial scaffold |
| Dependency review in CI | Yes | PR-only dependency review job present |
| SBOM / attestation | Yes | Release workflow generates both |

## Open Remediation Queue

- [ ] Configure the `pypi-publish` environment with required reviewers.
- [ ] Add workflow linting to CI.
- [ ] Re-run this audit after optional backends and release metadata mature.

## Accepted Risks

- Risk: the scaffold publishes a release workflow before the first release candidate exists.
  - Why accepted: release-path hardening is easier to review when it lands early.
  - Owner: repo maintainers
  - Sunset date: before `v0.1.0`

## Decision Summary

The repo is partially hardened and ready for implementation work, with two
clear follow-ups remaining before the first release: protected publish
environment configuration and workflow linting.
