# FF9 / pinned Memoria integration

## Ownership and boundaries

`plugins/ff9` owns this integration. Lexer's later decision in #73 supersedes the
old direct-launch/embedded-INI-editor specification:
https://github.com/Lexer-Lux/Lexeditor/issues/73#issuecomment-5550129793

Normal Play uses `GameInstallSpec.launch_path = "FF9_Launcher.exe"` so Memoria's
existing launcher supplies its own settings UI. Tweaks has a Memoria subtab with
Lexer's requested explanatory message only. Do not recreate the Memoria settings
editor or expose configuration-read/write endpoints in FF9. The Information-panel
settings action also delegates to the existing launcher. Managed installation,
recovery and preservation of existing INI bytes are separate from settings editing.
Do not modify FF7, FF8 or shared UI files to implement this FF9 decision.

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

A persistent OS-owned lock serializes install, recover and the explicit settings
launcher action. Never unlink a lock based only on a stale PID:
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

## Links that only exist between two files

Measured on the installed Memoria `v2025.07.04` data
(`D:\SteamLibrary\steamapps\common\FINAL FANTASY IX\StreamingAssets\Data`).

**An ability slot names a battle action.** Each per-character file under
`Characters/Abilities/` stores only `Id` and `AP`, and its own header says "Use 0
for a void ability, AA:X for active abilities and SA:X for passive abilities".
Across every character file, each `AA:X` was compared with the `Battle/Actions.csv`
row whose `id` is X: 156 ids compared, all but two naming the same thing. The two
differences are Memoria's own spellings, `Frost` (Quina `AA:97`) against `Freeze`,
and `Armor Break` (Steiner `AA:145`) against `Armour Break`. The action's `mp`
column is therefore the ability's MP cost — Cure `AA:1` reads 6 MP, Cura `AA:2`
reads 10. `SA:X` ids index the support-ability table instead and must never be
matched to an action; `Characters/Abilities/AbilityGems.csv` stores plain numeric
ids, so it is a different table again.

A shipped ability file pads its learn list with id-0 rows (Beatrix1.csv holds 18
real abilities and 30 such rows). They are real rows and stay visible; Lexeditor
names each one `Empty slot N` so a list of identical `Void` rows can be read.

**A shop row is a list of item ids.** `Items/ShopItems.csv` stores
`Comment;Id;Items`, where `Items` is a comma-separated list of item ids in display
order, and the trailing comment carries the shop's real name (`# Shop 0000 Dali
Weapon Shop`) even though the `Comment` column itself only says `Shop 0000`. All
32 shops resolve every stocked id to a row in `Items/Items.csv`; shops 23 and 24
stock nothing at all. FF9 has no shop name of its own, so the comment-derived name
is a display label the game never reads.

`Items.csv` is the only table whose `Price` is what a shop charges and whose
`SellingPrice` is what a shop pays back, so Lexeditor labels those two columns
`Buy price` and `Sell price` for that dataset alone. `Synthesis.csv` has its own
`Price`, meaning the recipe's charge, and keeps its name. The CSV column keys are
unchanged in every case — only the displayed label moves.
