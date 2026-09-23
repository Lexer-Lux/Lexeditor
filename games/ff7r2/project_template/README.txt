Final Fantasy VII Rebirth Lexeditor project

Lexeditor edits a proved Rebirth DataObject surface without writing to the
installed game.

Source input (read-only):
  source/End/Content/DataObject/Resident/PlayerParameter.uasset

Saved project output:
  content/End/Content/DataObject/Resident/PlayerParameter.uasset

The source must be the original IoStore-state Rebirth DataObject, not a
Zen-converted legacy uasset/uexp pair. Lexeditor does not bundle game data.

Packaging is separate from Save. The optional candidate builder requires:
  LEXEDITOR_FF7R2_UNREALREZEN = local UnrealReZen.exe from the FF7R2 release
  LEXEDITOR_FF7R2_OODLE       = local user-supplied oo2core_9_win64.dll
  A matching UnrealReZen.deps.json that records CUE4Parse/1.1.1
  A located Rebirth installation with its original .utoc/.ucas archives

LEXEDITOR_FF7R2_OODLE must point to oo2core_9_win64.dll already in the same
directory as UnrealReZen.exe. The reviewed CUE4Parse dependency checks for that
local file before entering its downloader. Lexeditor does not download, copy,
relocate or redistribute Oodle or UnrealReZen.

Build Candidate writes only:
  build/ff7r2-candidate-*/Lexeditor-FF7R2_P.pak
  build/ff7r2-candidate-*/Lexeditor-FF7R2_P.utoc
  build/ff7r2-candidate-*/Lexeditor-FF7R2_P.ucas
  build/ff7r2-candidate-*/manifest.json

A candidate is not installed and is not treated as game-accepted. For acceptance,
manually copy all three package files to:
  <game>/End/Content/Paks/~mods/

Make one harmless fixed-width edit, verify it in Rebirth, then remove all three
candidate files and verify the vanilla value returns. Record the game build and
manifest hashes before any automatic installation path is considered.
