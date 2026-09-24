# Make a game plugin for Lexeditor

Reuse the shared controls and layouts before you add a new implementation.
Within a plugin, use one panel component and one set of CSS sizing rules for
repeated data views. Check all callers after a shared change. Add a screen-specific
override only when the screen has a different requirement, and explain why.

This is the default methodology for adding a new game to Lexeditor. It is written
for humans and coding agents. Follow it in order unless there is a concrete reason
not to. The goal is to spend effort on the parts nobody has solved yet, preserve
unknown game data safely, and get one plugin from research to real-game acceptance
without scattering the work across a pile of half-finished PRs.

The shared shell already owns navigation, windows, settings, history, common
controls, Credits, Mod Loading, project selection and GitHub integration. A game
plugin should contain only game-specific detection, data knowledge, editing and
runtime/deployment behavior.

## 0. Keep one unit of work

**Default: one new game plugin = one branch and one PR.** Keep that PR draft while
the plugin is incomplete. Add parsers, UI, deployment, tests and acceptance evidence
to the same PR instead of opening a PR for every subsystem. Split out shared
infrastructure only when it is genuinely reusable by multiple plugins and has an
independent reason to land first.

Use the existing game-labeled GitHub issue as the request/source of truth. Do not
create duplicate issues just to track parser/UI/deployment subtasks. Record concise
implementation state in the existing Worklog when continuity is needed.

Before coding, write down the intended scope in the PR or Worklog:

- exact game edition(s) and build(s) supported;
- what data will be readable/editable;
- what remains explicitly unsupported;
- how mods are loaded/deployed;
- what counts as final acceptance.

Do not merge a plugin just because CI is green. Parser, browser, installed-runtime,
deployment and in-game acceptance are different evidence levels.

## The plugin's UI files

One shape, checked by `tools/verify_shared_ui_contract.py`:

- `editor.html` — the page. Every plugin with a UI has exactly this file, under
  exactly this name, and it holds **markup only**: no inline `<script>` beyond
  the one-line transition boot in `<head>`, and no inline `<style>`.
- `<name>.js` / `<name>.css` — a module of that page, named for what it holds
  (`items.js`, `crime.js`, `editor.css`, `troop_trees.js`), loaded by the page
  with a **relative** path (`<script src="items.js">`), so the page works
  whether its own service or a test server serves it. A module nothing loads is
  deleted, not kept. The modules run in the order the page lists them, sharing
  one global scope, so a value one module reads at load time must be defined by
  a module the page lists earlier.
- The plugin's service routes them with `self.send_page_module(PLUGIN_ROOT,
  path)` from `plugin_http.py`; `tests/plugin_module_routes_check.py` starts
  every service, asks it for each module its page names, and loads the page to
  see that the modules can still see each other.
- No theme file. A theme is tokens handed to `mountShell`. A stylesheet may set
  tokens and style the game's own classes; a selector naming a shared class
  (`.lex-…`) is counted by `tools/verify_shared_ui_budget.py`, and that count
  may fall but never rise.

Every shared component is listed in `ui/component-catalog.js` and shown in
Blank. A component exported without being catalogued fails the tests.

## 1. Research before writing parsers

This is usually the highest-leverage step. **Do not start by reverse-engineering a
format from scratch. First find out who already did it.**

Search for:

- open-source editors, modding tools and converters for the game;
- open-source mod loaders/mod managers and their package formats;
- decompilation/reimplementation projects;
- libraries that parse the relevant archives, resources, scripts, models or text;
- format documentation, wikis, reverse-engineering notes and community references;
- tools for adjacent versions/ports of the same engine;
- existing tests, sample schemas and documented build/version signatures.

Useful search patterns include the game name plus `editor`, `mod tool`, `mod loader`,
`github`, `decomp`, `file format`, an extension such as `.bin`/`.rpf`/`.fs`, or a
known archive/file name.

For every promising source, answer four questions before reusing it:

1. **What does it already know?** File layout, offsets, enums, compression,
   serialization, loader rules, executable hooks, etc.
2. **Can Lexeditor reuse code directly?** Prefer a maintained library or a small,
   well-understood source module over reimplementing the same algorithm.
3. **What is the license?** Copy/adapt code only when its license permits it and
   preserve required notices. Treat a separately invoked tool differently from
   code bundled into Lexeditor.
4. **How should it be credited?** Add useful sources to Credits *as soon as they
   materially inform the implementation*, not at the end when provenance is easy
   to forget.

Prefer, in order:

1. use an existing compatible library/tool;
2. adapt compatible open-source code with its license/notice;
3. implement from published/open-source format knowledge and credit the reference;
4. reverse-engineer only the missing gap.

Do not copy code from a repository merely because it is public. Public source is
not automatically permissively licensed.

When settled game-format knowledge is discovered, put durable mechanics/schemas in
`codex/<game>/` so the next feature does not repeat the research. Keep guesses,
failed attempts and current implementation state in Worklog instead.

## 2. Decide the plugin boundary before building breadth

Before writing new lifecycle/deployment architecture, identify the **closest existing
Lexeditor plugin precedent**: safe-project-only editor, established-loader package,
pre-launch compositor, native module system, or rebuilt archive/update overlay. Reuse
that plugin's host/session/project/deployment pattern when it fits. A game's file
formats should be novel only where the game actually forces them to be; do not invent
a sixth lifecycle model because its first parser happens to be different.

Before the first real editor, define these contracts explicitly:

### Supported installation

Identify the executable/build, required files and supported edition. Use
`GameInstallSpec` and fail closed when a materially different/unknown build cannot
be handled safely. A directory existing is not proof that its contents match the
format you expect.

### Read-only source vs writable project

Installed game data is source material. Editing should normally write a separate
project/overlay via `ModProjectSpec`, never casually rewrite the installed archive.
Keep source hashes where useful, preserve unknown fields/bytes, and refuse stale
writes when the source changed underneath the editor.

### Mod loader and package model

Look for the established ecosystem loader before inventing a new one. If one exists
and can express Lexeditor's output, target its format and conventions. Build a de
novo loader/compositor only when existing loaders cannot satisfy the requirements,
and document why.

Fill in `ui/mod-loading.json` **at the beginning of implementation**, not as cleanup:

- **Mod Loader** — existing loader, fork, de novo implementation, native game
  mechanism, or explicitly not implemented yet;
- **Mod Structure** — where a mod lives and what files/folders/manifest it uses;
- **Overriding** — load order, coexistence and the granularity of conflicts.

Decide whether conflicts are whole-file last-wins, ordered patches, semantic
record/field merges, mutually exclusive modules, or something else. If a packed
file can be merged safely at record/field granularity, prefer that over making two
otherwise-compatible gameplay mods obliterate each other.

### Helper software and updates

Bundle all helper software used by the plugin with Lexeditor. This includes
loaders, runtimes, extractors and converters such as FFNx, Memoria, WSE2 or RedHook.
Install and configure the helpers as part of the plugin's first-time setup. Do not
require the user to find, download or install them separately.

For each helper:

- Bundle a tested, pinned version with its required license and notices.
- Add it to the **Updates drawer on the main menu** through the shared update
  system. Keep the installed version, Lexeditor-pinned version and newest upstream
  version distinct.
- Disable automatic updates in the helper and any updater it installs. Lexeditor
  must not automatically update the helper either. Apply updates only when the
  user requests them through the shared Updates drawer.
- Verify installation and the saved automatic-update settings before setup reports
  success. Check that automatic updates remain disabled after an update or repair.

Test first-time setup with no helper already installed. Confirm that the bundled
helper works, appears in the Updates drawer and does not update itself.

### Acceptance and recovery path

Design the last mile **now**, not after the editor is otherwise finished. Decide how
a user will deploy/install the project, how Lexeditor will back up or isolate what it
touches, how to revert it, how the game is launched, and what concrete native
behavior proves success. Prepare any test save, fixture, helper or diagnostic needed
for that acceptance while the relevant implementation is still being built.

A plugin that can edit a beautiful project but has no proved path from that project
to the game is not almost finished; its most important integration boundary is
still unresolved.

## 3. Prove one thin vertical slice

Before implementing dozens of datasets, prove one representative path end to end:

**detect -> read -> decode -> show -> edit -> serialize -> reopen -> deploy/load -> verify**

Choose a record/file that exercises the real architecture, not a toy setting. This
quickly exposes bad assumptions about archive structure, offsets, project layout,
loader behavior and preservation before they spread through the entire plugin.

For binary/packed data, prove both:

- **no-op preservation** — opening and saving without a modeled change does not
  damage or gratuitously rewrite unrelated data; and
- **changed round-trip** — the intended edit survives reopen while unrelated and
  unknown data remain intact.

Prefer byte-exact no-op preservation where practical. Where canonical serialization
makes that impossible, prove semantic preservation and explain why bytes differ.

Writes should be atomic. Deployment should be reversible. Never make "try it and
hope" the recovery strategy.

## 4. Map the game before pretending coverage

Every plugin needs a **Data Map**. Build it early and keep extending it as the
format surface becomes understood.

For each relevant file/data family, distinguish:

- structured and editable;
- readable/previewable but only partially editable;
- recognized but unsupported;
- not yet understood.

A generic raw-file viewer, hex dump or export button is not structured editor
coverage. Be explicit about limitations rather than hiding unknown areas.

Use actual schemas whenever known: bounded numeric controls, named enums, bitflag
controls, units, special sentinel values and record identity. Preserve unsupported
fields instead of zeroing/reconstructing them from guesses.

Do not commit proprietary game dumps to the repository. Use generated/synthetic
fixtures for deterministic tests and read real installed data locally for
acceptance. Small derived metadata such as hashes, offsets or schemas must be safe
to redistribute.

## 5. Register and serve the plugin

Create `plugins/<game>/__init__.py` and `plugin.py`. Export one `GamePlugin` named
`PLUGIN`; discovery is automatic. Give it a unique letters/numbers/hyphens ID,
name, accent, `check`, `launch`, `session_factory`, and a
safe `smoke()` before shipping.

```python
from pathlib import Path
from plugin_api import GamePlugin
from service_session import LocalPluginSession

ROOT = Path(__file__).resolve().parents[2]

def check():
    return []  # Replace with real checks; never invent readiness.

def session(extra_env=None):
    return LocalPluginSession(module="plugins.example.server", plugin_id="example",
                              app_root=ROOT, check=check, extra_env=extra_env)

def launch():
    from desktop_host import run_host
    return run_host({"example": PLUGIN}, "example")

PLUGIN = GamePlugin(
    plugin_id="example",
    name="Example",
    accent="#557788",
    check=check,
    launch=launch,
    session_factory=session,
)
```

Register the server in `runtime_bootstrap.SERVICE_MODULES`; the installed Lexeditor
runtime only starts explicitly allowed child services.

The child service listens only on `127.0.0.1` at `LEXEDITOR_PORT`. `/api/plugin`
must report the correct identity and honest capabilities. Serve `/` and `/shared/`
with resolved-path containment checks. Do not expose arbitrary filesystem paths or
unbounded request bodies. The host owns child-service lifetime and must be able to
stop it cleanly.

## 6. Use the shared UI instead of rebuilding it

Start with `plugins/blank` as the shared-control gallery, not as markup to copy.
Load `/shared/framework.css` and `/shared/framework.js` and use the common controls
listed in `ui/component-catalog.js` and demonstrated by the gallery.

Use the shell's **Info button** for setup, deployment, runtime status, Credits and
project-file management. Use its **Data Map button** for the shared Data Map.
Wire both actions through `mountShell`. Do not add Data Map, Info, Deployment or
Changes as normal content tabs. Show a loading state as soon as navigation starts;
never leave the previous page visible under the newly selected tab.

Use `LexeditorUI.dataMap` for the Data Map, including its integration icons.
Use one **Integration** column; do not add a separate Coverage column.
- **Integrated:** all of the represented data can be viewed and edited in Lexeditor.
- **Partial:** only part can be viewed or edited, or the viewer has no editor yet.
- **Not integrated:** there is no usable viewer or editor.
A parser, file download, or command-line tool alone does not make data integrated.
Describe what players can change and what is missing in plain language. Keep
format research in Codex, and export/deployment instructions in Info.

An optional **Misc.** tab holds editable data that does not need a dedicated page.
Use the tab ID `misc`. The shell places it after all other regular tabs and before
**Tweaks**. Omit it if there is no suitable data. Use the shared searchable,
paginated tables and detail controls, with readable names and schema limits.
Misc. must save real edits through the plugin's normal save path. A file list,
hex dump, or read-only preview does not count as an editor. List these files in
Data Map and link them to Misc.; use Partial when any represented fields remain
unsupported. Give frequently used or complex data a dedicated editor when needed.

There is no separate editable-table mode. All record tables use the shared cell
editors. Supply each editable column's `edit` callback and its schema controls
(`choices`, numeric bounds, or `editor`) so a double-click edits the same value
shown in Detail. Do not build a second table example with permanent inputs.

Use `pagedListDetail` and `columnList` for record lists. Search and pagination
belong in the shared bottom bar. Do not substitute a scrolling HTML table,
dropdown file picker or custom Next/Previous controls. Check this with enough
records to fill several pages. Editable values belong in the selected record's
Detail pane. Related file names can be properties or list columns.

For localized text, use one subtab per language, with its flag before its name.
List that language's text entries across resource files. Show the resource path
as a property; do not make users select a file before they can find text.

Center popup-modal contents and make action buttons share the full available
horizontal space. Use only the actions the question needs.

Do not add general disclaimer banners about implementation, evidence, read-only
data or safe writes. Disabled controls and source selection already show those
states. Put necessary explanations in the relevant `infoHelp` bubble. Use a
visible warning only for a specific problem that affects the current action.

Keep record identity in the master list and editable properties in the detail pane.
Default identity columns to real numeric ID, readable name, then internal name.
Omit fields the source does not have; do not invent names or numeric IDs. Never
label a parser row index, list position, or generated counter as an ID or show it
as a detail badge. Internal selection and save keys can use row indices without
showing them to the user. Preserve saved pin and column-order choices.
Use semantic controls: checkbox/toggle for booleans, selects for known enums,
bounded number/range controls for real numeric limits, and decomposed bitflags when
possible. Help text should explain effect, unit, special values and restart/runtime
requirements rather than restating the field name.

Present the type the player edits, not the type the file stores. A value kept as a
byte that only ever means yes or no is a switch, and is written back as 0 or 1. A
byte that indexes a fixed list is a select, not a number. Reading the storage type
straight out of a schema is what produced a spin box labelled "Can Sell" with a
range of 0-255. Keep a small per-field override map in the plugin next to the
schema, so the mapping is visible and each entry can be justified.

Every list of records is a shared paged Table + Detail. Its search and paging live
in the shared bottom bar, so a plugin never builds its own search box above a bare
table: doing that silently caps the view at one page.

Tweaks is a settings page, not a record table. `plugins/blank`'s Tweaks tab is the
reference: a master switch that owns the page, dependent controls disabled until it
is on, bounded values with units, selects for fixed choices, and related switches
grouped into one property.

All Tweaks lists must use pagination. Use `LexeditorUI.settingsColumns` for
setting cards, `paginateSettings` for an existing group container, or
`detailPanel({paginate:true, ...})` for a settings detail page. The shared control
keeps six groups per page and provides an inner scroll area for tall groups.
Keep the pager outside that scroll area. Never rely on the outer window to
scroll: the desktop shell can prevent it. Check every page, the last control in
a tall group, and edit retention at small window sizes and large UI scales.
Run `python tools/verify_tweaks_pagination.py` for the shared reachability check.

Credits and Mod Loading are shared Info-page sections; do not hand-build per-game
copies. A plugin still has to supply their data, and discovery will reject it if it
does not. The Mod Loader section is enforced: every plugin must call
`LexeditorUI.modLoaderSection` and fill all five fields.

## 7. Credits and provenance are a hard requirement

Update `ui/credits-sources.json` while researching. Credit:

- open-source code that was copied or adapted;
- projects whose source materially supplied format/reverse-engineering knowledge;
- external helpers/tools Lexeditor relies on;
- documentation/authors that materially resolved behavior or structure;
- required license and source notices for redistributed code/assets.

Keep the same record beside the plugin: every `plugins/<id>/` folder holds a
top-level `credits.md` with all of its third-party attributions and license
notices inlined (no `THIRD_PARTY.md` variants, credits subfolders, or
scattered license files). Point that plugin's license `sourcePath` entries at
its `credits.md` so the generated bundle embeds the same texts.

Run:

```text
python tools/generate_credits.py
python tools/generate_credits.py --check
```

The source registry, generated Credits bundle and discovered plugin IDs must agree.
A plugin with an entirely empty Credits section is invalid and Lexeditor will not
start with it present.

If a plugin truly used **no** outside code, documentation, tools, reverse-engineering
work or other meaningful assistance, make that explicit instead of leaving Credits
blank. For example, add a contribution named **"Nobody but myself"** with a role
such as "No third-party code or reverse-engineering references were used." This is
an intentional declaration, not a recommended default.

Do not use that escape hatch when external work actually informed the plugin.
Credit generously; attribution is much cheaper than rediscovering provenance later.

## 8. Verification ladder

Do not collapse these into one vague word like "tested":

1. **Format/unit tests** — malformed input, bounds, enums, parser behavior.
2. **Preservation tests** — no-op and changed round-trip, unknown fields, source
   isolation and stale-write refusal.
3. **Service/smoke tests** — real plugin identity, APIs, temporary save/readback,
   clean shutdown.
4. **Shared browser/UI acceptance** — actual rendered controls, resize, keyboard,
   sorting/selection, empty states, dirty/save/discard behavior.
5. **Installed-distribution/runtime acceptance** — the plugin service, metadata and
   dependencies start from the same installed Lexeditor checkout/venv/shortcuts a
   normal user runs (or from a future packaged build if distribution changes).
6. **Installed-game acceptance** — real supported installation, actual deployment
   or loader package, reversible removal/revert, game launch and native behavior.

A passing level never implies the next one. In particular, CI cannot prove native
visual/audio/gameplay behavior unless it actually runs that environment.

Useful test cases for every writable format include truncated input, invalid counts,
out-of-range values, unknown enum/flag values, no-op save, one-field save, multiple
edits, external source modification, atomic-write failure and reopen after save.

Run at minimum:

```text
python plugin_metadata.py
python tools/generate_credits.py --check
python app.py --list
python app.py --game <id> --check
python app.py --game <id> --smoke
```

Then run the plugin-specific and shared browser/distribution suites relevant to the
changed files.

## 9. Definition of done

A new plugin is not complete until the applicable items below are true:

- [ ] Research pass found/reviewed existing open-source tools, loaders and docs.
- [ ] Reused/adapted code has compatible licensing and required notices.
- [ ] The closest existing Lexeditor lifecycle/deployment precedent was reused where it fits.
- [ ] Supported game edition/build boundary is explicit and safely detected.
- [ ] Installed source data and writable project/deployment output are separated.
- [ ] One representative vertical slice works end to end.
- [ ] Data Map honestly records editable, partial and unsupported areas.
- [ ] `ui/mod-loading.json` explains loader, structure and overriding semantics.
- [ ] All helper software is bundled and installed during first-time setup.
- [ ] Every helper appears in the main-menu Updates drawer with distinct installed, pinned and upstream versions.
- [ ] Helper automatic updates are disabled and remain disabled after an update or repair.
- [ ] First-time setup works without a preinstalled helper; helper installation and update settings are verified.
- [ ] Credits contain at least one explicit attribution/declaration and regenerate cleanly; `plugins/<id>/credits.md` holds the same record.
- [ ] Unknown/unmodeled data is preserved; no-op and changed round-trips are tested.
- [ ] Save/deployment writes are atomic and recovery/revert behavior is defined.
- [ ] The deployment, revert, launch and native acceptance path was designed before the endgame.
- [ ] Shared UI controls are used instead of game-local clones.
- [ ] Info and Data Map use the shell buttons, with no duplicate content tabs.
- [ ] Record lists use shared search and pagination, verified across several pages.
- [ ] Integration icons are visible in the rendered Data Map.
- [ ] Loading a page cannot leave the previous page under the new tab selection.
- [ ] Necessary help uses info bubbles; generic disclaimer banners are absent.
- [ ] Safe smoke test exists and does not mutate a real installation/save.
- [ ] Browser/shared-UI acceptance passes.
- [ ] The normal installed Lexeditor runtime can start the plugin and its dependencies.
- [ ] Real installed-game deployment/loading has been exercised when the plugin claims it.
- [ ] Native gameplay/visual/audio behavior has been checked for features that require it.
- [ ] No proprietary game dumps, credentials or unlicensed assets were committed.
- [ ] The original issue and PR state accurately describe what remains.
- [ ] The plugin stayed in one implementation PR unless there was a concrete shared-infrastructure reason to split work.

## 10. Common time-wasters to avoid

- Reverse-engineering before searching for existing source/documentation.
- Reimplementing a parser/library that can legally and cleanly be reused.
- Inventing a new plugin lifecycle when an existing Lexeditor precedent already fits.
- Building UI before proving serialization and the loader/deployment boundary.
- Inventing a new mod loader when the established ecosystem loader is sufficient.
- Leaving deployment/revert/native acceptance design until every editor screen is finished.
- Assuming one observed game build proves offsets/layout for every edition.
- Editing installed archives directly as the normal editor-save path.
- Reconstructing whole binary files from modeled fields and destroying unknown data.
- Treating every same-file collision as unavoidable when semantic merging is feasible.
- Forgetting credits until the end and then trying to reconstruct provenance from memory.
- Splitting one plugin into many PRs that cannot be meaningfully accepted alone.
- Calling source tests, screenshots or CI "in-game acceptance."

When in doubt, prefer **research, reuse, preservation, explicit boundaries and one
end-to-end proof** over breadth. Those five habits save more plugin-development time
than clever code written before the game's existing ecosystem is understood.

### Help for new users

Use the shared question-mark help on tabs, sections, and fields. Explain what
the player can change, the effect in the game, and how related controls work
together. Explain special values and preview-only controls. State unknown
behaviour clearly. Check that help is reachable by mouse and keyboard and does
not activate the control beneath it. Storage-format notes alone are not user help.
