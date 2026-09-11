# Shipping ReShade presets with a Lexeditor mod

Lexer's requirement, in his words: he wants to add ReShades with his mods, there
should be one ReShade managed by Lexeditor rather than a copy per mod, and a
published mod must still work for someone who does not use Lexeditor.

Those three pull against each other, so this is what the shape has to be.

## What Lexeditor owns

One ReShade installation per game, managed by the editor, living beside the
editor rather than inside any project. The editor knows the game's renderer, so
it is the right place to pick the DLL name (`dxgi.dll`, `d3d11.dll`, `opengl32.dll`)
and to install or remove it. Nothing about that is per-mod.

The shader repositories are the same: one on-disk copy of each repository the
user has added, versioned, shared by every project. A mod that references
`qUINT/Bloom.fx` names the shader, it does not carry it.

## What a mod owns

A project directory gets one `reshade/` folder holding only the things that are
genuinely the author's work:

- `preset.ini` - the ReShade preset, the actual creative content.
- `shaders/` - only shaders the author wrote or modified, not copies of a public
  repository.
- `reshade.json` - which repositories and versions the preset needs, and the
  target DLL.

The manifest is what makes the mod portable without shipping other people's
shaders. It records repository name and version, not a path on Lexer's machine.

## What a player who does not use Lexeditor gets

This is the constraint that decides the format: the preset must be a plain
ReShade preset. If someone downloads the mod and already has ReShade, dropping
`preset.ini` into their ReShade folder and installing the listed repositories
has to work with no Lexeditor involvement. That rules out any bespoke container
or an editor-specific preset dialect.

Lexeditor's contribution for players who do use it is doing that by hand for
them: read the manifest, check the repositories, place the preset, select it.

## Licensing, which decides more than it looks like

ReShade's own binary is redistributable under its licence, but the shader
repositories are not uniformly so, and several common ones forbid
redistribution outright. That is the real reason a mod ships a manifest rather
than a shader bundle. The editor should refuse to copy a repository's shaders
into a project directory even when the author asks, and say why.

## What has to be built

1. A per-game ReShade install/uninstall in the editor, with renderer detection.
2. A repository list with versions, stored once per machine.
3. `reshade.json` read and written by the plugin's project storage.
4. A Tweaks-page section: enable ReShade, choose preset, see which required
   repositories are missing.
5. Export: the mod's `reshade/` folder plus a readable note naming the
   repositories a manual installer needs.

## What is built now

Items 3 and 4 are done. `reshade_projects.py` reads and writes the manifest,
lists the presets and authored shaders a mod carries, and detects whether a
ReShade loader is actually installed for the game by looking for its name inside
the renderer DLL - a game's own `d3d11.dll` is not mistaken for one. The desktop
host exposes `mod_reshade` and `save_mod_reshade`, and the shared
`LexeditorUI.reshadeSection()` puts the same section on every game's Tweaks
page. The shared UI contract now requires it of any plugin that has a Tweaks
page, so a new game cannot quietly leave it out.

The section is deliberate about the three ways this silently does nothing -
ReShade not installed, no preset in the mod, or a manifest naming a preset file
that is not there - because each of those used to be indistinguishable from a
working setup until the game launched unchanged.

Item 1 is done too. Lexeditor keeps one ReShade, which the user points it at
once; it is not vendored here, because which build to ship is their decision
rather than one a mod editor should make quietly on their behalf. Installing
copies that DLL into the game under the loader name its renderer needs, and it
refuses outright when a file of that name already exists and is not ReShade -
a game's own d3d11.dll is not ours to replace. Removing deletes only a DLL that
identifies itself as ReShade, for the same reason.

Items 2 and 5 are done, which closes the list.

The repository list is one file per machine, `repositories.json` beside the
stored ReShade DLL, holding a name, a version and an optional URL each. It is
deliberately not per project: every mod's preset resolves against the same list,
which is what makes "this mod needs qUINT 3.0" a statement the editor can check.
The Tweaks section adds and forgets entries, shows what the machine has, and
reports each repository a mod names as ready, missing, or a version mismatch.
A mismatch is reported separately from missing because the shaders are there,
they are just not the ones the preset was authored against, and that produces a
different kind of wrong picture.

The export note is plain text written into the mod's own `reshade/` folder as
`INSTALL-RESHADE.txt`. It names the loader DLL the game's renderer wants, every
repository with its version, where the preset goes, and any shaders the author
actually wrote. It opens by saying the reader does not need Lexeditor, because
that is the requirement the whole format exists to satisfy: a published mod has
to work for someone who has never heard of this editor.
