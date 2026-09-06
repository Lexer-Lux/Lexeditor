# GitHub #112 - selling items and wallet cap

## Diagnosis

- The wallet cap was enforced only after cash had already entered the wallet.
  `enforceWalletCap()` observed the over-cap balance and removed the excess on
  the following economy tick. That add-then-remove sequence explains the HUD
  counter swinging upward and then back down.
- Merchant sales already expose their selected catalog item through
  `Global_1935689.f_10190` and the Sell action's `PromptSelectEnabled` binding
  through `Global_1935689.f_10214`. The #146 merchant rejection path proved
  that writing this binding false and disabling `INPUT_SHOP_SELL` greys and
  blocks the transaction before it occurs.
- Rockstar's `satchel_ui_event_handler.c` calls native
  `0x7A62A2EEDE1C3766` (`_ITEM_DATABASE_FILLOUT_SELL_PRICE`) with
  `SELL_SHOP_DEFAULT`. Its returned currency/amount records provide the
  selected item's cash sell price.
- The installed `Banking.asi` has no public API. Binary inspection of the exact
  installed build (SHA-256
  `EE6EE67208175C0CF47C7E9956350AE0C56619579F105E7955CB9559E2E9B360`)
  found its persistent bank balance in cents at image RVA `0x53A48`. Its own
  save routine periodically writes that value as the first integer in
  `Banking.dat`. The identified PE timestamp is `0x63A0E7D4` and image size is
  `0x5A000`.

## Implementation handed to integration

- `GameplayTweaks/modules/world_economy.cpp`
  - Reads `[Misc] Auto-Bank` directly from `GameplayTweaks.ini`, defaulting to
    enabled even before the integration-owned sample INI is updated.
  - When Auto-Bank is off, disables and greys Sell before a selected item's
    known unit price would cross the current rank cap.
  - When the price cannot be resolved, it still blocks sales once the wallet is
    already full; any smaller overshoot from an unknown/modified payout remains
    covered by the wallet observer.
  - Shows the standard top-right feed whenever the player attempts a blocked
    sale.
  - When Auto-Bank is on, permits sales and transfers observed excess cents to
    the Banking mod's in-memory persistent balance.
  - Validates `Banking.asi`'s PE timestamp and image size before accessing the
    version-pinned RVA. Missing or mismatched Banking builds never receive a
    memory write and excess earnings are not deleted.
  - Writes transfer and rejection evidence to
    `GameplayTweaks.wallet-cap.log` and the existing
    `GameplayTweaks.merchant-buy.log`.

## Static verification

- The implementation is confined to the economy feature module plus this
  issue-owned worklog. No dispatcher, build, install, or GitHub state was
  changed by this feature agent.
- The merchant override path still preserves explicit buyer rejects while now
  running the wallet gate even when no buyer override CSV entries are loaded.
- Auto-Bank integer addition is range-checked before cash is removed. If the
  Banking bridge or account capacity is unavailable, cash is retained.

## Integration and runtime boundary

- Integration should add `Auto-Bank=1` under `[Misc]` in the shipped INI, run
  the full build/test suite, install/hash-verify the ASI, and move #112 to
  `test me` only after that install.
- In-game confirmation is still required for: known-price sales are disabled
  before crossing the cap with Auto-Bank off; each attempted blocked sale
  produces the feed; Auto-Bank deposits exactly the excess and Banking.asi
  persists it; ordinary non-shop cash gains do not visibly oscillate more than
  one observer tick.
- Auto-Bank still necessarily observes vanilla cash after a transaction because
  no supported pre-credit hook was found. It prevents loss and deposits the
  exact excess, but whether Rockstar's animated cash ticker briefly displays the
  intermediate amount remains an in-game acceptance boundary.

## Global wallet-indicator audit

- The earlier `Tithing/PlayerCash` finding does not describe the global
  top-right wallet indicator. Rockstar creates that container for the camp
  donation HUD: camp scripts write both `CampFunds` and `PlayerCash`, and the
  `HUD_CTX_TITHING`/`HUD_CTX_TITHING_NOGANG_CASH` contexts control its
  `CAMP_CASH` slot.
- The global wallet ticker is the separate engine-owned `CASH` HUD slot.
  `HUD_CTX_MONEY_ANIMATION_PLAYING` and `HUD_CTX_PROMPT_MONEY` only change that
  slot's visibility state. They expose no color or disabled state.
- The public RDR3 HUD/native surface can read named colors and set color only
  for script-drawn text. It exposes no HUD-slot tint setter. The money natives
  expose only get, increment, and decrement operations.
- The extracted UI data defines `COLOR_CASH_GOLD`, but changing that data would
  recolor every consumer for the entire game session; it cannot express the
  requested at-cap-only state. The global cash widget's compiled layout is not
  a DataBinding model with a supported color field.
- Therefore no technically supported implementation of the requested dynamic
  grey state was added. Adding guessed fields to `Tithing`, globally replacing
  `COLOR_CASH_GOLD`, or hiding the stock widget and drawing a guessed overlay
  would not modify the requested global vanilla indicator correctly. This
  visual requirement remains unresolved, so the full issue is not complete.
