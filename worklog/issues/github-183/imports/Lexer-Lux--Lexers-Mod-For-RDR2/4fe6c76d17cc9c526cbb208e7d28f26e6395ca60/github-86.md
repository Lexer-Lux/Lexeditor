# GitHub issue #86 — recon animal diamonds

## Implemented

- Added a white/alpha `lex_blip_recon_animal` diamond derived against
  Rockstar's extracted 32x32 small-human-dot asset and packed it into the
  existing `lex_blips` dictionary.
- Registered `LEX_BLIP_RECON_ANIMAL` with Rockstar's ordinary ambient
  higher/lower elevation linkages so map tint and elevation behavior remain
  engine-owned.
- Applied the icon only to nonhuman ped targets created by recon. Humans keep
  their existing icon/scale; the player's horse has no recon-created map blip;
  object/plant/collectible paths were not changed.
- Used cached `GET_MODEL_DIMENSIONS` bounds as the authoritative size source.
  The cube root of model volume is quantized into stable 0.45, 0.55, 0.68, and
  0.82 scales for tiny, small, medium, and large animals.

## Evidence boundary

Static checks prove routing, asset/linkage integrity, stable model-based sizing,
and isolation from human/object paths. In-game confirmation is still required
for representative species, herds/overlap, tint, map zoom, and elevation.

## 2026-08-06 — root cause of "they're black boxes"

Lexer, on the installed build: *"i can see them on the map. they're black boxes.
how many times are we going to get this error? you've solved this… take a look
at all the other icons you've added to the game and do whatever you did there."*

He is right that it was already solved, and the diamond art was never the fault.

**Root cause: the texture dictionary was never requested.**
`LEX_BLIP_RECON_ANIMAL` is declared at `MyOverhaul/blipdata.ymt:5574-5581` with
`<TextureDictionary>lex_blips</TextureDictionary>` (line 5576), and the sprite
really is shipped — `GameplayTweaks/icons/build_lex_blips/dds/
lex_blip_recon_animal.dds`, packed into `MyOverhaul/stream/lex_blips.ytd`. But
`lex_blips` is a **streamed** dictionary, not a resident one, and `recon.cpp`
contained no reference to it at all: no `REQUEST_STREAMED_TEXTURE_DICT`, no
`HAS_STREAMED_TEXTURE_DICT_LOADED`. A blip whose dictionary is not resident
renders as an untextured quad — the black boxes. This is the "white squares"
defect one layer down: not a wrong name, an unloaded dictionary.

The other icons Lexer pointed at do it correctly: `collectibles_map.cpp:820-834`
(`ensureLexBlipTextures`) requests `lex_blips` on a periodic hook, and it is
called from `refreshNativeCollectibleBlips()` at line 840. That is why the
collectible icons render and the recon diamond did not.

### Changed in `GameplayTweaks/modules/recon.cpp`

- `reconEnsureBlipTextures()` now requests `lex_blips` alongside the other
  dictionaries, every frame, from the top of `updateReconTagging` (before every
  early return), using the same native pair as the working module
  (0x54D6900929CCF162 / 0xC1BA29DF5631B0F8).
- `configureReconBlip()` logs, once per launch, `lex_blips exists=<n>
  loaded=<n>` — `DOES_STREAMED_TEXTURE_DICT_EXIST` 0x7332461FC59EB7EC and
  `HAS_STREAMED_TEXTURE_DICT_LOADED`, the same probe pair and the same
  distinction (`not reachable by the mod loader` vs `not requested`) that
  `collectibles_map.cpp:829-832` uses. A future black box is therefore
  diagnosable from the log rather than by another guess.
- The icon assignment, the four size buckets, and the human/horse/plant/object
  paths are unchanged.

### The "vanilla diamond" question, answered against shipped data

Both parts were checked rather than assumed:

- **There is no vanilla diamond blip.** All 321 sprites of the resident `blips`
  dictionary were unpacked at `GameplayTweaks/icons/vanilla/png/blips/` and
  measured: for each, the alpha mask's fill ratio against a centred rotated
  square. Not one centred sprite reaches a diamond fill. The single high-scoring
  sprite, `blip_ambient_new.png`, is a small badge glyph offset into the
  top-right corner, not a centred marker. Rockstar's own ped markers are round
  dots in three authored sizes — `blip_ambient_ped_small.png`,
  `blip_ambient_ped_medium.png`, `blip_ambient_npc.png` — and `blip_animal.png`
  is the paw this issue exists to replace. A diamond therefore has to be custom
  art, which is what `GameplayTweaks/icons/tools/prepare_lex_blips.py:66-88`
  already authors from `blip_ambient_ped_small.png` as the reference.
- **Rockstar's size-scaling mechanisms are two, and both are real.** Data-side:
  authored per-size linkages (`BLIP_AMBIENT_PED_SMALL` / `_MEDIUM`,
  `blipdata.ymt:1503` and `:1511`, each with its own HIGHER/LOWER elevation
  linkage) selected by `BM_SetLinkage` styles such as `DEFAULT_PED_SMALL` /
  `DEFAULT_PED_MEDIUM` (`blipdata.ymt:8255`, `:8277`); plus the `BM_SetScale`
  modifiers `BLIP_MODIFIER_SCALE_1` (1.2) and `BLIP_MODIFIER_SCALE_2` (1.5) at
  `blipdata.ymt:11071-11084`, applied with `ADD_BLIP_MODIFIER`. Script-side:
  `MAP::SET_BLIP_SCALE`, which Rockstar drives from live data at
  `_downloads/RDR2-Decompiled-Scripts/script_rel/short_update.c:27727`.

  The data-side path gives three fixed steps against one authored art size; the
  scale channel gives the four continuous-source buckets #86 asked for over
  every animal model without a species table, and keeps a single tintable
  diamond so the engine's tint and elevation rules still apply. The existing
  `SET_BLIP_SCALE` implementation is therefore kept, now with its provenance
  recorded in the source. `BLIP_MODIFIER_SCALE_*` is documented in the same
  comment as the alternative that was considered and why it was not used.

### Standing risk, not fixed here (not an owned file)

`GameplayTweaks/icons/README.md` records a second, separate failure of the same
family: *"The native map renderer rejected that separate dictionary as black
squares"*, fixed by `build_blips_override.ps1`, which rebuilds the resident
`blips` dictionary from all 321 vanilla sprites and appends the custom ones.
That override is currently **disabled** —
`MyOverhaul/stream/_disabled/blips.ytd.disabled` — and every `LEX_BLIP_*` entry
except `LEX_BLIP_NEWSPAPER_AVAILABLE` (`blipdata.ymt:5558-5565`) still points at
`lex_blips`. If the once-per-launch probe added above reports
`exists=1 loaded=1` and the diamond is still a black box, that is the remaining
cause and the fix is asset-side: re-enable the `blips` override and repoint
`LEX_BLIP_RECON_ANIMAL` at `blips`. Those files are outside this pass.

No build, install, commit, push or label change was performed.

## Current actionable pass

The remaining dictionary risk was taken out of the linkage: the animal diamond
now names the resident `blips` dictionary. `prepare_blips_override.py` rebuilds
the complete resident archive and appends `lex_blip_recon_animal`; it does not
replace the archive with only custom textures. The generated source and LML
archives match at SHA-256
`E97EE7D4712F6B4599A9AB3A330A0CD643F9FDFA45D22CBC3CEA9F11BBC6DCB8`.
The issue verifier checks the resident linkage, full-size archive, tintable art,
elevation helpers, and four model-bound scale buckets. In-game acceptance must
confirm both the diamond and ordinary vanilla blips.

## Integrated release

The resident `blips.ytd` is live through the game folder's `MyOverhaul`
junction and hashes `E97EE7D4712F6B4599A9AB3A330A0CD643F9FDFA45D22CBC3CEA9F11BBC6DCB8`.
The companion development ASI is
`696933A6D99BCA262E85B19B723998E40E6B636BBC3278BFB9A85A2F12DEEB53`.
Workflow after install: `test me`.

## 2026-08-10 actionable correction: use the proven resident dictionary

The second installed test still rendered a black box, disproving the appended
resident-`blips` archive route. The project already has one custom map glyph
that uses a different, proven path: `LEX_BLIP_CAMPFIRE_INACTIVE` links to the
complete `INVENTORY_ITEMS_MP` replacement, whose builder preserves all 432
Rockstar textures before appending custom textures.

The same builder now appends `lex_blip_recon_animal`, and
`LEX_BLIP_RECON_ANIMAL` links to `INVENTORY_ITEMS_MP`. The rebuilt archive has
438 textures (432 Rockstar plus six custom) and is staged at
`MyOverhaul/stream/inventory_items_mp.ytd`. The #86 verifier now requires this
exact proven route, the complete multi-megabyte archive, tintable diamond art,
elevation helpers, and isolated four-bucket animal sizing. It passes. Runtime
acceptance after the combined hash-verified install remains required, so #86
stays `actionable` until then.

## 2026-08-10 returned-test repair: attitude colors

The installed diamond was finally the correct silhouette, but horse and grizzly
diamonds were black instead of following the human blue / grey / red attitude
colors. The source art was checked directly: every non-transparent pixel in both
the 32x32 PNG and prepared 128x128 DDS is white, so the texture was not baking
in black.

The black color came from two source decisions in `recon.cpp`:

- `reconDispositionFor()` returned one unconditional `Animal` disposition
  before reading relationship/combat state, so no animal could become ally,
  neutral, or enemy.
- `reconBlipStyle(Animal)` selected `BLIP_STYLE_PICKUP_ANIMAL`.
  `MyOverhaul/blipdata.ymt:14148-14161` is authoritative for that style and
  explicitly applies `BM_SetColor/COLOR_BLACK`.

Animal species and attitude are now independent. All peds, human or animal, use
the same relationship/combat classification. Enemy selects
`BLIP_STYLE_ENEMY` (`COLOR_ENEMY`), ally selects
`BLIP_STYLE_FRIENDLY_ON_RADAR` (`COLOR_FRIENDLY`), and neutral selects
`DEFAULT` (`COLOR_GREY`). Nonhuman targets still receive
`LEX_BLIP_RECON_ANIMAL`, the four model-bound size buckets, and the animal centre
glyph; only their engine-owned tint style changes. The bounded 250 ms live
disposition maintenance continues recreating a blip when attitude changes.

`python tools/reverse-engineering/verify_recon_animal_diamonds_issue_86.py`
passed. It now verifies that animal attitude is not collapsed, requires the
three authoritative style routes, rejects `BLIP_STYLE_PICKUP_ANIMAL`, preserves
species-based icon routing, and checks that every opaque PNG pixel is white for
engine tint. This pass was source/static only; no asset rebuild was necessary,
and no ASI build/install, shared dispatcher/INI/manifest edit, or GitHub
mutation was performed.

## 2026-08-10 returned-test repair: vanilla-style outline

The next installed test proved the shape and tint correction, but Lexer
reported that the diamond still lacked the contrasting outline he had
explicitly requested from the vanilla marker style. The source assets explain
why: the custom generator authored every nontransparent pixel as white, and the
#86 verifier enforced that exact all-white mask. That made an actual contrasting
outline impossible even though alpha antialiasing made the preview edge look
slightly dark against some backgrounds.

Rockstar's extracted primary reference,
`GameplayTweaks/icons/vanilla/png/blips/blip_ambient_ped_small.png`, is two-tone:
an opaque white/tintable centre surrounded by dark RGB pixels with a feathered
outer alpha edge. The #86 generator now preserves that presentation on the
custom silhouette. It authors an 8x-supersampled diamond with a white inner
diamond and a near-black opaque rim, then downsamples to the tracked 32x32 RGBA
source. Engine attitude tint can still colour the white centre while the dark
rim remains contrasting, just as on the vanilla human marker.

The verifier no longer accepts the rejected all-white mask. It requires the
two authored distance-field layers, a white opaque centre, dark opaque cardinal
rim pixels, transparent corners, and a fill larger than the rim. The installed
log already proves the recon module created entity blips (`mark blip ...
exists=1`), so this returned defect was asset presentation rather than missing
execution or routing.

This pass updated the issue-owned source art/generator and static verifier only.
Integration must rebuild the complete `INVENTORY_ITEMS_MP` replacement from the
new PNG before installation. Runtime acceptance then requires a red enemy, blue
ally, and grey neutral animal diamond to retain a clearly visible dark outline
at representative map zoom levels and across the four size buckets. No ASI or
YTD build, installation, shared dispatcher/INI/manifest edit, or GitHub
mutation was performed here.
## 2026-08-10 combined release

- Release ASI built successfully: `FC692F30C1EFB7B3DE5B101D08939FE1319676F2C50BD13768DAC948AAC43589`.
- RDR2 was running, so one hidden payload-only installer was queued. The issue remained actionable pending game-root hash verification.
- Current installed test artifact was later superseded, without an issue-owned source change, by `CDF66230508FBDB4AAF3A59D2B571A0229F6DD1E7FE7244F36AC9C6F7D0C23A2`.
## fuckups.txt recurrence audit

- The prior generator and verifier encoded an all-white icon, making the requested contrasting outline impossible while still reporting success.
- The source is now a rendered two-tone diamond derived from Rockstar's white-centre/dark-rim convention, and the rebuilt archive contains that asset. Actual red, blue, and grey map contrast at multiple zooms remains the acceptance boundary.

## 2026-08-10 recurrence audit before the latest repair

- **Primary evidence/reference:** the latest live comments report one grizzly
  oscillating red/grey across minimap/map and a small black artifact beside the
  diamond. The follow-up requests the animal name on hover. The authoritative
  sources are the current blip handle/style lifecycle, installed recon log, the
  exact `BLIP_STYLE_*` entries in `blipdata.ymt`, and Rockstar's named-blip
  script calls. Texture claims must be checked against the complete resident
  `INVENTORY_ITEMS_MP` archive, never a linkage table or the rejected
  standalone dictionary.
- **Sanctioned path:** keep one stable animal blip handle and change style only
  when a proven relationship/combat state changes; attach the actual model's
  localized display name through Rockstar's blip-name native. Do not alternate
  styles from transient line-of-sight/aim state or manufacture a second label
  sprite.
- **Execution proof:** log old/new disposition inputs, chosen style, handle
  recreation count, and resolved name. A `mark blip` call alone proves neither
  stable tint nor a usable hover label.
- **Player-visible acceptance:** the same hostile grizzly remains red on map and
  minimap without red/grey flicker, ally/neutral animals retain blue/grey, the
  outlined diamond has no stray black artifact, and hover shows the species
  name without changing non-animal blips.
- **Every per-frame native:** disposition/name mutation must remain on the
  existing bounded maintenance cadence. Map marker rendering is engine-owned;
  no new per-frame texture request, blip recreation, or style fight is allowed.

## 2026-08-10 returned-test root cause and repair

The screenshot's small black dash was not part of the diamond art or an aborted
label background. `configureReconBlip()` explicitly attached
`AUTO_MODIFIER_COP_SEARCH_CONE` to every recon blip and rotated it during
maintenance. That law-search heading wedge was the exact second glyph beside
the symmetric diamond. Both the modifier and the now-ownerless rotation loop
were removed.

The red/grey oscillation came from recreating a tagged blip whenever raw
`IS_PED_IN_COMBAT`/relationship output changed. A grizzly can transiently drop
the combat task with range while remaining the same hostile tagged animal, so
the old 250-ms maintenance alternated `BLIP_STYLE_ENEMY` and `DEFAULT`. Recon
now latches Enemy once observed and does not downgrade it on a Neutral combat
dropout; an explicit Ally relationship can clear the latch. Blip recreation
remains bounded and occurs only when that stable disposition really changes.
The transition log records previous, observed, stable, relationship, combat,
latch, and cumulative recreate count.

Animal blip creation now resolves species through Rockstar's own
`PLAYER::_0x0139637A3BFF8B6D` discoverable name/type pair, localizes it with
`_CREATE_VAR_STRING(0, nameHash)`, and passes it to the established
`SET_BLIP_NAME` wrapper. This is the animal info-box label path in
`short_update.c:31880-31882` and runs only when a blip is configured. A bounded
line records both hashes and whether a nonempty label was applied.

`python tools/reverse-engineering/verify_recon_animal_diamonds_issue_86.py`
verifies the stable latch, absence of the search cone/rotation, authoritative
species label path, outlined resident art, linkage, and isolation. Runtime
acceptance remains: a hostile grizzly stays red on minimap and pause map as
distance/combat tasks change; no black dash appears; hovering the map diamond
shows the localized species; explicit friendly animals may still become blue.
No build/install/shared file or GitHub state was changed.

## 2026-08-11 recurrence audit: animal vision cones

- **Primary evidence/reference:** Lexer's latest screenshot reports a tagged
  animal diamond without the expected minimap vision cone. The previous repair
  proved that `AUTO_MODIFIER_COP_SEARCH_CONE` renders a separate black dash, not
  the requested animal-awareness cone. The only acceptable source is Rockstar's
  shipped blip data or a Story script that applies the exact cone mechanism to
  an entity-backed ped blip.
- **Sanctioned path:** preserve the resident `INVENTORY_ITEMS_MP` diamond, its
  attitude style, stable hostility latch, species name, and size scale. Add a
  cone only through a named Rockstar blip style/modifier that is proved to own
  the ordinary ped-facing cone. Do not restore the rejected police-search
  modifier or invent another plausible hash.
- **Execution proof:** a bounded configuration log must record the blip handle,
  selected cone mechanism, current heading, and a post-call blip-exists readback.
  A source constant or setter call alone is not execution proof.
- **Player-visible acceptance:** every tagged animal diamond has one correctly
  oriented awareness cone on the minimap, with no black dash, duplicate glyph,
  tint flicker, or change to human/object/plant blips.
- **Cadence:** configure the cone once and update heading only on the existing
  250 ms tag-maintenance transition. No per-frame modifier or rotation fight is
  permitted.

## 2026-08-11 evidence result: source-only cone path is not safe yet

`MyOverhaul/blipdata.ymt` has seven `BM_ShowHeading/LOSCone` entries, all checked
directly against their complete action blocks:

- `BLIP_MODIFIER_ENEMY_ON_GUARD_DISAPPEARING` also sets unalerted-enemy color,
  applies the `AIBlips` timed fade, and pushes `AUTO_ENEMY_ANGRY`.
- `BLIP_MODIFIER_ENEMY_ON_GUARD` also sets unalerted-enemy color and pushes
  `AUTO_ENEMY_ANGRY`.
- `BLIP_MODIFIER_NEUTRAL_ON_GUARD` also sets objective color, scale 1.1, and the
  objective category.
- `BLIP_MODIFIER_ENEMY_STEALTH_KILL` also sets unalerted-enemy color.
- `BLIP_MODIFIER_ENEMY_IS_ALERTED` also sets enemy color.
- `AUTO_MODIFIER_COP_SEARCH_CONE` is the only color-neutral block, but it is the
  exact modifier removed after it rendered as the reported black dash beside
  the diamond.
- `AUTO_MODIFIER_WITNESS_LAW` also replaces the centre linkage with
  `BLIP_AMBIENT_LAW`.

The file's top-level `DefaultLOSCone` is `BLIP_NPC_SEARCH`, but no source native
turns that linkage on without one of the `BM_ShowHeading` styles above.
Re-adding the cop modifier would reproduce a known failed player-visible result;
the other six would damage the diamond's red/blue/grey attitude, scale, fade,
category, or centre glyph.

No cone change was shipped in this source-only pass. A safe next step needs a
recon-specific data modifier containing only Rockstar's
`BM_ShowHeading/LOSCone` action, followed by a rendered minimap check, or a
bounded in-game comparison probe if that modifier still renders as a dash. The
current diamond, outline, scale, attitude latch, and hover name remain intact.
Issue #86 therefore still has real implementation work and must remain
`actionable`.

## 2026-08-11 data-layer recurrence audit before cone repair

- **Primary evidence/reference:** all seven shipped `BM_ShowHeading` actions
  whose value is `LOSCone` were opened in `MyOverhaul/blipdata.ymt`. The
  heading action has only a `Value` and an optional action-local
  `ColorOverride`. Rockstar's cleanest source shape is the one-action
  `AUTO_MODIFIER_COP_SEARCH_CONE`, but that modifier name and its observed
  black-dash result are rejected. Story proves that an entity blip accepts a
  heading modifier once: `act_caunc_rustling.c:3935-3938` creates two
  `BLIP_STYLE_ENEMY` entity blips and applies
  `BLIP_MODIFIER_ENEMY_ON_GUARD`; it does not script their rotation.
- **Sanctioned path:** add a recon-owned modifier key whose only action is the
  schema-proven `BM_ShowHeading` / `LOSCone` / action-local `COLOR_WHITE`
  block, then apply that exact modifier only when recon configures a nonhuman
  entity blip. Do not inherit or push a police/enemy style, change the centre
  linkage, or add color, fade, scale, category, threat, or conditional actions.
- **Execution proof:** the configure-time record must identify the modifier,
  target heading, blip handle, and a post-call blip-exists readback. Static XML
  parsing must prove that the custom modifier has exactly one action and that
  it cannot mutate disposition color, fade, scale, category, or centre glyph.
- **Player-visible acceptance:** each tagged animal diamond has one white
  awareness cone that follows the animal on the minimap. The diamond retains
  its red, blue, or grey centre, dark rim, size bucket, species hover name, and
  elevation behavior. No black dash or duplicate cone appears.
- **Cadence:** apply the modifier only when a recon animal blip is created or
  recreated. The entity-attached blip owns heading updates. No per-frame or
  250-ms rotation write is permitted.

## 2026-08-11 data-layer cone repair

The material difference from the rejected path is heading ownership, not the
new modifier name. The tracked rejected source applied
`AUTO_MODIFIER_COP_SEARCH_CONE`, wrote `SET_BLIP_ROTATION` when it configured
the blip, and wrote rotation again from the live tag loop. The replacement
modifier's only action is behavior-equivalent to Rockstar's cone action, but
recon now applies it once and never writes blip rotation. This matches Story's
entity-owned pattern in `act_caunc_rustling.c:3935-3938`: create an entity blip,
apply `BLIP_MODIFIER_ENEMY_ON_GUARD` once, and leave heading updates to the
attached entity.

`MyOverhaul/blipdata.ymt` now defines
`LEX_BLIP_MODIFIER_RECON_ANIMAL_CONE` with exactly one action:

- `BM_ShowHeading`
- `Value=LOSCone`
- action-local `ColorOverride=COLOR_WHITE`

It has no parent, exclusive type, linkage, general color, fade, scale,
category, threat, or conditional action. It therefore cannot replace the
diamond centre, change its red/blue/grey disposition tint, alter its four size
buckets, or push another style. Recon applies this modifier only inside the
existing nonhuman branch of `configureReconBlip()` and records modifier return,
target heading, and post-call blip existence.

The actual resolved presentation was inspected rather than inferred. The
file's global `DefaultLOSCone` is `BLIP_NPC_SEARCH`; that linkage uses Rockstar's
resident `blips` dictionary and the extracted `blip_npc_search.png`. The source
texture is 32x32 transparent light cone art with an opaque white tip. It is not
a dash or a custom texture. The schema exposes no per-modifier cone linkage or
cone scale field, so this is the only source-backed clean data route.

The #86 verifier parses both the modified and pristine shipped XML. It proves
that all seven shipped LOS-cone action schemas are the reference, the custom
modifier has exactly one allowed action, the default cone resolves to the
resident Rockstar linkage, the extracted art is transparent light cone art,
and recon contains no police modifier or scripted rotation call. Adjacent recon
verifiers for the crash guard, #94, #176, #162, and plant #96 also pass.

Runtime acceptance remains required. Each tagged animal must show one correctly
oriented white cone while its diamond retains attitude tint, dark outline,
scale, label, and elevation behavior. If the clean entity-owned path still
renders as a dash, this YMT schema cannot select a different cone asset or scale
for one modifier; a different renderer would be required instead of another
modifier guess.
