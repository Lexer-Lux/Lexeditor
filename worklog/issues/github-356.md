# Native battle repair delivery

## Shipped work

- Party Switch: resolve and measure actual character names, retire the outgoing
  model before loading its replacement, restore turns on cancellation, refresh
  cached name/HP, and keep command input suppressed during the transition.
- Red HP bars: native row boundary, not padded glyph atlas height.
- Blue GF HP bars: independent per-mod toggle; above names, left-to-right;
  combined junctioned GF HP with live charging HP during a summon.
- Editor search/header and compact Enemies UI remain included from master.

## Package evidence

The actual Windows x86 DLL is packaged, not merely source. Driver SHA-256:
`cf237e90a3c0a099c5182e58561e6469951bf2a493bc8a346938aceff2ab0e77`.
See the packaged `ISSUE51_BUILD_REPORT.md` for build/source provenance.
Build run 34035158902 compiled and linked the DLL; its later licence-copy step
failed, and the unchanged DLL/PDB were recovered from the archived candidate.
Promotion run 34035977911 validated and committed the reviewed package.
Integration run 34036574375 merged current master and passed native package,
compiled C++, GF settings, search, Enemies UI, card decoder, shared Magic and
FFNx settings regressions together. Linked verifier rejected all 11 binary
mutations. Private EXE tests passed for all three party slots and eight names.
The shipping smoke test checks actual Windows Git checkout bytes, backup and
upgrade of a fake installation, repeat installation and running-game refusal.
The follow-up Windows test's UTF-8 decoding and search fixture's timing race
were corrected without weakening runtime verification.

## Player acceptance (not performed by the agent)

Close FF8 before applying the upgrade. Pull master and restart Lexeditor.
In the active mod's Gameplay tweaks, enable HP Bars, GF HP Bars and Party
Switch, then Save. Saving enabled native tweaks uses the controlled derivative
installer; it backs up the prior driver. Do not replace FF8_EN.exe manually.
Leave Shared Magic Inventory off for this test: its combination with Party
Switch remains deliberately blocked pending separate combination validation.

Use a save with three active characters and at least one healthy unlocked
reserve, with a GF junctioned to the active character. Enter a normal battle.

1. Check all three rows: the red bar sits at the bottom of its row, while the
   blue bar sits immediately above the name. Blue fills from left to right.
2. When a character has a ready turn, press L1. Reserve names must be visible.
   Cancel once: the same ready turn must remain available.
3. Open again and confirm a reserve with X. The actor/model and displayed
   name/HP must change; battle input must return and the incoming ATB must
   start empty. Repeat for the other active slots and switch back.
4. During GF charging, damage to the GF must update the blue bar. Check an
   injured GF, a full-HP GF and a character without a junctioned GF.
5. Check that the Enemies changes, live search and hidden FFNx header remain.

Report a screenshot for any layout mismatch, and FFNx.log plus the affected
party/GF setup for any switch failure. These steps require the real game;
automated resource-I/O stubs do not establish live-game visual acceptance.
