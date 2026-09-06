# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356484204 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/314

Created: 2026-08-29T15:23:56Z; updated: 2026-09-05T16:00:56Z

Exact metadata: [source record](sources/issue-5356484204-edbde16def7189ebb1916ae94a1f018cd981afb28d5f56abb8ed9c30b1280366.json).

Custom battle commands:
- Magic uses the single GF’s preset spellbook, including zero-stock spells.
- Squall’s Switch opens GF selection.
- Irvine’s Shoot uses the firing interface, consumes ammo, and spends 1/X ATB per shot. X is a weapon value from 1–10, default 1.
- Quistis draws once from each enemy instance. Disable Draw only when no valid target remains.
- Selphie’s Summon uses the GF command. Angelo remains undefined.

Repaired Draw's enemy tracking and Shoot's turn, timer, and ATB handling. The changes are installed; other unfinished mechanics remain open.

Check the Draw repair:
- [ ] Restart Lexeditor. Enable Draw Once Per Enemy and Streamlined Draw, save, and enter a battle with two drawable enemies while below the spell-stock limit.
- [ ] Draw successfully from the first enemy. Confirm the second can still be drawn from, and the first cannot.
- [ ] Draw from the second. Confirm Draw becomes unavailable when no drawable enemy remains. Report which step fails.
- [ ] Use Irvine's Shoot. Confirm it stays open, consumes ammo, and spends the configured ATB per shot. Cancel once and confirm the next command works.



## issue 5356484204 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/314

Created: 2026-08-29T15:23:56Z; updated: 2026-09-06T12:59:35Z

Exact metadata: [source record](sources/issue-5356484204-02037d0add882e8e009e2957ef5eada3f2f507f10051a886f90e2f14735eedd5.json).

**Status: Partial.** Latest Draw tracking and Shoot repairs are installed; GF spellbooks (#93) and remaining custom-command behavior are unfinished.

- [ ] Enable Draw Once Per Enemy and Streamlined Draw, save and enter a battle with two drawable enemies while below the stock cap. Draw from each in turn: using the first must not disable the second; Draw should disable only when no valid target remains.
- [ ] Use Irvine’s Shoot: it should consume ammunition and the configured fraction of ATB per shot. Cancel and confirm the next command works. Report the command and failed step.

## issue 5356484204 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/314

Created: 2026-08-29T15:23:56Z; updated: 2026-09-06T12:59:35Z

Exact metadata: [source record](sources/issue-5356484204-6662547e7214161a70c553dcd59d716633d3be4fd5e901185ede500e537dbd0d.json).

**Status: Partial.** Latest Draw tracking and Shoot repairs are installed; GF spellbooks (#93) and remaining custom-command behavior are unfinished.

- [ ] Enable Draw Once Per Enemy and Streamlined Draw, save and enter a battle with two drawable enemies while below the stock cap. Draw from each in turn: using the first must not disable the second; Draw should disable only when no valid target remains.
- [ ] Use Irvine’s Shoot: it should consume ammunition and the configured fraction of ATB per shot. Cancel and confirm the next command works. Report the command and failed step.

## comment 5550345126 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/314#issuecomment-5550345126

Created: 2026-08-29T22:07:28Z; updated: 2026-08-29T22:07:28Z

Exact metadata: [source record](sources/comment-5550345126-9d3d837cf8a15945915a93437abca109c3aec108f0a723888100bd3734fc0e63.json).

Two mechanics are now implemented as separate Settings toggles. Draw Once per Enemy keeps vanilla draw strength, filters used enemies, greys Draw when no eligible target remains, and resets each battle. Irvine Shoot installs the real Shot command in Irvine's third slot, consumes normal ammo, spends ceil(full ATB / Shots per ATB) after every shot, returns to the same turn, and stays locked until his next ATB-ready transition. Weapons exposes Shots per ATB as a bounded 1-10 field, default 1. Both generated-patch contracts and rendered controls pass. GF Magic pages and Switch remain actionable.

## comment 5550345151 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/314#issuecomment-5550345151

Created: 2026-08-30T19:39:15Z; updated: 2026-08-30T19:39:15Z

Exact metadata: [source record](sources/comment-5550345151-93c0a7aeefb700e92b2425e012e9dc5d2e3368abcf855d0b3b096c52faf40e45.json).

Runtime regressions: Shoot crashes and must remain fail-closed until repaired; its visible name is Shoot. Draw Once appears to track party-wide completion instead of the acting character's one-use-per-enemy state, and its unavailable message must be No valid targets. Fixed Command Menu remains dependent on Monogamy and must implement the specified character slot 3 and GF-supplied slot 4 instead of leaving vanilla Attack/Magic/GF/Draw.

## comment 5550345169 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/314#issuecomment-5550345169

Created: 2026-08-30T20:02:07Z; updated: 2026-08-30T20:02:07Z

Exact metadata: [source record](sources/comment-5550345169-3d842430edc07fe05c65f74cdd68ac805c1b0755adb61315fe09d698d55f2cd9.json).

Draw Once per Enemy now uses one party-wide used-enemy mask. The first successful Draw from an enemy makes that enemy ineligible for every actor, instead of letting other party members continue drawing from it. The existing vanilla Draw amount and FFNx achievement wrapper remain in place.

## comment 5550345181 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/314#issuecomment-5550345181

Created: 2026-08-30T20:30:54Z; updated: 2026-08-30T20:30:54Z

Exact metadata: [source record](sources/comment-5550345181-340e08c123a0ddacf7b163c3b4794c74548c3f498736c689cacbacbae6df08ab.json).

The Shoot crash came from removing four bytes from the caller stack after replacing a CALL with a JMP. That adjustment is gone. Shoot is now part of Fixed Command Menu rather than an Irvine-only setting, and Shot is displayed as Shoot. Queue, ammo/ATB share, same-turn return, next-turn lock, and combined command-builder checks pass statically; battle acceptance remains.

## comment 5550345198 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/314#issuecomment-5550345198

Created: 2026-08-31T09:27:42Z; updated: 2026-08-31T09:27:42Z

Exact metadata: [source record](sources/comment-5550345198-7c0694616d81ef0648c6b60aaf9a17e4b94d8fe38e7628a3c32e0a8462843c14.json).

Switch, repaired Shoot, Draw, Selphie's Summon label, the fixed command builder, Shots per ATB bounds, settings persistence, and the rendered controls now pass their current contracts. The only unresolved requirement is GF Magic pages. FF8 has no native GF spell inventory or GF-to-spell table, and the issue does not say which spells belong to each GF. I need that mapping before I can implement the page without inventing gameplay data. Please provide the spell list for each GF; the completed battle mechanics still need in-game review.


## comment 5550345219 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/314#issuecomment-5550345219

Created: 2026-09-05T06:51:11Z; updated: 2026-09-05T06:51:11Z

Exact metadata: [source record](sources/comment-5550345219-9b84a6eeea69405fa427fd77f25aa18f18769151e627232b1f77f1892e007231.json).

Draw Once per Enemy failed in the reported two-enemy encounter: after drawing from one enemy, Draw became disabled although another enemy remained. The state must be per enemy, not per encounter. Drawing from one must not invalidate a different otherwise drawable enemy. Test remaining target eligibility separately from full-stock filtering and disable Draw only when no eligible target remains. Screenshot and report preserved; cause unconfirmed. Deferred.
