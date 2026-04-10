# Publishing Checklist

Use this as the release checklist for cutting a new `textguard` version and
publishing it to PyPI.

## Versioning

Use semver-style bumps:

- Patch (`0.1.1`): bug fixes, packaging fixes, docs fixes, non-breaking detector refinements
- Minor (`0.2.0`): new public API surface, new CLI commands, meaningful detector additions
- Major (`1.0.0`): intentional breaking changes to result shapes, config/env names, or CLI behavior

## Release Punch List

- [ ] Start from a clean release scope: `git status -sb`
- [ ] Sync the release base: `git fetch --tags origin` and `git pull --ff-only`
- [ ] Pick the next version number
- [ ] Update version metadata in:
      `pyproject.toml`
- [ ] Update version metadata in:
      `src/textguard/__init__.py`
- [ ] Re-read `README.md` and confirm install, config, API, and CLI examples still match the code
- [ ] Update `README.md` and any user-facing docs if install steps, config behavior, or CLI workflows changed
- [ ] Re-read `docs/AUDIT-supply-chain.md` and refresh it if dependencies, workflows, or release controls changed
- [ ] Run release validation:
      `python3 -m py_compile src/textguard/*.py tests/*.py`
- [ ] Run release validation:
      `uv run ruff check src/ tests/ scripts/`
- [ ] Run release validation:
      `uv run mypy src/textguard/`
- [ ] Run release validation:
      `uv run pytest -q`
- [ ] Run release validation against the minimum supported Python:
      `uv run --python 3.11 pytest -q`
- [ ] Remove stale build artifacts before rebuilding:
      `rm -rf dist/`
- [ ] Build fresh artifacts:
      `uv build`
- [ ] Verify package metadata/rendering:
      `uvx --from twine twine check dist/*`
- [ ] Smoke-test the built wheel before upload:
      `uv run --isolated --with dist/textguard-X.Y.Z-py3-none-any.whl textguard --help`
- [ ] Stage only release files explicitly and review them:
      `git add ...`, `git diff --staged --name-only`, `git diff --staged`
- [ ] Commit release metadata:
      `git commit -m "chore: prepare vX.Y.Z release"`
- [ ] Create an annotated tag:
      `git tag -a vX.Y.Z -m "vX.Y.Z"`
- [ ] Push the release commit and tag:
      `git push origin main`, `git push origin vX.Y.Z`
- [ ] Verify the publish environment and trusted publishing settings are enabled in GitHub before tagging
- [ ] Verify the pushed tag triggers `.github/workflows/publish.yml`
- [ ] Verify the published install path from PyPI:
      `uvx --refresh --from "textguard==X.Y.Z" textguard --help`
- [ ] Verify the PyPI project page and Git tag both show the new version correctly
- [ ] Confirm the tree is clean again:
      `git status -sb`

## Notes

- Do not publish from a dirty tree.
- Do not reuse old `dist/` artifacts blindly; rebuild for every release.
- Trusted publishing is the intended default. Do not add long-lived PyPI tokens as a fallback without a documented incident-level reason.
- If release work changes config paths, environment variables, or CLI flags, update the public docs in the same release.
