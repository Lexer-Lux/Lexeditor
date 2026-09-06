# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5318381754 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/80

Created: 2026-09-02T00:46:07Z; updated: 2026-09-04T12:25:11Z

Exact metadata: [source record](sources/issue-5318381754-943c6f35cf913f6bc12ba61d11a475c1188e6781b976f4b5eaa0cae5f2c0b966.json).

A single toggleable Memoria tweak for FF9, exposed in the plugin's Tweaks tab. Every binding below needs a keyboard equivalent as well as the controller button.

## Dialogue and cutscenes

- **Circle** — instantly complete the message currently being typed out in the dialogue box, the same way X does, but *do not* advance to the next message. This exists so the player can reveal text without risking a skip.
- **Triangle** — step back one message so the player can re-read what they missed. Strictly a display rewind: it must not re-run scripts, re-trigger decisions, or re-award anything. Replaying an item grant would let players farm items, so the history has to be a record of rendered messages, not a re-execution of the dialogue.
- **Square (held)** — advance through available dialogue as fast as the engine allows.

## Battle status panel

- Remove the ATB column from the bottom-right party status table.
- Move each character's ATB bar **above** their row and their Trance bar **below** it, each stretched to the full width of the row.
- Redistribute the freed width across the remaining columns.
- Add an HP bar under the HP number and an MP bar under the MP number, in their own columns.
- ATB fills left to right as normal. When a character acts, it drains **right to left**, timed so it reaches empty exactly as the action/animation finishes and refilling begins.

## Notes

- Depends on Memoria being installed (see #77 for the managed installer).
- Ships as one tweak toggle named "Improved Interface"; the dialogue and battle halves should be able to fail independently rather than taking the whole tweak down.

## Tetra Master opponent prompt

Absorbs #76. FF9 already shows a card icon near an opponent who can play Tetra Master. Make that prompt glow, or otherwise look distinct, when the player has not yet beaten that opponent.

- Use the normal prompt after that opponent has been beaten.
- Track the result per opponent. Reuse an existing durable game value if one exists; add compatible save storage only if it does not.
- This remains part of the single Improved Interface tweak.

## issue 5318381754 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/80

Created: 2026-09-02T00:46:07Z; updated: 2026-09-06T12:45:45Z

Exact metadata: [source record](sources/issue-5318381754-f475668744d9a3a2994141bca7547401d7c7ffe94b0e470821930801ca1d072d.json).

One optional Improved Interface tweak should add safe text reveal/history/fast-forward, full-width ATB/Trance with HP/MP bars, and a distinct prompt for unbeaten card opponents. Include keyboard equivalents.

**Work remains:** first reuse the capabilities Memoria already provides, then implement the gaps. Dialogue history must not replay scripts or rewards. No completed candidate is ready for your testing.

## comment 5505465544 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/80#issuecomment-5505465544

Created: 2026-09-02T06:29:56Z; updated: 2026-09-02T06:29:56Z

Exact metadata: [source record](sources/comment-5505465544-a9fe0fcf5cb461aea01da018b0dc2b3f9029f7d70eb889eeb7df2a29bdb75eaf.json).

Before building any of this, audit what Memoria already provides and do not reimplement it.

Memoria ships a large set of interface and QoL options of its own — its launcher exposes Skip intros, Skip battle load time, UI lines/columns, text fading, dialog progress buttons (`DialogProgressButtons` in `Memoria.ini` already lists which buttons advance cutscene dialog), PSX scrolling behaviour, battle and interface sections, and more. Several pieces of this spec may be partly or wholly covered there.

For each item below, check `Memoria.ini` and the launcher UI first:
- Circle completing the current message without advancing — compare against `DialogProgressButtons` and the `[Interface]` section.
- Square held to fast-forward dialogue — Memoria may already expose a dialogue speed or skip control.
- Battle status panel layout — check `[Battle]` and `[Interface]` for existing ATB/Trance/HP/MP display options before rewriting `BattleHUD`.

Where Memoria already has a setting, the tweak should drive that setting rather than patch the assembly. Only the gaps should become new code, which also keeps the derivative fork as small as possible to rebase.

Triangle (step back through rendered messages without re-running scripts) looks genuinely new and is likely the main piece of real work here.
