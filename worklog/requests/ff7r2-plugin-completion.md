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
  Candidate output is .pak/.utoc/.ucas plus a manifest with input/tool/output
  hashes and acceptedInGame=false. Tests prove dependency refusal, exact command,
  adjacent Oodle requirement, no game-folder writes, tool/dependency hash
  stability and cleanup on failure.
  Lexeditor does not install the candidate or claim mod collision order.
- Candidate blocker in this agent environment: no mounted Rebirth installation,
  real IoStore archives or user-supplied Oodle DLL exist here, so producing a
  real candidate would require inventing/obtaining inputs and is intentionally
  not attempted.
- Other open Rebirth requests #470, #471, #472, #473 and #477 remain visible as
  not integrated because no proved asset/runtime path is available yet.
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
