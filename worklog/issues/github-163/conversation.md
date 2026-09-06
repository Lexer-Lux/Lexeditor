# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356298462 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/163

Created: 2026-08-06T02:44:26Z; updated: 2026-09-05T06:58:14Z

Exact metadata: [source record](sources/issue-5356298462-7123fe8d32386a042d03095dd11a882bfbffbcf820b8e22b7dc752bcb1741ff9.json).

Since you'll be unlocking them in a different way you shouldn't be able to just grab them. Can you even edit the map tho? Actually, maybe I should get a map editor too? How good is it?

REMOVE WORLD-COLLECTIBLE MASKS — remove the fixed world pickups for every
     mask that's been reassigned to a Bandit challenge reward, so completing the
     challenge is the only way to get them. Leave the unused masks alone and
     preserve existing-save ownership.

## issue 5356298462 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/163

Created: 2026-08-06T02:44:26Z; updated: 2026-09-06T12:54:39Z

Exact metadata: [source record](sources/issue-5356298462-e46a12ab70bb0315d29ce4d09de040ec341806af395d8dc6dbc22c12614deaf2.json).

Remove only the fixed world pickups for masks now awarded by Bandit challenges. Preserve already-owned and unaffected masks.

**Status: Still broken.** The latest check found the Cat Mask still present. Verify the actual pickup is removed before asking you to revisit it again; no successful replacement test is recorded.

## comment 5550126366 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/163#issuecomment-5550126366

Created: 2026-08-06T03:57:58Z; updated: 2026-08-06T03:57:58Z

Exact metadata: [source record](sources/comment-5550126366-ec4b9094b25196dd5905d593d33a130f84569d1d88a2ea64a05dbacbbbae5d33.json).

Research result: feasible, with a safe boundary: remove only each reassigned mask's world acquisition source, never its catalog/inventory record. Challenge rewards grant the normal items, so existing ownership survives if records are not revoked. For each of the nine masks, identify whether the pickup is an authored map entity/scenario or script-created object, then remove/suppress only that source. Do not blanket-remove mask archetypes because unused masks must remain. Verify an unowned save cannot collect targets, an owned save keeps/equips them, challenge grants work, and untouched masks remain obtainable.

## comment 5550126386 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/163#issuecomment-5550126386

Created: 2026-08-06T07:48:23Z; updated: 2026-08-06T07:48:23Z

Exact metadata: [source record](sources/comment-5550126386-593c0bc5759e5bb796997a92c0bda22cbb23261cebf936f668b9d505dd7a15d2.json).

Audit proved the exact four fixed-world Bandit reward masks and coordinates. No unsafe suppression was shipped: deleting the Pagan scenario would also remove its corpse, journal, and discovery site, while inventory rollback would leave a takeable pickup. Lexer-Lux/Lexeditor#163 remains actionable pending a supported Story-script grant patch or proven interaction-entity hook; the other four Bandit mask rewards are not discoverable-world grants.

## comment 5550126406 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/163#issuecomment-5550126406

Created: 2026-08-10T09:16:28Z; updated: 2026-08-10T09:16:28Z

Exact metadata: [source record](sources/comment-5550126406-ee0bb5ae7afcb94791f06c45bd936b59e0c4185855aca42619f8f9ce71b30f6d.json).

Please don't mark things as "test me" if you didn't actually do them. It just wastes my time.

## comment 5550126424 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/163#issuecomment-5550126424

Created: 2026-08-10T19:32:34Z; updated: 2026-08-10T19:32:34Z

Exact metadata: [source record](sources/comment-5550126424-5c77526e99e134b85f975b3986b72088f8aad974fc50a74ca1c15ab8ff5f1ec1.json).

Cat mask is still there. Can you not just remove it, then check to see if it's still there or not? Why do I have to keep checking this over and over?
