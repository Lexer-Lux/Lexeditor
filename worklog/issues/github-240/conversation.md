# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356316921 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/240

Created: 2026-08-10T10:55:17Z; updated: 2026-09-05T07:02:18Z

Exact metadata: [source record](sources/issue-5356316921-b5b1e4246119f4c5d8c66447f74034d40eb638e53350209b79b8273e12475af4.json).

Thermometer item. Max held: 1. Buyable at any general store. Upon buying it
<img width="395" height="73" alt="Image" src="https://github.com/user-attachments/assets/1704ecf8-041c-4e42-b77c-4b2b9cb258eb" />

the top-right of the screen, just underneath where the time would be if you had a pocketwatch, should show the in-game temperature. to see how it should look, look at the temperature text  in the vanilla location/info popup you get when you hit alt.

## issue 5356316921 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/240

Created: 2026-08-10T10:55:17Z; updated: 2026-09-06T13:31:49Z

Exact metadata: [source record](sources/issue-5356316921-acfa4ec2bb739a82db227c9d57c14abcad34eb4356da978402b129e51e58bec4.json).

**Needs testing.** Thermometer and placement controls are installed; shop artwork currently reuses the watch presentation.

[Display reference](https://github.com/user-attachments/assets/1704ecf8-041c-4e42-b77c-4b2b9cb258eb).

- [ ] Buy a Thermometer at a General Store. Its temperature should match the location/info popup; a second thermometer should not be carryable.
- [ ] Note its position, adjust one Thermometer position percentage, and confirm only temperature moves within about a second—not the clock. Restore it. Report an incorrect reading, position or carry limit.

## issue 5356316921 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/240

Created: 2026-08-10T10:55:17Z; updated: 2026-09-06T13:31:49Z

Exact metadata: [source record](sources/issue-5356316921-e2f6071b18293bc6d00c6efa50f2cbcea72a5eb580cd64de68df5a6068c670a7.json).

**Needs testing.** Thermometer and placement controls are installed; shop artwork currently reuses the watch presentation.

[Display reference](https://github.com/user-attachments/assets/1704ecf8-041c-4e42-b77c-4b2b9cb258eb).

- [ ] Buy a Thermometer at a General Store. Its temperature should match the location/info popup; a second thermometer should not be carryable.
- [ ] Note its position, adjust one Thermometer position percentage, and confirm only temperature moves within about a second—not the clock. Restore it. Report an incorrect reading, position or carry limit.

## comment 5550146729 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/240#issuecomment-5550146729

Created: 2026-08-10T11:33:57Z; updated: 2026-08-10T11:33:57Z

Exact metadata: [source record](sources/comment-5550146729-0419c84f416060da28aa90ea0a1975ed1c79b5513c2f18ee12ed77237e93aff4.json).

Implemented and integrated in source/data. `LEX_THERMOMETER` is a max-one provision item stocked and printed in `ST_GENERAL`; ownership enables a 1 Hz ambient-temperature readout directly beneath the pocketwatch clock, using Rockstar's coordinate-temperature native, metric preference, Celsius-to-Fahrenheit conversion, and integer rounding. It suppresses with pause/fade/death/protected UI. Story data contains no thermometer model/texture, so the item deliberately reuses the resolved pocketwatch shop presentation rather than inventing an unverified asset, but it omits the pocket-watch behavior tag and cannot trigger the held-watch interaction. The deterministic data editor is idempotent and the runtime/data/provenance verifier passes. This remains `actionable` until the new post-FC692 source is built and installed.

## comment 5550146739 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/240#issuecomment-5550146739

Created: 2026-08-10T23:02:46Z; updated: 2026-08-10T23:02:46Z

Exact metadata: [source record](sources/comment-5550146739-54d8a83c8653341cc4247a8b2d1bc67f76de2c9724d57543388bd570ef727de0.json).

The requested independent temperature placement controls are installed in build `A81224B26B7604164D48D4D2442F8BCB467271D601917C5B87A7E643CAC25730`: `Thermometer.PositionXPercent` controls its right-aligned edge and `PositionYPercent` controls its top edge, both 0-100% and hot-reloaded within about one second. They appear in LEXEDITOR and the in-game settings menu and do not depend on the pocketwatch coordinates.
