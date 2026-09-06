# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356311288 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/216

Created: 2026-08-06T10:32:16Z; updated: 2026-09-05T07:01:02Z

Exact metadata: [source record](sources/issue-5356311288-9002f19112aae1eb4f17e2d2d88b23355a5e762b3bfb9d9c41e056e7b6e19a3e.json).

## Problem

Vanilla RDR2 teleports the owned horse near the player when a saved game starts, even when the horse was left outside whistling range. Preserve the horse where it was when the game was closed instead of bringing it to the player on startup.

## Reference

- Nexus: https://www.nexusmods.com/reddeadredemption2/mods/473
- Downloaded archive: `D:\Downloads\Horse Persistance-473-1-0-1618230943.rar`
- Decompile/analyze the downloaded `horseTele.asi` and its data format as behavioral evidence. Reimplement the behavior independently; do not redistribute the reference author's assets.
- The reference reportedly does not work for hitched horses; determine whether our implementation can safely cover them rather than silently inheriting that limitation.

## Required behavior

- Record the owned horse's last valid world position before shutdown/save transition as safely as ScriptHook permits.
- On a later game startup/load, prevent the vanilla startup relocation and restore the horse to its persisted position without moving the player.
- Do not interfere with stable retrieval, horse replacement, missions, temporary mounts, death, or intentional whistling/summoning behavior.
- Fail safely when the stored horse identity or position is stale or invalid.

## In-game acceptance

1. Leave the owned horse outside whistling range, exit cleanly, restart, and load the save.
2. Confirm the horse remains at the stored location instead of appearing near the player.
3. Confirm the same horse can still be retrieved normally from a stable and summoned normally afterward.
4. Verify mission transitions, horse death/replacement, and a hitched horse do not produce duplication, deletion, or invalid placement.

## issue 5356311288 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/216

Created: 2026-08-06T10:32:16Z; updated: 2026-09-06T13:31:30Z

Exact metadata: [source record](sources/issue-5356311288-ba9b4555b39d8cddf83d585e9ae978f1e50da8efb3b7ffefd09d14fc9e0bcb9f.json).

**Needs testing.** The installed persistence feature records a state on its first run.

[Original reference mod](https://www.nexusmods.com/reddeadredemption2/mods/473).

- [ ] In Story Mode, leave your owned horse outside whistle range and exit cleanly. Restart the same save: the horse should remain there, not appear beside you.
- [ ] Retrieve it normally and repeat with it hitched. Confirm no duplicate/missing horse or player relocation. Report the failing transition.

## issue 5356311288 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/216

Created: 2026-08-06T10:32:16Z; updated: 2026-09-06T13:56:13Z

Exact metadata: [source record](sources/issue-5356311288-dfcd2b9de9f67806072b67eba3a3857499be24ec1da993806c2c8adcc5e4b2c6.json).

**Needs testing.** The installed persistence feature records a state on its first run.

[Original reference mod](https://www.nexusmods.com/reddeadredemption2/mods/473).

- [ ] In Story Mode, leave your owned horse outside whistle range and exit cleanly. Restart the same save: the horse should remain there, not appear beside you.
- [ ] Retrieve it normally and repeat with it hitched. Confirm no duplicate/missing horse or player relocation. Report the failing transition.

## comment 5550140397 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/216#issuecomment-5550140397

Created: 2026-08-06T10:35:45Z; updated: 2026-08-06T10:35:45Z

Exact metadata: [source record](sources/comment-5550140397-6c31a8e3f35671a1465b95c0833474184e595d721365ed1653a23c6a4762f3d2.json).

Implemented, built, installed, and hash-verified in the release ASI (SHA-256 \5E9FB765F5191E3558F9E121D7328BE597DCBB92C20F4DB7DD4A5ECEDA5DC632\). The independent implementation uses the reference mod's confirmed three-coordinate persistence behavior but adds a versioned state record, horse-model identity, heading, bounds validation, startup overwrite protection, and mounted/attached/dead/mission safety gates. The issue has moved from \^Gctionable\ to \	est me\ per the installed-release workflow. On this first run it establishes our state file; after leaving the owned horse somewhere and exiting cleanly, the following startup is the first persistence acceptance run.

## comment 5550140397 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/216#issuecomment-5550140397

Created: 2026-08-06T10:35:45Z; updated: 2026-08-06T10:35:45Z

Exact metadata: [source record](sources/comment-5550140397-a17c013fffbe1575110a355366626a4a346feb4860cc824802eb8b55e7583003.json).

Implemented, built, installed, and hash-verified in the release ASI (SHA-256 \5E9FB765F5191E3558F9E121D7328BE597DCBB92C20F4DB7DD4A5ECEDA5DC632\). The independent implementation uses the reference mod's confirmed three-coordinate persistence behavior but adds a versioned state record, horse-model identity, heading, bounds validation, startup overwrite protection, and mounted/attached/dead/mission safety gates. The issue has moved from \ctionable\ to \	est me\ per the installed-release workflow. On this first run it establishes our state file; after leaving the owned horse somewhere and exiting cleanly, the following startup is the first persistence acceptance run.
