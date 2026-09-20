# FF7R2 plugin completion handoff

Branch: codex/ff7r-2-plugin-completion
Rebased onto master 72ee978a2ff36686a6349696b19860057356468a to preserve concurrent shared UI/test work.
Draft PR: #491, FF7R-2 Plugin

## Requirement / gap / evidence / next work

- Structured gameplay data: implemented PlayerParameter parser/editor with real
  FName row identity, fixed-width bounded scalar controls, byte-preserving
  project staging, source/project switching, Save/Discard/Reopen and reset.
  Evidence: synthetic source/service tests plus FF7R2 rendered browser workflow.
  Next: inspect current workflow results and screenshots.
- UI: Characters uses shared paged Table + Detail; Info/Data Map expose source,
  staging, helper and unresolved issue states; Tweaks preserves ReShade and
  Shader Injector. Markup/JS/CSS are split into editor.html/editor.js/editor.css.
  Next: fix any branch-native rendered failures; inspect desktop/narrow/150%.
- Extraction: retoc v0.1.5 researched and pinned by release hash, but not invoked
  because its Oodle path may acquire a proprietary DLL when absent. GamePlugin
  also currently has one shared helper slot occupied by Shader Injector.
  Next: coordinated multi-helper/dependency-explicit framework work, not this PR.
- Packaging/deployment: FF7R2 UnrealReZen behavior is documented; Save currently
  stages only the content path. Automatic package/install remains unavailable
  until Oodle can be supplied explicitly and a real Rebirth patch is accepted.
- Other open Rebirth requests #470, #471, #472, #473 and #477 remain visible as
  not integrated because no proved asset/runtime path is available yet.
- Real-game acceptance: only after all agent-side checks/screenshots/candidate
  work is complete. It must confirm a real PlayerParameter source parse, one
  harmless staged edit, external package load, and in-game behavior without
  overwriting the installation.
