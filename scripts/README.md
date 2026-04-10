# Unicode Data Tooling

`textguard` will vendor generated Unicode metadata rather than depending on
runtime packages for script tables or confusable mappings.

Current scaffold state:

- `generate_unicode_data.py` exists only as a placeholder command surface.
- The full generator lands in Phase 4.
- Generated artifacts will live under `src/textguard/data/`.

Planned workflow:

1. Run `python scripts/generate_unicode_data.py` with the pinned Unicode version.
2. Review the generated diff for `scripts.json`, `confusables.json`, and
   `confusables_full.json`.
3. Commit the updated generated artifacts alongside any code that depends on
   them.
