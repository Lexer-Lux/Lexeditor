# Module source and installed data

Warband loads a selected module from `<Warband>/Modules/<module>/`. `Native` is
the base-game module. A separate mod module does not need to replace Native.

The Module System contains editable Python files such as `module_troops.py`.
Its build exports game data such as `troops.txt` into the directory selected by
`export_dir`. That directory should be the intended mod module. The game reads
the exported files, not the Module System Python source.

Lexeditor's current troop page reads Module System source. It does not yet write
troop records. This is an implementation gap, not proof that Warband troop data
cannot be edited. A future source writer must preserve valid Python; a compiled
data writer must preserve the `troops.txt` format and explain that a Module System
build can overwrite those compiled edits.

Source: [official Module System documentation, part 1](https://mbmodwiki.github.io/Official_Module_System_Documentation%3A_Part_1).
