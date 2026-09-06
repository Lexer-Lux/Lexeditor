# FF9 / pinned Memoria integration

## Ownership and boundaries

`games/ff9` owns this integration. Normal Play is already
`GameInstallSpec.launch_path = "x64/FF9.exe"`; never replace it with the launcher.
The explicit Information-panel settings action may open `FF9_Launcher.exe`.
Do not modify FF8 or shared UI files merely to implement an FF9 feature.

The CSV editor writes project overlays, not installed `p0data` archives. Its
12 registered datasets are not complete FF9 support. In particular, enemies,
encounters, the other Memoria data formats and in-game export/deployment proof
remain part of #74.

## Publisher format and installation safety

The approved release remains `v2025.07.04`; this change does not upgrade the pin.
Primary reference:
https://github.com/Albeoris/Memoria/blob/v2025.07.04/Memoria.Patcher/Program.cs

The patcher footer is `MEMORIA\0`, followed by the uncompressed file-byte total
and gzip offset as little-endian Int64s. Signed releases append an Authenticode
certificate. Records contain UInt32 size, Int64 timestamp, a byte component
count, and a UInt16 path dictionary with the high bit denoting a new UTF-8 part.
`memoria_patcher.py` only inspects this format; the publisher patcher still
performs installation. No game executable or upstream data records are bundled.

Do not trust exit code zero: the publisher catches extraction errors internally.
Verify every declared non-INI output against its uncompressed SHA-256. Account
for the Steam-overlay launcher's `.fix` destination. The pinned source's x64-only
branch sends platform output to x86, so refuse incomplete Steam layouts before
patching rather than claiming a successful x64 installation.

Before patching, snapshot every declared destination, its publisher backup,
launcher `.fix`, and the `StreamingAssets/Assets/Resources/CommonAsset` tree that
the publisher removes. Snapshots live outside the game; manifests and originals
must survive until recovery succeeds. Restore existing Memoria.ini/Settings.ini
byte-for-byte because the publisher's INI merge changes comments and formatting.

A persistent OS-owned lock serializes install, recover, config writes and the
explicit settings launcher. Never unlink a lock based only on a stale PID:
concurrent recovery can otherwise remove a new owner's lock. Process death
releases the OS lock; a pending recovery journal still blocks a fresh install.
Never restore assemblies while FF9, a launcher or a patcher remains running.

Version information comes from binary resources, or a root-scoped install record
whose runtime hashes still match. An arbitrary INI `Version` key and another
installation's record are not version evidence.

## New verified character files

Sources are under
https://github.com/Albeoris/Memoria/tree/v2025.07.04/Memoria.Patcher/StreamingAssets/Data/Characters

| File | Git blob | Records | Original encoding |
| --- | --- | ---: | --- |
| CharacterParameters.csv | `674e8b769d0ae1d805bb4767755431458c6be595` | 12 | UTF-8 BOM |
| DefaultEquipment.csv | `3a35c40cf298eed8887dbfbe3d3691ed5ec315b3` | 16 | Windows-1252 |
| Leveling.csv | `70c4cfb0e903ec77ba05415cd00f1ef87b9155b2` | 99 | UTF-8 |

SHA-256 pins are in `memoria_baseline.FILES`. Raw-byte Git blob hashes were
checked as well: text transport can transcode the equipment file's punctuation.
Leveling has no stored ID; display its ordered records as levels 1–99 without
adding an ID column to the file. Equipment `-1` remains a valid empty slot.

## #80 upstream audit: existing controls are not the full feature

Pinned primary sources:
- https://github.com/Albeoris/Memoria/blob/v2025.07.04/Memoria.Launcher/Presets/SteamPreset.ini
- https://github.com/Albeoris/Memoria/blob/v2025.07.04/Assembly-CSharp/Memoria/Configuration/Structure/ControlSection.cs
- https://github.com/Albeoris/Memoria/blob/v2025.07.04/Assembly-CSharp/Memoria/Configuration/Structure/InterfaceSection.cs

The launcher's shipped Steam preset documents `Control.DialogProgressButtons`
as the buttons that **advance** dialogue, not a reveal-only button. Do not map
Cancel/Circle into it and claim that messages cannot advance.

`Control.TurboDialog` already exists. The shipped preset documents F9 toggling
automatic basic-dialogue skipping, and Shift+Confirm / Right Bumper+Confirm for
held skipping. This is reusable behavior, not evidence that the requested
Square-only hold mapping is already implemented. Trace pinned input dispatch
and choice handling before adapting it.

`Interface` already provides PSXBattleMenu, ThickerATBBar, battle rows/columns,
menu/detail position and dimensions, and fade/text-fade durations. These settings
are not evidence of the requested full-row ATB/Trance bars, HP/MP mini-bars or
right-to-left action-time drain. Reuse settings only where their actual behavior
matches; do not ship a misleading all-in-one toggle.

Still required: full input/launcher-UI behavior audit, immutable rendered-message
history that never replays scripts or rewards, safe choice handling, battle HUD
hooks and timing, independent failure of dialogue/battle components, and durable
Tetra Master per-opponent victory tracking. #80 remains actionable. #83 explicitly
says not to build Better Eat yet; no Better Eat behavior was added.
