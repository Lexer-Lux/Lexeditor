# Factorio plugin research

PR: #492 `Factorio Plugin`
Branch: `codex/factorio-plugin`
Master baseline at start: `a47f0a57f8b44113b0ca1d42e5795f59f707372a`
Current reconciled master: `95a15cae8f0e53f2884222f573f8222600aaae58`

## Repository references

- PR #492 scope was isolated on 2026-09-22 by rebuilding the current Factorio tree delta directly on master `95a15cae8f0e53f2884222f573f8222600aaae58`. The pre-isolation history is preserved at `backup/pr-492-pre-isolation-e1fac3a` (`e1fac3a1c54bf159c6b8ef791da78989cce8d0ae`); it is not an implementation branch and has no PR.

- Starting revisions: `AGENTS.md` `ec8d363d…`, `docs/ADDING_A_GAME.md` `78a987c5…`, Blank `cd3c79ba…`, RDR2 `9d11f8a0…`.
- Current revisions after reconciliation: `AGENTS.md` `41355ce0b783c55a03ad250ed279666f785c6e67`; `docs/ADDING_A_GAME.md` `7fe6d35dd82fa3fe4e6378ca558ecbb0a316c4c0`; `docs/UI-MANUAL.md` `14a3269992031d7e7893fcb127728a48b944e71f`.
- Current shared UI references: Blank `plugins/blank/editor.html` `b0b235d010952bf0c7524dcce172ef72f7cf63e4`; RDR2 `plugins/rdr2/editor.html` `899bfdb45cbf25da55aed43a590db6ee476b523b`.
- `ui/component-catalog.js` now exists on current master at `a11e52e31ee92bce495c6cbf54a66d4597d52139`. The starting-master 404 is historical only.
- Current plugin UI contract uses markup-only `editor.html`, relative game-local JS/CSS modules, shared `plugin_http.PluginRequestHandler.send_page_module`, and no new game CSS selectors targeting shared `.lex-*` classes.
- No pre-existing Factorio codex/worklog path was found on the starting master.

## Official Factorio references

Reviewed before implementation:

- Factorio Wiki — Modding tutorial: https://wiki.factorio.com/Tutorial:Modding_tutorial
- Factorio Wiki — Mod structure: https://wiki.factorio.com/Tutorial:Mod_structure
- Factorio Wiki — command-line parameters / `--dump-data`: https://wiki.factorio.com/Command_line_parameters
- Factorio prototype/runtime documentation: https://lua-api.factorio.com/latest/
- Factorio prototype JSON auxiliary documentation: https://lua-api.factorio.com/latest/auxiliary/prototype-json.html
- Wube `factorio-data`: https://github.com/wube/factorio-data

The current prototype documentation was rechecked on 2026-09-22 and reports version **2.1.20**. The plugin target is the **Factorio 2.1.x** prototype line and exports `factorio_version: "2.1"`. Generated mod/dependency versions use Factorio's exact three-component 0–65535 format.

## Data lifecycle / trust boundary

Factorio source mods build `data.raw` during the prototype stages `data.lua`, `data-updates.lua`, and `data-final-fixes.lua`, in dependency/load order. Lexeditor does not evaluate any of those source files.

The import boundary is Factorio's own `--dump-data` JSON output copied into a project as `source/data-raw-dump.json`. An optional copied `source/mod-list.json` supplies enabled source-mod names for late override load ordering only.

Lexeditor saves its own `overrides.json` and exports a separate native Factorio mod. The generated `data-final-fixes.lua` contains only validated assignments to existing prototype identities. It never copies arbitrary Lua from the source mods.

## Implemented semantic scope

- Recipes: `enabled`, `energy_required` (> 0.001), `maximum_productivity` (>= 0).
- ItemPrototype descendants: inherited `stack_size` across current 2.1 item subclasses, including gun/item-with-label/item-with-tags and Space Age's space-platform-starter-pack; fixed-one subclasses and `not-stackable` records remain at 1.
- Crafting machines: assembling machines, furnaces and rocket silos, inherited `crafting_speed` (> 0).
- Technologies: `enabled`, validated prerequisite TechnologyIDs with cycle rejection, fixed `unit.count` (> 0 uint64), and finite `unit.time`. Formula-controlled counts remain read-only.
- Reference diagnostics cover modeled recipe item/fluid references, recipe/machine categories, technology prerequisites, and unlock-recipe effects.

Anything else remains visible as unsupported/partial in the Data Map rather than being promoted to complete support.

## DLC/version detection

The configured installation's `data/base/info.json` supplies the exact Factorio version. The plugin fails its support flag closed outside the 2.1 major/minor line.

Space Age, Quality, and Elevated Rails installation state is detected from their official data-mod `info.json` files. Separately, copied `mod-list.json` identifies whether Space Age was enabled in the prototype dump's source mod set. Installed and active are intentionally not conflated.

## Open-source survey / licenses

- Wube `factorio-data`: official examples/reference; no code is vendored.
- `jacquev6/factorio-data-raw-json-schema`: useful dump-format research reference. No repository license file was found during the audit, so no code/schema was copied or bundled.
- `slikts/factorio-data`: MIT, archived and targeted at old Factorio data; surveyed but not used as a dependency.
- Lua-executing extraction approaches were rejected because they violate the no-untrusted-Lua host boundary.

No third-party helper is required or bundled. Factorio's native mod loader consumes the generated package, so there is no plugin helper update channel to manage.

## Current mod-portal compatibility survey

Rechecked 2026-09-22 against public 2.1 releases. This is loader/metadata evidence only, not an in-game acceptance claim.

- Factory Planner 2.1.x uses the internal name `factoryplanner` and a three-component `base >= 2.1.x` requirement.
- Rate Calculator 3.4.1 uses `RateCalculator` with `base >= 2.1.0` and `flib >= 0.17.0`.
- Even Distribution 2.1.0 uses `even-distribution` with a three-component base requirement.
- AAI Industry 0.7.4 uses `aai-industry`, targets Factorio 2.1, and publicly documents changes to technologies, recipes, machines and compatibility with Space Age/Bob's/Angel's. Its portal license is Limited Distribution Only, so Lexeditor uses metadata only and does not redistribute the mod.
- Krastorio 2 2.1.2 uses `Krastorio2`, targets Factorio 2.1, and is a current overhaul adding/changing buildings, items, recipes and technologies. Its public source is reference/compatibility evidence only; Lexeditor does not bundle it.
- Those real identifiers (mixed case and hyphenated names included) are covered by the dependency/load-order regression. The two overhaul/content cases exercise names for mods that materially change prototype families Lexeditor edits. Enabled source mods remain optional dependencies of the generated override, so Lexeditor loads after them without making them permanently mandatory.
- This establishes dependency grammar/load-order compatibility only. Actual coexistence and overlapping-value behavior still require loading the isolated candidate in Factorio with the same source-mod profile used to create the dump.
