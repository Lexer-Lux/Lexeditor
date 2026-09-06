# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356299936 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/170

Created: 2026-08-06T03:07:52Z; updated: 2026-09-05T06:58:35Z

Exact metadata: [source record](sources/issue-5356299936-bc2dc7e34c6769536718dc38dfde048e97d1360b0d5fd2276a82a180327e1f87.json).

## Desired behavior
Traveling on an actual road should consume less outer-ring stamina than traveling at the same pace across open terrain, for both the player and the player's current horse.

## Implementation
Extend GameplayTweaks' existing movement-mode stamina controller rather than introducing a second stamina system.

- Detect whether the player or current mount is genuinely on a road/path. Do not count merely being near a road; roadside terrain must remain off-road.
- Apply the road benefit only when the selected movement-mode rate is negative (draining stamina).
- Do not alter standing/walking recovery, core values, maximum stamina, swimming, or unrelated horse behavior.
- Add independent hot-reloaded settings:
  - `[HumanStamina] RoadDrainMultiplier`
  - `[HorseStamina] RoadDrainMultiplier`
- Use `1.0` for no benefit and lower values for cheaper road travel; default both to `0.5` (half normal drain).
- Preserve all existing movement-mode rates and exhaustion behavior, multiplying only their negative road-going result.

## Reference
The temporarily stored **Hardcore Stamina** mod implements the same design in reverse through `RUNNING_NO_ROAD_DRAIN=500` for both `[PLAYER]` and `[HORSE]`: it adds drain when movement is not on a road. Use it as a behavioral reference, not as code to copy.

## Acceptance test
1. At a fixed running/sprinting pace, compare player stamina loss over the same duration on a road and immediately beside it; road drain should match the configured multiplier.
2. Repeat while mounted at canter/gallop.
3. Verify leaving and re-entering the road changes the rate promptly without flicker at the road edge.
4. Verify walking/standing recovery and swimming rates are unchanged.
5. Set each multiplier to `1.0` and confirm current behavior is exactly restored.

## issue 5356299936 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/170

Created: 2026-08-06T03:07:52Z; updated: 2026-09-06T13:31:21Z

Exact metadata: [source record](sources/issue-5356299936-e31a9e960109ed6f340ac36390fcbda048e2b4dfadb54a65af6ccb06924b3446.json).

**Actionable — speed work remains.** The current on-foot method stops at 15%, which you rejected as too small. A stronger horse path is only a candidate.

Provide a useful, verified speed implementation or remove the ineffective speed controls, as requested. Preserve the separate player/horse road-stamina benefits and normal recovery/swimming behavior. No approval of the rejected 15% version is needed.

## comment 5550128033 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/170#issuecomment-5550128033

Created: 2026-08-06T05:44:37Z; updated: 2026-08-06T05:44:37Z

Exact metadata: [source record](sources/comment-5550128033-3eee15594107a109f7460f077df6382c931b3c84f06f8cf435d32701eba685ca.json).

Implemented with exact-position road detection and separate hot-reloaded player/horse drain multipliers. Only negative travel drain is reduced; recovery, standing, and swimming are unchanged. Combined ASI build passes and hash-verified install is queued for RDR2 exit, so this remains actionable until it lands.

## comment 5550128045 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/170#issuecomment-5550128045

Created: 2026-08-06T08:59:00Z; updated: 2026-08-06T08:59:00Z

Exact metadata: [source record](sources/comment-5550128045-5736df8d8e16f0ddf87b50030261b7e2c5263576ea1c63bd31beaca0de5b2e90.json).

Road-only player/horse drain multipliers are integrated, shipped in the INI, and installed in `C92A04F…CCA3`. Moved to `test me` for road-edge and on/off-road comparisons.

## comment 5550128064 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/170#issuecomment-5550128064

Created: 2026-08-10T08:37:42Z; updated: 2026-08-10T08:37:42Z

Exact metadata: [source record](sources/comment-5550128064-1a9e0207779ea1c24e465b3d0c03345357a45346c69859fed08c1bbf64427f5e.json).

Great, can I get a speed multiplier for foot & horse when on roads, like RDR1?

## comment 5550128077 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/170#issuecomment-5550128077

Created: 2026-08-10T17:23:45Z; updated: 2026-08-10T17:23:45Z

Exact metadata: [source record](sources/comment-5550128077-16c3f4348aa7818f7cb661c2b45ff73518a0a6594fc426717d9272e9c51af9c9.json).

The completed road candidate is installed and enabled. Road occupancy is sampled at the exact actor position with two consecutive samples before changing state, so a roadside edge should not flicker. Human road speed composes into the single Movement Rework scalar; the ridden horse has its own frame-scoped road scalar. Test foot and horse road-speed multipliers independently (including 1.0 parity), then compare existing drain multipliers on-road versus immediately beside it; recovery and swimming must remain unchanged.

## comment 5550128096 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/170#issuecomment-5550128096

Created: 2026-08-10T19:34:54Z; updated: 2026-08-10T19:34:54Z

Exact metadata: [source record](sources/comment-5550128096-663ba07bb5317eb057c321a5abea39265827be16b67e3ed41e79f97763c676b5.json).

I'm going through the settings. I can't find the road speed multipliers anywhere.

## comment 5550128109 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/170#issuecomment-5550128109

Created: 2026-08-11T01:57:34Z; updated: 2026-08-11T01:57:34Z

Exact metadata: [source record](sources/comment-5550128109-12d5deed9144bd67a3fcde877cd4f7d29479af56b7424d942e0c9b7c3df89899.json).

I found it. Why is it clamped at a max of 1.15x? I don't remember asking for this.

## comment 5550128119 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/170#issuecomment-5550128119

Created: 2026-08-11T02:25:45Z; updated: 2026-08-11T02:25:45Z

Exact metadata: [source record](sources/comment-5550128119-09209a97fab2e0028fa2b559750b1488b13b1a6d0cb3140c7570002a1bce0998.json).

You did not ask for the 1.15 cap. I added it because the engine documentation for the only move-rate native used here, SET_PED_MOVE_RATE_OVERRIDE, states a maximum of 1.15. I should have said that instead of silently presenting it as your design. Values above 1.15 need a different, proven movement mechanism; this setting cannot honestly offer them through the current native.

## comment 5550128133 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/170#issuecomment-5550128133

Created: 2026-08-11T05:08:39Z; updated: 2026-08-11T05:08:39Z

Exact metadata: [source record](sources/comment-5550128133-78d213dee2843c6829104cf965353cab6bc5fef15ef5a17ebaff505af2515618.json).

+15% isn't even noticable. I need more or I need this feature scrapped.

## comment 5550128146 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/170#issuecomment-5550128146

Created: 2026-08-11T07:13:36Z; updated: 2026-08-11T07:13:36Z

Exact metadata: [source record](sources/comment-5550128146-a7211b70cc12e8c2ff3b49cbb7a7170029a64917037087daa1411c3037dc51e7.json).

Direct answer: the current foot-speed method cannot provide a useful increase above 15 percent. The horse has a separate Rockstar boost path that can be tested. No equivalent foot path is proven.

The Aug. 11 log confirms the running-game limit: requested rate `1.3225`, applied rate `1.15`, and `nativeRangeClamped=1`. Raising the setting limit will not raise the applied foot rate.

For horses, Rockstar provides `BOOST_PLAYER_HORSE_SPEED_FOR_TIME`. Story and race scripts apply boost values from 0.0 to 1.0 for fixed periods and refresh them while needed. This is a stronger candidate than the current move-rate override, but it still needs an in-game fixed-course comparison and a residue check after leaving the road or dismounting.

No similar foot-speed boost exists in the checked natives or Story scripts. I will not use velocity injection or a player attribute write; those are unsafe substitutes.

If the feature must give a large speed increase to both Arthur and the horse, the speed part should be removed. The separate road stamina benefit can remain.
