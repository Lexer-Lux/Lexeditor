# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356290597 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/128

Created: 2026-08-06T02:04:47Z; updated: 2026-09-05T06:56:20Z

Exact metadata: [source record](sources/issue-5356290597-82f85e486903546bfb2ec331583f776b4a49139d5369324da66938844b09e5ee.json).

done as a separate little mod, needs an
     in-game confirmation after a restart.
     What are looting prompt / quick behavior rules? Why aren't they in the
     editor? Shouldn't they be? Why is this a separate mod -- shouldn't we add
     this to our existing mod, either by adding the ability to make it through
     the editor or by simply doing a one-off change to the data side of our
     mod? ~Lex

APparently it was done as a separate mod for some reason? I don't want that. 

## issue 5356290597 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/128

Created: 2026-08-06T02:04:47Z; updated: 2026-09-06T13:07:13Z

Exact metadata: [source record](sources/issue-5356290597-98eb6c6eb4075fdf87ad1a0a121a4c0a35cfc45159311e35b746782dec70b07e.json).

**Status: The change is now part of the main overhaul, not a separate mod.**

- [ ] Restart Story Mode with room for ammunition. Walk over a defeated enemy without looting: your reserve should not increase merely from proximity.
- [ ] Loot the corpse deliberately and confirm normal eligible loot still works. Report the weapon/ammo and which action changed its count. Mission-specific behavior remains protected.

## issue 5356290597 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/128

Created: 2026-08-06T02:04:47Z; updated: 2026-09-06T13:53:59Z

Exact metadata: [source record](sources/issue-5356290597-7f57aa26c786731f45959a490fcd60801a06e23cf670f51605d84b3911445545.json).

**Status: The change is now part of the main overhaul, not a separate mod.**

- [ ] Restart Story Mode with room for ammunition. Walk over a defeated enemy without looting: your reserve should not increase merely from proximity.
- [ ] Loot the corpse deliberately and confirm normal eligible loot still works. Report the weapon/ammo and which action changed its count. Mission-specific behavior remains protected.

## comment 5550117052 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/128#issuecomment-5550117052

Created: 2026-08-06T03:56:47Z; updated: 2026-08-06T03:56:47Z

Exact metadata: [source record](sources/comment-5550117052-fb09b1475578c659259b7c571cad8ce172749d15b545749066a50f449317db68.json).

Research result: this belongs in the overhaul, and it already is in the overhaul's data stack. `lootconfigdata.meta` controls TAKE_AMMO `QuickBehavior`; removing those entries disables automatic ammo collection without an ASI. `MyOverhaul/install.xml` installs the merged file directly, so the old separate mod is obsolete. The editor does not expose these prompt-table rules yet; a focused “Auto-pick up nearby ammo” toggle is safer than a raw prompt editor. Remaining proof is a restart test covering corpse ammo, ordinary loot, and mission-specific overrides.
