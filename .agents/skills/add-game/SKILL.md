---
name: add-game
description: Starting, scoping or filing issues for a Lexeditor game plugin. Use before writing a new plugin or parser, and when creating or checking a game's Plugin parent issue and its five subissues.
---

# Adding a game

## Before writing code

- Read `docs/ADDING_A_GAME.md` and follow its research-first workflow. Survey
  existing open-source tools and loaders, documentation and format knowledge
  before writing new parsers.
- Record material sources in Credits as you use them, not afterwards.
- `docs/ADDING_A_GAME.md` is the public technical methodology. Keep issue
  administration, worker coordination, chat URLs and cleanup out of it.

## Plugin requirements

- A Data Map screen covering every area of the game's data (see AGENTS.md).
- The installation descriptor names the game's own executable (`executable=`),
  relative to the installation root and set by hand: the process that
  renders, not whatever Play starts. ReShade's folder is derived from it, so a
  game whose executable is not in the root must say where it is.
- After adding the plugin, run `python tools/check_plugin.py --write-workflows`.

## Issue structure

Every game plugin has one parent issue titled `Plugin`, identified by its game
label (the plugin id). An edition that runs another plugin's code shares that
plugin's label and issues through `issueLabel` in its `plugin.json` (ff7-2013
files under `ff7`). The parent links these five real subissues in this order,
each with the same game label. The developer page shows their status per game,
and `tests/shared/test_plugin_issues.py` fails when one is missing. Mark
`UX Refinement` and `Mod Loader` as blocked by `Create Editor` using GitHub's
issue dependencies.

1. `Create Editor`: Research existing tools and format knowledge first. Build
   the plugin and required code, vendor permitted helpers, and record Credits.
   Integrate every Data Map area with appropriate editable views. Do not hide
   unsupported rows or call raw-file access full integration. Only Lexer can
   exclude areas as not worth the effort; ask when scope or value is in doubt.
   Unknown semantics stay protected until proven; report the gap, not success.
2. `UX Refinement` (blocked by `Create Editor`): Make the screens usable and
   human-friendly with shared controls, clear help and good navigation.
   Inspect rendered screens and interactions, repair UI defects, and check
   small windows and large UI scales.
3. `Mod Loader` (blocked by `Create Editor`): Find, add, load and remove real
   mods. Support record overrides and composition against vanilla where the
   format requires them, rather than replacing a whole file for unrelated
   record changes. Define load order, conflicts, dependencies and restoration.
   Test a documented range of real online mods in isolation, including
   overlapping edits, and make supported mods work without manual repair.
   Record unsupported cases.
4. `Create Theme`: Use the game's fonts, colours and sound effects for a
   fitting theme. Record asset provenance and distribution rights; extract
   locally when redistribution is not permitted.
5. `ReShade`: Get ReShade working on the game's rendering executable, set the
   game's ReShade defaults so they apply on a fresh install, and customise the
   CRT filters for the game where Lexer wants them. It starts `waiting`, since
   each step needs Lexer in the running game.

These five track one plugin. Reuse existing matching issues. Each open
subissue carries its own truthful workflow label (see
`.agents/skills/github-issues/SKILL.md`); the parent carries none, because its
status is its subissues' statuses. Source, rendered UI, mod compatibility,
delivered candidate and in-game acceptance are separate checks, and the parent
is not complete while required scope remains.
