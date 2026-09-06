# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356286403 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/112

Created: 2026-08-06T01:41:37Z; updated: 2026-09-05T06:55:22Z

Exact metadata: [source record](sources/issue-5356286403-bc992a61d6fe16b205f245f9ab9ede119b364e64347c9830c7a7cfbbe5ede28a.json).

I want separate map icons for activated and deactivated campfires. They should be identical in all but one way, like maybe fire vs. no fire. Need to mockup some icon pairs first.

## issue 5356286403 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/112

Created: 2026-08-06T01:41:37Z; updated: 2026-09-06T13:17:05Z

Exact metadata: [source record](sources/issue-5356286403-8ecaa12b91742bdc8401ce664b107b0170fb841bfa02e4e5cb642d71f38e7d07.json).

**Status: Closed design record.** You chose the simple campfire icon with its flame blacked out for inactive camps, not the stove variant. The last report here still showed black squares; complete map-artwork repair is tracked in #245. Do not treat that failed image check as acceptance.

## comment 5550112096 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/112#issuecomment-5550112096

Created: 2026-08-06T03:56:45Z; updated: 2026-08-06T03:56:45Z

Exact metadata: [source record](sources/comment-5550112096-25297f19025f50c91c9a6dbb6aefb52e61e6015328283c07a3e3c6edb2019a6a.json).

Research result: this does not need new icon art unless the existing pair is rejected. The extracted set already contains `blip_campfire` and `blip_campfire_full`, and the campsite system already distinguishes inactive from activated state. The remaining proof is visual: review both at real map size, then verify a marker switches on activation and survives reload. If the pair looks right, this is implementation-ready; otherwise custom mockups should use these as baselines.

## comment 5550112120 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/112#issuecomment-5550112120

Created: 2026-08-06T05:07:13Z; updated: 2026-08-06T05:07:13Z

Exact metadata: [source record](sources/comment-5550112120-601bd9ca138df08884d67908e279f32634149aae073eab04e42e1f2645fddc5c.json).

campfire full just adds this weird stove thing on top lol. i hate it. the regular one is nice and simple and great. just take the fire part and black it out. here, use this:

<img width="32" height="32" alt="Image" src="https://github.com/user-attachments/assets/f2cc6c9a-0ae1-41cc-a20b-a22a95be708f" />

## comment 5550112135 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/112#issuecomment-5550112135

Created: 2026-08-06T05:52:41Z; updated: 2026-08-06T05:52:41Z

Exact metadata: [source record](sources/comment-5550112135-6be84d2bda41970d2d099450f4cd7e694e2921be01bc8571d81769ccc8aae2b8.json).

Integrated the exact blacked-out-fire attachment, rebuilt the 9-texture lex_blips dictionary, registered the icon, and compiled the combined ASI. Inactive uses the custom unlit flame; active uses vanilla BLIP_CAMPFIRE (no stove). The ASI install/restart is still queued, so this remains actionable until it lands.

## comment 5550112154 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/112#issuecomment-5550112154

Created: 2026-08-06T07:25:52Z; updated: 2026-08-06T07:25:52Z

Exact metadata: [source record](sources/comment-5550112154-fc23639a95a10f9d169ab1c12d3b8e0288b3fc5ca7777a2f239c48074aca25a4.json).

it's a black square
the same error we got a million times with the other map icons until you learned how to fix it
you literally know how to fix this. you got over it. you found it out. so how are you making the same mistake? wtf?

## comment 5550112164 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/112#issuecomment-5550112164

Created: 2026-08-06T09:14:12Z; updated: 2026-08-06T09:14:12Z

Exact metadata: [source record](sources/comment-5550112164-9315dacd254cce25b6993db53721cf44539b96448dceba6fa9f6856743d4db08.json).

Built and installed in ASI C7FD09E0. Fixed the inactive-campfire black square by servicing the custom texture dictionary asynchronously and relinking inactive blips once it becomes resident. Please test activated vs. deactivated campfire icons on the map.

## comment 5550112179 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/112#issuecomment-5550112179

Created: 2026-08-06T09:44:30Z; updated: 2026-08-06T09:44:30Z

Exact metadata: [source record](sources/comment-5550112179-128a0ea6a3d600e84d57ff71ade5d1f3754770cd01b38af1804541fb24d97868.json).

deactivated campfires are still black squares. did you never properly convert the image i gave you? are you just sticking .pngs into the game and hoping they'll work or something?

## comment 5550112201 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/112#issuecomment-5550112201

Created: 2026-08-06T11:30:42Z; updated: 2026-08-06T11:30:42Z

Exact metadata: [source record](sources/comment-5550112201-11b185090e1df53ce4a1499292ea3e2080f44d9f25fc980a56358b137ab87117.json).

deactivated campfires are still black squares.
