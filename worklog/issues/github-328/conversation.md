# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356486650 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/328

Created: 2026-09-05T06:51:22Z; updated: 2026-09-05T16:07:45Z

Exact metadata: [source record](sources/issue-5356486650-5ac31d9fda243f0e4b9ea7c4c1bbac48a8b747f05f8a9c4b9e84ff29c72709e0.json).

HP bars should be thin red/black lines beneath each visible battle HP number. They run from right to left. Their total width represents maximum HP out of 9,999. XP bars should be yellow, fit inside their panels, and disappear outside the correct screens.

The user confirmed EXP-result progress works. The latest repair adjusts its colour and edges, and ties battle HP bars to the game's own visible HUD rows.

Your check:
- [ ] Start a battle with HP Bars enabled. Confirm each line appears with its HUD row, lies below its HP number, and ends at the ATB bar's right edge.
- [ ] Take damage or heal. Confirm the red part changes. A character with about 1,000 maximum HP should use only the rightmost tenth of the full width.
- [ ] Win a battle. Confirm XP bars are yellow and inside the panel edges. Advance to items and AP; confirm they disappear.
- [ ] Check XP bars in the party menu and Status screen. Report any wrong position or value.


## issue 5356486650 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/328

Created: 2026-09-05T06:51:22Z; updated: 2026-09-06T12:31:37Z

Exact metadata: [source record](sources/issue-5356486650-d734cea1644a1952211dbfbdc50a183a2878e4267ea4dbe6102455affadc86ea.json).

HP bars should sit beneath each HP number, fill right-to-left, and scale to maximum HP out of 9,999. XP bars should be yellow, stay inside their panels, and disappear outside the relevant screens.

**Status: Work remains.** XP progress was confirmed, but HP bars are still too low. The height repair is in draft PR #356; its Windows game driver is not yet built and packaged. There is no new HP-bar build for you to test.
