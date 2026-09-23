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

## 2026-09-22 — completion audit: loader compatibility and remaining p0data

The earlier installed-game checklist was not the end of agent-side scope. Re-reading
live #74, `AGENTS.md`, the pinned Memoria loader source
(`d8df6e69ddb618adc753a27d9424409d66216a35`) and public FF9 tooling exposed
both a real mod-order defect and several known p0data families hidden by the old
catch-all Data Map row. #74 returned to `actionable`.

### Memoria load-order / conflict findings

- Runtime priority is **`FolderNames` first = highest priority**. Pinned
  `IniReader.cs` reads folders in reverse specifically so the first folder's
  changes overwrite later folders.
- Memoria's launcher reconstructs its installed-mod list from `Priorities`
  before `FolderNames`. Lexeditor previously inserted itself first only in
  `FolderNames`; after opening/saving the launcher, an existing `Priorities`
  list could move Lexeditor behind those mods. PR #490 now keeps Lexeditor first
  in both lists when `Priorities` already exists, and removes only its own entry
  on revert.
- Exact-path collisions between the Lexeditor project and a later external mod
  are therefore whole-file **Lexeditor wins**. Lexeditor does not merge separate
  mods at CSV record/field granularity.
- `MergeScripts` is a Memoria setting. With it disabled, normal priority applies;
  with it enabled, pinned Memoria attempts an experimental binary-diff merge and
  logs conflicts. Lexeditor neither enables nor rewrites this setting.
- Tests now cover two pre-existing external mod entries, launcher priority
  persistence, `MergeScripts` preservation, exact-path overlap, and byte-exact
  non-modification of the external mod file.

### Real online mod audit (no installed game)

Memoria's live catalog contained 79 top-level mods at audit time. The connector can
read catalog/release metadata and public repository trees, but cannot retrieve
binary release assets; release-only archive contents therefore remain uninspected.
No third-party package bytes are committed.

| Mod evidence | What was inspected | Compatibility that can be established without FF9 | What is not proven |
| --- | --- | --- | --- |
| Dualsense Buttons 1.1 / release `Main`, source commit `76e80966cdd4e8a6df960701e2c6081b2b07f4fa` | Real `ModDescription.xml`; release metadata; tree with `FF9_Data/EmbeddedAsset` UI/QuadMist atlases | Valid Memoria-style root; no default path overlap with Lexeditor's CSV/raw16 project output in the inspected tree | Release ZIP byte identity and in-game icon override |
| Chocobo Hot and Cold QoL / `v1.0.1`, commit `512b685be41d753ddf4bb70b53f57c51d0279dd3` | Real grouped `ModDescription.xml`; 183-entry mod tree; `FF9_Data` text plus `StreamingAssets/.../eventbinary/field/*.eb.bytes` in alternative submods | Memoria group/submod layout is structurally compatible. Author metadata explicitly requires loading above Alternate/Ferny; Lexeditor's own exact-path collision rule is now documented separately | Release ZIP extraction and gameplay behavior |
| Ukrainian Translation / main commit `1a936722ec83ccade65f28bdf324ea8e7ad3d258` | Catalog points to GitHub branch archive; real `DictionaryPatch.txt`, `ModDescription.xml`, `FF9_Data` text and 173-entry `StreamingAssets` field-map tree with `.bgx`/PNG overrides | Mixed Memoria root markers and loose asset overrides are recognized loader shapes. Lexeditor deploy/revert leaves such external folders untouched | Native localization rendering and interactions with other translation/gameplay mods |
| FFIX: The Lost Chapters 1.2.0 / commit `f50b7dacfca21b1296ba556ff518c3727acf0b14` | Current catalog/release metadata and public readme; release asset exists but built payload is not present in the tag tree | Declared incompatibilities (Trance Seek, Ferny Fantasy, No Cutscene/KupoMail in catalog) can be surfaced as metadata facts; no reason to override them | Package internals, overlap paths and in-game compatibility |
| CostumePack 2.1 / commit `3d85d4d97e3aba2a1f9b392dc494ee120c7550d5` | Catalog + GitHub release metadata | **Unsupported by the current Lexeditor helper pin:** catalog requires Memoria `2026.07.21`, newer than pinned `2025.07.04` | Any native behavior on a newer helper |

Across the current catalog, 38/79 entries declare `MinimumMemoriaVersion`; four
currently require a newer helper than Lexeditor's pin: **Ferny Fantasy IX
(2025-07-13), MistwakeUI - English Version (2026.09.01), CostumePack (2026.07.21),
and Extra Equipment Menu (2026.07.21)**. They stay outside the supported loader
boundary until the helper pin is deliberately advanced and re-verified.

Catalog-declared `IncompatibleWith`, submod groups and load-order instructions are
metadata, not proof of native coexistence. Without a real FF9 runtime this audit can
prove package shape, loader ordering, version boundaries, non-destructive
deploy/revert behavior and deterministic exact-path conflict resolution; it cannot
prove that two overlapping gameplay mods both behave correctly in game.

### p0data audit

The old single “other p0data” row is split into concrete gaps:

- `p0data1*.bin` — field backgrounds/scenes, cameras and walkmeshes. Hades Workshop
  reads numbered field bundles; MIT-licensed Dream World IX/ff9mapkit can extract,
  fork and rebuild these families. Lexeditor has not adapted those codecs into a
  preservation-tested field editor.
- `p0data2.bin` beyond the integrated BattleScene raw16 records — public tools
  also handle battle geometry/background/effect/sequence-related assets. No safe
  Lexeditor structured editor exists for them yet.
- `p0data3.bin` — world-map geometry/material/effect assets are publicly
  understood and overrideable. The current World tab only covers Memoria CSV data.
- `p0data4.bin` — field/character model prefabs are native Unity GameObjects with
  skinned meshes; public tooling exports them to editable models. Lexeditor has no
  tested mesh/rig import pipeline.
- `p0data5.bin` — serialized AnimationClips with public extraction/loose-override
  paths. Lexeditor has no semantic animation import/editor round-trip.
- `p0data7.bin` — compiled field, battle and world event scripts. Public tooling
  decodes/emits real `.eb` scripts; Lexeditor has no safe script UI/recompiler
  integration.
- `p0data6*.bin` and unmatched bundles — publicly enumerable UnityRaw containers,
  but this audit did not establish bounded player-facing schemas for their
  remaining contents.

Dream World IX source is MIT but explicitly excludes FF9-derived bytes from the
license grant. It is credited as format/interoperability research only; no source,
binary or extracted game data is bundled.

### Current next work

- [ ] Decide/implement preservation-tested player-facing editors for the known
      p0data families above, or obtain an explicit Lexer exclusion for individual
      low-value areas.
- [ ] Continue real-mod compatibility work where package bytes can be legally and
      technically inspected; do not turn metadata-only evidence into in-game claims.
- [ ] After agent-side Data Map/mod-loading scope is actually exhausted, rebuild an
      exact-head candidate and return #74 to `untested` for installed-game proof.

## 2026-09-23 --- per-game-ff9 branch status (no new codecs)

- No new p0data codec on this branch: each remaining family still needs a
  preservation-tested player-facing editor or an explicit Lexer exclusion, and
  only Lexer can exclude a Data Map area as not worth the effort.
- Gap rows stay explicit in `games/ff9/server.py` `UNRESOLVED_AREAS` and are now
  locked visible-but-closed by `tests/test_ff9_datamap_gui.py` (#525).
- Agent-side mod-loading scope stands as audited above; installed-game proof is
  still required and is now checklisted in `worklog/issues/github-523.md`.
- Exact needs: per-family pursue-or-exclude decision (see
  `worklog/issues/github-522.md`), then the installed-game battle proof from the
  earlier checklist (edit a visible enemy/encounter value, Deploy Project,
  launch through Memoria, confirm in battle, revert to vanilla).


## 2026-09-23 --- per-game-ff9 verification and discovery repair

- `per-game-ff9` fast-forwarded to master `e0e15a63` (PR #540 merged; upstream
  `origin/per-game-ff9` was gone and is re-pushed by this session).
- Repaired red discovery on this branch (both install shapes declared; kept
  root-aware hooks only) and regenerated `ui/credits.json` (the #524 theme
  provenance note was missing from the bundle).
- Agent-side verification: FF9 Python 164 passed + 74 subtests, node 18 passed,
  metadata pass, credits `--check` pass, `app.py --list` / `--game ff9 --check`
  (`ff9: ready`) / `--game ff9 --smoke` (5 PASS) pass, shared UI contract pass,
  rendered `ff9_browser_check` pass.
- Pre-existing failures unrelated to FF9, unchanged by this branch:
  `plugin_module_routes_check` (missing `LEXEDITOR_CHRONO_TRIGGER_ROOT`),
  `verify_tweaks_pagination` (harness `TypeError` before any game is reached).
- Exact needs below are unchanged: p0data codecs or Lexer exclusions, then the
  installed-game battle proof.
