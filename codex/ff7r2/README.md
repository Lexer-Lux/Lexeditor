# Final Fantasy VII Rebirth (ff7r2)

## Scope and audited baseline

This note is Rebirth-only. Remake remains a separate plugin/worker under games/ff7r.
Shared Unreal/helper framework changes are blockers here rather than changes this PR competes for.

The work began from master a47f0a57f8b44113b0ca1d42e5795f59f707372a and was last reconciled wholesale against 72ee978a2ff36686a6349696b19860057356468a. Live master was re-audited at 76ec7c3b9b289f1d52bcf684c691d5020619c3f6; it has advanced substantially, so this worker adopted only Rebirth-local compatible changes instead of overwriting concurrent shared work.

Current-master references read for this audit:
- AGENTS.md — 41355ce0b783c55a03ad250ed279666f785c6e67
- docs/ADDING_A_GAME.md — 7fe6d35dd82fa3fe4e6378ca558ecbb0a316c4c0
- docs/UI-MANUAL.md — 14a3269992031d7e7893fcb127728a48b944e71f
- ui/component-catalog.js — a11e52e31ee92bce495c6cbf54a66d4597d52139
- games/blank/editor.html — b0b235d010952bf0c7524dcce172ef72f7cf63e4
- games/rdr2/editor.html — 899bfdb45cbf25da55aed43a590db6ee476b523b, including shared paged Table + Detail and Data Map patterns
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
- keeps FString, FName-map, arrays and browser-unsafe 64-bit integers read-only;
- validates storage bounds and finite floats;
- patches a copy of the source bytes and preserves every untouched byte;
- rejects unproved package shapes rather than falling back to raw hex/files editing.

PlayerParameter is the only gameplay table promoted to the first structured UI.
BattlePlayerParameter remains not integrated because public evidence shows
behavior-linked arrays and the current writer intentionally does not resize arrays.

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
therefore requires a matching CUE4Parse/1.1.1 dependency manifest and copies only
the explicitly supplied Oodle DLL into a temporary process working directory
before UnrealReZen starts. It uses Zlib package compression and never implements
or calls a dependency downloader itself. The release's downloader explicitly
disables HTTP proxy use, so proxy environment variables are not treated as a
safety boundary.

The exact FF7R2 command contract is GAME_UE4_26,
--mount-point ../../../End/Content/, --game-dir-top-only, game archives from
End/Content/Paks, and staged content rooted at project/content/End/Content.
Output is always an isolated project/build/ff7r2-candidate-* directory containing
Lexeditor-FF7R2_P.pak/.utoc/.ucas plus a manifest with input/tool/output hashes.
The builder never copies that candidate to the installed game and marks it
acceptedInGame=false. Current public Rebirth mod instructions consistently place
accepted .pak/.utoc/.ucas triples in End/Content/Paks/~mods; that remains a manual
acceptance step until Lexeditor has proved collision/removal behavior in-game.

A real package candidate cannot be produced in the agent environment because it
has no Rebirth installation/archive set and no user-supplied Oodle DLL. The
candidate builder and refusal/isolation tests are nevertheless complete and
exercise the exact command, no-install boundary, runtime Oodle copy integrity,
missing-dependency refusal, and cleanup on failure.

## Theme and rendered browser evidence

The Rebirth theme intentionally uses no copied Square Enix art, fonts, audio or
other proprietary assets. Public menu references were used only to identify the
game's dark surface / luminous blue selection / white-text visual vocabulary.
Lexeditor implements that with original CSS tokens (#3f7fd0 accent, #2a4a72
highlight, #f2f7ff accent text) on the shared shell. The current master removal
of a game-specific detail-label width override was adopted so shared sizing owns
the layout.

Rendered CI artifact ff7r2-rendered from head
e82aa8ef14cca1fec778c3c5459d3fd50db0e257 was downloaded and visually inspected:
desktop Characters, narrow Characters, Data Map, Information and Tweaks were
usable; unsupported Data Map rows remained visible and PlayerParameter remained
Partial. The old 150% screenshot used CSS zoom plus full-page capture, which
created an artificial 1440x1350 blank tail. The test now captures the visible
viewport at simulated 150% instead; this is a browser approximation of host UI
scale, not installed-app or game acceptance.

## Current public leads for unresolved requests

The issue audit was refreshed on 2026-09-19 rather than treating the five open
gameplay requests as one generic IoStore blocker.

- #470 Chocobo whistle: no matching public Rebirth implementation was found.
  The requested behavior still needs a proved runtime/asset hook for legal riding,
  safe placement, instant mount and vanilla fallback.
- #471 Formulae / Steal: Gantz79's public "100 Percent Steal and Drop Rate" mod
  demonstrates that a packaged Rebirth tweak can force rates, but its published
  description does not expose the actual Steal formula, named inputs, roll-vs-
  no-item failure distinction, or source asset. It is evidence of feasibility,
  not enough semantics for a Formulae screen.
- #472 blue benches / cushion: the public "Refreshed Chocobo Rest Stops (Static
  Mesh)" mod confirms rest-stop mesh replacement is practical and also shows this
  is not safely reducible to one universal bench mesh. The Lexeditor request also
  needs the gameplay identity of restable benches plus cushion consumption.
- #473 minimap zoom: the 2026 "FF7 Rebirth Accessibility - Visibility Overhaul"
  publicly enlarges the minimap/HUD and can resize HUD windows, while
  FF7RebirthFix exposes gameplay/camera FOV changes. Neither documents a world-
  minimap zoom scalar or persistence path, so those controls are not conflated
  with the requested zoom setting.
- #477 Faster Queen's Blood: current public research found no implementation that
  proves the legal-move predicate, turn-skip transition, no-moves-for-both end
  condition, or intro input-state hook. Lexeditor will not recreate those rules
  from guesswork.

FF7R Row Forger (published July 2026) is also a useful ecosystem signal: its
public description says it can edit/add rows in most Resident DataObject tables
and uses FModel plus UnrealReZen. It explicitly forks the Synthlight/LordGregory
parser, however, so its parser code is not imported here; Lexeditor retains its
independent bounded implementation and the licensing boundary recorded above.

## Implemented project boundary

Project marker: lexeditor-project.json

Read-only extracted input:
source/End/Content/DataObject/Resident/PlayerParameter.uasset

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
