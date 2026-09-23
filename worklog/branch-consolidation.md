# Branch consolidation — 2026-09-22

Compared the 23 archived branch heads with master `76ec7c3b`, its file history,
and the current plugin code. A different commit ID does not establish missing
work: several branches were applied through other commits, then changed again.
The 15 open plugin PRs and `misc-fixes` remain separate. No issue was closed by
this audit, and no installed-game acceptance is implied.

## Recovered work

- `fix/ff7-formation-semantics` (`d130e6d5`): recovered named formation layouts,
  arena choices, battle restrictions, next-battle references, depth rows, and
  initial-condition/cover controls. Kept later kernel semantics. Checked the
  stored flag inversion against Scarlet's `BattleSetupData.cs`. Unknown flag
  bits remain unlabelled and are preserved. Did not restore the old unsupported
  claim that the opening-camera index selects one of three stored placements;
  it remains an advanced numeric value.
- `fix/ui-standardization-20260906` (`d34c6455`) and the shared UI follow-up:
  restored immediate numeric-fill repaint after right-click reset. Call the
  paint function directly instead of sending an extra input event to the data
  model. Keep current sizing rules instead of restoring the old 10% label lane.
- Updated the FF7 browser fixture to load its extracted `editor.js`, retained
  save/reload coverage for the recovered formation control, and added reset-fill
  coverage to the existing shared browser checks.
- Added source credit for the formation references. Regenerated offline credits,
  which also removes an encoding mismatch in the RDR2 MinHook notice. Updated
  the stale shared verifier to the current 7.5% label-width default.

## Branch-by-branch disposition

| Archived branch | Result |
| --- | --- |
| `codex/ff9-issues-20260906` | One extra Unity reference-package download in an obsolete workflow. Master deliberately removed that workflow in `c208a706`. Do not restore it. |
| `codex/global-semantic-info-bubbles-349` | Semantic help and its tests are present in the extracted plugin scripts and shared controls. Current semantic-help tests pass. Temporary applicators and their workflow are not needed. |
| `fix/all-plugin-ui-conformance-20260906` | Shared detail adapters and all-plugin verification are covered by current code and `verify_shared_ui_contract.py`. The old verifier required outdated plugin repository metadata and HTML-only scripts. Keep the current host-owned issue tracker and verifier. |
| `fix/ff7-blank-ui-contract` | Extra diagnostic printing for an old neutral browser fixture, not a product change. Do not restore its obsolete selectors. |
| `fix/ff7-formation-semantics` | Recovered with the corrections above. |
| `fix/ff7-full-semantic-editor` | Kernel, dataset, semantic-editor, and verifier file versions are in master history. The extracted editor retains the concept tables and reference controls. Formation follow-up overlaps the recovered branch. Omit one-shot applicators/workflows. |
| `fix/ff8-enemies-layout` | Alternative early Enemies implementation. Its final commit explicitly retained the then-current master implementation after comparison. Current card artwork, enemy detail tables, and controls use the later implementation; do not restore the private `enemies_ui` module. |
| `fix/ff8-native-battle-batch` | All changed product/runtime file versions are in master history. The only unmatched file is a temporary build-cache export workflow. Keep the newer packaged driver and source. |
| `fix/ff8-ui-battle-regressions` | All three changed file versions are in master history. |
| `fix/ff8-world-camera-pitch` | Camera implementation appears in master history. Current integration adds battle controls, speed configuration, and later native features. The remaining seam-test difference is whitespace. Keep current integration, not the old world-only patch. |
| `fix/global-issues-20260906` | Current developer-mode tests include the old coverage and later restart fixes. Both workflows have newer coverage. Tests pass. |
| `fix/rdr1-editor-runtime-handoff` | Changed file versions are already in master history. Keep current plugin work in its open PR. |
| `fix/rdr2-issue-batch` | Historical worklog-only update, not code. It recorded runtime PR `Lexer-Lux/Lexers-Mod-For-RDR2#212`, decay for partial Recon progress, and distance-scaled tags; source run `34050295438` and package run `34050295402` passed then. It did not establish installed or gameplay acceptance. Preserve this history here, without replacing current issue handoffs or restoring dead conversation-archive links. |
| `fix/shared-ui-batch-20260906` | Current code contains identity-derived Developer Mode, shared model preview, pinnable Enabled columns, retained divider preferences, boolean-row clicks, and reference controls. Later code replaces its temporary scripts and obsolete UI layout rules. Reset repaint is recovered above. |
| `fix/ui-standardization-20260906` | Recovered reset repaint. Current layout and fitting code supersedes its old 10% CSS overrides. |
| `maintenance/human-issue-audit-20260906` | Historical issue-count/audit report only. No implementation to merge; do not replay old status changes. |
| `ui/ff8-blank-global-polish` | Source-export workflow only. |
| `ui/ff8-blank-global-polish-final` | All changed product/test file versions are in master history. |
| `ui/ff8-enemies-compact` | All changed file versions are current or in master history. |
| `work/ff7r-bundled-runtime` | Bundle of an earlier loader scaffold at `a62be775`. Current runtime source has later feature and validation contracts. Do not install or ship this old DLL as the current runtime. Current-build packaging remains part of the separate FF7R plugin work; this audit does not mark it delivered. |
| `work/ff7r-native-runtime` | The older diagnostic probe is superseded by `native_runtime/RuntimeProbe.cpp`, with the same map/raw-input evidence fields and stricter current anchors. `3d0e32b0` preserves the report schema; current configuration tests pass. Do not restore the parallel `native/` directory. |
| `work/ff8-remaining-batch-1` | Source-export workflow only. |
| `work/ff8-reptile-323` | Source-export workflow only. |

Three additional `tmp/terraria-*` branches were ancestors of the open Terraria
PR and required no merge. The first 101 removed branches were already accounted
for by ancestry, a merged PR at the exact head, or matching patches.

## Evidence and limits

- FF7 semantic/control and binary-save suites: 26 tests passed, including
  unknown-bit/value preservation and installed-file preservation.
- Headless browser: formation choice saves and reloads; reset fill changes from
  80% to 20% immediately. The formation screen was inspected. This is fixture
  evidence, not installed-game acceptance or acceptance of every editor layout.
- Semantic-help, developer-mode, global, and FF7R runtime configuration tests:
  43 passed, two skipped. Shared UI contract passed.
- Full archived Git history remains in the verified local bundle under
  `C:\Users\Lexer\Documents\Lexeditor-branch-archive\20260922-183418`.
  Its SHA-256 is `03e75774fd6301fa841587b28c00d178e572ba5c8f57062834a57ed1575ef04b`.
  This report contains decisions and evidence, not copies of GitHub discussions.

Formation references: [Scarlet](https://github.com/petfriendamy/ff7-scarlet/tree/main/src/SceneEditor)
and [battle-scene format notes](https://ff7-mods.github.io/ff7-flat-wiki/FF7/Battle/Battle_Scenes.html).
