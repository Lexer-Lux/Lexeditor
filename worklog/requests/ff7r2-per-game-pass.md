# FF7R2 per-game pass handoff (issues 469, 470, 471, 472, 473, 477)

Branch: per-game-ff7r2 (from master 5de3c63c, in sync with origin/master).
PR #491 already merged: all agent-provable ff7r2 work is on master.
This pass verified master state, ran the touched-area suite, and made no
game-code changes: every remaining gap needs the game or unpublished
persisted-storage evidence, and speculative controls were deliberately not added.

## Verification this pass

- `pytest tests/test_ff7r2_dataobject.py tests/test_ff7r2_server.py
  tests/test_ff7r2_packaging.py tests/test_ff7r2_shader_injector.py`: 66 passed.
- Live issues + comments for 469/470/471/472/473/477 re-read; Lexer triage on
  each confirms the branch line owns them and only in-game acceptance remains.
- Dirty files left untouched: ui/chooser.html, ui/framework.css,
  tests/ff8_graph_layout_browser_check.py, tests/test_chooser_app_theme.py,
  tmp_tab_probe.py (other work, not this game).

## Exact needs from Lexer (per issue)

- #469 (IoStore reader / max-HP reduction): needs a mounted Rebirth install
  with real IoStore archives to parse a real extracted PlayerParameter, make
  one harmless fixed-width edit, build the isolated candidate, copy the three
  candidate files to End/Content/Paks/~mods, verify in-game, then remove them
  and verify vanilla restoration. Record game build, hashes, manifest.
- #470 (chocobo whistle teleport+mount): needs in-game proof of the callable
  safe teleport + immediate-mount sequence, distance-ratio semantics/ranges,
  ride-legality predicate and vanilla fallback. Public names only prove the
  seams exist.
- #471 (Formulae/Steal): needs the complete Steal formula/terms, the
  roll-vs-no-item failure branch conditions and the message hook, plus proof
  that array writes are safe. Stays read-only/Partial until then; no
  Steal-only rate control (rate data is shared with drops).
- #472 (blue benches + cushion): needs the complete restable-placement ->
  blue-mesh mapping and the inventory/state transition consuming a cushion
  for every valid rest, without changing unusable benches.
- #473 (minimap zoom): needs which NaviMapScale category binds to which
  persisted setting, the complete stored range/default, and the save/config
  location. No invented slider.
- #477 (Queen's Blood skips): needs the legal-move predicate, automatic pass
  transition, both-sides-no-moves termination and the intro
  first-skippable-input hook. Timing fields are not a substitute.

No Fixes lines: these issues stay actionable until the above acceptance exists.
