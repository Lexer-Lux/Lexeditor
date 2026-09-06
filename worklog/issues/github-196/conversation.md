# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356306245 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/196

Created: 2026-08-06T05:59:32Z; updated: 2026-09-05T06:59:58Z

Exact metadata: [source record](sources/issue-5356306245-117d03c975c71fd44c2ae89d598f7c4711f6b96da530090f2c816f3a2b009b28.json).

Legacy TODO 70

## Dependency

Depends on Lexer-Lux/Lexers-Mod-For-RDR2#98. Test and resolve Lexer-Lux/Lexers-Mod-For-RDR2#98 first because this feature relies on the ammo-type counts in the weapon radial.

Each ammo family gets one combined capacity. Any single variant can fill the whole pool, and the combined total is what is capped.

Families: Pistol (.225), Revolver (.307), Repeater (.444), Rifle, Shotgun, Arrow, and Varmint (.22). All default to 0, meaning vanilla per-variant limits, until configured.

## Test

- [ ] Set `Revolver=100`.
- [ ] Carry a mix of .307 ammo types.
- [ ] Confirm their combined total stops at 100.
- [ ] Confirm excess pickups do not stick.

## issue 5356306245 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/196

Created: 2026-08-06T05:59:32Z; updated: 2026-09-06T12:55:34Z

Exact metadata: [source record](sources/issue-5356306245-aeec9e3f5c88ac9ba81efe020158984816359be37ae03d289d52f8b87927c88a.json).

Each configured ammunition family should share one capacity across its variants; zero keeps vanilla per-variant limits.

**Status: Dependent test preparation remains.** The ammo-count display in #194 still needs delivery. Then prepare the Revolver=100 mixed-ammo test with reliable before/after totals. Do not treat an unreadable or duplicated counter as proof of the cap.
