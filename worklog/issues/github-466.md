# Issue 466 — Battle results three-column item help

## Requirements
Three columns (Item, Quantity, Help) on the battle results screen; every
received item's help visible at once, wrapping without overlap; HELP box
removed; amounts, inventory updates, and confirm behavior preserved; modded
descriptions used. Acceptance: single reward, several rewards, long and
modded descriptions render; confirm awards exactly once.

## Findings (2026-09-22)
- No results-screen layout code exists in plugins/ff8: the screen is drawn by
  the game exe natively. Reward-adjacent code (`formats.py` XP/drop fields,
  `mug_drops.py`) covers data, not layout.
- Only Lexeditor's own FFNx patch files are vendored
  (`plugins/ff8/ffnx_status_bars/`); the pinned FFNx source with the battle
  draw code is an external checkout, so hook locations cannot be confirmed
  from this repo.
- Precedent for renderer changes exists (`fast_start_ffnx.py` patches pinned
  FFNx C++ sources), so the likely implementation is an FFNx draw patch or
  an exe Hext patch — both unproven until rendered in-game.

## Next work (agent)
Locate the battle-results draw code (pinned FFNx source or FF8_EN.exe
static analysis), prototype the three-column layout, then hand the four
acceptance renders plus the award-once check to Lexer with a save/fixture.

## 2026-09-23 misc-fixes: flipped to waiting with concrete checklist

Per Lexer's rule (needs concrete Lexer-side work means waiting), posted the
exact game-session/decision checklist as a comment and swapped actionable
for waiting. A failed session returns it to actionable with evidence; a
passed session closes it subject to the merge workflow.
