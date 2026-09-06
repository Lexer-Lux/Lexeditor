# Worklog: Todo 199

## #199 projectile flag restoration — 2026-08-05

The original diagnosis was correct but named the field imprecisely. `WeaponFlags`,
`AmmoFlags` and generic `Flags` retained their vanilla content. `ProjectileFlags`
did not: 31 of its 41 records lacked vanilla tokens — 9 arrow, 9 throwing-knife,
4 tomahawk and 9 hatchet records. The old TODO's "8 arrows" was a counting typo.

Git provenance identified the rewrite in `f627f50`: its "flag-fixed" weapon file
used readable reference-sourced lists but omitted unresolved vanilla bit markers
and several raw identifiers. The pre-rewrite `df8b821` file and the retained
`datasets/vanilla/weapons.ymt` agree on those tokens.

Restored the vanilla tokens as a semantic union rather than replacing whole flag
lists, so readable/known flags already present were retained. Readable names were
matched to raw tokens with case-sensitive Jenkins hashing; unknown-bit markers
were matched by bit index. Result: 214 tokens restored across exactly 31 records,
and all 41 ProjectileFlags fields now contain their vanilla baseline.

`tools/check_weapon_flags.py` reproduces the audit and can repair with `--fix`.
LEXEDITOR's weapon save path now applies the same invariant before serialization,
so an edit is refused if any vanilla projectile flag token is absent. The active
`MyOverhaul` directory is junction-installed; a full game restart and #51 unique-
weapon recovery retest remain the runtime acceptance boundary. The migrated live
tracker is GitHub #70 with the `test me` label; old local TODO #199 was removed.
The project and game-path `weapons.ymt` both hashed
`9160B8E8F29FFBF5242D969D5AB753FD3F7A55C3163DB65F88D05C4DDD86EDBA`; the game
path is a junction to the project directory, so no separate copy was performed.

