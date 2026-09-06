# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5285953371 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/26

Created: 2026-08-29T10:18:23Z; updated: 2026-09-05T06:16:45Z

Exact metadata: [source record](sources/issue-5285953371-d9470935a5c5fb94ecb4fa7c2d8695fb3c710b0da8819e45eeefc2c1000dc0de.json).

Create a shared game-asset and source-provenance system for all plugins.

Requested behavior:
- On first setup, extract only the installed game assets and data that the plugin needs for an authentic local UI. Generate private fonts, icons, and other UI assets locally. Do not redistribute the player's game assets.
- When a field refers to a game concept with a known icon, such as an element or status effect, show the installed game's icon beside its name.
- Every editable value must expose its vanilla value when available and let the player restore that value.
- Plugins can register reference-mod datasets. Show each reference value beside the active value and let the player apply it without free-form copying.
- Clearly identify whether the active value comes from vanilla, the current project, or a named reference.
- Keep extraction manifests, source paths, and unsupported boundaries visible in the Data Map.

The common framework owns the provenance controls and dataset contract. Each game plugin supplies its formats, installed-asset decoder, and named reference sources.

## issue 5285953371 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/26

Created: 2026-08-29T10:18:23Z; updated: 2026-09-06T13:30:52Z

Exact metadata: [source record](sources/issue-5285953371-a57f3193689ee52c754649a269f6f175875678512e3e7fdc7e36ae7ab542c0ca.json).

**Needs testing.** Shared references and Data Map file buttons are implemented. Unavailable references remain explicit; game assets stay in private caches.

- [ ] In a copied RDR1 mod, change an item, shop or mission value, then click Vanilla. Confirm the original value returns as a normal tracked edit.
- [ ] In RDR1, RDR2 and FF8 Data Map, use a file button. It should reveal the file, containing folder or archive, or clearly report it missing.
- [ ] Confirm source-file banners are absent from ordinary editing pages. Report the failing field or row.

## issue 5285953371 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/26

Created: 2026-08-29T10:18:23Z; updated: 2026-09-06T13:30:52Z

Exact metadata: [source record](sources/issue-5285953371-e26de72d59b57cab2df44c2e6084caefda02a4d9975e6a46fdb33a0d18405302.json).

**Needs testing.** Shared references and Data Map file buttons are implemented. Unavailable references remain explicit; game assets stay in private caches.

- [ ] In a copied RDR1 mod, change an item, shop or mission value, then click Vanilla. Confirm the original value returns as a normal tracked edit.
- [ ] In RDR1, RDR2 and FF8 Data Map, use a file button. It should reveal the file, containing folder or archive, or clearly report it missing.
- [ ] Confirm source-file banners are absent from ordinary editing pages. Report the failing field or row.

## comment 5461867312 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/26#issuecomment-5461867312

Created: 2026-08-29T10:43:01Z; updated: 2026-08-29T10:43:01Z

Exact metadata: [source record](sources/comment-5461867312-4ab7feed830d9a8b9776aad541ab92cb2fbf29450daa8369ba34c0099f7aa2f5.json).

The shared provenance control and FF8 implementation are in place. FF8 first-start extraction now pulls icon.sp1/icon.TEX privately, renders only the needed local icons, and exposes vanilla plus optional C:/FF8Mod/references/<name> values through the normal dirty/save path. This issue stays actionable because older plugins still have game-specific provenance widgets and non-integrated FF8 fields do not yet have source controls.

## comment 5462684518 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/26#issuecomment-5462684518

Created: 2026-08-29T13:28:57Z; updated: 2026-08-29T13:28:57Z

Exact metadata: [source record](sources/comment-5462684518-ef5a7465043781ae3fc278210020fd39c7c98c3626a7551a120d6391160f7cb0.json).

FF8 item references now use the game's real menu-type icons from the installed icon atlas. The item type comes from mitem.bin, so this follows FF8's own mapping rather than guessing from names. Icons now prefix Items list entries and the selected Item title, Shop stock controls, weapon ingredients, and item-valued fields. If an icon is unavailable, the text remains aligned and no broken-image symbol appears. This completes the FF8 item-icon part; the broader cross-plugin provenance work remains actionable.

## comment 5462903122 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/26#issuecomment-5462903122

Created: 2026-08-29T14:16:03Z; updated: 2026-08-29T14:16:03Z

Exact metadata: [source record](sources/comment-5462903122-8e6c4e19247eb9f1bfba3850d58fb351be2ab31f908fdca0d08f0923eb3e5a16.json).

Numeric reference values now use one shared display in FF8 and RDR2. A source appears only when its value differs from the current value; if every available source matches, the complete reference display is absent. Vanilla uses the short V label, values stay beside their controls, and clicking a differing value still restores it. Hidden-window checks passed in both plugins. The broader cross-plugin provenance work remains actionable.

## comment 5466776242 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/26#issuecomment-5466776242

Created: 2026-08-30T04:49:41Z; updated: 2026-08-30T04:49:41Z

Exact metadata: [source record](sources/comment-5466776242-8f9ea3df27c7448f4105559e07fb98fce4357efbfe2eb5b779c191d89ffa6e7f.json).

FF8 bitfields now use one provenance control per displayed toggle. Boolean references show only the green V plus a check or X; raw bitmasks and true/false text no longer appear. Numeric controls keep their own reserved reference rail, so editing one Junction value does not attach one combined reference to the whole row. The broader cross-plugin provenance migration remains actionable.

## comment 5477039078 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/26#issuecomment-5477039078

Created: 2026-08-31T10:28:33Z; updated: 2026-08-31T10:28:33Z

Exact metadata: [source record](sources/comment-5477039078-ca7f78f95d44d3e756ebaf9f36d130522d75553e8e64aa0c4449fc981fc9a643.json).

Completed the remaining cross-plugin provenance migration. RDR1 now loads prepared Vanilla item, shop, and mission datasets beside the active project and uses the shared live reference control for every editable field in those views. A changed value shows V immediately, and clicking it restores the field through the normal dirty path. Blank, FF7, FF8, RDR1, and RDR2 now share the common reference renderer. Warband has no installed Native Module System source, and FF9 has no extracted vanilla Memoria CSV, so those plugins do not invent Vanilla field values. Static contracts, RDR/RDR2 hidden renders, RDR smoke tests, and non-FF8 table regression checks passed. Please inspect one changed RDR item, shop value, and mission reward.

## comment 5549917468 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/26#issuecomment-5549917468

Created: 2026-09-05T06:16:45Z; updated: 2026-09-05T06:16:45Z

Exact metadata: [source record](sources/comment-5549917468-fdc9ef5e0634d4777f675430292754ac4b218f279f237458568d40a1f0188419.json).

Every Data Map filename now has the standard file-location button. It reveals a prepared original file, a shared folder for grouped or duplicate names, or the named installed source archive. Missing files show an error; this does not extract arbitrary archive members. I fixed RDR1 archive-member paths during the audit and verified the real content.rpf location. Hidden checks confirmed the buttons and their desktop requests in FF8, RDR1, and RDR2.

RDR2 source-file banners are also removed from the regular editing pages; that information stays in Data Map.
