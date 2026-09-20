Final Fantasy VII Rebirth Lexeditor project

Lexeditor edits a proved Rebirth DataObject surface without writing to the
installed game.

Source input (read-only):
  source/End/Content/DataObject/Resident/PlayerParameter.uasset

Saved project output:
  content/End/Content/DataObject/Resident/PlayerParameter.uasset

The source must be the original IoStore-state Rebirth DataObject, not a
Zen-converted legacy uasset/uexp pair. Lexeditor does not bundle game data.

Packaging is intentionally separate from Save. Public FF7R2 packaging tools can
load Oodle dynamically; Lexeditor will not silently download or redistribute
that proprietary dependency. The editor stages the exact content path first,
then reports packaging as unavailable until a user-supplied safe toolchain has
been verified against a real Rebirth installation.
