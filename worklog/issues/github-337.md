# RDR1 issue #337

## 2026-09-22 — PR #487 completion pass

Current implementation branch: `codex/rdr1-plugin-completion`.
Draft PR: #487. Keep this as the one RDR1 implementation PR; do not merge or
auto-merge from the worker.

### Source evidence

- Structured tabs remain Items, Shops, Strings, Loot Tables, Missions and
  Tweaks; Data Map is the shared Help view and there is no raw Files editor.
- Items preserve unsupported/nested XML while exposing bounded direct scalar
  fields. Shops expose only verified `ShopInventory` fields and verify packed
  round trips before publishing an override.
- PC `.strtbl` text support is format-specific and preservation-oriented:
  byte-exact no-op save, changed-text relocation, stale-write refusal, shared
  physical language blocks, and non-BMP UTF-16 counts are covered by synthetic
  tests. The UI is language-first across resources; logical language tabs do
  not expose parser row indexes as game IDs.
- The exact corpse-loot WSC is Partial and rewrites only verified length-safe
  item-enum call sites. Other WSC rows stay Not integrated.
- `tools/verify_rdr_data_map_audit.py` audits every generated Data Map row:
  generated research metadata cannot promote a row by itself, filenames must
  be unique, unrelated WSCs remain Not integrated, and `_ps3.strtbl`
  duplicates remain unavailable in the PC plugin. Dynamic parser-backed PC
  STRTBL and ShopInventory promotion is tested separately.
- MagicRDR is registered in the shared helper-version path at pin `v1.3.10`.
  Status/upstream checks are read-only; there is no install or auto-update
  action. Its binaries/source remain excluded from candidate redistribution
  because upstream declares no redistribution license.
- RedHook remains an external in-game prerequisite. Lexeditor only detects it,
  links to the official page on explicit user action, and backup-preserves the
  supported `RedHook.ini` change; it does not bundle or silently update it.

Exact-head source checks are run by `.github/workflows/rdr1-checks.yml` and
the extracted-candidate checks in `.github/workflows/rdr1-candidate.yml`.
Record the final run IDs in the live PR/issue after the final handoff commit;
do not infer current-head success from older runs.

### Rendered evidence

The exact-head rendered suite uses production RDR editor modules with synthetic
API fixtures and captures Items, Strings and Missions at:

- 1200×800, 100% UI scale;
- 900×620, 100% UI scale;
- 1200×800, 150% UI scale.

It also exercises the fuller editor interaction fixture for list/detail fitting,
save preflight, save/discard/reopen, project/Vanilla switching, deterministic
shop/mission handoffs, and error recovery. Final exact-head run/screenshots
must be recorded after this handoff commit; older screenshots are historical
evidence only.

### Candidate evidence

`rdr1-candidate.yml` builds an isolated RDR-only ZIP from the exact source
SHA, narrows shared metadata to RDR1, excludes other game plugins, excludes font
files, and excludes `tools/magic-rdr/app`, `cli`, and `source`. The ZIP
contains exact PowerShell environment/setup instructions plus save,
discard/reopen, Data Map and RedHook acceptance steps. The extracted ZIP reruns
RDR source/round-trip/cache/layout/Data Map checks.

Final exact-head candidate artifact ID, archive SHA-256 and source SHA must be
recorded in the live PR/issue after the final handoff commit.

### In-game evidence

Not established by this worker environment. No installed RDR1 game/runtime is
available here. Real deployment/revert and gameplay behavior remain separate
human acceptance, including the deterministic shop price test (#341), mission
reward test (#344), runtime/development mode (#332), weapon wheel (#333), HUD
(#340), and the other native feature issues. Source, rendered browser and
candidate evidence do not close those checks.

