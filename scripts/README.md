# Unicode Data Tooling

`textguard` will vendor generated Unicode metadata rather than depending on
runtime packages for script tables or confusable mappings.

Current implementation:

- `generate_unicode_data.py` fetches and verifies the pinned Unicode sources.
- Generated artifacts are written under `src/textguard/data/`.
- The generator currently pins Unicode `17.0.0`.
- `Scripts.txt` comes from the versioned UCD path.
- `confusables.txt` comes from `security/latest/` and the script verifies that the
  upstream header still declares the pinned Unicode version.

Planned workflow:

1. Run `python scripts/generate_unicode_data.py`.
2. Review the generated diff for `scripts.json`, `confusables.json`, and
   `confusables_full.json`.
3. Commit the updated generated artifacts alongside any code that depends on
   them.
