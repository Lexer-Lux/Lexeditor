# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5285785637 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/23

Created: 2026-08-29T09:38:53Z; updated: 2026-09-04T10:42:11Z

Exact metadata: [source record](sources/issue-5285785637-597f6bda847d5916d4a5dbe21f2094d853b9a0259ea65369761a033c839cf400.json).

Add a shared LEXEDITOR Settings screen. Its first setting is update-check frequency. The setting governs LEXEDITOR and managed helper programs.

For Final Fantasy VIII (2013), make FFNx a managed helper. On the first FF8 setup, download and install the compatible FFNx release into the detected game directory. On later FF8 launches, check for a newer compatible release only when the configured interval has elapsed, then update the managed FFNx files. Show progress and failures in plain language and write details to the error log. Do not overwrite user-managed FFNx configuration without an explicit merge policy. Verify release authenticity, preserve required license and source notices, and keep offline launches usable.

Acceptance:
- LEXEDITOR has one shared Settings screen.
- Update-check frequency uses named bounded choices, not unrestricted text.
- FF8 first setup installs the compatible FFNx helper.
- Later launches respect the chosen update interval.
- Offline and failed checks do not prevent the editor from opening.
- User FFNx configuration is preserved.
- Installed version and last-check result are visible.


## issue 5285785637 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/23

Created: 2026-08-29T09:38:53Z; updated: 2026-09-06T13:30:50Z

Exact metadata: [source record](sources/issue-5285785637-14a6844b42aade3072be06fc73c8a1930a017e60f6c503dd900fae0a4bb712bb.json).

**Needs testing.** FFNx installation and patch loading are recorded working. Helper versions remain pinned; checking for updates must not silently replace them.

- [ ] Restart Lexeditor. Change update frequency, save and reopen Settings; confirm persistence. Check FF8 Info shows the installed helper version.
- [ ] In Lexer Mode, note Volume, then try 50%, 1% and 0% while using menu controls. Sound should change immediately; 0% should be silent. Restore your value.
- [ ] Report any save, version-status or sound failure. Gameplay effects have separate checks.

## issue 5285785637 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/23

Created: 2026-08-29T09:38:53Z; updated: 2026-09-06T13:30:50Z

Exact metadata: [source record](sources/issue-5285785637-87f37545cbf85c7c560c7b50f20a805168b71c3cc4eef47501f07b3a59c717b2.json).

**Needs testing.** FFNx installation and patch loading are recorded working. Helper versions remain pinned; checking for updates must not silently replace them.

- [ ] Restart Lexeditor. Change update frequency, save and reopen Settings; confirm persistence. Check FF8 Info shows the installed helper version.
- [ ] In Lexer Mode, note Volume, then try 50%, 1% and 0% while using menu controls. Sound should change immediately; 0% should be silent. Restore your value.
- [ ] Report any save, version-status or sound failure. Gameplay effects have separate checks.

## comment 5461642207 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/23#issuecomment-5461642207

Created: 2026-08-29T09:50:29Z; updated: 2026-08-29T09:50:29Z

Exact metadata: [source record](sources/comment-5461642207-ff2387878538678cef416f7590e57231fdb9a03b7822a99643e0961f615543f3.json).

The shared Settings screen now controls update-check frequency for Lexeditor and managed helpers. FF8 preparation can install or update the official stable FFNx package, verifies the published checksum, keeps the user's FFNx configuration, and backs up replaced files. It detected that FF8 is running, so it did not touch the game directory. Close FF8 and reopen Lexeditor; the next safe startup scan will retry setup automatically.

## comment 5461866068 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/23#issuecomment-5461866068

Created: 2026-08-29T10:42:46Z; updated: 2026-08-29T10:42:46Z

Exact metadata: [source record](sources/comment-5461866068-463e3d7671f1983a9e9f2adc7b63f9042b28dd2f74ec72d17ad3ef5cdfc302ec.json).

Managed FFNx 1.24.3 is installed. Lexeditor keeps its Hext path on C:/FF8Mod/hext and direct-mode path on C:/FF8Mod/direct, including on a not-due startup without a network request. The remaining check is one FF8 launch that shows the helper and generated patch in the FFNx log.

## comment 5466411094 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/23#issuecomment-5466411094

Created: 2026-08-30T03:12:58Z; updated: 2026-08-30T03:12:58Z

Exact metadata: [source record](sources/comment-5466411094-5c74a72efae771389712d80a36449fc55a7ca9bae2ea14558bb7da07d854689b.json).

Found the patch-loading fault. FFNx adds ff8/en to its configured Hext base directory, but Lexeditor installed the patch in the base itself. Lexeditor now installs the patch in C:\FF8Mod\hext\ff8\en and rejects the former layout.

The next check is one FF8 launch from Lexeditor. FFNx.log must show that exact patch file as applied. I did not launch the game.

## comment 5470254631 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/23#issuecomment-5470254631

Created: 2026-08-30T17:41:42Z; updated: 2026-08-30T17:41:42Z

Exact metadata: [source record](sources/comment-5470254631-fca68e00b4628c34f7a5e7ee105ea3037bbbdd4452a7f1b57a3e9189b3e6f105.json).

I found and fixed a second FFNx path fault. FFNx prefixes Direct Mode with the game directory, so the absolute C:/FF8Mod/direct setting could not resolve. Lexeditor now creates a game-local lexeditor-direct junction to the active project and configures FFNx with that relative name. The installed config now uses direct_mode_path = lexeditor-direct, and the junction resolves to C:/FF8Mod/direct. Temporary install/update contracts pass. The remaining check is one FF8 launch that confirms the Hext patch and a Direct Mode override load in FFNx.log.

## comment 5470548602 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/23#issuecomment-5470548602

Created: 2026-08-30T18:40:59Z; updated: 2026-08-30T18:40:59Z

Exact metadata: [source record](sources/comment-5470548602-d7496d4aba440b1a06270594ce4e95898e8796a7900a1df5240e5481efa1a33d.json).

The repeated FFNx failure had an edition-path cause, and the old verifier was wrong. The installed log identifies FF8 1.2 US English (Nvidia); FFNx scans ff8/en_nv for that build, not ff8/en. Lexeditor now generates the current patch in en_nv, removes the obsolete copies, and keeps waiting while the game is still starting instead of treating another early Hext line as failure. Static path and startup-state checks pass. I did not launch FF8. The remaining runtime check is one launch whose current FFNx.log contains Applied Hext patch for ff8/en_nv/Lexeditor.FLYING_EVA.txt.

## comment 5470563631 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/23#issuecomment-5470563631

Created: 2026-08-30T18:44:07Z; updated: 2026-08-30T18:44:07Z

Exact metadata: [source record](sources/comment-5470563631-9d2797464cbca1861a61ffb21b2795977874dfacaa3f0e291e4987cd14399c66.json).

Runtime follow-up: the current installed FFNx.log, written at 12:37, now contains Applied Hext patch for C:/FF8Mod/hext/ff8/en_nv/Lexeditor.FLYING_EVA.txt. I did not launch FF8. This proves FFNx loaded the corrected patch path. The only remaining check is the visible in-game effect of the enabled gameplay changes.

## comment 5471754528 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/23#issuecomment-5471754528

Created: 2026-08-30T22:51:17Z; updated: 2026-08-30T22:51:17Z

Exact metadata: [source record](sources/comment-5471754528-f018d0435922ca534868b1bece9d9435aeddd8404880eefc7b4b05228f66db1a.json).

Lexer Mode must expose a packaged-default companion control for every user setting, including the new percentage-based Home menu height. The ordinary user value remains local; the Lexer companion changes the distributable default.

## comment 5471817900 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/23#issuecomment-5471817900

Created: 2026-08-30T23:05:22Z; updated: 2026-08-30T23:05:22Z

Exact metadata: [source record](sources/comment-5471817900-24f283f2db3f838e5f27f88727d7274c4170231ddf7d1ffc8eb8f5f1f2b7acf0.json).

Lexer Mode now covers every current user setting with an EVERYONE companion, including Home menu height. Verification kept the personal value at 10% while saving 12% as the packaged default, so the two scopes stay independent.

## comment 5472127438 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/23#issuecomment-5472127438

Created: 2026-08-31T00:10:04Z; updated: 2026-08-31T00:10:04Z

Exact metadata: [source record](sources/comment-5472127438-e93c8b48cd077293a6659eecfead78bdf1632298c6be8f289a82c380d6b63c84.json).

Add a Lexer-only 0–100% packaged default for Absent-game cover desaturation. It will appear only in the Lexer settings lane, be returned to Home in every settings snapshot, and affect no Ready or Broken artwork.

## comment 5472166577 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/23#issuecomment-5472166577

Created: 2026-08-31T00:16:10Z; updated: 2026-08-31T00:16:10Z

Exact metadata: [source record](sources/comment-5472166577-f723b8fa2d91a5ab5a56f57b3eb7c06a05d1551634e204b3e59db8d8530f7a87.json).

Added a Lexer-only Absent game desaturation setting. It accepts 0-100%, defaults to 75%, and changes the packaged default for every user without creating a personal user control. The settings round-trip and rendered Settings checks passed.

## comment 5473653487 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/23#issuecomment-5473653487

Created: 2026-08-31T04:18:56Z; updated: 2026-08-31T04:18:56Z

Exact metadata: [source record](sources/comment-5473653487-77fd8a6eee5a972ae2cb477f9a66cbc43bd0bc74109cc6e3a30b1f9e2e77996a.json).

The global menu-sound volume is now fully connected: settings persistence and bounds, the desktop bridge, one normalized playback gain, the Sound on/off gate, and the Lexer EVERYONE companion all pass. FFNx is installed, its path is corrected for the Nvidia English edition, and the current log proves it loaded Lexeditor's patch. This issue now only needs your visible gameplay and listening acceptance.

## comment 5473846399 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/23#issuecomment-5473846399

Created: 2026-08-31T04:46:11Z; updated: 2026-08-31T04:46:11Z

Exact metadata: [source record](sources/comment-5473846399-11c48564f4c79345904d4e3826481defa18611e2b84cfbd1c272dbbb5b3175c1.json).

Lexer Mode's paired default controls no longer have nested purple boxes. Each companion now uses a purple DEFAULT label plus a purple input border or checkbox accent. The rendered Settings check also passed the existing layout, save, discard, and responsive-fit tests.

## comment 5473893655 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/23#issuecomment-5473893655

Created: 2026-08-31T04:52:58Z; updated: 2026-08-31T04:52:58Z

Exact metadata: [source record](sources/comment-5473893655-716c1bef2064fb59d1f6cd566851cfe0b7331b6f42618e9e33c03241aad6242d.json).

Found the cause: Volume is a Lexer-only setting, but playback still preferred a legacy personal 50% value from the local settings file. That made newly saved defaults appear ineffective or restart-dependent. Runtime now ignores that stale personal value, applies Lexer Volume live, stops active sounds at 0%, and uses a squared gain curve (1% = 0.0001 gain). One restart is needed to load this code revision; later Volume changes require no restart.
