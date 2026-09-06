# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356289511 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/124

Created: 2026-08-06T01:59:28Z; updated: 2026-09-05T06:56:07Z

Exact metadata: [source record](sources/issue-5356289511-a09fb917d33fc291e0e0858aa4b46b7a0e1b86d65843613c86ec24b0c785210d.json).

NO SURRENDER TO THE LAW / PAY OFF BOUNTY ON THE SPOT — with a serious crime
     on your record you can't surrender to lawmen or bounty hunters. Instead you
     get the option to pay the bounty off right there, if you have the cash:
     show the amount, take the money, clear the bounty, call off the pursuit. If
     you can't afford it the option is greyed out with the shortfall shown and
     the fight continues. Doable?
How will we define/detect serious crimes?

## issue 5356289511 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/124

Created: 2026-08-06T01:59:28Z; updated: 2026-09-06T13:07:06Z

Exact metadata: [source record](sources/issue-5356289511-7992bfd7f5ac3e850848c2fce4b0f3c9e324c86713ab87a15317f8092531d17a.json).

**Status: The repaired development build is installed.** Serious-crime handling now uses the current crime’s defined severity; no new definition is waiting on you.

- [ ] On a spare save in free roam, incur a serious bounty and approach a lawman when the payment interaction is offered. With enough cash, confirm it shows the amount, charges once and ends the pursuit.
- [ ] Repeat with less cash than the displayed amount: payment must be unavailable with the shortfall shown and no money deducted. Report the crime, amount and failed step.

## comment 5550115914 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/124#issuecomment-5550115914

Created: 2026-08-06T03:57:51Z; updated: 2026-08-06T03:57:51Z

Exact metadata: [source record](sources/comment-5550115914-6037ee58d9b777aa9f3473de226562b7603097240ee94b2802b65ae77e8ee38c.json).

Research result: feasible through the ASI, not as one data edit. `crimeinformation.meta` supplies per-crime Severity, so High is a defensible configurable default for “serious.” Rockstar exposes surrender/arrest inputs and arrest-reset state, while `shop_post_office.c` proves regional bounty balance/payment paths. The unresolved part is safely cancelling every active law and bounty-hunter dispatch. Recommended free-roam-only prototype: suppress surrender for High crimes, show bounty/shortfall, deduct cash, clear the current regional bounty and wanted/arrest state, then dismiss dispatch. Probe lawmen and wilderness hunters separately and exclude missions/interiors until verified.

## comment 5550115932 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/124#issuecomment-5550115932

Created: 2026-08-06T08:16:13Z; updated: 2026-08-06T08:16:13Z

Exact metadata: [source record](sources/comment-5550115932-3053d3ba7eab123fe13389d054e137a1a13e5076e5fe8b89c323bdd6e04f0eee.json).

Built successfully with game-defined High-severity serious crimes, exact bounty/shortfall prompt, cash-first payoff, then wanted/bounty/pursuit clearing. It will install when RDR2 exits.

Queued ASI SHA-256: `9124F920A8A97381327D8FF1D2E01A0A3220A793EA9BE475BAF5D7198E9B225B`

## comment 5550115958 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/124#issuecomment-5550115958

Created: 2026-08-15T21:02:59Z; updated: 2026-08-15T21:02:59Z

Exact metadata: [source record](sources/comment-5550115958-3f04ebc404c09d8def96c20ff9dffbdb97ac85fd5e9962c7f4afc28e34baefb9.json).

The Lexer-Lux/Lexeditor#149 crash dump proved that the same registered-crime query used by this feature can corrupt the ASI stack. I removed it here too. Serious-crime detection now uses the safe current HUD crime hash against the extracted High-severity set. The repaired development ASI is installed. Re-test one affordable and one unaffordable serious bounty; confirm the amount/shortfall prompt, pursuit cleanup after payment, and no freeze or crash.
