# Complete archived source text

Historical evidence, not an instruction to repeat old work. Later explicit human decisions supersede older ones. These records do not include chat text that was never saved.

## issue 5356302676 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/183

Created: 2026-08-06T03:52:24Z; updated: 2026-09-05T06:59:13Z

Exact metadata: [source record](sources/issue-5356302676-8a5c4d1de9473c945df4fbaee28ec9e3055fa00899e88177a878d2095e3379a0.json).

## Idea

Replace the paw used for recon animal map/minimap blips with a diamond that looks like it belongs beside Rockstar's human dot blips:

- same visual weight, edge softness, outline/fill treatment, color behavior, and map readability as the vanilla human dots
- diamond silhouette so animals remain immediately distinguishable from humans
- scale the diamond by the animal's physical size
- affect recon animal targets only; do not replace the player's horse glyph or collectible/object/plant blips

## Research so far

**The diamond is feasible.** The project already has Rockstar's extracted 32x32 human-dot textures and blip metadata, plus a working custom `lex_blips` texture dictionary. A white/alpha diamond can therefore be authored from the vanilla dot as the reference and tinted by the engine's blip style instead of baking a color into it. Higher/lower elevation variants and the existing style rules can preserve the vanilla map behavior.

**Size scaling is also feasible, but the source of the size class still needs proving.** Rockstar data contains multiple animal-size concepts, including `SMALL_ANIMALS`, `MEDIUM_ANIMALS`, `LARGE_ANIMALS`, health classes from very small through large, and internal `LA_SIZE_SMALL/MEDIUM/LARGE` names. However, no public ScriptHook native has yet been confirmed that returns one universal Rockstar animal-size enum for a live ped.

The reliable fallback is to use each animal model's world-space bounds from `GET_MODEL_DIMENSIONS`, which this mod already reads and caches, and map them into a few discrete icon scales. That covers every animal model without a hand-maintained species list.

## Questions to resolve before implementation

- Can Rockstar's actual loot/animal size class be read reliably for a live animal, or should model bounds be the authoritative source?
- If using bounds, choose thresholds that make representative animals sensible (small bird/rabbit, fox/coyote, deer/wolf, bear/bison/alligator) without extreme or noisy icon sizes.
- Decide whether to use three sizes or include a fourth “very small” size.
- Verify elevation variants, map zoom levels, herds/overlap, color tinting, and that human/player-horse/collectible blips remain unchanged.

Exploratory only: research and report before implementing.

## issue 5356302676 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/183

Created: 2026-08-06T03:52:24Z; updated: 2026-09-06T13:17:23Z

Exact metadata: [source record](sources/issue-5356302676-0252d6c2ff2983e2cfaf2ff24bb615c9980fb3c57a1fa1dbf909257379caa0f3.json).

**Status: Closed for the animal-marker redesign.** Animals use the distinct marker treatment, stable hostility colors and the game’s discoverable name. The last comment reported a missing vision cone, so this record alone does not prove cone coverage; facing-indicator work is tracked separately in #296.

## issue 5356302676 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/183

Created: 2026-08-06T03:52:24Z; updated: 2026-09-06T13:58:11Z

Exact metadata: [source record](sources/issue-5356302676-5b43c16dd3a7bf64b82c441eaf6c94ea48222befe0a5d1d996a66bf4fc6962cc.json).

**Status: Closed for the animal-marker redesign.** Animals use the distinct marker treatment, stable hostility colors and the game’s discoverable name. The last comment reported a missing vision cone, so this record alone does not prove cone coverage; facing-indicator work is tracked separately in #296.

## comment 5550131124 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/183#issuecomment-5550131124

Created: 2026-08-06T05:13:08Z; updated: 2026-08-06T05:13:08Z

Exact metadata: [source record](sources/comment-5550131124-78390105d7310f99530f3e7442d98f0cd7059e81840836d7110594e71c7c86a4.json).

>However, no public ScriptHook native has yet been confirmed that returns one universal Rockstar animal-size enum for a live ped.
Was your job not to do the research? I don't understand.

## comment 5550131147 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/183#issuecomment-5550131147

Created: 2026-08-06T07:43:27Z; updated: 2026-08-06T07:43:27Z

Exact metadata: [source record](sources/comment-5550131147-96ff672c1dbae10831723b0c72e1de479bb6ecf27cc9229f221820defc1eb3a9.json).

You are right: the research needed to settle the source instead of leaving it as an open question.

Concrete result: there is no confirmed public ScriptHook native that returns Rockstar's `SMALL_ANIMALS` / `MEDIUM_ANIMALS` / `LARGE_ANIMALS` classification for a live ped. `_GET_PED_ANIMAL_TYPE` returns the species/stat hash (`AT_DEER`, etc.), not a size enum. The extracted `stats_group_item_sets.meta` lists those three names only as members of the manual `AnimalGroups` set; it does not provide model membership or a live lookup. Decompiled shop code that returns `SMALL_ANIMALS` does so through a large hard-coded carcass-item switch, proving that path is item/species mapping rather than a universal ped-size getter. Loot data also contains presentation/model size concepts, but no exposed live-ped query was found.

Use model bounds as the authoritative runtime source. `GET_MODEL_DIMENSIONS` works for every loaded animal model, needs no species table, and the current recon implementation already caches bounds by model hash and validates/falls back on bad extents. For the blip, derive a scalar from horizontal footprint plus height, then quantize to a small set of icon scales. This is more robust than pretending Rockstar's several unrelated size taxonomies are one enum.

Recommended implementation decision (not implemented here): four visual buckets so tiny birds/rats do not share a diamond with rabbits; calibrate thresholds from representative model bounds captured by a human runtime probe, clamp the final blip scale, and keep the same white/alpha diamond texture across buckets so vanilla tint/elevation modifiers continue to work. Only recon animal blips should receive the texture/scale; owned horse, human, plant, collectible, and object paths remain untouched.

Static research is complete. Human validation remains for representative bounds/thresholds, map zoom/elevation, herd overlap, and tint/readability. No game launch, asset edit, or implementation was performed.

## comment 5550131157 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/183#issuecomment-5550131157

Created: 2026-08-06T14:42:20Z; updated: 2026-08-06T14:42:20Z

Exact metadata: [source record](sources/comment-5550131157-464f80550118cb65d8e8c65f6bdfcde3dd035165d1638a0f496b8b5daf2b3a6d.json).

Installed in development build `9703EA026B90F542FC82F63CAFD897C135265DBDE1F5DC7B1AB85F6D743A4103`. Test recon animals from tiny through very large: diamond icon, sensible four-level size, tint, elevation, map zoom, and herd overlap. Humans, owned horse, plants, objects, and collectibles must remain unchanged.

## comment 5550131167 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/183#issuecomment-5550131167

Created: 2026-08-06T18:53:22Z; updated: 2026-08-06T18:53:22Z

Exact metadata: [source record](sources/comment-5550131167-836420e8783fd1c9061a7e0593af9d7d510a60e1f0056d786c022a8b1eef26b3.json).

oh my god. i can see them on the map. they're black boxes. how many times are we going to get this error? you've solved this. you've figured this out. you've done this multiple times now, and if at any time you forget, you can just take a look at all the other icons you've added to the game and do whatever you did there.

## comment 5550131184 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/183#issuecomment-5550131184

Created: 2026-08-09T09:04:34Z; updated: 2026-08-09T09:04:34Z

Exact metadata: [source record](sources/comment-5550131184-37f59dc17f53fa21ddf13375fb1c24e1664b7d1e373a9c4421aeaab347356eed.json).

black box. again. unbelievable.

## comment 5550131198 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/183#issuecomment-5550131198

Created: 2026-08-09T11:07:16Z; updated: 2026-08-09T11:07:16Z

Exact metadata: [source record](sources/comment-5550131198-7f5c79fb2bd70c1968887ea7ef9bd2b730d82f41a6a59a9b4c467a2bf4c07b7d.json).

Installed development build 696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53. The animal diamond now links to resident blips, and the complete resident archive (not a partial override) includes the custom tintable sprite at hash E97EE7D4712F6B4599A9AB3A330A0CD643F9FDFA45D22CBC3CEA9F11BBC6DCB8. Test animal size buckets and confirm ordinary vanilla blips remain intact.

## comment 5550131209 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/183#issuecomment-5550131209

Created: 2026-08-10T06:37:42Z; updated: 2026-08-10T06:37:42Z

Exact metadata: [source record](sources/comment-5550131209-b1ae2330570d936ca93d39a720952fbb198677ae96e30759537e6c01bf7e2aeb.json).

Again. There is no excuse for this. So how do you keep messing up? 

## comment 5550131220 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/183#issuecomment-5550131220

Created: 2026-08-10T07:17:00Z; updated: 2026-08-10T07:17:00Z

Exact metadata: [source record](sources/comment-5550131220-7c153948030bc2e2aadd6e921ee9d03efedc5ab6032aa0df62bc47793dead507.json).

Installed combined build AC952387AA9932EFD4AA43C580D4369F0534537A01B0196A529BBC88519551D9. Test animal diamonds from tiny through large, tint/elevation/map zoom, and confirm no black boxes or changes to non-animal blips.

## comment 5550131233 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/183#issuecomment-5550131233

Created: 2026-08-10T09:14:23Z; updated: 2026-08-10T09:14:23Z

Exact metadata: [source record](sources/comment-5550131233-e79301714489e59c6724c1b424e8dd6be3baa0321a61c32e8f68371f0a222ee0.json).

Close, but they don't follow the same blue/grey/red coloring based on attitude like humans do.
Horse blips: black.
Grizzly bear blip: also black?


## comment 5550131239 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/183#issuecomment-5550131239

Created: 2026-08-10T10:39:44Z; updated: 2026-08-10T10:39:44Z

Exact metadata: [source record](sources/comment-5550131239-220341ed1b1a89137b578e9680f1e9bbb773124ef357fde5b1a30e03475a2dd2.json).

<img width="106" height="110" alt="Image" src="https://github.com/user-attachments/assets/88824de1-4966-4c26-b53e-e55ce2fcb7be" />

Okay but there's no outline. I asked you to make it in the style of the vanilla one and specifically mentioned the outline as one of those aspects.

## comment 5550131249 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/183#issuecomment-5550131249

Created: 2026-08-10T10:57:15Z; updated: 2026-08-10T10:57:15Z

Exact metadata: [source record](sources/comment-5550131249-595635a9d1adccff9f44ef0a5daa52a81e5e2bf1a72c3f911e47974066375bc4.json).

Returned-test root cause found and repaired in source: the animal-diamond generator and verifier explicitly forced every nontransparent pixel white, so a contrasting outline was impossible. The regenerated 8x-supersampled icon now follows the vanilla pattern: white tintable center, opaque near-black rim, feathered alpha. Installed logs already prove blip creation, so this is an art repair. Remains actionable until the rebuilt inventory archive is installed and the rim is visible under red/blue/grey styles.

## comment 5550131265 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/183#issuecomment-5550131265

Created: 2026-08-10T13:23:40Z; updated: 2026-08-10T13:23:40Z

Exact metadata: [source record](sources/comment-5550131265-bf1ba21c21d13c395328b5baed3f465918cd723b8e06218cc9cf828f3953369a.json).

The rebuilt resident archive now contains the corrected outlined animal diamond together with every older custom map icon; no icon uses the rejected standalone dictionary anymore. After the next full game restart, confirm the animal diamond retains its dark rim under red/blue/grey tint and that the older custom markers are artwork rather than black squares.

## comment 5550131279 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/183#issuecomment-5550131279

Created: 2026-08-10T15:04:01Z; updated: 2026-08-10T15:04:01Z

Exact metadata: [source record](sources/comment-5550131279-30412565fc023a6a110b9303ca8e0118012f1c06a0dab6ddf34a1cf970af3f50.json).

Grizzly bear. Red on my minimap. Grey on the map? Then I walk away slightly and it's grey on the minimap too? Oh no now he's back to red. Now he's grey again. What the fuck?

## comment 5550131290 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/183#issuecomment-5550131290

Created: 2026-08-10T15:05:24Z; updated: 2026-08-10T15:05:24Z

Exact metadata: [source record](sources/comment-5550131290-363190c0d6b3ccf69c2cad6fe08769b5a6fb001dd5d7e76dd26a35f36a371ae0.json).

<img width="143" height="166" alt="Image" src="https://github.com/user-attachments/assets/3d2b2799-8016-4f76-8b16-e93e6561aae0" />

I'm also noticing that the blips have this tiny black thing next to them? Looks like the aborted attempt of those black-BG labels all the other map blips have. Would be cool if you could give them the label of the animal they are so you can mouse over them and see what they are specifically!

## comment 5550131296 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/183#issuecomment-5550131296

Created: 2026-08-10T17:01:00Z; updated: 2026-08-10T17:01:00Z

Exact metadata: [source record](sources/comment-5550131296-c31eddac8262c49137ea0d8af4ad0101e3dd3253b7ac29038e6a1c0bb9bcd862.json).

The corrected animal blips are installed. The stray black dash came from an aborted police-search-cone modifier and is removed. Hostile state now survives transient combat dropouts instead of flickering red/grey, allies can still clear it, and the map hover name comes from Rockstar's discoverable-animal label. Test a hostile animal at several distances and hover its full-map marker.

## comment 5550131311 — Lexer-Lux

Source: https://github.com/Lexer-Lux/Lexeditor/issues/183#issuecomment-5550131311

Created: 2026-08-11T02:13:54Z; updated: 2026-08-11T02:13:54Z

Exact metadata: [source record](sources/comment-5550131311-890c5b24a3e37617e9927b712726e3ac9edfee4393714ab0d67a9a865f65b344.json).

<img width="153" height="84" alt="Image" src="https://github.com/user-attachments/assets/2cb4c718-13b6-4e27-8cbb-3c8f521e83c3" />

This animal doesn't seem to be getting a vision cone for some reason on the minimap? Can you tell why? They should all get cones when they go on the map.
