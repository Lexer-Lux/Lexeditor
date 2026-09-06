# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356299705 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/169

Created: 2026-08-06T03:01:40Z; updated: 2026-09-05T06:58:32Z

Exact metadata: [source record](sources/issue-5356299705-ec7f1e691d93622d575961136670cc6bd7b77963fcffb22417c344dc2ea697e5.json).

Migrated from local TODO #199.

## Status
Built and installed. The active `MyOverhaul/weapons.ymt` now retains every vanilla `ProjectileFlags` token while preserving the readable/known flags already present.

The affected set was exactly 31 ammo records:
- 9 arrow records
- 9 throwing-knife records
- 4 tomahawk records
- 9 hatchet records

A total of 214 missing vanilla tokens were restored. `tools/check_weapon_flags.py` now reproduces the audit, and LEXEDITOR refuses to save weapon data if a vanilla projectile flag is absent.

## Test
After a full game restart:
1. Fire ordinary and special arrows and confirm their impact/trail/wet/seeking behavior remains normal.
2. Throw representatives of every knife, tomahawk, and hatchet family and confirm impact, sticking, pickup, and recovery behavior.
3. Recheck the unique-weapon recovery behavior tracked separately in Lexer-Lux/Lexeditor#165.

Technical evidence and provenance are recorded under Worklog #199.

## issue 5356299705 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/169

Created: 2026-08-06T03:01:40Z; updated: 2026-09-06T13:07:25Z

Exact metadata: [source record](sources/issue-5356299705-38d192b3367dc3f791c56b863ea1f4f42a8290e177b4fc6e3cc0d036db69feec.json).

**Status: Restored projectile flags are installed.** No intentional new weapon behavior is part of this repair.

- [ ] Fully restart Story Mode. Fire ordinary and special arrows; check their impact and special effects.
- [ ] Throw a knife, tomahawk and hatchet, then retrieve each where normally possible. Confirm sticking and recovery still work. Report the exact weapon and failure; unique locker recovery is separate in #165.
