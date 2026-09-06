# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5347203364 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/87

Created: 2026-09-04T10:53:51Z; updated: 2026-09-04T12:25:17Z

Exact metadata: [source record](sources/issue-5347203364-a142bb189de80fdb0e6b9d232478c2a489f46cabe2571e8d3c86f2e5dd53d38c.json).

Add an optional FF8 tweak that replaces the normal Start or pause-button action, including its keyboard equivalent, with an in-game Journal.

## Menu structure

- Header: Journal.
- The first entry is always Main Quest and states where to go or what to do next.
- Unlocked side quests follow it and show their current objective.
- Locked side quests come last. They show their name and how to begin them.
- The complete Journal feature is toggleable as one per-mod Tweak.

## Updates

Use the game's normal toast presentation:

- Side quest unlocked! — a side quest has become available in the Journal.
- Journal updated — the Main Quest or a side quest advanced to a new stage.
- Side quest completed! — a side quest completed.

Do not repeat a toast merely because a save loaded or the menu reopened.

## Required side quests

- A Dog And Its Bone
- Card Club Master
- Chocobo Forest
- Combat King
- Obel Lake
- Master Fisherman
- Shumi Village
- Tonberry King
- Odin
- Phoenix
- Doomtrain
- Jumbo Cactuar
- Deep Sea Research Center
- I Want To Believe
- Omega Weapon
- Top Level
- Top Rank
- Magazine Addict
- Collector
- Dog Trainer
- Diablos
- Blue Magic Master
- Maximum HP

## State model

- Store Main Quest and side-quest definitions as declarative state machines.
- Resolve stages from proven durable state such as current and previous field IDs, disc, persistent savemap variables and flags, party, inventory, and completed events.
- Main Quest stages change when the player's next destination or required action changes. A cutscene does not need its own stage when the objective remains the same.
- Keep every side quest independent so optional, concurrent, failed, completed, and missable quests do not corrupt one another.
- Scan field JSM for durable variable reads and writes, dialogue references, and MAPJUMP or WORLDMAPJUMP transitions to propose stage conditions.
- Human review still owns quest names, player-facing instructions, branch meaning, and ambiguous conditions.
- Keep definitions in editable mod data so Lexeditor can expose and revise them.
- Implement the in-game menu through the managed FFNx runtime.

## De-linearization compatibility

The Journal must not hard-code one vanilla sequence. The separate De-linearization proposal can change world access, quest availability, and valid stage order. Quest conditions and unlock rules must be overrideable data and must compose with that tweak.

## Acceptance direction

- Start and its keyboard equivalent open Journal while the tweak is enabled.
- Disabling the tweak restores the original Start or pause behavior.
- New Game and representative saves from every disc select the correct Main Quest objective.
- Every named side quest has explicit locked, unlocked, staged, completed, failed, and missable handling where applicable.
- Locked entries give a valid method of starting the quest.
- Toasts fire once per real transition.
- Field, world-map, battle, scripted transitions, save/load, and De-linearization do not produce impossible objectives.
- Every stage has a fixture or equivalent repeatable validation state.
- No implementation begins until Lexer triages this issue.

## issue 5347203364 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/87

Created: 2026-09-04T10:53:51Z; updated: 2026-09-06T12:45:56Z

Exact metadata: [source record](sources/issue-5347203364-f773dcade595d2ee5f7317fea5a0ad9c936fe4445ff9790732dd526abb851dea.json).

Start should open an optional Journal: Main Quest first, active side quests next, locked quests last with start instructions. Cover the requested side quests and show one-time unlock/update/completion notices.

**Not implemented.** Map reliable quest state and preserve editable progression rules, including compatibility with #88. The detailed request already supplies the direction; research and implementation are agent work.
