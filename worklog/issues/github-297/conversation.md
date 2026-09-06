# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356333790 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/297

Created: 2026-08-20T19:16:51Z; updated: 2026-09-05T07:05:33Z

Exact metadata: [source record](sources/issue-5356333790-440f61b8161fca89545c483a9872d6c6d7155da283d8ea636e4f3978b7d60c39.json).

Recon tags for law roles must use the matching Rockstar map-role artwork instead of the generic enemy or human icon.

Requirements:
- Bounty hunters use the bounty-hunter map icon.
- Law officers use the proper law/cop map icon.
- Law icon presentation follows the existing state: white before hostility, dark red for the intermediate alerted state, and red when hostile.
- Resolve every texture and state mapping against current game assets or current 1491.50 behavior. Do not guess a hash from its name.
- Neutral humans, allies, animals, the owned horse, and plants keep their separate icon rules.
- The icon, ring, opacity, and 2D/3D scaling stay aligned.

Acceptance: tag a bounty hunter and law officers in each available state; the correct role icon and color appear without changing unrelated tags.

## issue 5356333790 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/297

Created: 2026-08-20T19:16:51Z; updated: 2026-09-06T12:57:26Z

Exact metadata: [source record](sources/issue-5356333790-80dfb28776291f1aaa76771c946084a387f5a0156fe4c11524a99b0c643ffe0e.json).

Use the correct law/bounty artwork and preserve the map marker’s white, alerted dark-red and hostile red states.

**Status: Source implementation complete, but unbuilt.** The overhead glyph still remains white because matching its state color is unresolved. Deliver and explain that remaining boundary before final visual acceptance.

## comment 5550167431 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/297#issuecomment-5550167431

Created: 2026-08-20T19:43:06Z; updated: 2026-08-20T19:43:06Z

Exact metadata: [source record](sources/comment-5550167431-08870e27b7dd26f6a4bef92138aa01215c7468ec4e4c5618e3fca620f94e4145.json).

Source implementation is complete but unbuilt. Recon now identifies current law and bounty relationship groups and uses Rockstar's cop and bounty-hunter map art with the matching BLIP_STYLE_COP and BLIP_STYLE_BOUNTY_HUNTER styles. The map blip keeps Rockstar's white, dark-red, and red state changes. The overhead role glyph uses the correct art but stays white because no safe conditional-color readback is resolved. After the next install, test neutral, alerted, and hostile law states plus a bounty hunter.
