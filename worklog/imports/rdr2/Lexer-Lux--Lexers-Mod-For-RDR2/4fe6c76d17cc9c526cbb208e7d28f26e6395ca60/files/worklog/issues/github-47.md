# GitHub #47 - Horse Camera Centering Toggle

## Requirement

Stop the ordinary third-person camera from pulling itself back behind the horse
while riding, controlled by `DisableHorseCameraCentering` under `[Camera]`.

## Evidence and design

The referenced `Disable Horse Camera Centering` download is an LML replacement
for the complete `cameras.ymt` file. Public conflict documentation confirms that
it collides with other camera-data mods. That approach also cannot implement an
ASI INI toggle: LML loads data before the script and cannot swap camera tuning
live.

The local native database exposes the mounted camera's relative heading and
pitch getters/setters. `horse_camera.cpp` therefore lets Rockstar process real
mouse/controller look input, records the resulting orbit, and reapplies that
orbit only once input stops. This rejects the unwanted input-free drift without
reimplementing sensitivity, acceleration, inversion or controller deadzones.

The controller yields to aiming, first person, cinematic cameras, gameplay
hints, Look Behind, loss of player control, and every unmounted state. Returning
to the ordinary third-person mounted camera captures its current orbit rather
than snapping to an old one.

## Integration handoff

The integration agent must:

1. Include `modules/horse_camera.cpp` after `world_economy.cpp` (where
   `g_iniPath` is available).
2. Call `updateHorseCameraCentering(ped)` once per main loop after Rockstar has
   supplied the current player ped. The module re-reads its own INI key every
   two seconds.
3. Perform the unified build, install, hash verification, and GitHub transition.

## Static acceptance

- `[Camera] DisableHorseCameraCentering=1` is present and defaults on.
- The implementation runs only on a live mounted player in the ordinary
  third-person gameplay camera.
- Real look input re-anchors both heading and pitch; idle frames restore them.
- No complete `cameras.ymt`, third-party binary, or third-party source was
  copied into the project.

## Runtime acceptance still required

With the option on, ride straight at a gallop, turn the camera to either side
and slightly up/down, release look input, and confirm it stays there without the
pull/zoom-like return. Confirm mouse and controller input still feel native;
aiming, Look Behind, first person and cinematic/scripted cameras still work.
Set the option to `0`, allow config reload, and confirm vanilla mounted
recentering returns.

Static inspection cannot prove frame-order behavior or rule out a one-frame
movement at input release; those require the in-game check above.

## 2026-08-06 correction after installed camera jumping

The installed ASI controller failed its runtime test: the mounted camera jumped
continuously. The cause was architectural, not a threshold problem. It read and
rewrote relative heading and pitch on idle frames while Rockstar's mounted
follow camera was updating the same orbit, so two controllers fought every
frame.

The exact referenced release was downloaded and verified before reuse:

- archive SHA-256:
  `CD801F995250FDA8AC47F1A8B66EE6ACE637DE47E55596034CD7B71EDFB34F8A`;
- author: Riyusso, release 1.0;
- payload: `cameras.ymt` plus its LML `install.xml`;
- game target: `update:/x64/data/metadata/cameras.ymt`.

Comparison against the vanilla-derived `No Kill Cam Filter` 1.1 camera file
(whose documented camera change is only the separate kill-cam member) isolated
the reference mod to four values inside camera record `0x95DDC7CB` / block
`0x8C427004`:

| Member | vanilla-derived | reference |
|---|---:|---:|
| `0x791B55E6` | 0.5 | 0.0 |
| `0xFB0803FA` | 0.55 | 0.0 |
| `0xF82ED670` | 15.0 | 3000.0 |
| `0x1AAAAB19` | 1.1 | 1.0 |

The unrelated baseline kill-cam difference was not imported from that baseline;
The verified archive established the four-field mechanism, but the integration
gate rejected shipping its byte-identical `cameras.ymt`: project policy requires
release data to be rebuilt from Lexer's own vanilla extraction rather than
redistributing another mod's complete payload. The reference file and temporary
install fragment were therefore removed after recording the four values above.

`horse_camera.cpp` no longer calls either relative heading/pitch setter. Its
update entrypoint is deliberately inert until the compliant data payload exists;
it does not move files or imply that the reserved INI toggle currently changes
camera data. This removes the known frame fight without shipping a false fix.

The ASI frame-fighting setters remain removed and Riyusso is credited for the
mechanism. The issue remains actionable until an own-extracted vanilla
`cameras.ymt` can receive only those four narrow edits and be installed.

No new runtime acceptance is requested from this pass: without the compliant
own-extracted data payload, only removal of the rejected ASI camera fight is
complete.

## 2026-08-06 static regression guard

The latest live issue comment remained the installed-jumping report. A new
issue-local verifier replaced the obsolete check that still required the
rejected per-frame camera setters. It now fails if any relative heading or
pitch getter/setter returns to `horse_camera.cpp`, and also checks that this
worklog retains the verified archive hash, camera record/block, all four narrow
field changes, and the own-extracted-vanilla gate.

`python tools/reverse-engineering/verify_horse_camera_issue_47.py` passed. This
proves the known jumping controller is absent; it does not prove the requested
centering toggle is implemented. The issue remains actionable pending the
vanilla `update:/x64/data/metadata/cameras.ymt` OpenIV export and integration-
owned LML data packaging.

## 2026-08-06 vanilla extraction attempt

The remaining local extraction route was rechecked directly. OpenIV is installed
at `%LOCALAPPDATA%\New Technology Studio\Apps\OpenIV\OpenIV.exe`, but its
documented command-line switches only select a game/core or open an archive;
they do not expose a headless file-export operation. The repository's tested
RPF8 tools cannot read the encrypted nested update archive that owns
`update:/x64/data/metadata/cameras.ymt`.

A targeted search of the repository, Downloads, Desktop, Documents, OpenIV
Recovery, and the local Temp tree found exactly two `cameras.ymt` payloads:

- `Temp\rdr2-camera-341\baseline\No Kill Cam Filter\cameras.ymt`;
- `Temp\rdr2-camera-341\Disable Horse Camera Centering\cameras.ymt`.

Both are third-party comparison files and remain ineligible as release sources.
No project-owned vanilla export exists locally. RDR2 was also running during
this attempt (`RDR2.exe` from the configured Steam game root), while the settled
OpenIV extraction procedure requires RDR2 to be closed. The feature agent was
not authorized to launch/close the game or take visible GUI control, so it did
not open OpenIV or disturb the active session.

The precise remaining blocker is therefore a manual OpenIV export, after RDR2
is closed, of `update:/x64/data/metadata/cameras.ymt` into
`_downloads/extract/`. Once that own-extracted file exists, apply only the four
record `0x95DDC7CB` / block `0x8C427004` changes already recorded above, package
the result through the integration-owned LML route, and retain the inactive ASI
controller. Issue #47 remains actionable; no compliant implementation artifact
was produced by this pass.
