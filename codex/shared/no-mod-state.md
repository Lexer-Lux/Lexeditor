# The unmodded game: Vanilla, read-only

Lexer's rule, and the reason this page exists: **Lexeditor never creates a mod
the reader did not ask for.** Opening a game must land on the game's own data,
read-only, and creating a mod is an action the reader takes.

## What the reader sees

The mod control in the shell header names the source being shown. When no mod
exists it reads **Vanilla**, shows a lock, and its subtitle says the page is the
game's own data. The mod menu lists the same Vanilla row so the list does not
read as empty, beside **Add a Mod** and **Find a Mod**.

The save button is disabled and its tooltip says why: a session the host
opened without a mod is read-only even when the plugin never grew its own
read-only notion. There is no separate `NO MOD` badge in the command row any
more; it repeated what the selector already says.

## What used to happen, and why it mattered

The control read **"No mod"** over the folder a mod *would* use. For Terraria
that folder is inside tModLoader's own `ModSources`, so the header showed a
long path in a folder that did not exist, under a name that says a mod is
missing rather than that none was ever made. Lexer read that as "the editor
made a mod and left it empty", then found every tab empty as well.

## Editing the game's own data

An edit attempt - a click or a keystroke in a property row, or in a bare
control - opens one dialog: **Create a mod?** with `Create a mod` and `Cancel`.
Creating runs the same flow as **Add a Mod**: name it, the host creates it from
the plugin's starter, and the host restarts the plugin on the new project.
`LexeditorUI.createModProject(pluginId, {pluginName})` is the one call a page
needs for its own button.

A mod that is a read-only library reference keeps its own separate prompt,
which offers to make an editable copy instead. `current.vanilla` rows never get
either prompt: there is nothing to copy.

## A plugin's own tabs in this state

With no mod, the tabs must state the state and offer the action, not show empty
tables. What this plugin can read belongs in the panel's question-mark help;
the page itself carries the state and the button. Terraria is the worked
example: `tests/terraria/terraria_no_mod_check.py` fails when any tab stops
saying that the game has no mod or stops offering `Create a mod`.
