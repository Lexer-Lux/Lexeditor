# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5322892743 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/83

Created: 2026-09-02T10:44:53Z; updated: 2026-09-04T12:25:13Z

Exact metadata: [source record](sources/issue-5322892743-70941127df588c83cc2713efd6f4232faf48aa1fae136d2ce5588da05f1bacdb.json).

A Memoria-side tweak for the FF9 plugin. Do not build yet.

- Eat cannot be selected on an enemy that is neither low enough HP to be eaten nor carries an ability the party has not learned. The command is unavailable rather than wasting a turn.
- Enemies that do carry a still-unlearned ability show a blue glow, so the player can see which ones are worth eating without checking a guide.

Notes:
- Check what Memoria already exposes before writing code (see the audit note on the Improved Interface issue). The "unlearned ability" lookup may already exist for its own UI.
- The glow needs a battle-target render hook; confirm whether Memoria has an existing target-highlight path before adding one.

## issue 5322892743 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/83

Created: 2026-09-02T10:44:53Z; updated: 2026-09-06T12:45:48Z

Exact metadata: [source record](sources/issue-5322892743-09b46eaac351f7c4b07c2d6fa2c5f6345d8927178c93ed5416949bfb9eaf9f5f.json).

Make Eat's target/availability rules avoid unproductive use, and give enemies carrying an unlearned ability a blue glow.

**Not delivered.** Check Memoria's existing eligibility and highlight support before adding code. No implementation result or prepared test justifies a Waiting label.
