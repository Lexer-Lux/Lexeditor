# FF7R2 plugin completion handoff

Branch: codex/ff7r-2-plugin-completion
Last wholesale reconciliation: master 72ee978a2ff36686a6349696b19860057356468a. Live master re-audited at 76ec7c3b9b289f1d52bcf684c691d5020619c3f6; only compatible Rebirth-local changes were adopted because shared work has advanced substantially.
Draft PR: #491, FF7R-2 Plugin

## Requirement / gap / evidence / next work

- Structured gameplay data: PlayerParameter parser/editor uses real FName row
  identity, bounded fixed-width scalar controls, byte-preserving project staging,
  source/project switching, Save/Discard/Reopen and reset. Synthetic format and
  service tests cover no-op/changed round trips, bounds, stale writes and source
  preservation.
- UI/theme: Characters uses shared paged Table + Detail; Info/Data Map expose
  source, staging, dependency and unresolved issue states; Tweaks preserves
  ReShade and Shader Injector. The theme is proprietary-asset-free and uses only
  original dark/blue/white CSS tokens derived from publicly visible Rebirth UI.
  Current-master shared detail sizing was adopted by removing the stale local
  label-width override.
- Rendered evidence: the ff7r2-rendered artifact at e82aa8e was downloaded and
  visually inspected. Desktop, narrow, Data Map, Information and Tweaks were
  usable; unsupported Data Map rows remained visible. The 150% browser check now
  captures the viewport rather than a CSS-zoomed full page, which previously
  created an artificial blank tail. The exact live head `5a7149ae9cdd5351f998800c47835f1bc21d681e`
  reran the FF7R2 workflow successfully on Linux, Windows and Chromium. Its
  `ff7r2-rendered` artifact was downloaded and visually inspected: desktop,
  narrow, simulated 150%, Data Map, Information and Tweaks all remained usable;
  unsupported Data Map rows stayed visible and Information still states that the
  staged output is not packaged or installed.
- Extraction: retoc v0.1.5 remains researched/pinned but is not invoked because
  its absent-Oodle path can acquire a DLL. GamePlugin still exposes one shared
  managed-helper slot, already owned by Shader Injector. Do not compete for a
  shared framework/multi-helper rewrite from this PR.
- Packaging/deployment: a dependency-explicit UnrealReZen candidate builder is
  implemented. It requires explicit LEXEDITOR_FF7R2_UNREALREZEN and
  LEXEDITOR_FF7R2_OODLE paths and the known CUE4Parse/1.1.1 dependency manifest.
  That CUE4Parse helper checks for oo2core_9_win64.dll before its downloader, so
  LEXEDITOR_FF7R2_OODLE must point to that exact filename already beside the
  explicit UnrealReZen executable. Lexeditor does not download, copy or relocate
  Oodle and runs the tool from that directory. Proxy variables are not relied on
  because that historical downloader disables proxy use. The route uses GAME_UE4_26 +
  ../../../End/Content/ + top-only archive scanning and writes only
  project/build/ff7r2-candidate-*.
  Candidate output is .pak/.utoc/.ucas plus a manifest with staged/tool/output
  hashes and acceptedInGame=false. The packer now audits every regular file under
  content/End/Content instead of assuming PlayerParameter is the only input:
  staged symlinks are refused, every path/size/hash is recorded, and the complete
  staged set plus hashes are rechecked after UnrealReZen exits. Synthetic tests
  cover multiple staged inputs, input mutation and staged-set mutation in addition
  to dependency refusal, exact command, adjacent Oodle requirement, no game-folder
  writes, tool/dependency hash stability and cleanup on failure.
  Lexeditor does not install the candidate or claim mod collision order.
- Candidate blocker in this agent environment: no mounted Rebirth installation,
  real IoStore archives or user-supplied Oodle DLL exist here, so producing a
  real candidate would require inventing/obtaining inputs and is intentionally
  not attempted.
- #470 Chocobo whistle pursuit: public Rebirth constants now narrow this to
  ResidentParameter rows CallChocoboAtFieldActionDistanceParamRatio0/1 plus
  key_ChocoboWhistle, FA0407_00_ChocoboWhistle_Standard and ChocoboRide identity
  leads. Missing: a proved instant teleport/mount hook, safe-placement rule,
  ride-legality predicate, vanilla fallback, and semantics/ranges for the two
  distance ratios. No speculative control was added.
- #471 Formulae / Steal pursuit: BattleItemPossession publicly exposes
  NormalItemPercent_Array, RareItemPercent_Array, StealItemName_Array,
  StealItemQuantity_Array and StealFaildCountArrayIndex. The 100% Steal/Drop mod
  author reports Rebirth shares the 25% data between stolen and dropped items.
  Missing: writable array-element support, the complete Steal formula/terms,
  roll-vs-no-item failure branch and message hook. A Steal-only percentage
  control would therefore be misleading and was not added.
- #472 bench/cushion pursuit: public constants identify
  scgCmn_Tmp_Bench_Init/Rest, trgCmn_Bench_Rest,
  acgCmn_RecoverAll_ForBench and UI7033_00_ConsumedItem_Cushion. Public mesh
  evidence confirms the blue bench is separate from Chocobo-rest benches and
  multiple bench models exist. Missing: the complete restable-placement-to-model
  mapping and the universal cushion-consumption gate.
- #473 minimap pursuit: MapIconInfo exposes navimap visibility/layer, offsets and
  view-distance fields but no zoom field. Public 2026 accessibility work proves
  minimap position/size can be changed in packaged HUD data and distinguishes
  that from its UE4SS HUD mover. Missing: a world-minimap zoom scalar, valid
  range and persistence path; size/position/FOV are not mislabeled as zoom.
- #477 Queen's Blood pursuit: public CardGameCommonParameter/CardGameAIParam
  constants expose EffectWaitTime, NeedCanPutCount and player/enemy prediction
  fields, but do not prove the legal-move predicate, automatic pass transition,
  both-sides-no-moves end condition or intro skippable-input state. Score/card
  cheat evidence is not used as proof of those hooks.
- These five areas remain visible as not integrated, but their Data Map rows now
  name the concrete public data families and exact blockers rather than treating
  them as generic unsupported requests.
- Shared-suite status at that head: `Shared UI contract` fails because merged
  `ui/framework.css` defines `--lex-detail-label-width:7.5%` while the current
  verifier expects `minmax(var(--lex-detail-label-floor),10%)`; PR #491 does not
  modify that shared file. `Shared UI visual acceptance` times out in the shared
  Blank acceptance before any Rebirth-specific check. These are tracked as
  shared-baseline failures, not Rebirth regressions.
- Real-game acceptance remains required: parse a real extracted PlayerParameter,
  make one harmless fixed-width edit, build the isolated package candidate, copy
  the three candidate files manually to End/Content/Paks/~mods, start Rebirth,
  verify the intended harmless value change, then remove all three files and
  verify vanilla restoration. Record exact game build, source/candidate hashes,
  candidate manifest and observed behavior before any automatic install path is
  considered.
