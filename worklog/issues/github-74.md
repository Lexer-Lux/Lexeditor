# #74 — FF9 CSV editor coverage

## 2026-09-06 — character-data increment

Added Character parameters, Starting equipment and Level growth under Characters,
using three SHA-256-pinned official v2025.07.04 CSVs. Catalog/Data Map registration
now includes all 12 implemented files; Data Map links carry the exact dataset key.

Verified official raw-byte Git blob/SHA-256 hashes and read/edit/reload of all three
schemas (12, 16 and 99 rows). Unit fixtures exercise typed booleans/numbers, bounds,
empty equipment slots, UTF-8 BOM, Windows-1252 punctuation, mixed line endings and
missing final newlines. Stale source changes and selecting a baseline as the
project are refused. Empty saves do not create overlays. Non-finite floats cannot
be serialized; fractional integer edits are no longer silently truncated by JS.

Status: partial/actionable. No enemy/encounter editor or p0data writer was added.
The remaining Memoria data formats, full real-shell render matrix and game
readback/deployment acceptance are still agent work; do not close this issue or
call placeholder tabs complete. Full repository smoke was not run in this
connector-backed, partial local checkout.

Prepared acceptance checklist after review:
- [ ] In Characters, open all four subtabs; check search, sorting and record selection in the real editor.
- [ ] Save one row/pose checkbox, one starting equipment field and one level-growth field; restart the editor and confirm them.
- [ ] Compare the installed baseline with its original; only the selected mod-project overlay should have changed.
- [ ] Verify deployed character equipment/growth changes in a disposable in-game test.
