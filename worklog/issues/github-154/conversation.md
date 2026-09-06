# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356296624 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/154

Created: 2026-08-06T02:38:29Z; updated: 2026-09-05T06:57:48Z

Exact metadata: [source record](sources/issue-5356296624-4410f672a9be9862bfb33fd9a40b09a32559674f94f1dcdd8c98269fd1eb6900.json).

81.  BOUNTY-HUNTER SYSTEM EDITOR — expose spawn rate, group size, animal/allied
     support, equipment, tactics and escalation so bounty hunters become a
     deliberate challenge instead of a recurring annoyance.

Doable? Where is this info storeD?

## issue 5356296624 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/154

Created: 2026-08-06T02:38:29Z; updated: 2026-09-06T12:54:21Z

Exact metadata: [source record](sources/issue-5356296624-a9441054b545c1b1ecbcbf39de850a70983d858c1a223a5a9eb4bdedaaf53ed7.json).

**Status: The editor exists, but its explanations are still incomplete.** The latest request is for help beside each wanted tier explaining what that particular tier means, not another generic definition of wanted level.

Establish those meanings and add the missing explanations before asking you to choose spawn-delay values.

## issue 5356296624 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/154

Created: 2026-08-06T02:38:29Z; updated: 2026-09-06T13:55:40Z

Exact metadata: [source record](sources/issue-5356296624-aed93de8e5d0a45f30372da5067500a31f70d2e4f509a30ef2aaed6a59d204fa.json).

**Status: The editor exists, but its explanations are still incomplete.** The latest request is for help beside each wanted tier explaining what that particular tier means, not another generic definition of wanted level.

Establish those meanings and add the missing explanations before asking you to choose spawn-delay values.

## issue 5356296624 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/154

Created: 2026-08-06T02:38:29Z; updated: 2026-09-06T18:24:01Z

Exact metadata: [source record](sources/issue-5356296624-16c2a1dc2e8259983a6e0a160e2e95b31b196a536aab3611af760282e569400f.json).

**Status: The editor exists, but its explanations are still incomplete.** The latest request is for help beside each wanted tier explaining what that particular tier means, not another generic definition of wanted level.

Establish those meanings and add the missing explanations before asking you to choose spawn-delay values.

## issue 5356296624 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/154

Created: 2026-08-06T02:38:29Z; updated: 2026-09-06T18:24:01Z

Exact metadata: [source record](sources/issue-5356296624-36ed52afc2c1673206b7a12f68add524b915f9ff89501f8284fa9856b1317871.json).

The Bounty Hunters editor already contains the requested per-tier explanations in current `master`; this issue's old actionable status was stale.

Each cooldown row renders its own `?` beside the tier and uses the backend/fallback definitions:
- **Clean:** active wanted/search score 0; regional bounty debt can still exist.
- **Wanted 1:** internal wanted score 1–4,999.
- **Wanted 2:** 5,000–14,999.
- **Wanted 3:** 15,000–24,999.
- **Wanted 3+:** 15,000+; special target-undetected cooldown row.
- **Wanted 4+:** 25,000+ and includes level 5, which begins at 100,000.

These are pursuit/search severity tiers, **not bounty-dollar ranges**. The table also explains that Min/Max are randomized delays in in-game hours and that Clean does not mean $0 bounty.

**Status: Needs Testing.** Refresh the current editor and open Crime & Law → Bounty Hunters. Confirm each Wanted tier cell has its own `?` and that the help text above is visible/readable at both wide and narrow widths. No spawn-delay values were changed by this status correction.

## comment 5550124290 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/154#issuecomment-5550124290

Created: 2026-08-06T03:57:56Z; updated: 2026-08-06T03:57:56Z

Exact metadata: [source record](sources/comment-5550124290-b4fd655e63b18c4962b124b8c7f9bee0f0f3b6df762eebf4521d3918b31fd526.json).

Research result: yes—most requested controls are data-driven. `wilderness/bountyhunters.meta` defines the free-roam response, cooldown, minimum bounty, town distance, five escalation phases, group scaling, shotgun/sniper groups, and higher-tier police-dog support. Common dispatch data exposes spawn delays, group/preset weights, ped counts, transitions, and combat overrides; combat/loadout data supplies equipment and tactics. Build a curated Bounty Hunters editor for frequency, threshold, size, dogs, weapons, accuracy/aggression, and escalation—not a raw dispatch graph. Remaining probes: field units, runtime ownership of the global cooldown, and hot-load versus restart.

## comment 5550124310 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/154#issuecomment-5550124310

Created: 2026-08-06T05:32:46Z; updated: 2026-08-06T05:32:46Z

Exact metadata: [source record](sources/comment-5550124310-ef6d2a2578a1229bac4ed6b125a9ba0d37616aca5d133859f9c711f4bcef7a00.json).

yeah ok make that a subtab under crime and law called bounty hunters.

## comment 5550124328 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/154#issuecomment-5550124328

Created: 2026-08-06T08:09:05Z; updated: 2026-08-06T08:09:05Z

Exact metadata: [source record](sources/comment-5550124328-ae153b32eac9f4dd905a86eaf00870935818843baf16d9e73e7449b604b0fbb2.json).

The safe editor implementation is live in LEXEDITOR and the current update-layer `bountyhunters.meta` is registered in MyOverhaul. Editable controls cover thresholds, response weight, spawn distances, cooldowns, group sizes, shotgun/sniper weights, and dog chances across all five tiers. Shared ordinary-law equipment/combat/chase specs are shown read-only to avoid silently retuning all lawmen. Moved to `test me` for editor save/reload and in-game spawn/escalation behavior.

## comment 5550124348 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/154#issuecomment-5550124348

Created: 2026-08-10T08:23:02Z; updated: 2026-08-10T08:23:02Z

Exact metadata: [source record](sources/comment-5550124348-d9f8ae665931f51e2e0a6eb0748baaec83ee3c7bc60547ea1a9d6c2e4336e5ee.json).

<img width="2022" height="140" alt="Image" src="https://github.com/user-attachments/assets/86fb47e9-f030-4399-aee8-bd7dcd48a368" />

There are all these values that don't seem to use the normal markup/code for values. They also desperately need ? explainers, if they can be explained.

<img width="467" height="737" alt="Image" src="https://github.com/user-attachments/assets/d0a78ef2-c898-4d0d-9264-132be02fcd75" />

That seems to be the case for almost everything here. I have no clue what any of this stuff means. Wanted 4?

## comment 5550124366 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/154#issuecomment-5550124366

Created: 2026-08-10T11:02:44Z; updated: 2026-08-10T11:02:44Z

Exact metadata: [source record](sources/comment-5550124366-bc9a799927518ce3c7ad29b1623f18d2a7525dda745b226860a78e565b232183.json).

<img width="341" height="1110" alt="Image" src="https://github.com/user-attachments/assets/b4e3aa66-119e-432a-8999-df2fc7edeeb3" />

all you did was completely break the entire screen.

## comment 5550124383 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/154#issuecomment-5550124383

Created: 2026-08-10T12:09:00Z; updated: 2026-08-10T12:09:00Z

Exact metadata: [source record](sources/comment-5550124383-bcad881ef3aa56460a6fe9678a006e4a0a581ef0e8db3249b42866a02c02a190.json).

<img width="297" height="809" alt="Image" src="https://github.com/user-attachments/assets/834e13a4-fa50-4c21-8fa8-a859d4550e32" />

you literally didnt fix anything

## comment 5550124403 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/154#issuecomment-5550124403

Created: 2026-08-10T12:48:04Z; updated: 2026-08-10T12:48:04Z

Exact metadata: [source record](sources/comment-5550124403-c1dd262238f432c7bee417c14e96c0f2b3075ec58fe9c4828a9968391736b069.json).

The failure was real: the running editor backend was serving an older bounty payload with no labels/help/vanilla references, and the page printed those missing fields as literal 'undefined'. The page now normalizes both old and current payloads before rendering, so it works even with that already-running backend. I also rendered the real page at wide and narrow widths: no undefined text, 25 help controls, 86 vanilla references, and the narrow tables scroll without clipping. Refresh LEXEDITOR and check Bounty Hunters.

## comment 5550124411 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/154#issuecomment-5550124411

Created: 2026-08-10T15:37:25Z; updated: 2026-08-10T15:37:25Z

Exact metadata: [source record](sources/comment-5550124411-bb68a9a6d986415f19a67f578887e718a1381fd2555f54b8b7c982c69e85a530.json).

<img width="2377" height="397" alt="Image" src="https://github.com/user-attachments/assets/f79d3180-8d9e-4c64-bdd7-aed97cf3afd7" />

Still not very helpful. "Clean"? That implies no bounty. But then....how is there a field for the time bounty hunters take to come for me when I have NO bounty? And these wanted levels. Huh??? What does that mean? Is it based on my bounty? Nowhere is it explained.

## comment 5550124422 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/154#issuecomment-5550124422

Created: 2026-08-10T17:00:49Z; updated: 2026-08-10T17:00:49Z

Exact metadata: [source record](sources/comment-5550124422-c42a6aa046039eea99eabf19767dbc9a1d3d24f25a3223036e387dcbfbefbc3d.json).

The Bounty Hunters page now explains the actual meaning of every tier: Wanted tier is the current wanted/search state, not bounty dollars; Clean means no active wanted/search level, not zero regional bounty; min/max are the randomized in-game-hour delay bounds. Refresh LEXEDITOR and check the labels, help text, vanilla references, and narrow table scrolling.

## comment 5550124442 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/154#issuecomment-5550124442

Created: 2026-08-11T02:21:41Z; updated: 2026-08-11T02:21:41Z

Exact metadata: [source record](sources/comment-5550124442-0c92024ae2057dbe5fe7abcd2f767097f008cb243acb7b43c6b195a28c0caee1.json).

<img width="146" height="678" alt="Image" src="https://github.com/user-attachments/assets/5b3e9b34-1d1c-4ffd-8464-679e65235833" />

Why not put the ? next to each wanted tier as well to explain what that tier, specifically, means? Do you even know? Because while this is better...it doesn't actually explain what each tier MEANS
How do I know what values to put in here when I don't even know what they do?
