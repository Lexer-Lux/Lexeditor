# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356487232 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/331

Created: 2026-08-24T15:15:54Z; updated: 2026-09-05T07:40:24Z

Exact metadata: [source record](sources/issue-5356487232-69e1384e33a4994492ed7e5f027fefd9b536bcd846e8ed8d689aa33d6d1978b8.json).

Create a private Git-backed project for Lexer's Red Dead Redemption mod. Use the existing Lexeditor RDR2 plugin contract and visual language as the base. Detect the installed Steam game, read its RPF6 archives without changing them, prepare an editable project workspace, and expose those files through a managed RDR Lexeditor plugin. Keep original archives and prepared vanilla cache outside Git.\n\nAcceptance:\n- Lexeditor detects the installed RDR game.\n- Setup reads the installed RPF6 data without writing to the game directory.\n- An editable project file can be opened, changed, saved, and read back.\n- The RDR plugin reports the correct managed-plugin identity and installation state.\n- The private Git repository contains no original game archives.

## issue 5356487232 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/331

Created: 2026-08-24T15:15:54Z; updated: 2026-09-06T12:38:38Z

Exact metadata: [source record](sources/issue-5356487232-d6464d2738e8527ee1df6a9671ce824311ab980b24ecf81f5866db83dc74810d.json).

**Status: The managed plugin and editable workspace exist.** Installed archives are kept separate from mod edits.

The old handoff asks you to edit a raw file, but the current goal is structured editing. Prepare a current, specific save/reopen check through the real editor and explain how it reaches the game before marking this ready. Remaining editor coverage is in #337.

## issue 5356487232 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/331

Created: 2026-08-24T15:15:54Z; updated: 2026-09-06T12:38:38Z

Exact metadata: [source record](sources/issue-5356487232-e4d01e76ae8c299284d18e0363d11bfc2755d8682a9c662fd742f66bfc302f53.json).

**Status: The managed plugin and editable workspace exist.** Installed archives are kept separate from mod edits.

The old handoff asks you to edit a raw file, but the current goal is structured editing. Prepare a current, specific save/reopen check through the real editor and explain how it reaches the game before marking this ready. Remaining editor coverage is in #337.

## comment 5550348480 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/331#issuecomment-5550348480

Created: 2026-08-24T15:34:44Z; updated: 2026-08-24T15:34:44Z

Exact metadata: [source record](sources/comment-5550348480-bd356f163911bd35fb756edffdfb703f2d070ad128ba9ff9a75f456c0216102b.json).

The private project and managed RDR plugin are ready. Lexeditor detected the Steam install and prepared 1,915 files without changing the source archive. Open Lexeditor, select Red Dead Redemption, edit a file such as tune/ai/motives.xml, and select Save. The first save creates the matching project file under C:\RDRMod\mod\tune_d11generic. Confirm the editor layout and one retained edit/save.
