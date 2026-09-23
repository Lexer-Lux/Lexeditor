Final Fantasy VII Rebirth Lexeditor project

Lexeditor edits a proved Rebirth DataObject surface without writing to the
installed game.

Source inputs:
  source/End/Content/DataObject/Resident/PlayerParameter.uasset
    - editable only for proved fixed-width PlayerParameter scalar fields
  source/End/Content/DataObject/Resident/BattlePlayerParameter.uasset
    - optional, structured Battle Params view only; never staged or saved
  source/End/Content/DataObject/Resident/BattleItemPossession.uasset
    - optional, structured Formulae source view only; never staged or saved

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

Information also audits complete native package triples already under
<game>/End/Content/Paks/~mods without opening or changing them. It reports only
publicly documented filename/path precedence: higher numeric _<n>_P patch levels
win, and at the same patch level the case-insensitively smaller complete path
wins. It does not inspect asset overlap or change external mod order.

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
