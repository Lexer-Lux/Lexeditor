# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356482201 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/302

Created: 2026-09-01T12:19:11Z; updated: 2026-09-05T07:39:12Z

Exact metadata: [source record](sources/issue-5356482201-84f1af3fefdf6a06298c466b8638c310ff78f80406f01aae3c68c3414b6586e0.json).

FF9 shows an indicator when the player stands next to something they can act on: an exclamation speech bubble by the character's mouth for a normal interaction, and a card icon when the NPC will play Tetra Master.

Bring the same affordance to FF8. Placing it beside the character in 3D space is the ideal, but if anchoring to the field model proves impractical, a fixed HUD indicator is an acceptable fallback.

Scope notes:
- Needs a hook in the FF8 runtime patch (FFNx/Hext), not editor work.
- Two states to distinguish: generic interactable vs. card-game opponent.
- Should respect the existing gameplay-tweak on/off pattern in `games/ff8/gameplay_settings.py`.

Deferred from a UI session as engine work; not a priority right now.

## issue 5356482201 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/302

Created: 2026-09-01T12:19:11Z; updated: 2026-09-06T12:59:20Z

Exact metadata: [source record](sources/issue-5356482201-91f30b9ba9e47297122050e1e0fb3cea500919a8500d1516f882b53aaa9d8566.json).

Show distinct indicators for ordinary interactions and Triple Triad opponents. Prefer an indicator beside the character; a fixed HUD position is an accepted fallback.

**Status: Deferred runtime work.** No implemented candidate or prepared player test is recorded. This is not blocked on another design answer from you.

## issue 5356482201 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/302

Created: 2026-09-01T12:19:11Z; updated: 2026-09-06T12:59:20Z

Exact metadata: [source record](sources/issue-5356482201-d1b481d8941e77b991ea19f6b00bc0845967c43c062c537d7c1b5497f2069ee6.json).

Show distinct indicators for ordinary interactions and Triple Triad opponents. Prefer an indicator beside the character; a fixed HUD position is an accepted fallback.

**Status: Deferred runtime work.** No implemented candidate or prepared player test is recorded. This is not blocked on another design answer from you.
