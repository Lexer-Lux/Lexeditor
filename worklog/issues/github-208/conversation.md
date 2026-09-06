# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356309506 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/208

Created: 2026-08-06T06:38:02Z; updated: 2026-09-05T07:00:38Z

Exact metadata: [source record](sources/issue-5356309506-15e511c528eacf836036184acb495e539c370c62b5c966c1113902beebd17dc5.json).

there's that money counter effect where the amount displayed gradually moves to the actual amount. except now it just swings wildly all over the place until eventually settling back if you manage to exceed it. moreover, there's no message or anything telling you you've hit the wallet cap. it should do the standard popup in the top right corner saying "hey, you've hit the wallet cap!" every time you try to collect money while at the wallet cap. moreover, you shouldn't be able to sell anything if it would take you above the wallet cap. can you also grey out the wallet/money indicator UI thing when at the wallet cap.

add a misc. .ini toggle: Auto-Bank. Default: yes. When done, you CAN do things that would take your wallet above the max. when done, any excess goes straight into your bank account.

## issue 5356309506 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/208

Created: 2026-08-06T06:38:02Z; updated: 2026-09-06T13:31:26Z

Exact metadata: [source record](sources/issue-5356309506-753af4d162877143e9d08e6e9ca6312b548f18558f3c7485b05c536da5c1a2df.json).

**Waiting on your test and display choice.** Auto-Bank and sale blocking are installed; conditional native-HUD greying is unsupported by the checked path.

- [ ] On a spare save near the wallet cap, enable Auto-Bank and collect excess cash. Confirm only the excess reaches the bank and the wallet stays capped.
- [ ] Disable Auto-Bank: over-cap sales should be blocked; pickups at the cap should warn. Report lost or duplicated money.
- [ ] Choose the existing native display without greying or a separate custom HUD replacement.

## comment 5550138250 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/208#issuecomment-5550138250

Created: 2026-08-06T07:19:06Z; updated: 2026-08-06T07:19:06Z

Exact metadata: [source record](sources/comment-5550138250-c2debc104981f98138e1ae6280a6c10d681c4eaa8fa9fde89bbb570f937465d4.json).

The critical sale behavior is built and installed: over-cap sales are blocked with a wallet-limit feed when Auto-Bank is unavailable/off; Auto-Bank defaults on and sends exact overflow into the version-validated installed Banking.asi balance without destroying earnings on unknown builds.

I am leaving this issue actionable because the requested global wallet-indicator grey state is not yet implemented, and the issue is not wholly complete. Please feel free to exercise the installed sale/Auto-Bank path meanwhile.

Installed ASI SHA-256: `85C62841F5F6C8C5B2D069A0965D3AAFA703095B9B0B74876E7728BFE5ED5D32`

## comment 5550138263 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/208#issuecomment-5550138263

Created: 2026-08-06T07:26:23Z; updated: 2026-08-06T07:26:23Z

Exact metadata: [source record](sources/comment-5550138263-8dcbd405691cfe91e9ef440c597eba1bf472a0ae5e8bd3af8fe9de7c77719e0f.json).

Follow-up audit found no supported way to conditionally grey the vanilla global CASH HUD slot: Rockstar exposes its visibility contexts but no tint/disabled-state setter. The similarly named PlayerCash binding is the camp donation widget, and COLOR_CASH_GOLD is global to all consumers. I am therefore leaving Lexer-Lux/Lexeditor#208 actionable unless the grey-indicator requirement is dropped; the critical sale blocking/feed/Auto-Bank behavior is already installed.

## comment 5550138277 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/208#issuecomment-5550138277

Created: 2026-08-06T07:34:50Z; updated: 2026-08-06T07:34:50Z

Exact metadata: [source record](sources/comment-5550138277-94b73378945365caf447cdfd55e4cd0e46daa11f6ba8e262403f71642d99a85d.json).

The remaining grey-wallet requirement has now been exhaustively checked and has no supported vanilla implementation path: the global CASH HUD slot exposes visibility but no conditional tint/state control; the similarly named PlayerCash binding is the camp donation widget; the cash-gold color is global. The critical sale/Auto-Bank repair is installed, but completing the issue now requires a human decision to accept it without conditional wallet greying (or explicitly authorize a non-vanilla replacement overlay). Moved from `actionable` to `needs a human`.
