# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356299528 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/168

Created: 2026-08-06T02:52:40Z; updated: 2026-09-05T06:58:29Z

Exact metadata: [source record](sources/issue-5356299528-3f5d2d731d3b88990c8266004d0a938516b0679048f91d548cfab6825d24231d.json).

NO SPARKLE ON OWNED GEAR — pickups stop glowing when I already own the gun.
     Working for all 80 weapon models. Hats can't use the same mechanism because
     they aren't pickup entries and their catalog records have blank model
     fields. WAITING: one safe Story-mode session near a collectible hat so we
     can capture its real identity and finish the hat path.

## issue 5356299528 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/168

Created: 2026-08-06T02:52:40Z; updated: 2026-09-06T12:54:46Z

Exact metadata: [source record](sources/issue-5356299528-de0d527ddf4d033a2f01d75da50f65f06a0b43b015508b9dd05b3da7d121fb7a.json).

Owned weapons and collectible hats should stop advertising themselves as new pickups.

**Not working:** the weapon implementation was removed after repeated crash isolation. The hat path is also unfinished. Restore a safe implementation and prepare any necessary identification probe before asking you for a capture.

## comment 5550127614 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/168#issuecomment-5550127614

Created: 2026-08-06T07:33:45Z; updated: 2026-08-06T07:33:45Z

Exact metadata: [source record](sources/comment-5550127614-5efd6e4526edc0e270696325851a68c25d14c7e8c61b91549bb9f78120ccd215.json).

The remaining hat path explicitly requires a safe Story Mode session near a collectible hat, so this is blocked on human-controlled gameplay. Moved to `needs a human`.

## comment 5550127630 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/168#issuecomment-5550127630

Created: 2026-08-10T03:05:55Z; updated: 2026-08-10T03:05:55Z

Exact metadata: [source record](sources/comment-5550127630-548e89fd97e043e28a02824369e5026cd49601830b414de18633db012b812e23.json).

Crash repair for the implemented weapon path: progressive isolation proved `suppressOwnedGearSparkles` caused the delayed `ERROR:FFFFFFFF`.

Removed undocumented hash `0x50C14328119E1DD1`, which had been given the invented name `BLOCK_PICKUP_LIGHT` and an unsupported object argument. Retained the SDK-documented `SET_PICKUP_PARTICLE_FX_HIGHLIGHT` and `_SET_PICKUP_OBJECT_GLOW_ENABLED` operations, with pickup/object existence guards and unified logs for each newly suppressed owned pickup.

Installed full ASI `20606EB185A06CB52AF979EFAEB8021F94E42ADC8B94172F7EFAF3CB8CA6BB6B`; hashes match. The separate collectible-hat identification requirement remains, so this issue stays `needs a human`. No labels changed.

## comment 5550127637 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/168#issuecomment-5550127637

Created: 2026-08-10T04:35:35Z; updated: 2026-08-10T04:35:35Z

Exact metadata: [source record](sources/comment-5550127637-9a3b078753da9d2a303c1a903bc96a750e979107dabb822a0a6c0a6bea859798.json).

Crash isolation result (2026-08-09): the shortened staged build survived Ancient Tomahawk and Hunter Hatchet, then raised ERROR:FFFFFFFF only after owned-gear sparkle activation while child vulnerability remained held. Both the pickup-placement scanner and the guarded pickup-object scanner reproduced this boundary. The weapon sparkle runtime has therefore been removed completely from the live translation unit (loader, timer, dispatcher, pool scans, and effect-native wrappers); it is not being represented as working. Installed normal ASI: 80105728F13BBD3CAC5D54832B252744018461DFDE296F9A52B93CC3043806CF. The existing needs a human label is unchanged because the separate collectible-hat identification session is still outstanding.
