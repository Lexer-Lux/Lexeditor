# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356303595 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/187

Created: 2026-08-06T04:04:50Z; updated: 2026-09-05T06:59:27Z

Exact metadata: [source record](sources/issue-5356303595-a2bbe7647aa10728dffe65599825701056fa79d19b09a5bfd0e1c0f291b28cfe.json).

## Player-facing behavior

When the player's horse is left idle near an appropriate food or water source, it should naturally satisfy its own needs:

- Drink autonomously near horse troughs and, if technically reliable, suitable natural water.
- Eat autonomously when left near hay or another clearly valid horse-feed source.

Find the existing mod that provides similar behavior and use it as a behavioral and technical reference. Respect its permissions and do not copy protected code or assets.

## Research first

- Identify the reference mod and document exactly what triggers its eating and drinking behavior.
- Determine which Rockstar horse scenarios/animations, trough props, hay props, and natural-water checks are available in Story Mode.
- Establish whether natural water can be validated safely: reachable shore, adequate depth, no dangerous current or drop, and a valid drinking animation position.
- Determine how autonomous feeding/drinking should affect the horse's cores and whether it should integrate with the overhaul's thirst interpretation rather than inventing a separate hidden meter.

## Requirements

- Apply only to the player's owned/current horse, not arbitrary nearby horses.
- Trigger only while the horse has been left idle long enough to make the behavior feel intentional.
- Require an actual need: do not repeatedly eat or drink with full relevant cores.
- Use appropriate authored horse animations and align the horse correctly with the trough, water edge, or hay.
- Restore the corresponding horse core gradually or on completion; do not refill merely because the animation started.
- Prevent rapid retriggering with sensible cooldowns.
- Do not trigger while mounted, hitched, fleeing, injured, in combat, following closely, in a mission-sensitive state, or otherwise busy.
- Allow player recall/mounting or danger to interrupt the behavior cleanly.
- Do not consume decorative hay or require the world prop to disappear unless that is genuinely appropriate.
- Prefer troughs as the reliable drinking baseline; natural-water drinking may be separated or deferred if safe positioning cannot be proven.

## Acceptance test

1. Leave the owned horse near a valid trough with a depleted relevant core and confirm it approaches or aligns, drinks, and receives restoration.
2. Repeat near valid hay and confirm autonomous eating and restoration.
3. Confirm neither behavior loops while cores are full.
4. Verify clean interruption by whistling, mounting, combat, or nearby danger.
5. Verify no broken poses, clipping, drowning, falls, or navigation traps at several source locations.
6. Confirm unrelated NPC and wild horses are unaffected.
7. If natural water is supported, test multiple shorelines and reject unsafe or unreachable drinking positions.

## issue 5356303595 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/187

Created: 2026-08-06T04:04:50Z; updated: 2026-09-06T12:55:19Z

Exact metadata: [source record](sources/issue-5356303595-8fd870abe4d643fe9ec45d2893b562f6defa665772db9d3346e35d63950c6f9c.json).

An idle owned horse should approach safe food/water when needed, restore its cores and stop cleanly for player input or danger.

**Status: Latest approach and water-marker repairs are source-only.** The previous session found a valid source but issued no approach. Build and install the corrections before another horse test; the flashing-marker repair is also undelivered.

## issue 5356303595 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/187

Created: 2026-08-06T04:04:50Z; updated: 2026-09-06T13:55:17Z

Exact metadata: [source record](sources/issue-5356303595-89152eb71ea4c2403a99b032a1c6110622fba96cecd0cd905e0f83f49bd01011.json).

An idle owned horse should approach safe food/water when needed, restore its cores and stop cleanly for player input or danger.

**Status: Latest approach and water-marker repairs are source-only.** The previous session found a valid source but issued no approach. Build and install the corrections before another horse test; the flashing-marker repair is also undelivered.

## comment 5550132173 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/187#issuecomment-5550132173

Created: 2026-08-06T06:41:51Z; updated: 2026-08-06T06:41:51Z

Exact metadata: [source record](sources/comment-5550132173-4e330c8050ac47c6f86ccecc69dade4d6720e9e3b97179dd1f365f6413927208.json).

Implementation update: the owned-horse autonomous needs module is integrated and the combined release build passes. It currently supports authored trough drinking and validated dry hay grazing, with gradual core restoration, cooldowns, and interruption/safety gates. Natural shoreline drinking remains deliberately unimplemented because a safe placement/animation path is not yet proven. The build and its horse_need_sources.csv are queued for hash-verified installation when RDR2 closes, so this correctly remains actionable.

## comment 5550132191 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/187#issuecomment-5550132191

Created: 2026-08-06T07:26:25Z; updated: 2026-08-06T07:26:25Z

Exact metadata: [source record](sources/comment-5550132191-f0f840359b3f35471b6388b04fa4f0e2e589a33bf4dbb48afb580c74925ea147.json).

Hardened the authored trough/hay baseline: actions now yield when the player approaches, reject falling/swimming horses, require visible stationary unattached source props, and navmesh-validate loose-hay positions. Generic hay bales were removed because Rockstar also uses those models in stacks and vehicles. Natural shoreline behavior remains excluded because the available Story Mode script only uses authored event coordinates and provides no safe general bank/depth/current solver. The release build is queued to install after RDR2 exits; the issue remains actionable until that installation completes.

Queued ASI SHA-256: `A32E040DF8BC2A07FB7F9964476C3B249B81B77BAF45DFC93527CD656E7840C0`

## comment 5550132211 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/187#issuecomment-5550132211

Created: 2026-08-06T07:41:30Z; updated: 2026-08-06T07:41:30Z

Exact metadata: [source record](sources/comment-5550132211-f7a8ecae8c995bbc0d4b2943fb851bc14102b896aa95f2a7771e8a27d094ea1b.json).

Installed and hash-verified. The safe authored trough/loose-hay implementation is ready for the acceptance tests in the issue; natural shoreline behavior was deliberately excluded because no safe general solver exists in Story Mode evidence.

Installed ASI SHA-256: `7DB7F0B5466F772C5564CF083F270D1F1E24F48D6CA4CCBF2657A58318FB8BC0`

## comment 5550132231 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/187#issuecomment-5550132231

Created: 2026-08-10T07:12:04Z; updated: 2026-08-10T07:12:04Z

Exact metadata: [source record](sources/comment-5550132231-188f7dff47543acb4e75186a918ca1f237ed9b9645b0cc5a9a8eee80ab5d2ed5.json).

Okay. My horse's stamina core is at 1/2. I left it at a water trough. How do I make it drink?

## comment 5550132241 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/187#issuecomment-5550132241

Created: 2026-08-10T07:24:09Z; updated: 2026-08-10T07:24:09Z

Exact metadata: [source record](sources/comment-5550132241-ac0b611bf37e2c7d64eb94db380e1636a0c2a71223d72ad99b4e355d4b8aeb9c.json).

The trough behavior is automatic; there is no activation key. To test the currently installed build: (1) use the owned/current horse with stamina core below 75%; (2) dismount and make sure it is not hitched, attached, fleeing, injured, in combat, or otherwise busy; (3) leave it beside an actual horse trough; (4) walk 6-80 m away; and (5) leave the horse still for 15 seconds. It should take the authored trough-drinking scenario and restore the stamina core gradually. Approaching, whistling, mounting, danger, or another busy state interrupts it. The hay path has the same automatic idle/need behavior near the validated loose-hay sources. This implementation is already present in the hash-verified installed combined ASI (AC952387AA9932EFD4AA43C580D4369F0534537A01B0196A529BBC88519551D9), so this needs in-game confirmation rather than more implementation.

## comment 5550132254 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/187#issuecomment-5550132254

Created: 2026-08-10T08:58:38Z; updated: 2026-08-10T08:58:38Z

Exact metadata: [source record](sources/comment-5550132254-e7bbef03e22454d03376a2c2613e0cda11e793d96ba99e641f59f1340fbfd48f.json).

Okay, well, I tried changing its settings to make it activate and it still did nothing.

I want a "horse drink" map icon for drinkable items for the horse -- like rain barrels and troughs. It can't just be a water droplet or something -- it has to reflect it's drinkable for HORSES. An icon indicative of water alone will make players think they can drink from it. I want this icon to show up on the minimap for nearby (~100m) drinkables when the player is leading their horse around.

## comment 5550132268 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/187#issuecomment-5550132268

Created: 2026-08-10T09:43:13Z; updated: 2026-08-10T09:43:13Z

Exact metadata: [source record](sources/comment-5550132268-512928e784e16d976263367ac339c3cf81e527dd9ce0f154bf28972146f08a6d.json).

Returned runtime test (2026-08-10): even after changing the horse-drinking settings to make triggering much easier, autonomous drinking still did not visibly activate. The horse repeatedly lowered its head and sometimes pawed/digged at the ground, but it is unclear whether that is this feature or vanilla idle behavior. Treat this as failed/unproven, not accepted.

Required addition: a horse-specific water-source icon that is clearly water *for a horse*, not a generic human-drinkable water droplet. While the player is leading the owned horse, show these icons on nearby (~100 m) horse-drinkable objects such as troughs and water barrels; clear them immediately when no longer leading. Also document whether the settings hot-reload or require a restart, and ensure the diagnostics distinguish the mod's authored approach/drink scenario from vanilla idle head-lowering/pawing.

## comment 5550132277 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/187#issuecomment-5550132277

Created: 2026-08-10T09:49:57Z; updated: 2026-08-10T09:49:57Z

Exact metadata: [source record](sources/comment-5550132277-898ea0c5cef7d2e183f873ba1ebc902ece823fa2fc7bd115b8beacba6548b214.json).

Source repair update (not yet installed): the failed test used easier 2 s / 99% / 1 m / 5 s values, but the installed module silently clamped them to 5 s / 99% / 2 m / 30 s, rejected ordinary trough props without a separate pre-placed active scenario point, and emitted no diagnostics because all horse-needs logging was gated behind DevelopmentTrace.

The repaired module hot-reloads this section within two seconds, accepts the actual zero/easy test ranges, logs exact effective values, distinguishes `scenario-issued call-only` from authoritative `mod-scenario-confirmed`, and creates/binds an owned temporary trough scenario when no valid pre-placed point exists. The lead-only 100 m `LEX_BLIP_HORSE_DRINK` path now covers configured troughs plus the water barrel model resolved as water; it clears immediately when the owned horse is no longer being led. The horse-specific icon is packed for the combined release. This remains actionable until that build is installed and hash-verified; visual pose and restoration still require the new runtime test.

## comment 5550132290 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/187#issuecomment-5550132290

Created: 2026-08-10T11:01:51Z; updated: 2026-08-10T11:01:51Z

Exact metadata: [source record](sources/comment-5550132290-14c247281f1d392484132e09e5d49533d3df0a2f7f0c55575b08b3e39c4d53f3.json).

You have a reference mod. Decompile it. Look at the code. You have no excuse for this. None at all.
Also, there are no blips. You know how to make blips. No excuse for that either.

## comment 5550132301 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/187#issuecomment-5550132301

Created: 2026-08-10T19:02:45Z; updated: 2026-08-10T19:02:45Z

Exact metadata: [source record](sources/comment-5550132301-6b46b63b3616843dccc6e93b2f71c43da0edc688b26ca0d0c60f13213c7848f0.json).

No change. This is getting ridiculous.

## comment 5550132318 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/187#issuecomment-5550132318

Created: 2026-08-10T22:17:12Z; updated: 2026-08-10T22:17:12Z

Exact metadata: [source record](sources/comment-5550132318-e0a60865da84b498fad1bf94bfc9eba02ef74e3b82d5fdbb08dcbaa14314b7c8.json).

The failed build never reached either drinking or the map-icon scan: every installed heartbeat reported `gate=no_owned_horse horse=0`. It relied only on `GET_MOUNT_OWNED_BY_PLAYER`, which returned zero for the actual Story saddle horse.

Installed and hash-verified build `70B66FAB3A0082C6638633A2379AF40147AABEF99D8DBC9EFFA1CC9591746F1B` now resolves the horse from, in order: current mount, exact led horse, active horse, saddle horse, then the old owned-mount getter. Its heartbeat prints all five handles and the selected source.

I also removed the guessed runtime scenario-point path. The exact Thirsty Horse 1.6 archive was hash-pinned and disassembled; its real trough sequence is approach -> face source -> Rockstar trough `ENTER`/`BASE` animation. The new build follows that sequence and restores the Stamina Core only after the exact animation reads back live. While leading the selected horse, the 2 Hz icon scan now marks every streamed configured water object within 100 m, not just one nearest object per model.

Please test with the existing easy profile: lead the horse near troughs/barrels and confirm all nearby horse-water icons appear; stop leading and confirm they disappear; then leave the horse idle near a source with its Stamina Core below 99. Pose/alignment remains an in-game acceptance item, especially for barrels.

## comment 5550132330 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/187#issuecomment-5550132330

Created: 2026-08-20T12:53:23Z; updated: 2026-08-20T12:53:23Z

Exact metadata: [source record](sources/comment-5550132330-d4b13e9ad1c6f653b5b64142d98cd5ac9bb418a5fbb7f1a49beddfc1f136a5e2.json).

While the horse was being led, the water blips appeared only in brief flashes, then one appeared once more, and all disappeared permanently. The scan can create a blip, but its ownership or lifetime gate is removing it. Marked actionable.

## comment 5550132345 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/187#issuecomment-5550132345

Created: 2026-08-20T12:58:23Z; updated: 2026-08-20T12:58:23Z

Exact metadata: [source record](sources/comment-5550132345-85508dc9e0ac184dfa1bc963f076497c3ee7af2247b83a2e8fe3b43e3554009f.json).

The live log proved that the owned horse was resolved, both need cores were at 0, and a configured source was found, but no approach task was issued. The trough search checked only the centre of two sides, then an unsupported whole-object line-of-sight gate could reject the result. A later hay fallback also replaced the useful drink failure with a generic message.

The source repair now checks the centre and two bounded positions on both long sides. It keeps the ground, navigation, displacement, and water safety checks. Line of sight is recorded as evidence but does not cancel the reference approach task. If no position works, the log reports the exact rejection counts and preserves the drink failure. This is source-complete but not installed while the game is open.

## comment 5550132362 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/187#issuecomment-5550132362

Created: 2026-08-20T13:44:49Z; updated: 2026-08-20T13:44:49Z

Exact metadata: [source record](sources/comment-5550132362-b903bf799b779a1c670686649ee7f54f0be8fb0d90507e32e933f8ec6c2a5d07.json).

The brief water-icon flashes had two source causes: an unrelated locked state cleared every marker, and one missed 2 Hz object-pool scan deleted a valid marker without checking the stored water object. The repair keeps lock state diagnostic-only and validates the stored object plus blip before removal. It also reads the exact leading state once and shares it across marker and drinking gates. This is source-complete but not built or installed. After installation, lead the owned horse continuously past water for more than ten seconds; the icon must remain stable and disappear immediately when leading stops.
