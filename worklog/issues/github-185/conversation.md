# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356303079 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/185

Created: 2026-08-06T03:56:49Z; updated: 2026-09-05T06:59:20Z

Exact metadata: [source record](sources/issue-5356303079-2d9c13b601b7bc65f77d8388fbbe97beb89beaa9c297269b35a0008b6c0d2db7.json).

## Player-facing behavior

When the player is at a water pump, expose two hold interactions:

- **Hold E — Drink:** use the pump directly and restore the same amount of Stamina Core as one canteen drink.
- **Hold R — Refill canteen:** refill the reusable canteen from issue Lexer-Lux/Lexeditor#184 without directly restoring the core.

Use Rockstar's dedicated pump scenario/animation rather than approximating the motion.

## Confirmed game assets

- Scenario: `WORLD_PLAYER_CHORES_PUMP_WATER`
- Player variant: `PROP_HUMAN_PUMP_WATER_PLAYER`
- Animation set: `amb_work@prop_human_pump_water@male_a`
- Pump prop: `p_waterpump01x`
- Pump-drinking VFX event: `ENT_ANIM_PED_WATER_DRINK_PUMP`
- Rockstar also ships bucket-filling scenario variants.

These names are starting evidence, not runtime acceptance.

## Requirements

- Detect an eligible nearby water pump and present both prompts without interfering with unrelated scenario prompts.
- Hold E performs the complete pump/drink interaction.
- Direct pump drinking restores exactly the same configured Stamina Core amount as one use of the canteen from Lexer-Lux/Lexeditor#184.
- Hold R performs the refill interaction and fills the canteen to its defined capacity.
- Refilling does not itself restore Stamina Core.
- Handle a full canteen clearly and do not replay a meaningless refill.
- Both interactions must align the player and animate the pump correctly; a ped-only animation with a static handle is not acceptable.
- Cancel or safely break out if combat, ragdoll, mission state, obstruction, or another interruption makes the interaction invalid.

## Acceptance test

1. Approach a pump and confirm both hold prompts appear with the correct keys and labels.
2. Hold E and verify player alignment, pumping, moving handle, drinking presentation, and configured Stamina Core restoration.
3. Partially empty the canteen, hold R, and verify it returns to full without restoring Stamina Core.
4. Confirm R does nothing inappropriate when the canteen is already full.
5. Interrupt both actions and verify Arthur exits cleanly without freezing, teleporting, or leaving the pump in a broken pose.
6. Verify ordinary nearby prompts and scenarios still work.

## issue 5356303079 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/185

Created: 2026-08-06T03:56:49Z; updated: 2026-09-06T12:55:15Z

Exact metadata: [source record](sources/issue-5356303079-4856707703fb58e8fb67eee2b35f6331e3cb0dddcfc96b3ae102759777b3ed5e.json).

Water pumps should offer Hold E to drink and Hold R to refill the canteen, with properly moving pump/player animations. Drinking restores the configured core amount; refilling does not.

**Status: Incomplete.** Unvisited-pump coverage and missing scenario evidence still need preparation. The latest icon was rejected: redesign it around the recognizable pump head/handle in the established map style before asking for approval.

## comment 5550131633 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/185#issuecomment-5550131633

Created: 2026-08-06T07:11:10Z; updated: 2026-08-06T07:11:10Z

Exact metadata: [source record](sources/comment-5550131633-e83dfc65c5d72e5e8e269f6e4c0cb5a71a0fa0fcc4ac8f71649626314d512173.json).

Implementation update: integrated Hold E Drink and Hold R Refill at p_waterpump01x using Rockstar's exact authored PROP_HUMAN_PUMP_WATER point and WORLD_PLAYER_CHORES_PUMP_WATER variants. The real pump is associated with the scenario; rewards are gated on Rockstar drink/bucket-fill animation events, never a timer, and interruptions grant nothing. It uses Lexer-Lux/Lexeditor#184's narrow canteen API and updates CoreClock exactly. Static pump evidence checker and combined release build pass. Keeping actionable until verified install and in-game scenario/event testing.

## comment 5550131644 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/185#issuecomment-5550131644

Created: 2026-08-06T13:07:34Z; updated: 2026-08-06T13:07:34Z

Exact metadata: [source record](sources/comment-5550131644-6f0c0235b0e7dac71fbf94568f09ee7cb228866ef141a1959a213d673ed0b2e7.json).

create a map icon for them. then put them on the map.

## comment 5550131654 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/185#issuecomment-5550131654

Created: 2026-08-06T14:42:22Z; updated: 2026-08-06T14:42:22Z

Exact metadata: [source record](sources/comment-5550131654-3d771ec3275d75f8914fb4ec26f308541baebcd8f0ed400d32845e1fbcab406c.json).

Installed in development build `9703EA026B90F542FC82F63CAFD897C135265DBDE1F5DC7B1AB85F6D743A4103`. Test nearby and streamed water pumps: drink, refill the reusable canteen, and confirm the custom pump marker appears/disappears correctly.

## comment 5550131661 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/185#issuecomment-5550131661

Created: 2026-08-13T12:44:36Z; updated: 2026-08-13T12:44:36Z

Exact metadata: [source record](sources/comment-5550131661-2c7c49073ff25f9eb75639aa9f999fba89607fda2a0fce8361d807673b8e0ca5.json).

yeah i don't see any map icons for the pumps. im at the valentine one rn and there's nothing.

## comment 5550131670 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/185#issuecomment-5550131670

Created: 2026-08-13T13:43:31Z; updated: 2026-08-13T13:43:31Z

Exact metadata: [source record](sources/comment-5550131670-480593602b7810049711f00fb935c9efc8919275d2970a66c1ceeed19a292d4e.json).

Found the map failure: the scanner called a single-result scenario native as if it filled an 8,192-item array, so it could corrupt its own state before creating a marker. I removed that call. The replacement records the exact position of each streamed p_waterpump01x and logs discovery, blip creation, failure, and idle heartbeat separately. The command-line extractor reaches the level archive but cannot decode its encrypted split YMAP entries, so remote unvisited-pump coverage is still not proved and the issue remains actionable.

## comment 5550131684 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/185#issuecomment-5550131684

Created: 2026-08-14T22:39:38Z; updated: 2026-08-14T22:39:38Z

Exact metadata: [source record](sources/comment-5550131684-80695c55b2dfc94e7476d555cde5fedab8be75562cb193cee3c0a129c2f4ed91.json).

**Still blocked, and the blocker is a manual extraction step rather than code.**

The pump map cannot be completed from here. The command-line extractor reaches the level archive but cannot decode its encrypted split YMAP entries, so remote unvisited-pump coverage stays unproven. That is the same encrypted-archive wall recorded in `codex/archive-extraction.md`: every Rpf8Extract build and both texture toolkits fail on it, leaving OpenIV with the game closed as the only route.

Separately, this issue's own contract cannot run at all right now. `verify_water_pumps_issue_89.py` exits on a missing input — `_downloads/extract/update_1_common/common/data/ai/scenarios/mech.meta` — so the scenario evidence it checks is unverified. It used to die in a raw traceback; it now states plainly which file it needs and that the contract is unenforced without it.

Moving to `needs a human` because it needs you to run OpenIV with the game closed and extract that data. Once `mech.meta` and the level YMAP entries exist on disk, the scanner work can be finished and checked properly.


## comment 5550131696 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/185#issuecomment-5550131696

Created: 2026-08-15T02:04:46Z; updated: 2026-08-15T02:04:46Z

Exact metadata: [source record](sources/comment-5550131696-7b7b0556386ea055eafb9eced7278b880d9278267e76bb46c0bb52fee85629a8.json).

Okay now there's an icon...a weird one. Instead of showing the wholeass pump, just show the top with the head and pump part so it's recognizable. The bottom 75% or so is just noise.
ALso...it doesn't follow the format or style of vanilla rdr2 map icons....even though all the other ones you gave me do. I guess you'd need to get gpt to make a new one for you?
