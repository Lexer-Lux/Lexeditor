# FF8 mod and runtime layout

Lexeditor keeps mod source separate from the files that FFNx reads.

- The selected editable mod is a project such as `C:\FF8Mod`.
- Its data files stay under `direct\` and its Hext files stay under `hext\`.
- The active FFNx tree is `%LOCALAPPDATA%\Lexeditor\runtime\ff8\active`.
- FFNx points to the active tree. It does not point to the editable project.
- Before launch, Lexeditor composes the selected mod into the active tree.
- `composition.json` records each runtime file, its hash, its claimant, and its
  winner. The current composer has one selected mod, so it reports no conflicts.

This boundary makes a mod removable without removing the runtime. It also gives
load-order and conflict work one place to add more claimants later. A future
multi-mod composer must list every claimant for a path and show the winning mod.
It must not silently copy two versions of the same file.

`C:\FF8Mod` remains an ordinary editable mod. Lexeditor-owned downloaded mods
belong under `%LOCALAPPDATA%\Lexeditor\mods\ff8\<mod-id>` and must use the same
`direct\`, `hext\`, and `mod.json` shape.
