# Mod format and Lexer's Mods

Every game's mods follow one small standard, so the shared Mods tab can list,
name and switch any of them. Everything else about a mod is the game's own
format, so popular mods keep working as they ship.

## A mod

- One folder per mod, directly inside `<mod library>/<game id>/`.
- `mod.json` in the folder's root carries the standard metadata
  (`core/mod_metadata.py`):
  - `name`: required, at most 120 characters.
  - `author`, `description`, `credits`: optional text, may be blank.
  Credits travel with the mod they credit.
- Games keep their own keys in the same file (`enabled`, `order`, a tweak's
  `script`, a bundle's components); writing the standard fields keeps them.
- A mod that arrives without a name is never stored that way: creating a mod
  asks for its name, author and description, and adding one asks for whatever
  the package did not say about itself. The Mods tab shows an unnamed folder's
  folder name only for display and asks for a real one.

## Lexer's Mod for a game

- A game's `plugin.json` names it: `"lexmod": "Owner/Repository"` on GitHub.
  The developer dashboard's LEXMOD? column shows it. Because the repository
  comes from Lexeditor's own manifest, never from a download, its modules
  are trusted to run their build scripts.
- A Lexmod is a collection of modules. Every top-level folder of the
  repository holding a `mod.json` is one module, which is an ordinary mod. Its
  `mod.json` `enabled` is the module's default state and its `settings.json`
  holds the default settings.
- `README.md` has a `## Features` section: a bullet list whose last bullet is
  `lexmods.FINAL_FEATURE`. The first-run screen shows those bullets.
  `tests/shared/verify_lexmod_readmes.py` checks every published Lexmod.
- The latest version is the latest stable release, or the default branch's
  newest commit when there is none. Installed modules carry `.lexmod.json`
  naming the repository, version and files. Updates replace a module's files
  and keep its `settings.json` and on/off state; a folder the Lexmod did not
  install is never overwritten. Modules not downloaded appear greyed at the
  end of the Mods tab with a Download button, and downloaded ones are updated
  at most hourly when the Mods tab opens.
- A private repository cannot be downloaded by players; it reads as not
  published.

## First run

Once per game (`onboarding.json` in Lexeditor's data folder): offer Lexer's
Mod with its feature list, download and install it with its defaults, say it
is ready, then point at the Mods tab and the Tweaks tab. Without a published
Lexmod the screen starts at the Mods tab step.
