# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356334016 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/298

Created: 2026-08-23T06:07:15Z; updated: 2026-09-05T07:05:36Z

Exact metadata: [source record](sources/issue-5356334016-859f92ed3783279ecb4668037a2d1d1f8ee50e5b86a6b02f777a688abdd6f66f.json).

Crows around a dead body get no lower-right animal info box and cannot be studied, unlike other animals.

What the installed log already shows (session 2026-08-22, dev build):

- The crow IS the aimed entity: `aimed=1 aimedModel=0x05df8f2c` (`A_C_CROW_01`), so the reticle ray does resolve it.
- Recon never accepted it: `bestPed=0` on every scan, and `pedNearestScreen` stayed 0.196-0.387 against `radius=0.050`, i.e. the nearest ped anchor was measured well off screen centre.
- Rockstar's contextual animal focus never returned the crow either: `studyInteraction=0`, `studyEntity=0`, `studyAnimal=0` on every scan while the crow was aimed at.
- `animal infobox target=0` for the whole session, so the Lexer-Lux/Lexeditor#268 contextual-action bridge never armed - it only arms once Recon has already resolved an animal target, so a crow rejected by Recon's own gates can never reach Rockstar's info box through binoculars.

Open question that decides the fix: whether the crow ped carries a valid animal type, short description and discoverable name/type pair (it has a compendium entry, `CMPNDM_CROW` / `AT_CROW`, so it should), and whether crows even appear in the ped pool snapshot Recon scans.

`[CompendiumGlintProbe] Enabled=1` has been set in the installed INI so an F10 capture at a crow answers both without a rebuild.

## issue 5356334016 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/298

Created: 2026-08-23T06:07:15Z; updated: 2026-09-06T13:07:38Z

Exact metadata: [source record](sources/issue-5356334016-66a5198612060d103175f9af20c6085282fefcf902824ee5ae9596412dd72d5c.json).

**Status: The aimed-crow selection repair is installed.** The old claim that crows could not be resolved was incorrect.

- [ ] In Story Mode, aim a weapon at a crow near a corpse without shooting. Confirm the lower-right animal information/Study interaction appears for the crow rather than a nearby target. Avoid binoculars while #357 is unresolved.
- [ ] If it still fails, press F10 once while aimed with the already-prepared compendium probe enabled. Report the result and attach the probe output and GameplayTweaks.log.

## issue 5356334016 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/298

Created: 2026-08-23T06:07:15Z; updated: 2026-09-06T13:07:38Z

Exact metadata: [source record](sources/issue-5356334016-a686af71875ff7cd75f7e199093a5caaf00043137bee18bc19bf9ac0b261e469.json).

**Status: The aimed-crow selection repair is installed.** The old claim that crows could not be resolved was incorrect.

- [ ] In Story Mode, aim a weapon at a crow near a corpse without shooting. Confirm the lower-right animal information/Study interaction appears for the crow rather than a nearby target. Avoid binoculars while #357 is unresolved.
- [ ] If it still fails, press F10 once while aimed with the already-prepared compendium probe enabled. Report the result and attach the probe output and GameplayTweaks.log.

## comment 5550167249 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/298#issuecomment-5550167249

Created: 2026-08-24T10:11:03Z; updated: 2026-08-24T10:11:03Z

Exact metadata: [source record](sources/comment-5550167249-2c7280c4ca4fb03d233431f1fddb221942269bde0f38c81cd1dc763b38d63a07.json).

**The crow was never unresolvable. It was resolved and then thrown away by a proximity heuristic.**

The issue's own evidence pinned it:

```
aimed=1 aimedModel=0x05df8f2c   (A_C_CROW_01)   <- the reticle DOES resolve it
bestPed=0                                        <- recon rejected it anyway
pedNearestScreen 0.196-0.387  against radius=0.050
```

The aimed entity is passed through the same screen-radius test as any other candidate. A crow is small, and its anchor projects a fifth to a third of the screen away from the reticle even while the engine reports the player is aiming directly at it, so `screenDistance > g_reconAimRadius` discarded the one candidate the player had explicitly chosen. That is also why no info box appeared: the box follows the accepted ped, so rejecting the bird removed both the study path and the box together.

The open question on this issue - whether the crow carries a valid animal type, or even appears in the ped pool - never needed answering. It is in the pool, it resolves, and `GET_ENTITY_PLAYER_IS_FREE_AIMING_AT` names it.

**Two changes, both narrow:**

1. An engine-confirmed aimed ped is no longer rejected by the screen radius. Distance, projected extent and clear line-of-sight all still apply - only the proximity heuristic is bypassed, and only for a ped the engine says is being aimed at.
2. An aimed ped now WINS selection rather than merely competing. Without this a crow at 0.20 from centre still loses to any ped nearer the reticle, and the player's explicit choice is overruled by the same heuristic wearing a different hat.

**#162 is preserved deliberately.** That round replaced a forced `0.0f` screen distance - which skipped projection entirely and made every radius test meaningless - with a real measurement. The measurement stays: `pedNearestScreen` and the reject counters remain truthful, and the ordering for non-aimed candidates is untouched. Only the rejection is skipped. The contract now asserts both halves, and bans the return of the forced `0.0f`.

Contract added to `verify_recon_aim_tolerance_issue_162.py`, mutation-tested three ways: removing the bypass, letting an aimed ped merely compete, and dropping the `aimed` flag at the call site all fail.

Installed `B0A45F7E4F2F44D99FAAD6A97D9FD37A51504014543584108F2C28DA26A5BC4C`, hash verified. All 14 recon contracts pass.

What to check: aim at a crow around a corpse. It should get the lower-right info box and be studyable like any other animal. If it still does not, `pedRadiusRejected` will no longer be the reason and the next question is whether it carries an animal type at all - which the `[CompendiumGlintProbe]` F10 capture already set up on this issue can answer.

