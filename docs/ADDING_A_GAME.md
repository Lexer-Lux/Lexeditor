# Make a game plugin for Lexeditor

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

### Runtime helpers

If a helper such as FFNx, Memoria, WSE2, RedHook or another loader/runtime is
required, keep its installed version, Lexeditor-pinned version and newest upstream
version distinct. Do not let a helper silently self-update and break the supported
stack.

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

Create `games/<game>/__init__.py` and `plugin.py`. Export one `GamePlugin` named
`PLUGIN`; discovery is automatic. Give it a unique letters/numbers/hyphens ID,
name, subtitle, description, accent, `check`, `launch`, `session_factory`, and a
safe `smoke()` before shipping.

```python
from pathlib import Path
from plugin_api import GamePlugin
from service_session import LocalPluginSession

ROOT = Path(__file__).resolve().parents[2]

def check():
    return []  # Replace with real checks; never invent readiness.

def session(extra_env=None):
    return LocalPluginSession(module="games.example.server", plugin_id="example",
                              app_root=ROOT, check=check, extra_env=extra_env)

def launch():
    from desktop_host import run_host
    return run_host({"example": PLUGIN}, "example")

PLUGIN = GamePlugin(
    plugin_id="example",
    name="Example",
    subtitle="Example game",
    description="Edits the supported Example records.",
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

Start with `games/blank` as the shared-control gallery, not as markup to copy.
Load `/shared/framework.css` and `/shared/framework.js` and use the common controls
in `docs/UI-MANUAL.md`.

Keep record identity in the master list and editable properties in the detail pane.
Use semantic controls: checkbox/toggle for booleans, selects for known enums,
bounded number/range controls for real numeric limits, and decomposed bitflags when
possible. Help text should explain effect, unit, special values and restart/runtime
requirements rather than restating the field name.

Credits and Mod Loading are shared Info-page sections; do not hand-build per-game
copies. A plugin still has to supply their data, and discovery will reject it if it
does not.

## 7. Credits and provenance are a hard requirement

Update `ui/credits-sources.json` while researching. Credit:

- open-source code that was copied or adapted;
- projects whose source materially supplied format/reverse-engineering knowledge;
- external helpers/tools Lexeditor relies on;
- documentation/authors that materially resolved behavior or structure;
- required license and source notices for redistributed code/assets.

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
- [ ] Credits contain at least one explicit attribution/declaration and regenerate cleanly.
- [ ] Unknown/unmodeled data is preserved; no-op and changed round-trips are tested.
- [ ] Save/deployment writes are atomic and recovery/revert behavior is defined.
- [ ] The deployment, revert, launch and native acceptance path was designed before the endgame.
- [ ] Shared UI controls are used instead of game-local clones.
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
