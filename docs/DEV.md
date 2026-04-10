# Dev Environment Decisions

Cross-repo review of realitycheck, tweetxvault, outline-edit, shisad, and supply-chain-security to inform textguard's scaffold. Decisions finalized 2026-04-10.

---

## Cross-Repo Pattern Summary

| Aspect | realitycheck | tweetxvault | outline-edit | shisad |
|--------|-------------|-------------|--------------|--------|
| **Build system** | hatchling | hatchling | hatchling 1.29.0 | hatchling 1.29.0 |
| **Package manager** | uv | uv | uv | uv |
| **Layout** | flat (`scripts/`) | flat (`tweetxvault/`) | **src/** (`src/outline_edit/`) | **src/** (`src/shisad/`) |
| **Python** | >=3.11 | >=3.12 | >=3.10 | >=3.12 |
| **Linting** | none | ruff | none | ruff + mypy strict |
| **Testing** | pytest | pytest + asyncio | pytest | pytest + asyncio |
| **CI** | none | none (ref has GHA) | none | full GHA matrix |
| **uv.lock** | present (gitignored) | present | present | present (committed) |
| **Runtime deps** | 6 | 11 | **0** | 9 core + groups |
| **Dep groups** | dev only | dev only | dev only | dev, security-runtime, security-build, coverage, channels-runtime |

---

## Decisions

### 1. Build system: hatchling (pinned)

Every project uses hatchling. Pin to match outline-edit and shisad.

```toml
[build-system]
requires = ["hatchling==1.29.0"]
build-backend = "hatchling.build"
```

### 2. Layout: `src/` layout

Matches outline-edit and shisad — the two most recent and most mature projects. The flat layout in realitycheck/tweetxvault is older convention.

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/textguard"]
```

### 3. Python: `>=3.11`, dev pinned to 3.12

Package supports 3.11+ (oldest still-supported CPython; stdlib-only core benefits from wider compat). Local dev pins `.python-version` to `3.12` to match shisad.

### 4. uv with committed lockfile

All projects use uv. Per supply-chain-security policy, lockfiles must be committed for shisa-ai repos. shisad commits its `uv.lock`; textguard does too.

### 5. Both optional-dependencies and dependency-groups

textguard's `yara` and `promptguard` extras are **user-facing install targets** (`pip install 'textguard[yara]'`), not dev workflow groups. Need both mechanisms:

- `[project.optional-dependencies]` for `yara`, `promptguard`, `all` — pip-installable extras
- `[dependency-groups]` for `dev` — internal dev tooling (pytest, ruff, mypy)

Uses `[dependency-groups]` (PEP 735) for dev, matching shisad's newer convention over the older `[tool.uv]` dev-dependencies pattern in realitycheck/outline-edit.

### 6. Full supply-chain-security compliance

Per `shisa-ai/supply-chain-security/policy/repo-standard.md`:

- **Committed `uv.lock`** with hash verification
- **7-day age gate**: `UV_EXCLUDE_NEWER` in CI
- **Frozen installs in CI**: `uv sync --frozen`
- **`uv lock --check`** in CI to catch lockfile drift
- **GitHub Actions pinned to commit SHAs** (not version tags)
- **OIDC trusted publishing** to PyPI (no long-lived tokens)
- **SBOM generation** on release
- **`docs/AUDIT-supply-chain.md`** per the audit template

Non-negotiable for shisa-ai repos. shisad already implements all of this.

### 7. Linting: ruff + mypy strict

Security-sensitive code warrants strict typing. Matches shisad's config.

```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM", "RUF"]

[tool.mypy]
python_version = "3.11"
strict = true
```

### 8. Testing: simple pytest

Synchronous library — no need for pytest-asyncio.

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

### 9. CI from day one

Public repo at `shisa-ai/textguard` (to be created with `gh repo create`). Package name `textguard` available on PyPI, claimed on first publish. CI modeled after shisad but leaner:

- **Lint lane**: ruff + mypy
- **Test lane**: pytest on 3.11 + 3.12 matrix
- **Dependency review** on PRs
- **Publish workflow**: tag-triggered, OIDC trusted publishing, SBOM
- **`uv sync --exclude-newer P7D --frozen`** in all lanes

Can grow toward shisad's full multi-lane architecture (adversarial tests, coverage gating, zizmor) as the codebase matures.

### 10. Zero runtime dependencies for core

outline-edit proves this works. Strongest supply-chain posture — nothing to attack in the core install. Optional extras (`yara`, `promptguard`) bring in heavy deps but are opt-in.

### 11. CLI entry point via argparse

```toml
[project.scripts]
textguard = "textguard.cli:main"
```

Matches outline-edit's pattern. argparse over Click — lighter tool, no extra dependency.

### 12. Publishing: outline-edit checklist + shisad CI automation

Create `docs/PUBLISH.md` modeled on outline-edit's release checklist, extended with shisad's automated CI publishing:

- Manual `uv publish` for early releases (outline-edit pattern)
- Tag-triggered GHA publish workflow for stable releases (shisad pattern)
- `twine check` in dev deps for metadata validation

---

## shisad Consumption Model

shisad currently has its own `normalize.py` in its firewall (`src/shisad/security/firewall/normalize.py`). The extraction/adoption path is tracked as separate `shisad` migration work rather than as a `textguard` repo document.

**Decision: hybrid dependency placement.**

- `textguard` (bare) goes in shisad's **core** `[project.dependencies]` — zero transitive deps, so it costs nothing. shisad gets normalization, detection, and decode in every install.
- `textguard[yara]` also goes in shisad's **core** deps — YARA is fundamental to shisad's firewall, not optional.
- `textguard[promptguard]` goes in shisad's **`security-runtime`** group — PromptGuard is the only truly heavy optional dependency (onnxruntime + transformers). This is the dependency that resource-constrained environments (RPi, etc.) may not be able to run. The `security-runtime` group might eventually be renamed to `promptguard` since that's all it would contain after textguard absorbs the YARA pin.

---

## Minimum Scaffold File Tree

```
.github/
  workflows/
    ci.yml                # lint + test matrix + dep review
    publish.yml           # tag-triggered OIDC publishing
src/textguard/
  __init__.py
  types.py
tests/
  conftest.py
docs/
  AUDIT-supply-chain.md  # supply-chain-security compliance
pyproject.toml            # hatchling==1.29.0, >=3.11, optional-deps + dep-groups
.python-version           # 3.12
.gitignore                # .venv/, __pycache__/, dist/, build/, *.pyc
uv.lock                   # committed
```

---

## Raw Data: Per-Repo Details

### realitycheck (`lhl/realitycheck`)

**pyproject.toml highlights:**
- `name = "realitycheck"`, version 0.3.3
- `requires-python = ">=3.11"`, Apache-2.0
- 6 runtime deps: lancedb, pyarrow, pyyaml, beautifulsoup4, sentence-transformers, tabulate
- Dev deps via both `[project.optional-dependencies]` and `[tool.uv]` (duplicated)
- 6 CLI entry points via `[project.scripts]` (rc-db, rc-validate, rc-export, rc-migrate, rc-embed, rc-html-extract)
- Hatchling build with force-includes for integrations/ and methodology/ dirs
- pytest config with `requires_embedding` custom marker
- Coverage config with branch coverage

**Notable patterns:**
- `.python-version` = 3.12
- uv.lock present but gitignored (1576 lines)
- Makefile with comprehensive targets (test, install-skills, plugin management, release metadata)
- No CI/CD workflows
- No linting config
- `scripts/` flat package (not src layout)

### tweetxvault (`lhl/tweetxvault`)

**pyproject.toml highlights:**
- `name = "tweetxvault"`, version 0.2.2
- `requires-python = ">=3.12"`, no explicit license
- 11 runtime deps: browser-cookie3, httpx, lancedb, numpy, loguru, pydantic, pyarrow, rich, tqdm, typer, platformdirs
- Optional `embed` extra: huggingface-hub, onnxruntime, tokenizers
- Dev deps via both `[project.optional-dependencies]` and `[tool.uv]`
- Single CLI: `tweetxvault = "tweetxvault.cli:app"`
- Ruff config: line-length 100, py312, select ASYNC/B/E/F/I/RUF/UP
- pytest-asyncio with auto mode

**Notable patterns:**
- uv.lock present (187K)
- No .python-version file
- No Makefile or task runner
- No CI (but reference/tweethoarder has full GHA CI, justfile, pre-commit, git-cliff changelog)
- Flat package layout (`tweetxvault/` not under `src/`)
- Reference project (tweethoarder) demonstrates production-grade setup with uv-dynamic-versioning, deptry, zuban type checker

### outline-edit (`lhl/outline-edit`)

**pyproject.toml highlights:**
- `name = "outline-edit"`, version 0.2.1
- `requires-python = ">=3.10"`, MIT license
- **Zero runtime dependencies**
- Dev deps: build==1.4.2, pytest==9.0.2, twine==6.2.0
- Single CLI: `outline-edit = "outline_edit.cli:main"`
- Hatchling 1.29.0 (pinned), src layout
- Force-includes SKILL.md into wheel
- sdist includes integrations/, src/, tests/, docs/

**Notable patterns:**
- `.python-version` = 3.10
- uv.lock present (713 lines)
- No CI/CD workflows
- No linting config
- `docs/PUBLISH.md` with comprehensive release checklist (py_compile, help text verification, min python test, twine check, isolated wheel smoke test)
- Pre-built dist/ artifacts committed
- Version tracked in 3 places: pyproject.toml, `__init__.py`, cli.py USER_AGENT
- Single-module core (cli.py at 73KB)

### shisad (`shisa-ai/shisad`)

**pyproject.toml highlights:**
- `name = "shisad"`, version 0.6.2
- `requires-python = ">=3.12"`, Apache-2.0
- 9 core deps: pydantic, pydantic-settings, agent-client-protocol, click, pyyaml, cryptography, fido2, loguru, qrcode
- 5 dependency groups: dev, security-runtime, security-build, coverage, channels-runtime
- 3 CLI entry points: shisad, shisactl, shisad-approver
- Hatchling 1.29.0 (pinned), src layout
- Ruff: py312, line-length 100, select E/F/W/I/UP/B/SIM/RUF
- MyPy: strict=true, pydantic plugin
- pytest-asyncio with auto mode, custom markers (requires_cap_net_admin, live_smoke)

**CI architecture (`.github/workflows/ci.yml`):**
- Multi-lane: lint+test, security-runtime, privileged connect-path, adversarial PR core, adversarial nightly full, dependency review, zizmor
- Python 3.12 + 3.13 matrix
- `uv sync --exclude-newer P7D --frozen --dev` (7-day age gate)
- Per-module coverage enforcement (critical floor 80%, module floor 60%)
- YARA parity metrics and adversarial regression gating

**Publish workflow (`.github/workflows/publish.yml`):**
- Tag-triggered manual dispatch
- Version verification against package metadata
- Full lint + test suite on release branch
- pip-audit with hash requirements
- SBOM generation (Anchore)
- Attestations and trusted publishing via OIDC

**Deployment model:**
- Long-running daemon with CLI control interface
- tmux-based session management via `runner/harness.sh`
- Unix socket IPC for CLI-to-daemon communication
- `.env` file pattern, XDG-compatible config paths

**Text normalization integration point:**
- `src/shisad/security/firewall/normalize.py` — current custom implementation
- Functions: `normalize_text()`, `decode_text_layers()`, `DecodedText` dataclass
- Called from `ContentFirewall.inspect()` and `OutputFirewall.inspect()`
- No existing textguard references in codebase

### supply-chain-security (`shisa-ai/supply-chain-security`)

**Not a code package** — organizational security policy repo.

**Mandatory per-repo standards (`policy/repo-standard.md`):**
- Committed lockfiles: `uv.lock` for Python
- Frozen CI installs: `uv sync --frozen`
- 7-day age gate: `UV_EXCLUDE_NEWER` set to 7 days prior
- Build scripts deny-by-default
- GitHub Actions pinned to full commit SHAs
- `GITHUB_TOKEN` permissions default to read-only
- Dependency review on dependency-changing PRs
- SBOM generation on every build
- OIDC trusted publishing (no long-lived tokens)
- `zizmor` workflow linter on publish workflows

**Per-repo audit artifact (`policy/audit-template.md`):**
- Every active repo must maintain `docs/AUDIT-supply-chain.md`
- Contents: package manager status, lockfile status, install/release entry points, direct/transitive dependency inventory, CI review, hardening applied, open remediation items

See `shisa-ai/supply-chain-security` for full policy details, audit templates, and implementation guides.
