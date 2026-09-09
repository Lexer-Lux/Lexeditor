"""Regression audit for Lexeditor's shared UI contract.

This is deliberately source-level: it catches game-local regressions and old UI
concepts before they can silently reappear. Visual acceptance still belongs in
the running desktop app, but these invariants are structural and deterministic.
"""
from __future__ import annotations

from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


framework = text("ui/framework.js")
css = text("ui/framework.css")
manual = text("docs/UI-MANUAL.md")
host = text("desktop_host.py")
github = text("github_integration.py")
blank = text("games/blank/editor.html")
warband = text("games/warband/editor.html")

# Shared chrome is global by construction. Every real editor shell must load the
# shared framework, and a game theme may not swap the info-bubble glyph back to
# its own game font. This is what keeps Blank fixes from becoming Blank-only.
plugin_editors = sorted((ROOT / "games").glob("*/editor.html"))
require(plugin_editors, "no game editor shells were found")
for editor_path in plugin_editors:
    source = editor_path.read_text(encoding="utf-8")
    relative = editor_path.relative_to(ROOT).as_posix()
    require('/shared/framework.css' in source and '/shared/framework.js' in source,
            f"{relative} is bypassing the shared UI framework")
    require("Lexer Mode" not in source and "lexerMode" not in source,
            f"legacy Lexer Mode leaked into {relative}")
    for block in re.findall(r"\.lex-info-help\s*\{([^}]*)\}", source, re.I | re.S):
        family = re.search(r"font-family\s*:\s*([^;]+)", block, re.I)
        require(not family or "--lex-symbol-font" in family.group(1),
                f"{relative} overrides info-bubble glyph typography with a game font")
    for block in re.findall(r"\.lex-info-help\s*>\s*span\s*\{([^}]*)\}", source, re.I | re.S):
        require(not re.search(r"(?:transform|translate|top|bottom|left|right|font-family)\s*:", block, re.I),
                f"{relative} overrides shared info-bubble glyph geometry")

# Every plugin Info page gets the same three Mod Loading bullets from one
# reviewed registry. The registry and discovered plugin IDs must remain exact so
# adding a plugin without documenting its loader semantics fails CI.
mod_loading = json.loads(text("ui/mod-loading.json"))
mod_loading_plugins = mod_loading.get("plugins", {})
plugin_ids = set()
for plugin_path in sorted((ROOT / "games").glob("*/plugin.py")):
    source = plugin_path.read_text(encoding="utf-8")
    match = re.search(r"\bplugin_id\s*=\s*['\"]([^'\"]+)['\"]", source)
    require(match is not None, f"{plugin_path.relative_to(ROOT)} does not declare plugin_id")
    plugin_ids.add(match.group(1))
require(set(mod_loading_plugins) == plugin_ids,
        "mod-loading.json must cover every discovered plugin exactly")
for plugin_id, details in mod_loading_plugins.items():
    require(set(details) == {"loader", "structure", "overriding"},
            f"{plugin_id} Mod Loading entry must have exactly loader/structure/overriding")
    for field in ("loader", "structure", "overriding"):
        require(isinstance(details[field], str) and details[field].strip(),
                f"{plugin_id} Mod Loading {field} is empty")
require('new URL("mod-loading.json", sharedAssetBase)' in framework and
        'class: "lex-plugin-mod-loading"' in framework,
        "shared Info pages do not load the Mod Loading registry")
for label in ("Mod Loading", "Mod Loader", "Mod Structure", "Overriding"):
    require(label in framework, f"shared Mod Loading panel is missing label: {label}")
require("parent.append(modLoadingPanel(pluginId))" in framework,
        "shared Info pages do not inject the Mod Loading panel")

# One central GitHub workspace, filtered per game.
require('full_name=LEXEDITOR_REPOSITORY.full_name' in host,
        "game GitHub workspaces must use Lexer-Lux/Lexeditor")
require('issue_label=plugin_id' in host,
        "game GitHub workspaces must filter the central issue tracker by plugin label")
require('repository.issue_label' in github and '"--label"' in github,
        "GitHub issue listing must apply the game label filter")

# There is one owner-authenticated Developer Mode and no legacy Lexer Mode.
for path in ("desktop_host.py", "settings_manager.py", "ui/framework.js", "docs/UI-MANUAL.md"):
    require("lexerMode" not in text(path), f"legacy lexerMode remains in {path}")
require("There is no separate Lexer Mode." in manual,
        "manual must explicitly retire Lexer Mode")
require("developerAuthorized" in host,
        "host must expose owner authorization for automatic Developer Mode")

# Blank is the canonical gallery, not a second implementation surface.
require("design-review" not in blank.lower(), "Blank still references Design Review")
require("Editable Table" not in blank, "Blank still exposes a separate Editable Table type/demo")
require(not (ROOT / "ui/design-review.js").exists() and not (ROOT / "ui/design-review.css").exists(),
        "Design Review implementation files still exist")

# The shared model-preview drawer remains a reusable Detail capability, but the
# Warband Items detail is now the actual record editor rather than a preview
# surface. Do not regress it back into a model viewer just because the shared
# framework still supports model previews elsewhere.
require("modelPreview" in framework and "lex-model-preview-drawer" in framework,
        "shared Detail-panel model preview drawer is missing")
require("modelPreview:" not in warband and "Open model preview" not in warband,
        "Warband Items regressed back to a model-preview detail pane")
require("detailField" in warband and "/api/items/save" in warband,
        "Warband Items is not using structured editable Detail properties")
require("warband-item-preview-action" not in warband,
        "Warband still owns its old separate model-preview action")

# Shared semantic-control rules and terminology.
for phrase in ("most human-friendly semantic control", "checkless toggle", "Bitflags", "info bubble", "ref rail"):
    require(phrase.casefold() in manual.casefold(), f"UI manual is missing: {phrase}")

# Every plugin explains its mod loader, in the same five fields, in the same
# words. Five of the eight editors previously said nothing about how their
# output is loaded, which is the first thing anyone installing a mod needs.
for plugin in sorted((ROOT / "games").iterdir()):
    if not (plugin / "editor.html").is_file():
        continue
    editor = (plugin / "editor.html").read_text(encoding="utf-8")
    require("modLoaderSection(" in editor,
            f"{plugin.name} does not render the shared MOD LOADER section")
    for field in ("loader:", "output:", "order:", "safety:", "removal:"):
        require(field in editor,
                f"{plugin.name} mod loader section is missing {field.rstrip(':')}")
require("MOD LOADER" in framework and "MOD_LOADER_FIELDS" in framework,
        "the shared mod loader section is not defined in the framework")

# Property geometry / labels / metadata.
# Pin the single definition, not the number. Three separate declarations of
# this width existed at once and only the last one was live, so edits to the
# others silently did nothing.
require("--lex-detail-label-width:10%" in css.replace(" ", ""),
        "Detail property-name lane is not standardized to the shared 10% lane")
require("grid-template-columns:10%" not in css.replace(" ", ""),
        "A literal property-name lane width is overriding the shared variable")
require("lex-info-help" in css and "place-items:center" in css.replace(" ", ""),
        "info bubble glyph centering is not defined")
require("lex-toggle-name" in css and "writing-mode:horizontal-tb" in css,
        "multi-bool labels are not forced back to horizontal text")
require("data-lex-sort" in css and "lex-info-help" in css,
        "sorted-property metadata/info-bubble handling is missing")

# Ref rail conventions.
require("lex-reference-ll" in framework and "lex-reference-ll" in css,
        "LL ref token is not standardized")
require(re.search(r"lex-reference-ll[^}]*#(?:72ff1e|7fff00|80ff00)", css, re.I | re.S),
        "LL ref token is not lime green")

# Table editing is cell capability, not a table type.
require("beginCellEdit" in framework and "column.edit" in framework,
        "inline editing is not capability-based")
require("options.editable ? \"lex-editable-table\"" not in framework,
        "columnList still has a separate editable-table mode")
require("lex-cell-editing" in css and "font:inherit" in css,
        "inline editor does not preserve table typography/geometry")

# Hover mapping must work both ways even when no peer exists.
require("data-lex-property" in framework and "setColumnLit" in framework,
        "property/column hover mapping is missing")
require("pointerenter" in framework and "lex-column-lit" in css,
        "bidirectional hover affordance is missing")

# Pinning must not deliberately reset split state, and Enabled must participate.
require("enabledColumn(null)" in framework,
        "generated Enabled is still outside column preferences")
require("localStorage.removeItem(layoutKey)" not in framework,
        "pinning still clears the saved panel split and causes a flash")

# Reset feedback and live-control synchronization. The animation must resolve
# the destination color at reset time, so a hovered row returns to its hovered
# color instead of a hard-coded normal background.
require("syncRange(field)" in framework,
        "reset path does not synchronize number/range controls")
require("const target = getComputedStyle(field).backgroundColor" in framework,
        "property reset does not capture the current destination background")
require("getPropertyValue('--lex-accent')" in framework and "field.animate(" in framework,
        "property reset does not animate from the active accent color")
require("{backgroundColor: accent}, {backgroundColor: target}" in framework,
        "property reset does not ease back to the computed destination color")
require("dispatchEvent(new Event('input', {bubbles: true}))" in framework or
        'dispatchEvent(new Event("input", {bubbles: true}))' in framework,
        "reset path does not synchronize dependent slider/fill state")

# Shortcut badges are not duplicated on hover.
require('querySelector(".lex-tab-ordinal,.lex-tab-shortcut")' in framework,
        "tab hover can still duplicate the shortcut badge")

# Graph contract: all-caps large title, margin axes, top variable drawer/strip.
require("toLocaleUpperCase()" in framework and "lex-curve-heading-title" in framework,
        "curve title is not normalized to all caps")
require("lex-curve-variable-drawer" in framework or "lex-curve-variable-strip" in framework,
        "curve variable controls are not shared/top-mounted")
require("lex-curve-axis-name-y" in css and "rotate(180deg)" in css,
        "right-axis text/range rotation contract is missing")

# Project chooser must visibly distinguish editable/enabled/disabled sources.
require("📝" in framework and "lex-project-source-status" in framework,
        "project chooser is missing editable/status markers")
require("grayscale(1)" in css and "lex-project-source-status.disabled" in css,
        "disabled mods are not visually greyed as a whole")

# Internal runbooks do not belong in docs/.
docs = {p.name for p in (ROOT / "docs").iterdir() if p.is_file()}
require("warband-acceptance.md" not in docs and "warband-managed-wse2.md" not in docs,
        "Warband acceptance/runbook files leaked back into docs/")
require((ROOT / "worklog/acceptance/warband/pr-361.md").is_file(),
        "Warband acceptance material was not moved to Worklog")

print("shared UI contract audit passed")