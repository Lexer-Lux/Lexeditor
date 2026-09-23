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
- Rendered evidence: exact source head
  `e45da924d64d3d57c8e6293e2f942f2ac91067c7`, FF7R2 run 35806543930, passed
  browser + Linux + Windows. Artifact `ff7r2-rendered` digest
  `dc94da7164c4bc972fecda51d382be4358a3abff8ab73a05c0200991cd304bd1`
  was downloaded and visually inspected: desktop, narrow, simulated 150%,
  Data Map, Information and Tweaks were usable and evidence boundaries stayed
  visible. This remains the last completed rendered handoff before the newer
  Formulae/BattleItemPossession view; that view needs its own exact-head rerun.
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
- #470 Chocobo whistle pursuit: generated SDK declarations now prove concrete
  ride-legality/location/action seams beyond the original DataObject row names:
  `AEndLocationVolume.bDisableChocoboRide`,
  `UEndEnvQueryTest_IsDisabledChocoboRide`,
  `UEndEnvQueryContext_LastEnableChocoboRideLocation`,
  `FEndBehaviorChocoboRideOnExtraAction` and `UEndAnimNotifyCallChocobo`.
  Missing: the callable safe teleport + immediate mount sequence, distance-ratio
  semantics/ranges and vanilla fallback. #470 remains Not integrated.
- #471 Formulae / Steal pursuit: public format evidence proves _Array headers
  point to repeated values of the property's underlying type. Lexeditor now
  independently decodes fixed-width/name/string array elements read-only,
  exposes a source-only BattleItemPossession Formulae Table+Detail, and has
  synthetic preservation/bounds/edit-refusal tests. No BattleItemPossession file
  is staged or written. Public behavior evidence still says steal/drop share the
  25% rate data. Missing: safe accepted array writes, the complete Steal
  formula/terms, roll-vs-no-item failure branch and message hook. #471 is Partial
  and remains actionable.
- #472 bench/cushion pursuit: generated SDK declarations narrow the actor seam to
  `AEndFieldActionActorBenchBreak.BenchMeshComponent` and
  `ZabutonActorClass`; CampBreak derives from that bench actor. Missing: the
  complete restable-placement -> blue-mesh mapping and the inventory/state
  transition that consumes a cushion for every valid rest without changing
  unusable benches. #472 remains Not integrated.
- #473 minimap pursuit: generated SDK declarations now explicitly name
  `AreaNaviMapScale`, `LocationNaviMapScale` and `ZackNaviMapScale` option
  categories; `UEndNaviMap` exposes `PixelPerCm` and location prototype data
  has Min/Mid/MaxPixelPerCm. Missing: concrete requested-category range/default
  mapping and persistent save/config storage. No invented slider. #473 remains
  Not integrated.
- #477 Queen's Blood pursuit: generated types confirm `NeedCanPutCount`,
  player/enemy prediction fields, a `UEndCardGameMenu._PassClass` and yes/no
  handlers, plus turn/board-state seams. Missing: the legal-move predicate,
  automatic pass transition, both-sides-no-moves termination and intro
  first-skippable-input hook. Timing fields are not substituted for requested
  logic. #477 remains Not integrated.
- Deterministic service/browser assertions now lock the requested evidence states:
  #471 must be Partial/view/Formulae while #470/#472/#473/#477 must stay
  Not-integrated until real implementation advances them.
- Shared-suite status at exact rendered head `e45da924...`: Shared UI contract
  passed. Shared UI visual acceptance failed in Blank acceptance before
  Rebirth-specific checks; repository-wide verifier failures sampled there were
  other-game/shared failures. They are not counted as Rebirth source/rendered or
  in-game evidence.
- Real-game acceptance remains required: parse a real extracted PlayerParameter,
  make one harmless fixed-width edit, build the isolated package candidate, copy
  the three candidate files manually to End/Content/Paks/~mods, start Rebirth,
  verify the intended harmless value change, then remove all three files and
  verify vanilla restoration. Record exact game build, source/candidate hashes,
  candidate manifest and observed behavior before any automatic install path is
  considered.
