# #523 — FF9 mod loading

[Live GitHub issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/523)

## 2026-09-23 — per-game-ff9: agent-side state, installed-game proof needed

Agent-side implementation (on master, verified by `tests/test_ff9_mod_compat.py`
and the `tests/ff9_browser_check.py` mod-compat capture) already covers:

- Memoria as the established loader; Lexeditor deploys one canonical project
  folder, never a competing loader.
- Launcher-order repair: Lexeditor stays first in both Memoria `FolderNames`
  and existing `Priorities` (first = highest runtime priority); revert removes
  only its own entry.
- Exact-path overlaps are whole-file Lexeditor-wins; separate mods are not
  semantically merged; `MergeScripts` stays Memoria-controlled and untouched.
- Real online mod/package metadata audit recorded in `worklog/issues/github-74.md`
  (Dualsense, Chocobo QoL, Ukrainian Translation, Lost Chapters, CostumePack);
  four catalog entries need a newer helper than the pinned `v2025.07.04` and stay
  outside the supported boundary until the pin is deliberately advanced.
- Deploy/revert leaves external mod folders byte-untouched (tested).

One root-cause fix on `per-game-ff9`: commit `f51586c7` ("Save local edits ...",
unrelated stardew-valley merge prep) had accidentally deleted the default-root
`helper_install`/`helper_status` hooks from `games/ff9/plugin.py`, breaking the
existing shared-updates contract test. Both hooks are restored; the for-root
variants are untouched. Nothing else truthful remains without a real installed
game. Metadata inspection is not installed-game success.

Needs a human with a supported Steam FF9 install:

- [ ] Install/enable/remove path through the Lexeditor project folder.
- [ ] Exact load order against at least one real gameplay mod.
- [ ] Conflicts/overlap, dependencies/version boundaries, restoration.
- [ ] Documented unsupported cases (newer-helper mods, MergeScripts behavior).

Status: actionable, blocked on installed-game proof. Do not close on metadata.
