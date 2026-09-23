# Final Fantasy VII Rebirth (ff7r2)

## Scope and audited baseline

This note is Rebirth-only. Remake remains a separate plugin/worker under plugins/ff7r.
Shared Unreal/helper framework changes are blockers here rather than changes this PR competes for.

The work began from master a47f0a57f8b44113b0ca1d42e5795f59f707372a and was last reconciled wholesale against 72ee978a2ff36686a6349696b19860057356468a. Live master was re-audited at 76ec7c3b9b289f1d52bcf684c691d5020619c3f6; it has advanced substantially, so this worker adopted only Rebirth-local compatible changes instead of overwriting concurrent shared work.

Current-master references read for this audit:
- AGENTS.md — 41355ce0b783c55a03ad250ed279666f785c6e67
- docs/ADDING_A_GAME.md — 7fe6d35dd82fa3fe4e6378ca558ecbb0a316c4c0
- docs/UI-MANUAL.md — 14a3269992031d7e7893fcb127728a48b944e71f
- ui/component-catalog.js — a11e52e31ee92bce495c6cbf54a66d4597d52139
- plugins/blank/editor.html — b0b235d010952bf0c7524dcce172ef72f7cf63e4
- plugins/rdr2/editor.html — 899bfdb45cbf25da55aed43a590db6ee476b523b, including shared paged Table + Detail and Data Map patterns
- codex/ff7r/README.md — 5a25913ede861eb84ba30419ab21a47a0fbee8c6, used only where Remake/Rebirth Unreal context is explicitly shared

Still unavailable on that master:
- codex/ff7r2/ (this PR creates the Rebirth codex)
- a game-specific worklog/ff7r2/ (this PR keeps its concise task handoff under worklog/requests instead)

The component catalog did not exist at the original branch baseline; it was added on master during this PR and was re-read rather than retaining the obsolete unavailable-path note.

## Public Rebirth evidence

### DataObject

Synthlight/FF7R2-DataObject-Parser is CC BY-NC 4.0. It is used only as public format
documentation and a cross-check; no implementation code is vendored or adapted.
It documents original IoStore-state Rebirth DataObjects and published
PlayerParameter fields including HPMax, MPMax, Strength, Vitality, Magic, Spilit,
Dexterity, Luck, Experience, SPMax and TreeLevel.

Yoraiz0r/FF7RebirthDataObjectEditor is MIT. It independently confirms editing
Rebirth DataObject .uasset files after extraction while keeping them in their
original IoStore state and demonstrates byte-proxy editing as a conservative write path.

Lexeditor's independent bounded implementation therefore:
- reads real row FName identity and property descriptors;
- exposes only fixed-width scalar values that can be patched in place;
- follows proved _Array pointers and decodes their elements read-only using the
  property's underlying type and documented alignment;
- keeps FString/FName writes, array writes and browser-unsafe 64-bit integer
  edits disabled;
- validates scalar/array storage bounds and finite floats;
- patches a copy of the source bytes and preserves every untouched byte;
- rejects unproved package shapes rather than falling back to raw hex/files editing.

PlayerParameter remains the writable gameplay slice. BattleItemPossession has
a separate read-only Formulae view when an extracted source asset is supplied:
real row FName identity and array elements are visible, but no
BattleItemPossession file is staged or written. Synthetic fixtures prove no-op
byte preservation, name/int/byte array decoding, out-of-bounds pointer rejection
and rejection of attempted array edits without mutation.

BattlePlayerParameter is now a separate Partial/read-only Battle Params slice.
Synthlight's public property list and narknon/FF7R2UProj generated declarations
independently establish a distinctive typed storage signature, so Lexeditor can
validate the supplied table and show real row FName identities, fixed-width
scalars and decoded arrays without guessing the table. Its scalar gameplay
meaning, enum domains and safe edit ranges are not established publicly, so
Lexeditor deliberately exposes no BattlePlayerParameter save/staging route even
though the lower-level parser can mechanically decode those storage types.

### IoStore extraction

trumank/retoc v0.1.5 is MIT and supports DirectoryIndex IoStore containers,
including list/path discovery and extraction of a selected raw chunk.

Pinned Windows release reviewed:
- retoc_cli-x86_64-pc-windows-msvc.zip
- SHA-256 cc036b06ad3bdcf7003690b00d82719980c374e48a95bf0654f9959148d263aa

Issue #469 reports Rebirth UTOC version 2 / DirectoryIndex and an unencrypted
pakchunk3-WindowsNoEditor containing PlayerParameter and BattlePlayerParameter.

retoc is not automatically invoked by this PR. Its Oodle loader can fetch
oo2core_9_win64.dll when absent. Rebirth itself does not provide that DLL as a
loose redistributable file, so Lexeditor will not silently acquire or bundle it.

### FF7R2 packaging

matyamod/UnrealReZen branch ff7r is GPL-3.0 and is the public FF7R2-specific
packaging reference. Its GUI/source establish GAME_UE4_26, mount point
../../../End/Content/, top-only game archive scanning, and a Rebirth-specific
dependency-manifest workaround.

Release reviewed: ff7r2_v1, asset UnrealReZen_FF7R2_815f48a.zip.

Lexeditor does not register UnrealReZen as a second shared helper because
GamePlugin still exposes one managed helper slot and Rebirth already uses it for
Shader Injector. The candidate route is instead dependency-explicit: the user
must supply both LEXEDITOR_FF7R2_UNREALREZEN and LEXEDITOR_FF7R2_OODLE local
paths. The reviewed FF7R2 release references CUE4Parse 1.1.1, whose Oodle
helper checks for oo2core_9_win64.dll before entering its downloader. The builder
therefore requires a matching CUE4Parse/1.1.1 dependency manifest and requires
LEXEDITOR_FF7R2_OODLE to point to an existing oo2core_9_win64.dll already beside
the explicit UnrealReZen executable. Lexeditor runs UnrealReZen from that tool
directory and does not download, copy or relocate Oodle. It uses Zlib package
compression and never implements or calls a dependency downloader itself. The
release's downloader explicitly disables HTTP proxy use, so proxy environment
variables are not treated as a safety boundary.

The exact FF7R2 command contract is GAME_UE4_26,
--mount-point ../../../End/Content/, --game-dir-top-only, game archives from
End/Content/Paks, and staged content rooted at project/content/End/Content.
Output is always an isolated project/build/ff7r2-candidate-* directory containing
Lexeditor-FF7R2_P.pak/.utoc/.ucas plus a manifest with staged/tool/output hashes.
The builder now treats every regular file beneath content/End/Content as an
explicit candidate input: staged symlinks are refused, every input path/size/hash
is recorded, and the complete file set plus hashes are checked again after
UnrealReZen exits. This closes the old PlayerParameter-only audit gap while
keeping the candidate reusable for future proved Rebirth editors. The builder
never copies that candidate to the installed game and marks it acceptedInGame=false.
Current public Rebirth mod instructions consistently place accepted
.pak/.utoc/.ucas triples in End/Content/Paks/~mods; that remains a manual
acceptance step until Lexeditor has proved collision/removal behavior in-game.

f80h's public FF7 Rebirth Load ordering article, added 2026-08-04 and edited
2026-08-08 after patch 1.005, documents the native UE4.26 precedence rule used
by the current read-only audit: a higher purely numeric component immediately
before _P wins (base/_0_P = effective 100, _1_P = 200, _2_P = 300, and so on);
at equal patch level the case-insensitively smaller complete package path wins
because packages are mounted in descending path order and later mounts win.
Directory components participate in that complete-path comparison; directory
depth has no separate priority. Lexeditor scans only package filenames/paths,
does not unpack external mods, and reports incomplete or unclassifiable triples
instead of guessing. Candidate manifests record the observed read-only stack
snapshot plus the candidate's base patch level so manual in-game acceptance has
reproducible load-order context.

The current FF7 Rebirth Vortex extension is version 0.5.3 (2026-08-12); its
public changelog also exposes pak load-order sorting/deployment and its author
notes that Rebirth pak/ucas/utoc loading does not support symlink deployment.
That is ecosystem corroboration only: this PR neither depends on Vortex nor
copies its implementation.

A real package candidate cannot be produced in the agent environment because it
has no Rebirth installation/archive set and no user-supplied Oodle DLL. The
candidate builder and refusal/isolation tests are nevertheless complete and
exercise the exact command, no-install boundary, adjacent explicit Oodle
requirement, tool/dependency hash stability, missing-dependency refusal, and
cleanup on failure.

## Theme and rendered browser evidence

The Rebirth theme intentionally uses no copied Square Enix art, fonts, audio or
other proprietary assets. Public menu references were used only to identify the
game's dark surface / luminous blue selection / white-text visual vocabulary.
Lexeditor implements that with original CSS tokens (#3f7fd0 accent, #2a4a72
highlight, #f2f7ff accent text) on the shared shell. The current master removal
of a game-specific detail-label width override was adopted so shared sizing owns
the layout.

The most recent rendered artifact inspected before this feasibility pass was
ff7r2-rendered from exact head
cd04c60d2bf30f5301d8d78676d3f66d9832cbe6, workflow run 35811594406. Browser,
Ubuntu and Windows jobs all passed; artifact digest
b9be3f73ac6c7b253fd182a7c2857aa09e7c56789db53b5edb8fd5ab0fb1fa8f.
Desktop Characters, narrow Characters, simulated 150%, Formulae, Data Map,
Information and Tweaks were visually inspected and usable. The split
Table+Detail layout remained intact at narrow/150%, and Formulae read-only
evidence text/fields remained reachable. This is rendered browser evidence,
not installed-app/game acceptance.

The Battle Params view and native load-order Information slice in this
feasibility pass were implemented after cd04c60 and therefore require a fresh
exact-head rendered artifact before they inherit rendered evidence.

## Current public leads for unresolved requests

The issue audit was refreshed on 2026-09-22 rather than treating the five open
gameplay requests as one generic IoStore blocker. Synthlight's generated Rebirth
constants are used here as naming/schema evidence only; they do not prove runtime
meaning by themselves.

- BattlePlayerParameter: generated declarations at audited commit
  ae73efa89db7e48fc7f425dec0847a0208c15b80 identify CommandAbilityID_Array,
  EnableAerialShortCut, UniqueAbilityType0, UniqueAbilityParameterValue_Array,
  KeyDownTime, KeyDownEffectCreateTime, guard/dodge/limit arrays and related
  FName fields with concrete storage types. Synthlight independently publishes
  the matching property names. This is enough to validate and display a supplied
  BattlePlayerParameter structurally; searches for these names did not expose
  documented gameplay domains/ranges. Two current public gameplay mods independently
  demonstrate that real BattlePlayerParameter packages are used to alter Prime Mode,
  Overcharge, Ward Shift, Vengeance and charge-state behavior, but their public pages
  still do not publish a field/value/range mapping that Lexeditor can safely turn into
  semantic controls. The new Battle Params view is therefore Partial/read-only rather
  than speculative editing.
- #470 Chocobo whistle: ResidentParameter publicly names
  CallChocoboAtFieldActionDistanceParamRatio0/1. The public generated Rebirth SDK
  also exposes AEndLocationVolume.bDisableChocoboRide,
  UEndEnvQueryTest_IsDisabledChocoboRide,
  UEndEnvQueryContext_LastEnableChocoboRideLocation,
  FEndBehaviorChocoboRideOnExtraAction and UEndAnimNotifyCallChocobo. That proves
  ride-legality, last-safe-location, ride-on and call seams exist. The generated
  declarations do not expose the callable orchestration needed for safe
  teleport+immediate mount, nor the distance-ratio semantics/ranges or exact
  vanilla fallback. #470 remains Not integrated.
- #471 Formulae / Steal: BattleItemPossession publicly names
  NormalItemPercent_Array, RareItemPercent_Array, StealItemName_Array,
  StealItemQuantity_Array and StealFaildCountArrayIndex. Synthlight's public
  format work proves an _Array header points to repeated values of the property's
  underlying type, with explicit alignment. The generated Rebirth row declaration
  independently cross-checks the concrete schema: item arrays are TArray<FName>,
  NormalItemPercent_Array/RareItemPercent_Array/StealItemQuantity_Array are
  TArray<uint8>, and StealFaildCountArrayIndex is int32. Lexeditor now independently
  decodes those array elements read-only and exposes supplied BattleItemPossession rows
  in a shared paged Formulae Table+Detail. Gantz79's public mod evidence says the
  25% rate data is shared between steal/drop, so a Steal-only percentage control
  would still be misleading. Generated runtime enums independently distinguish
  StealFailed, AlreadyStolen and NothingToSteal and expose a StealSuccessRateAdd
  skill-effect type. That proves the requested miss/nothing states and a rate
  modifier exist, but not their branch conditions or arithmetic. Array writes and
  the complete Steal formula/terms remain unproved. #471 is Partial, not complete.
- #472 blue benches / cushion: public DataObject names identify the bench
  rest trigger/action rows and UI7033_00_ConsumedItem_Cushion. The generated SDK
  narrows the runtime/asset seam further: AEndFieldActionActorBenchBreak has both
  a UStaticMeshComponent* BenchMeshComponent and a
  TSubclassOf<AEndSkeletalMeshActor> ZabutonActorClass, and CampBreak derives from
  that bench actor. Public mesh evidence also confirms multiple bench models.
  Public gameplay documentation independently confirms the important vanilla split:
  ordinary blue benches do not expend a cushion, while Chocobo-stop benches do; a
  May 2026 mesh-mod discussion also identifies the blue bench as a separate asset
  family from Chocobo-stop benches. Missing evidence remains the complete
  restable-placement -> desired blue-mesh mapping and the inventory/state transition
  that consumes a cushion for every valid rest without changing unusable benches.
  #472 remains Not integrated.
- #473 minimap zoom: the generated SDK explicitly contains option categories
  AreaNaviMapScale, LocationNaviMapScale and ZackNaviMapScale, while UEndNaviMap
  exposes PixelPerCm and the location prototype data contains Min/Mid/MaxPixelPerCm.
  The option model can represent integer MinValue/MaxValue ranges. Independent
  player-facing documentation confirms two related controls already exist: a
  specific-location "Minimap Display Area" whose larger numeric choices show more
  area, and a world-travel navigation-map display-scale control with the same
  larger-number/wider-area behavior. This is substantially stronger than the
  earlier HUD-size evidence, but the generated enum names do not prove which
  category binds to which persisted setting, the complete stored range/default, or
  the save/config location. Lexeditor therefore cannot yet present a truthful
  bounded editor. #473 remains Not integrated.
- #477 Faster Queen's Blood: public CardGame data exposes EffectWaitTime and AI
  tuning fields; generated declarations confirm NeedCanPutCount,
  PlayerPredictionTurn and EnemyPredictionTurn are int8 members.
  UEndCardGameMenu also exposes a _PassClass and OnYesButtonPressed/
  OnNoButtonPressed, while the 3D manager exposes turn/board state. These are
  concrete pass/turn seams, but generated implementations are empty stubs and do
  not reveal the legal-move predicate, automatic pass transition,
  both-sides-no-moves termination or intro first-skippable-input hook. Animation
  timing such as FlagPlayTurnAnimDuration is not treated as a substitute for the
  requested logic. #477 remains Not integrated.

### Focused public-source recheck (2026-09-22)

The final agent-side feasibility pass explicitly rechecked these public sources,
without downloading or redistributing their game assets:

- meditationxp, **BattlePlayerParameter - Unique Ability Enhanced**:
  https://www.nexusmods.com/finalfantasy7rebirth/mods/1793
  - proves current real mods modify BattlePlayerParameter gameplay, but the public
    page does not publish a dependable serialized field/value/range mapping.
- OnionKnight49, **Various Gameplay Upgrades**:
  https://www.nexusmods.com/finalfantasy7rebirth/mods/1848
  - independently lists BattlePlayerParameter changes and a separate optional
    uasset-editing help download. The public description gives effects/vanilla
    comparisons, not enough field-address/range detail to expose safe controls here.
- peacefulz2, **Easier Fast Travel**:
  https://www.nexusmods.com/finalfantasy7rebirth/mods/2261
  - August 2026 real-mod packaging example: an ordinary .pak/.ucas/.utoc triple is
    copied to End/Content/Paks/~mods. It changes fast-travel availability, not the
    #470 safe call/teleport/mount orchestration.
- TheWolfster / Lobyrockstar, **Refreshed Chocobo Rest Stops** discussion:
  https://www.nexusmods.com/finalfantasy7rebirth/mods/2048?tab=posts
  - identifies the blue bench as separate from Chocobo-rest bench assets; it does
    not provide the complete restable-placement or cushion-state mapping for #472.
- Gamer Guides, **Chocobo Stops: Resting & Fast Travel**:
  https://www.gamerguides.com/final-fantasy-vii-rebirth/guide/gameplay/basics/chocobo-stops-resting-fast-travel
  - independently documents that Chocobo-stop rests consume cushions while ordinary
    blue benches do not.
- Seeking Tech, **How to make the Final Fantasy VII: Rebirth minimap show more area**:
  https://seekingtech.com/how-to-make-the-final-fantasy-vii-rebirth-minimap-show-more-area/
  and GameWith's Rebirth minimap guide:
  https://gamewith.jp/ff7rebirth/437417
  - confirm the shipped location/world navigation scale UI behavior for #473, but
    not the persistent storage binding required for a Lexeditor writer.
- f80h, **FF7 Rebirth Load ordering**:
  https://www.nexusmods.com/finalfantasy7rebirth/articles/46
  - current UE4.26/Rebirth filename/path and numeric _P precedence evidence used by
    Lexeditor's read-only ~mods load-order audit.

No searched public source established the complete callable/runtime behavior
required for #470, #472 or #477, or the persistence binding required for #473.
Those areas therefore stay protected as Not integrated instead of being represented
by guessed controls.

narknon/FF7R2UProj at public commit
ae73efa89db7e48fc7f425dec0847a0208c15b80 is used only as generated
reverse-engineering/type-declaration evidence for the runtime/schema seams above.
No root README/LICENSE/License.txt was present in the audited repository snapshot,
so Lexeditor does not copy, adapt, vendor or redistribute its source; only factual
type/member names are used as research cross-checks.

FF7R Row Forger (published July 2026) is also a useful ecosystem signal: its
public description says it can edit/add rows in most Resident DataObject tables
and uses FModel plus UnrealReZen. It explicitly forks the Synthlight/LordGregory
parser, however, so its parser code is not imported here; Lexeditor retains its
independent bounded implementation and the licensing boundary recorded above.

## Implemented project boundary

Project marker: lexeditor-project.json

Read-only extracted inputs:
- source/End/Content/DataObject/Resident/PlayerParameter.uasset (baseline source;
  proved fixed-width edits are written only to the staged project copy)
- source/End/Content/DataObject/Resident/BattlePlayerParameter.uasset (optional
  Battle Params source; schema-validated and never staged/written)
- source/End/Content/DataObject/Resident/BattleItemPossession.uasset (optional
  #471 Formulae source; never staged/written by this integration)

Saved staged output:
content/End/Content/DataObject/Resident/PlayerParameter.uasset

Save verifies the currently loaded file hash, applies only proved fixed-width
edits, writes atomically to the project staging path, and never changes the
extracted source or installed game. Discard reloads the last on-disk state.
Reopen creates a new parse from disk. Revert staged file removes only the project
candidate and falls back to the extracted source.

## Honest acceptance boundary

Synthetic structural tests can prove parser shape handling, bounded editing,
byte preservation, service save/discard/reopen behavior, dependency-explicit
candidate construction and rendered UI interactions. They cannot prove that an
arbitrary live Rebirth asset revision matches the public layout, that the
candidate produced from real archives loads, or that edited gameplay values
behave as intended in-game. Those claims remain pending real-game acceptance.
