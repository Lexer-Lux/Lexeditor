# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5288607257 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/58

Created: 2026-08-29T20:07:25Z; updated: 2026-09-04T12:24:59Z

Exact metadata: [source record](sources/issue-5288607257-3a42a5d0a53c2265095c252f017de8f9a18b781f7b21a478389e5d5ceed643db.json).

Rework the FF8 Info page opened by the top-right Info button.

The current toolbar text is not a real page title, the page omits the game installation location, it reports the extracted baseline as unavailable even while the editor is using it, and its FFNx status does not show the installed version.

Required layout:
- A top title panel with large FF8 title text and an Info icon followed by a short explanation.
- The first status panel shows the confirmed FF8 installation directory and a folder button that opens it in Windows Explorer.
- A gameplay-data panel reports the real extracted-baseline readiness state.
- An FFNx panel reports whether FFNx is installed and its installed version.
- Do not show the editable project directory or internal helper paths as page filler.

Acceptance:
- The baseline check validates the manifest paths correctly and reports Ready for the baseline already in use.
- The folder button uses a host-owned, plugin-scoped action. It cannot open an arbitrary page-supplied path.
- FFNx shows the managed installed version.
- The page renders as a clear vertical stack without the old toolbar caption.

## issue 5288607257 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/58

Created: 2026-08-29T20:07:25Z; updated: 2026-09-06T13:16:53Z

Exact metadata: [source record](sources/issue-5288607257-ea2de01f20ca37f9b7cb20e1b911780f0afe660ab05ac7be9056df65097b9a53.json).

**Status: Closed after the FF8 Info repair.** Info shows the installation folder, accurate prepared-data readiness and installed FFNx version. The folder button opens the actual game location; duplicate path handling no longer reports a usable baseline as missing.

## comment 5464645726 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/58#issuecomment-5464645726

Created: 2026-08-29T20:13:33Z; updated: 2026-08-29T20:13:33Z

Exact metadata: [source record](sources/comment-5464645726-08591ac81ef16b8e08892996ac73324c8d166a6749dcdfa84cd189300250766e.json).

Rebuilt the FF8 Info page. It now has a large title and Info introduction, followed by Game Installation, Game Data, and FFNx cards. The installation card shows the real game path and has a folder button that opens the configured FF8 root in Explorer. FFNx reports installed version 1.24.3.

The baseline warning was false: its manifest keys already started with `en/`, but readiness added another `en/`. The repaired check now reports Ready and confirms all 212 extracted files. Project and internal helper paths are no longer shown.
