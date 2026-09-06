# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356298250 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/162

Created: 2026-08-06T02:43:28Z; updated: 2026-09-05T06:58:11Z

Exact metadata: [source record](sources/issue-5356298250-ed2c1bd36fb8dee5063952dfdca2634c482bc5e1f80fdc120d696094ece168d0.json).

CASING CUSTOM PICKUP SOUND — replace the placeholder frontend click with a
     real brass-pickup sound. Needs audio-bank modding research. Meanwhile,
     surface the sound fields in LEXEDITOR's settings tab.

Doesn't every item already have a pickup sound set? Why not just expose that in LEXEDITOR and let me change it?

## issue 5356298250 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/162

Created: 2026-08-06T02:43:28Z; updated: 2026-09-06T12:54:37Z

Exact metadata: [source record](sources/issue-5356298250-8d0e0c5b8f14f437c05d6d4f4fa06ef0fa6631fa813095c64284f4f33b403540.json).

**Status: The routing approach is established; audio work has not started.** One custom sound event can serve casing pickups, but an item category does not create the audio itself.

- [ ] Attach the sound file you want for picking up brass, with its source and permission/credit details. It can then be authored into a playable event and used by the casing pickup paths.

## comment 5550126121 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/162#issuecomment-5550126121

Created: 2026-08-06T03:58:35Z; updated: 2026-08-06T03:58:35Z

Exact metadata: [source record](sources/comment-5550126121-d989643606f98759e8c5a76472942f8a2554cdfe8d41ace2a257efd871c6c395.json).

Research result: pickup audio is data-driven at the looting context level, but not proven per catalog item. Extracted `loot_sounds.meta` maps `PICKUP_CONTEXT` to `PICKUP_SOUNDSET`; the current casing feature instead uses configurable frontend sound name/set because it creates its own hold-to-pickup interaction. So “every item already has its own pickup sound” is not supported by the extracted data. The editor can expose the proven loot-context sound mappings, while casing-specific sound remains an ASI setting. A truly new brass sample requires an audio bank or reuse of a shipped sound discovered by audition; first inventory the relevant soundsets and test candidate shipped sounds before authoring audio.

## comment 5550126133 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/162#issuecomment-5550126133

Created: 2026-08-06T05:16:20Z; updated: 2026-08-06T05:16:20Z

Exact metadata: [source record](sources/comment-5550126133-9b73b5b45f90f03f09c6413252f01d06aedf7d3e3e4722c7c86e0fd8194ad7cb.json).

okay so can we not just create a new category then i just give you a sound to add for it, then put the casings in it? IDGI

## comment 5550126143 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/162#issuecomment-5550126143

Created: 2026-08-06T07:45:29Z; updated: 2026-08-06T07:45:29Z

Exact metadata: [source record](sources/comment-5550126143-2191b0f3d2f4ac501dab92827d4c04d7a4f7fefa9256ce0e2e89c27c465c656a.json).

Research complete. Yes: `loot_sounds.meta` does have the category mechanism you described, with one important boundary.

The extracted `CLootSoundsMapCollection` has:

- `PICKUP_CONTEXT -> PICKUP_SOUNDSET` (and `LOOT_CONTEXT -> LOOT_BODY_SOUNDSET`);
- a per-item `Sounds` map such as `AMMO_RIFLE -> AMMO`, `PROVISION_POCKET_WATCH_GOLD -> WATCH`, and `CONSUMABLE_BRANDY -> TONIC`.

So the casing item IDs can be added to that map with a new category/event name, e.g. `LEX_CASING_225 -> BRASS`. This is per catalog item, contrary to the earlier overly broad “not proven per item” answer.

But `BRASS` must also exist as a playable event inside `PICKUP_SOUNDSET` (or another bank/set used by the caller). `loot_sounds.meta` only routes item ID -> event name; it does not contain or create audio. A supplied sample still has to be authored into a compatible game audio bank/relationship and registered so the soundset resolves it.

There is also a casing-path distinction:

- native pickup mode may pass through Rockstar's pickup resolver, so the new item mapping is the correct data experiment;
- default casing mode uses `INVENTORY_ADD` and then explicitly calls `PLAY_SOUND_FRONTEND(PickupSoundName, PickupSoundSet)`, so merely placing casing IDs in `loot_sounds.meta` will not make that custom grant invoke the mapping. Once the custom event exists, this mode can call its set+name directly.

Therefore the concrete route is: you supply the sound; author/register one `BRASS` event in a modded bank/soundset; map all casing IDs to `BRASS` in `loot_sounds.meta` for native pickups; point the current casing sound settings at the same event for custom pickups; then verify both modes in game. LEXEDITOR can expose the item-to-category map and casing set/name, but cannot turn a WAV into a bank by itself.

Human input needed: the source sound file and permission/credit details. No audio or editor implementation was made under this exploratory issue.
