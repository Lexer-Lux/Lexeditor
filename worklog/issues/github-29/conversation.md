# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5286146661 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/29

Created: 2026-08-29T11:00:59Z; updated: 2026-09-04T10:42:05Z

Exact metadata: [source record](sources/issue-5286146661-2c356f79d39684916dd4a89b7309c0c3956bd5361b73749478e7013fddf207fa.json).

Add one global Developer Mode setting.

When Developer Mode is enabled:
- Show the active plugin's GitHub button in the top command row.
- Show a Restart button beside it.
- Place both immediately before Minimize, Maximize, and Close.
- GitHub still appears only when the configured owner account is available.
- Restart uses the normal unsaved-changes choices and restarts only the active plugin service.

When Developer Mode is disabled:
- Hide both developer controls.
- Keep normal editing, Data Map, Info, Save, and window controls unchanged.

Acceptance:
- Developer Mode persists across launches.
- Toggling it updates the current shell without requiring a manual restart.
- Restart replaces the active child service, reloads its URL, and does not create another desktop window.
- A dirty restart offers Save and Restart, Restart Without Saving, or Cancel.
- A rendered check confirms placement immediately before the Windows controls.

## issue 5286146661 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/29

Created: 2026-08-29T11:00:59Z; updated: 2026-09-06T13:06:41Z

Exact metadata: [source record](sources/issue-5286146661-533e3e75875fac18324c272b83603a75b20bcdc412ca0746016a6f49931e4cf7.json).

**Status: Implemented; needs your check.** Plugin Restart restarts the active editor; Home Restart restarts Lexeditor, even with no plugin open. Developer controls stay hidden when Developer Mode is off.

- [ ] Toggle Developer Mode in Settings. Confirm Restart appears/disappears immediately on Home and in a plugin.
- [ ] With a disposable unsaved edit, choose Restart, then Cancel. Confirm the edit survives. Save or discard deliberately, restart, and confirm only one window remains.
- [ ] Enable Lexer Mode and confirm Blank: The Game is available without an installation. Report missing controls or the wrong restart behavior.

## issue 5286146661 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/29

Created: 2026-08-29T11:00:59Z; updated: 2026-09-06T13:06:41Z

Exact metadata: [source record](sources/issue-5286146661-f1dcbaaeef87055887949c717d04c390428061ac199308a01be3c146086bd866.json).

**Status: Implemented; needs your check.** Plugin Restart restarts the active editor; Home Restart restarts Lexeditor, even with no plugin open. Developer controls stay hidden when Developer Mode is off.

- [ ] Toggle Developer Mode in Settings. Confirm Restart appears/disappears immediately on Home and in a plugin.
- [ ] With a disposable unsaved edit, choose Restart, then Cancel. Confirm the edit survives. Save or discard deliberately, restart, and confirm only one window remains.
- [ ] Enable Lexer Mode and confirm Blank: The Game is available without an installation. Report missing controls or the wrong restart behavior.

## comment 5461978691 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/29#issuecomment-5461978691

Created: 2026-08-29T11:06:13Z; updated: 2026-08-29T11:06:13Z

Exact metadata: [source record](sources/comment-5461978691-6e14055921dc5bc825ee9fdeb505dac6b61b33ec6ad5bdc67278853de19d2355.json).

Implemented Developer Mode as a global Lexeditor setting. When enabled, GitHub and Restart appear in the active game's top command row immediately before the Windows controls. GitHub still requires an authorized repository account. Restart replaces only the active plugin service in the same window and offers Save and Restart, Restart Without Saving, or Cancel when edits are unsaved. Settings persistence, restart lifecycle, hidden host checks, and the rendered placement check passed. Please inspect the controls and restart behavior.

## comment 5471601161 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/29#issuecomment-5471601161

Created: 2026-08-30T22:17:53Z; updated: 2026-08-30T22:17:53Z

Exact metadata: [source record](sources/comment-5471601161-6fcaaf3ee6cf467df4282b083551e031094de7ae3c534c42a638022507bc5ccb.json).

Settings now have ordered User, Developer, and Lexer lanes. Lexer Mode requires the active Lexer-Lux GitHub account, adds a distinct packaged-default control beside every setting, and supports double-clicking the name or description to copy the current value as the default. Shared dependency controls now remember values they turned off, restore them when the requirement returns, and show flowing arrows on hover. The manual now defines these scopes and behaviors.

## comment 5472576943 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/29#issuecomment-5472576943

Created: 2026-08-31T01:26:56Z; updated: 2026-08-31T01:26:56Z

Exact metadata: [source record](sources/comment-5472576943-ac11bd78403b405c3c22733b2a8ffa1ff9236389ee7b8918ffdf9f6be5ba899a.json).

Added the Home-screen Restart control for Developer Mode, the Lexer-only Blank Game card for inspecting unthemed shared UI, and the Lexer menu-SFX volume default (50%). Blank Game starts without an installation and serves the shared UI locally. Restart Lexeditor, enable Lexer Mode, and confirm Blank Game is the first card; then enable Developer Mode and confirm Restart appears when a game remains resident.

## comment 5472901659 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/29#issuecomment-5472901659

Created: 2026-08-31T02:20:32Z; updated: 2026-08-31T02:20:32Z

Exact metadata: [source record](sources/comment-5472901659-7de77454a7b68999e1f0cdef7b7b804c39e66bdec0745ec2ca828ed77bb2255d.json).

Home Restart now appears whenever Developer Mode is enabled, even when no plugin is resident. It restarts Lexeditor itself; a dirty resident plugin still sends you back to save or discard first.
