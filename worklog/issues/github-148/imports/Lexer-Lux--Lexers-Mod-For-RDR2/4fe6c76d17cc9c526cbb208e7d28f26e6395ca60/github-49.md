# GitHub #49 — Shop buy/sell acceptance report

## Completed editor path

The Shops tab already contained an Acceptance Report presentation, but its
`/api/shops/acceptance` endpoint did not exist, so selecting the report could
only fail with HTTP 404.

The endpoint now combines the runtime-captured sparse merchant buyer PDATA,
the explicit accept/reject overrides, and each catalog item's real
`SELL_SHOP_DEFAULT` cash price. It reports five deliberately distinct states:
explicit accept, listed without a price conflict, mod-blocked, globally
unsellable, and engine-default unknown. Absence from sparse buyer PDATA is
never presented as rejection.

The response keeps complete per-shop counts but returns row-level detail only
for the 147 contradictory listed-without-price cases, avoiding a 101,600-row
payload. Unknown PDATA tokens remain visible by shop.

Python compilation and report invariants passed across all 20 shops and 5,080
catalog items. LEXEDITOR runtime acceptance still needs the user to open Shops
then Acceptance Report and confirm the table loads and remains responsive.
