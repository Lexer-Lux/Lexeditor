# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5306402966 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/73

Created: 2026-09-01T00:42:35Z; updated: 2026-09-05T06:58:57Z

Exact metadata: [source record](sources/issue-5306402966-e2b8ee1a82b3818833ba8f3a1cb2705ec0318d67cb5bd92c211831f9f05266e1.json).

Expose the installed mod platform's own configuration in each game's Tweaks tab:

- FF7 and FF7 (2013): FFNx.toml
- FF8 (2013): FFNx.toml, beside the existing Gameplay tweaks
- FF9: Memoria.ini

Requirements:
- Use typed controls for booleans, numbers, known choices, lists, and strings.
- Preserve comments, ordering, and unknown settings. Change only the assigned value.
- Refuse stale writes and saving while the game is running.
- Create a backup before a write.
- Do not invent or create a configuration when the runtime is absent. Show its expected path and become editable automatically after installation.
- Include the platform configuration in each plugin's Data Map.

Implemented locally. Automated lossless round-trip checks pass for FFNx TOML and Memoria INI. Rendered checks pass for FF8's installed 126-setting FFNx file and for the absent-runtime states in FF7 and FF9. Player acceptance remains.

## issue 5306402966 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/73

Created: 2026-09-01T00:42:35Z; updated: 2026-09-06T13:30:58Z

Exact metadata: [source record](sources/issue-5306402966-4091755405402f907e40f4947270f1e74b86926983112c37783b22a471fe51eb.json).

**Actionable — partly implemented.** FF8 controls exist. FF7’s subtab and safer refresh handling are in unmerged PR #359.

FF7/FF8 need separate FFNx settings subtabs with backups and preserved unknown settings. FF9 should instead direct you to Memoria’s existing launcher, as you already decided. Integration and the FF9 Play handoff remain; no further design approval is needed.

## issue 5306402966 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/73

Created: 2026-09-01T00:42:35Z; updated: 2026-09-06T13:30:58Z

Exact metadata: [source record](sources/issue-5306402966-c187b1c9f17d961f0d4c18fc043f423b6c9529ac04d61f2fb59abcc36d745883.json).

**Actionable — partly implemented.** FF8 controls exist. FF7’s subtab and safer refresh handling are in unmerged PR #359.

FF7/FF8 need separate FFNx settings subtabs with backups and preserved unknown settings. FF9 should instead direct you to Memoria’s existing launcher, as you already decided. Integration and the FF9 Play handoff remain; no further design approval is needed.

## issue 5306402966 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/73

Created: 2026-09-01T00:42:35Z; updated: 2026-09-06T16:45:34Z

Exact metadata: [source record](sources/issue-5306402966-b67a1f76fe06231a7db835cc88c7d2919041c8c493bb27610b82c012482ff39e.json).

**Actionable — partly implemented.** FF8 controls exist. FF7’s subtab and safer refresh handling are in unmerged PR #359.

FF7/FF8 need separate FFNx settings subtabs with backups and preserved unknown settings. FF9 should instead direct you to Memoria’s existing launcher, as you already decided. Integration and the FF9 Play handoff remain; no further design approval is needed.

## issue 5306402966 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/73

Created: 2026-09-01T00:42:35Z; updated: 2026-09-06T16:45:34Z

Exact metadata: [source record](sources/issue-5306402966-ef4dc52ed690bd689a89a680b0f6b488789229031fcec21575531ac5659b1dad.json).

**Actionable — mixed-game issue; FF7 implementation is now merged.** PR #359 was merged into master as `3e2d2b924ac299f085b7f568c2394419ea0b3b63`.

**FF7, both editions:** Tweaks → FFNx is implemented with FF7-only setting filtering on reads and writes, backups, preserved unknown settings/comments, strict source snapshots, running-game protection, automatic detection of a newly created configuration, and protection against asynchronous refreshes discarding pending edits. Current-head binary/HTTP and Chromium CI passed; installed-game acceptance is separate.

**FF8 and FF9:** FF8 controls exist. Preserve the remaining FF8 integration work and FF9 Play handoff in their respective branches. FF9 should direct the user to Memoria’s existing launcher, not add a Memoria settings editor. No further design approval is needed. This FF7 pass does not claim to have completed or tested those other-game portions.

FF7 acceptance: with the game closed, change/save/reopen a harmless setting and confirm its backup; restore it. Check that FF8-only options never appear, unsaved values survive focus changes, external file changes refuse a stale save, and a running game refuses configuration writes. These behaviors have automated tests, but the installed-game checks were not performed in the recovery environment.

## comment 5486891895 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/73#issuecomment-5486891895

Created: 2026-09-01T00:53:02Z; updated: 2026-09-01T00:53:02Z

Exact metadata: [source record](sources/comment-5486891895-2ef5b69726e5d61d94fc3b05b9fbaf88816e9e0a22901a7addcf0cd413c42d50.json).

Fixed the startup regression. Two new TOML readers imported Python 3.11's tomllib, but Lexeditor ships Python 3.10.11, so plugin discovery failed before the window opened. Both readers now use dependency-free strict parsers. The packaged runtime imports every plugin, the FFNx and Memoria round trips pass, the shared-magic config contract passes, and the hidden WebView2 host completes its full startup/switch test. Close the error dialog and reopen Lexeditor.

## comment 5550129793 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/73#issuecomment-5550129793

Created: 2026-09-05T06:58:57Z; updated: 2026-09-05T06:58:57Z

Exact metadata: [source record](sources/comment-5550129793-c2a2e29567317db9a15b032f98ea65f6a226002c735d29418d6ce2e8d3f10d28.json).

No, I want to be able to edit FF7 and 8 FFnX settings via the tweaks menu with their own subtab. Memoria, as I said, has its own launcher to edit them through that shows up on each launch, so let's not waste our time. Make a memoria subtab, but make it just say "can't be bothered to make this when the memoria guys already did this themselves. just hit play and you can edit the settings in the launcher that comes up"

## comment 5559373755 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/73#issuecomment-5559373755

Created: 2026-09-06T12:58:59Z; updated: 2026-09-06T12:58:59Z

Exact metadata: [source record](sources/comment-5559373755-611c580e0fd3eba4ed7100dc2adf8931df61cfb5d2d4f9d3a382cea34976da12.json).

FF7 portion: PR #359 adds the requested FFNx subtab in both editions, filters out FF8-only settings, and preserves unsaved edits during configuration refresh. Tweaks also works when kernel loading fails. FF8 and FF9/Memoria are untouched; this shared issue remains open.

After checking out the PR separately:
- [ ] Open Tweaks → FFNx in both FF7 editions. Confirm the controls show shared/FF7 settings, not FF8-only options.
- [ ] With FF7 closed, change a harmless setting, save/reopen and confirm persistence plus its backup; restore the original value.
- [ ] Confirm an unsaved tweak survives switching focus. An external file edit must make Save refuse; Reload settings must ask before discarding edits. Saving while FF7 is running must also be refused.
