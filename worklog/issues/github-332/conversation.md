# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356487433 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/332

Created: 2026-08-24T15:38:07Z; updated: 2026-09-05T07:40:27Z

Exact metadata: [source record](sources/issue-5356487433-ed03de2d45193ce301d870e55b8f339537f44a9c9d611267681a61449dee27f9.json).

Build the first RDR PC plugin foundation for this project on the official RedHook SDK. Use the supported .red extension and also produce the requested .asi compatibility copy. Add a development compilation flag and a tilde-key development-mode toggle. Development-only tools and logs must be absent or disabled in release builds.

Install the current official RedHook files in the selected RDR game root. When the RDR Lexeditor plugin loads, it must check for RedHook.dll, winmm.dll, and RedHook.ini. If RedHook is absent or incomplete, show a clear install notice and automatically open the official RedHook download page once during plugin startup.

Acceptance: RedHook loads, the plugin records an idle heartbeat, tilde toggles development mode once per press in a development build, the release build does not expose the toggle, and the missing-RedHook Lexeditor path reports the prerequisite and automatically opens the official URL once.

## issue 5356487433 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/332

Created: 2026-08-24T15:38:07Z; updated: 2026-09-06T13:07:46Z

Exact metadata: [source record](sources/issue-5356487433-eb64275a662eb1248d0fa622f443d4ed831cb7e71cddff15cb050ebafee52130.json).

**Status: RedHook and the development plugin are installed.** The former manual-download blocker is resolved.

- [ ] Start Story Mode. Press tilde twice and confirm development mode turns on, then off, without breaking normal play.
- [ ] Quit normally and report any startup error, toggle failure or shutdown hang so the corresponding logs can be checked. Avoid opening the weapon wheel: its crash is tracked in #333.

## comment 5550348715 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/332#issuecomment-5550348715

Created: 2026-08-24T17:02:39Z; updated: 2026-08-24T17:02:39Z

Exact metadata: [source record](sources/comment-5550348715-88a0cfa669e0f4988e568d15fc9dbb6509b86515325fcb212751388a2fea9501.json).

The RDR runtime now builds in supported .red form and as the requested .asi copy. Lexeditor checks all three RedHook files at startup, opens the official Nexus page automatically when they are missing, and shows the missing-file notice. The official package still needs a signed-in Nexus download; close RDR, then run Install-RedHook.ps1 with that ZIP.

## comment 5550348732 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/332#issuecomment-5550348732

Created: 2026-08-24T17:24:54Z; updated: 2026-08-24T17:24:54Z

Exact metadata: [source record](sources/comment-5550348732-671da4b58fbc09b3a840aacc58d50ad6825d9f3d2349142396b5df7161f05a95.json).

The current game folder contains none of the required runtime files: RedHook.dll, winmm.dll, RedHook.ini, or LexerRDR.red. This is why every in-game feature is inactive. Source and editor checks did not install the mod. RDR is closed now; the remaining blocker is the official RedHook v0.8 ZIP from Nexus.

## comment 5550348739 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/332#issuecomment-5550348739

Created: 2026-08-27T05:28:09Z; updated: 2026-08-27T05:28:09Z

Exact metadata: [source record](sources/comment-5550348739-cc0194c53db9daeeb3f9dd198db96c4e46cd42260929e9e6d1473198d4806251.json).

Official RedHook v0.8 and the development LexerRDR plugin are now installed in the RDR game folder. Startup-logo skipping is enabled. Start Story Mode once, use tilde to toggle development mode, then close the game so the loader and heartbeat logs can be checked.
