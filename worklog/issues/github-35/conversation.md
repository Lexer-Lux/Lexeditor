# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5286258227 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/35

Created: 2026-08-29T11:24:30Z; updated: 2026-09-04T12:00:30Z

Exact metadata: [source record](sources/issue-5286258227-243d177356907890d48279a998c4f3ba4044da72ca7f20c132d9061c1a94b5e1.json).

Use Lexend as LEXEDITOR's neutral/default application font. This applies to the main menu and shared UI where a game theme does not intentionally replace body or display type.

LEXEDITOR must make the font available automatically. Prefer a bundled open-source webfont when its license allows redistribution; otherwise use the existing verified automatic font installer. Keep a safe local fallback so setup failure does not block the app.

Acceptance:
- Main menu and neutral shared shell use Lexend.
- Game-specific typography remains game-specific.
- A clean install receives Lexend without manual user work.
- The distribution includes the font license and source/version record.
- Hidden rendering verifies the loaded face instead of accepting a fallback.

## issue 5286258227 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/35

Created: 2026-08-29T11:24:30Z; updated: 2026-09-06T13:16:29Z

Exact metadata: [source record](sources/issue-5286258227-5dfac13f0d155245d6242e69176351df4473ff0baa582fd185216bd589dfb7ae.json).

**Status: Closed after implementation.** Lexend is bundled with its license for Home and neutral shared controls, so no manual font installation is needed. Game-specific typography remains separate.

## comment 5462117778 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/35#issuecomment-5462117778

Created: 2026-08-29T11:30:20Z; updated: 2026-08-29T11:30:20Z

Exact metadata: [source record](sources/comment-5462117778-df9d155167f12efbfe521a8d9762019fe368c026d9fe25ca42a22b6bb377a7c7.json).

Lexend 1.007 is now bundled directly with LEXEDITOR, so it needs no first-run download or system installation. The package includes the complete SIL Open Font License and a pinned source/hash record. The neutral main menu and shared defaults use Lexend; FF8, RDR1, RDR2, and Warband keep their own theme fonts. Hidden Edge confirmed the actual Lexend face loaded instead of a fallback.
