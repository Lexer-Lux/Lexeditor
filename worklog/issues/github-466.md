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

## 2026-09-23 misc-bucket review (no agent slice)

- Re-read live #466 plus comments: still no results-screen layout code in
  `games/ff8`; the screen is drawn by the game exe natively. Nothing to turn
  on, nothing further to prototype without the game.
- No code change on `per-game-misc` for this issue. Lexer-only needs: the
  four acceptance renders of the three-column battle reward screen (single
  reward, several rewards, long description, modded description) and the
  award-once confirm check with save/fixture details, reported on #466.

## 2026-09-23 agents/actionables-ff8: layout model plus gated tweak

New `plugins/ff8/battle_results_issue_466.py`: help lookup from kernel text
sections 39/40 slot 1 (current mod edits; Shear Feather 147 verified at
section 40 record 114), word-wrapping three-column layout with cumulative row
offsets (no overlap/cutoff), exactly-once award model, and fail-closed
gating. Registered the `battleResultsHelp` tweak (off, unavailable with
blocker) in `gameplay_settings.py` plus the Tweaks-list row in `boot.js`, so
the issue is now visible in the tweaks list. Exe sweep re-confirmed reward
text lives in data files. Still needs: results-screen drawing hooks plus
available-space analysis, and the four acceptance renders with award-once
proof from a game session.

## 2026-09-23 impl/ff8-actionables: game confirmed FF8, labeled

Verified from the issue body: `Shear Feather` is FF8 item id 147
(`plugins/ff8/schema/item.json`), so the missing game label was added
(`ff8`). No new agent-side slice exists: the reward screen is drawn by
the game exe natively and the three-column layout needs its drawing
hooks plus the four acceptance renders from a game session. Stays
actionable.

## 2026-09-23 impl/ff8-wave2: string sweep confirms exe holds no reward text

Static sweep of the installed FF8_EN.exe found no item names (Shear
Feather), HELP-box, reward, spoils, or bonus strings: the results screen
is drawn natively from data-file text, so the three-column layout still
needs its drawing routine plus available-space analysis in-game. No code
change. Needs Lexer/game: the four acceptance renders (single, several,
long, modded descriptions) and the award-once confirm check. Stays
actionable.
