# GitHub #172 - Remove First Person Rolling Option

## 2026-08-10 recurrence audit before implementation

- The live request was unambiguous: rolling in first person looked wrong and
  had to stay disabled. This was not a request for a configurable option.
- Primary evidence was the hash-pinned `CombatRoll.asi` camera predicate at
  `0xD1BA66940E94C547` and the active #6 roll state machine. The current source
  made that predicate conditional on `g_combatRollFirstPerson`, so a stale
  setting could still enable the rejected view.
- The recurring scope risk was to claim the option was removed after changing
  only the default. The issue-owned movement code had to reject the reference
  first-person predicate unconditionally and contain no reference to the
  option. Shared INI, settings schema, and dispatcher cleanup remained with the
  integration owner and could not be claimed by this change.
- The sanctioned path was the existing reference camera predicate. No guessed
  camera mode, frame-by-frame camera mutation, or input suppression was added.
- Static proof had to show an unconditional predicate gate in the #6 section
  and no `g_combatRollFirstPerson` dependency there. Player-visible acceptance
  remained that first-person view cannot start a replacement roll and third
  person remains unchanged.

## 2026-08-10 issue-owned implementation

The #6 movement section now calls the hash-pinned reference camera predicate as
an unconditional rejection gate. It no longer reads
`g_combatRollFirstPerson`, so no stale value can enable the rejected behavior.

`verify_dodge_roll_issue_172.py` hash-verified the reference ASI and passed the
unconditional-gate and no-option checks. The full adjacent roll, climbing,
prone, and #144 verifier set also passed.

The shared `AllowFirstPerson` declaration, INI key, settings schema entry, and
reader still require removal by the integration owner. This issue-owned change
did not edit those shared files and therefore did not claim that the visible
option was removed yet. No build or install was performed. Runtime acceptance
remains that first person cannot start the replacement and third person still
can.

## Integration cleanup

The integration owner removed `AllowFirstPerson` from the shared declaration,
reader, main INI, LEXEDITOR schema, and generated in-game settings menu. The
stale `CooldownMs` setting was removed from the same surfaces because the
active reference state machine never read it. The #172/#173/#6 and #17/#18
settings checks pass with neither key present. No runtime acceptance is claimed.
