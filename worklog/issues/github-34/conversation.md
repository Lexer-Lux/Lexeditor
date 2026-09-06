# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5286258145 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/34

Created: 2026-08-29T11:24:28Z; updated: 2026-09-04T10:42:05Z

Exact metadata: [source record](sources/issue-5286258145-979ed1982eeb6e2cea96df503f196a642188bc7aff0b15fa9357ee96a2fd708f.json).

Mouse Back and Forward must traverse the user's actual LEXEDITOR navigation history inside the current game. They must not act as unconditional Home shortcuts.

The LEXEDITOR wordmark in the shared top bar is the explicit Home control. Clicking it must always run the existing unsaved-change guard, stop the active game service when allowed, and return to the main game menu.

Acceptance:
- Back returns to the previous browsed editor destination and Forward returns to the next one.
- History includes tab and shared special-screen navigation without losing the current plugin window.
- The wordmark always means Home.
- Unsaved changes cannot be discarded silently.
- This is one shared-shell behavior across plugins.

## issue 5286258145 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/34

Created: 2026-08-29T11:24:28Z; updated: 2026-09-06T13:06:45Z

Exact metadata: [source record](sources/issue-5286258145-7f737b9d890233c1bd74683b9b6ce026909379cb4726712da794d781ad372cfc.json).

**Status: Implemented; physical mouse-button confirmation remains.** Back/Forward traverse editor history. The LEXEDITOR wordmark goes Home; the resident plugin behavior belongs to #59.

- [ ] Restart Lexeditor. Browse Items → another tab → Info, then use the mouse’s Back and Forward buttons. Confirm each returns to the correct page rather than Home.
- [ ] Make a disposable unsaved edit and click LEXEDITOR. Confirm the unsaved-change guard works; cancel and check the edit remains.
- [ ] Report which mouse button or navigation step fails.

## issue 5286258145 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/34

Created: 2026-08-29T11:24:28Z; updated: 2026-09-06T13:06:45Z

Exact metadata: [source record](sources/issue-5286258145-a59c6888ef3790e093d0e598fc09380a1d966847371b2d101719701823fd5a87.json).

**Status: Implemented; physical mouse-button confirmation remains.** Back/Forward traverse editor history. The LEXEDITOR wordmark goes Home; the resident plugin behavior belongs to #59.

- [ ] Restart Lexeditor. Browse Items → another tab → Info, then use the mouse’s Back and Forward buttons. Confirm each returns to the correct page rather than Home.
- [ ] Make a disposable unsaved edit and click LEXEDITOR. Confirm the unsaved-change guard works; cancel and check the edit remains.
- [ ] Report which mouse button or navigation step fails.

## comment 5462256525 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/34#issuecomment-5462256525

Created: 2026-08-29T11:50:06Z; updated: 2026-08-29T11:50:06Z

Exact metadata: [source record](sources/comment-5462256525-ce4b327ce7468a0e48b82e8232e17738d48c2a3808eaf6922f22722253dc0864.json).

Mouse Back and Forward now use a shared in-plugin browse stack for normal tabs, Data Map, Info, and the embedded GitHub workspace. Windows consumes each X-button press/release sequence before WebView2 can fall through to the chooser URL; one press moves one history entry. The LEXEDITOR wordmark remains the explicit Home control and still shows Save and Exit, Exit Without Saving, or Cancel when the editor is dirty. Hidden Edge completed Back/Forward, dirty Home, main-menu return, service shutdown, and same-window plugin switching. The remaining acceptance check is the physical Back/Forward buttons on your mouse.

## comment 5464105732 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/34#issuecomment-5464105732

Created: 2026-08-29T18:25:42Z; updated: 2026-08-29T18:25:42Z

Exact metadata: [source record](sources/comment-5464105732-daab2054a48efe31e298f1385b7bf787c7b57a07caa02a9b925eeee291f5ab94.json).

Fixed the LEXEDITOR wordmark. The plugin page was trying to redirect itself from HTTP to the local main-menu file, which WebView2 blocked. The native host now performs the navigation and stops the plugin only after navigation starts. A real clean wordmark click passed in the hidden desktop host.

## comment 5471601023 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/34#issuecomment-5471601023

Created: 2026-08-30T22:17:51Z; updated: 2026-08-30T22:17:51Z

Exact metadata: [source record](sources/comment-5471601023-a051507fc70bbf244a5913ead296f52c9b2e983cc39708f291b8b995e0ada37d.json).

Back now has a same-document guard behind the native mouse hook. If WebView receives the command first, it routes to the prior Lexeditor destination instead of exposing Home. The rendered FF8 check browsed Items to Weapons, used browser Back, returned to Items, and kept the plugin URL. Please confirm with your physical mouse Back button after restarting Lexeditor.

## comment 5472578638 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/34#issuecomment-5472578638

Created: 2026-08-31T01:27:14Z; updated: 2026-08-31T01:27:14Z

Exact metadata: [source record](sources/comment-5472578638-ea262426dde0e2177437d0658e1a06e624f32ad0b9a736ef738b058273169252.json).

Forward now uses the same native route as Back. The host handles both XBUTTON2 and browser-forward app commands, with a DOM mouse-button fallback, and an approved Home transition suppresses the unload warning before the pan begins. The native mapping and Back/Forward traversal checks pass. Please confirm the physical Forward button after restarting Lexeditor.

## comment 5473538369 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/34#issuecomment-5473538369

Created: 2026-08-31T04:03:31Z; updated: 2026-08-31T04:03:31Z

Exact metadata: [source record](sources/comment-5473538369-c601c0f4ad6e9d2d6c6dcfe120d3eff5b172082dca932c74812419ba10b1707b.json).

Undo and Redo now use distinct SVG icons. Plugin Restart and Home Restart use the same two-arrow cycle icon. Hosted Back and Forward traversal passed.
