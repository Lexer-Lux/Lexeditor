"""Structured RDR2 Data Map rows and truthful Lexeditor edit coverage."""

from __future__ import annotations

import fnmatch
import re
from collections import OrderedDict
from pathlib import Path


FILE_EXTENSIONS = (
    "meta", "ymt", "ytd", "xml", "dat", "txt", "json", "csv", "tsv",
    "ini", "gxt2", "fxc", "sco", "brf", "dds", "ymap", "ytyp", "yft",
    "ydd", "ydr", "ybn", "awc", "rel",
)
FILE_TOKEN = re.compile(
    rf"(?i)(?:[A-Za-z0-9_*.-]+:/)?[A-Za-z0-9_./*?+-]+\.(?:{'|'.join(FILE_EXTENSIONS)})"
)
FILE_PATH = re.compile(
    rf"(?i)(?:[A-Za-z0-9_.-]+:/)?"
    rf"[A-Za-z0-9_.*?+:-]+(?:/[A-Za-z0-9_.*?+:-]+)*"
    rf"\.(?:{'|'.join(FILE_EXTENSIONS)})"
)
CODE_SPAN = re.compile(r"`([^`]+)`")
STATUS_ONLY_NOTE = re.compile(
    r"(?:No Lexeditor writer exists for (?:this|the) file yet|"
    r"Not integrated(?: in Lexeditor)?|Integrated(?: in Lexeditor)?|"
    r"Partially integrated|Partial)\.?",
    re.IGNORECASE,
)
TABLE_METADATA_NOTE = re.compile(
    r"(?:High|Medium|Low|B|U|B\+U)(?:\s*\(case differs in source\))?\.?",
    re.IGNORECASE,
)


# Status means edit support in Lexeditor, not whether a file exists in the
# current mod. "partial" is used when Lexeditor writes selected records or
# fields but does not expose the complete file structure.
COVERAGE = [
    ("*catalog_sp.ymt", "partial", "items",
     "Items, prices, carry rules, effects, crafting links, and shop stock are editable; uncommon catalog fields remain source-only."),
    ("*strings.gxt2", "partial", "items",
     "Lexeditor edits item and feature text that its pages expose, not every localization entry."),
    ("*loot_table_ped.meta", "integrated", "loot",
     "Loot Tables edits table types, entries, rates, quantities, nesting, creation, and deletion."),
    ("*loot_table_itemgroups.meta", "integrated", "loot",
     "Loot Tables edits table types, entries, rates, quantities, nesting, creation, and deletion."),
    ("*loot_table_reward.meta", "integrated", "loot",
     "Loot Tables edits table types, entries, rates, quantities, nesting, creation, and deletion."),
    ("*loot_table_container.meta", "integrated", "loot",
     "Loot Tables edits table types, entries, rates, quantities, nesting, creation, and deletion."),
    ("*loot_table_herb.meta", "integrated", "loot",
     "Loot Tables edits table types, entries, rates, quantities, nesting, creation, and deletion."),
    ("*loot_items_matrix.meta", "integrated", "loot",
     "The loot matrix editor writes animal damage-quality output rows."),
    ("*goals_sp.meta", "partial", "challenges",
     "Challenges edits the supported goal ranks, conditions, rewards, and localized text."),
    ("*challenges_sp.meta", "partial", "challenges",
     "Challenges edits the supported strand and rank definitions."),
    ("*crimeinformation.meta", "partial", "crime",
     "Crime & Law edits the supported crime values, detection, witness, timeout, wanted, and disable fields."),
    ("*dispatch.meta", "partial", "crime",
     "Crime & Law edits supported dispatch and wanted-response values."),
    ("*dispatchresponses/wilderness/bountyhunters.meta", "partial", "crime",
     "Crime & Law edits supported bounty-hunter settings, cooldowns, phases, and groups."),
    ("*bountyhunters.meta", "partial", "crime",
     "Crime & Law edits supported bounty-hunter settings, cooldowns, phases, and groups."),
    ("*tune/incidentstuning.meta", "partial", "crime",
     "Only the supported wanted-incident evasion field is editable."),
    ("*incidentstuning.meta", "partial", "crime",
     "Only the supported wanted-incident evasion field is editable."),
    ("*ai/combatbehaviour.meta", "partial", "ai",
     "AI and Mobs edit scalar profile fields; graph structure and record creation are not exposed."),
    ("*combatbehaviour.meta", "partial", "ai",
     "AI and Mobs edit scalar profile fields; graph structure and record creation are not exposed."),
    ("*ai/pedperception.meta", "partial", "ai",
     "AI edits scalar perception profile fields and can create the mod replacement from the vanilla extract."),
    ("*pedperception.meta", "partial", "ai",
     "AI edits scalar perception profile fields and can create the mod replacement from the vanilla extract."),
    ("*ai/pedaccuracy.meta", "partial", "ai",
     "AI edits existing scalar values; it does not add or remove XML structure."),
    ("*pedaccuracy.meta", "partial", "ai",
     "AI edits existing scalar values; it does not add or remove XML structure."),
    ("*ai/peddistraction.meta", "partial", "ai",
     "AI edits existing scalar values; it does not add or remove XML structure."),
    ("*peddistraction.meta", "partial", "ai",
     "AI edits existing scalar values; it does not add or remove XML structure."),
    ("*ai/peddamage.meta", "partial", "ai",
     "AI edits existing scalar values; it does not add or remove XML structure."),
    ("*peddamage.meta", "partial", "ai",
     "AI edits existing scalar values; it does not add or remove XML structure."),
    ("*ai/noisetuning.meta", "partial", "ai",
     "AI edits existing scalar values; it does not add or remove XML structure."),
    ("*noisetuning.meta", "partial", "ai",
     "AI edits existing scalar values; it does not add or remove XML structure."),
    ("*pedhealth.meta", "partial", "mobs",
     "Mobs edits existing health, stamina, recharge, ability, and energy archetype fields."),
    ("*weapons.ymt", "partial", "weapons",
     "Weapons edits supported weapon and ammo scalar fields while preserving the required layered stack."),
    ("*weapon_*.ymt", "partial", "weapons",
     "Weapons edits supported override records in the layered weapon stack."),
    ("*weaponcomponents.meta", "partial", "weapons",
     "Weapons preserves and writes supported component layers; not every component field has a dedicated control."),
    ("*patch_weaponcomponents.meta", "partial", "weapons",
     "Weapons preserves and writes supported component layers; not every component field has a dedicated control."),
    ("*003_weaponcomponents.meta", "partial", "weapons",
     "Weapons preserves and writes supported component layers; not every component field has a dedicated control."),
    ("*004_weaponcomponents.meta", "partial", "weapons",
     "Weapons preserves and writes supported component layers; not every component field has a dedicated control."),
]


PROJECT_ROWS = [
    ("quickselectitems.ymt", "Item-to-radial-slot assignments and their display order.",
     "Editable from the Items detail panel with controlled slot selectors; quick-select menu layout remains outside this editor.", "integrated", "items"),
    ("GameplayTweaks.ini", "Gameplay feature switches and tuning values used by the ASI.",
     "The Settings page preserves comments and applies schema ranges.", "integrated", "settings"),
    ("alcohol_strengths.csv", "Per-item alcohol strengths and intoxication values.",
     "Editable from the Effects page.", "integrated", "effects"),
    ("custom_crafting_recipes.tsv", "Custom crafting recipes, ingredients, outputs, stations, and unlocks.",
     "Editable from Crafting > Custom with validation.", "integrated", "crafting"),
    ("projectile_speed_multipliers.csv", "Per-cartridge projectile-speed multipliers used by the runtime.",
     "Editable only when the runtime switching contract is available.", "partial", "weapons"),
    ("honor_actions.csv", "Honor values for supported player actions.",
     "Editable from Crime & Law.", "integrated", "crime"),
    ("merchant_buy_overrides.csv", "Per-merchant accept, reject, or vanilla item overrides.",
     "Editable from Shops > Buys.", "integrated", "shops"),
    ("mob_archetype_overrides.csv", "Runtime model-to-health-archetype overrides.",
     "Editable from the Mobs model view; observed probe data remains read-only evidence.", "integrated", "mobs"),
    ("parseddata/0x0BA63B3D.ymt", "Merchant buyer exception data consumed by the game.",
     "Shops edits the supported merchant/item override records only.", "partial", "shops"),
]


def _clean(value: str) -> str:
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = value.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", value).strip(" |")


def _file_tokens(value: str) -> list[str]:
    """Return only complete filename cells or complete Markdown code spans.

    DATA_MAP.md also contains prose that cites files. Treating every cited
    token as a table row produced shorthand names such as ``_8.xml`` and gave
    one file the description that belonged to an entire paragraph.
    """
    found: list[str] = []
    code_spans = CODE_SPAN.findall(value)
    candidates = code_spans if code_spans else re.split(r"\s*;\s*", _clean(value))
    for candidate in candidates:
        candidate = candidate.strip().replace("\\", "/")
        if FILE_PATH.fullmatch(candidate) and not candidate.casefold().startswith(("http:", "https:")):
            found.append(candidate)
    return list(dict.fromkeys(found))


def _bullet_entry(lines: list[str], index: int) -> tuple[str, int]:
    """Join one Markdown bullet with its indented continuation lines."""
    content = lines[index].lstrip()[2:].strip()
    cursor = index + 1
    while cursor < len(lines):
        continuation = lines[cursor]
        if not continuation.startswith(("  ", "\t")):
            break
        if continuation.lstrip().startswith(("- ", "* ")):
            break
        content = f"{content} {continuation.strip()}"
        cursor += 1
    return content, cursor


def _leading_file_list(value: str) -> tuple[list[str], str]:
    """Read a leading comma-separated list of code-formatted filenames."""
    files: list[str] = []
    cursor = 0
    while True:
        match = CODE_SPAN.search(value, cursor)
        if match is None:
            break
        separator = value[cursor:match.start()]
        if files and not re.fullmatch(r"[\s,;/]*(?:and\s+)?", separator):
            break
        if not files and separator.strip():
            break
        token = match.group(1).strip().replace("\\", "/")
        if not FILE_PATH.fullmatch(token):
            break
        files.append(token)
        cursor = match.end()
    return files, value[cursor:].lstrip(" .,:;-—")


def _shorthand_range(first: str, tail: str) -> tuple[list[str], str]:
    """Expand forms such as timecycle_mods_1.xml-`_8.xml`."""
    match = re.match(
        rf"\s*-\s*`_(\d+)\.({'|'.join(FILE_EXTENSIONS)})`",
        tail,
        flags=re.IGNORECASE,
    )
    start = re.fullmatch(r"(.+_)(\d+)\.([A-Za-z0-9]+)", first)
    if match is None or start is None or start.group(3).casefold() != match.group(2).casefold():
        return [first], tail
    first_number = int(start.group(2))
    last_number = int(match.group(1))
    if last_number < first_number or last_number - first_number > 50:
        return [first], tail
    files = [f"{start.group(1)}{number}.{start.group(3)}"
             for number in range(first_number, last_number + 1)]
    return files, tail[match.end():]


def _parse_bullet(content: str) -> tuple[list[str], str] | None:
    """Parse inventory bullets, but ignore ordinary prose that only cites files."""
    plain = re.match(
        rf"(?P<file>{FILE_PATH.pattern.replace('(?i)', '')})\s+(?:-|—|:)\s+(?P<description>.+)",
        content,
        flags=re.IGNORECASE,
    )
    if plain:
        return [plain.group("file")], plain.group("description")

    first_code = re.match(r"`([^`]+)`", content)
    if first_code:
        first = first_code.group(1).strip().replace("\\", "/")
        if not FILE_PATH.fullmatch(first):
            return None
        files, tail = _shorthand_range(first, content[first_code.end():])
        description = tail.lstrip(" .,:;-—")
        if description.casefold().startswith("are "):
            description = f"The listed files {description}"
        elif description.casefold().startswith("is "):
            description = f"This file {description}"
        return files, description

    category = re.match(r"\*\*([^*]+?):\*\*\s*(.+)", content)
    if category:
        files, description = _leading_file_list(category.group(2))
        if files:
            label = _clean(category.group(1))
            return files, f"{label}. {description}".strip()
    return None


def _coverage(filename: str) -> tuple[str, str, str | None]:
    normalized = filename.replace("\\", "/").casefold()
    for pattern, status, target, note in COVERAGE:
        if fnmatch.fnmatch(normalized, pattern.casefold()):
            return status, note, target
    suffix = Path(normalized).suffix
    if suffix in {".ytd", ".ydd", ".ydr", ".yft", ".ybn", ".ymap", ".ytyp", ".awc", ".rel", ".dds", ".brf", ".sco"}:
        return "not-integrated", "This binary resource needs a dedicated game-resource editor; Lexeditor does not write it.", None
    if "script_rel/" in normalized or "decompiled" in normalized:
        return "not-integrated", "Lexeditor may use this as read-only research evidence, but it does not rewrite game scripts.", None
    return "not-integrated", "", None


def _join_note(left: str, right: str) -> str:
    left = left.strip()
    right = right.strip()
    if not left:
        return right
    if not right:
        return left
    if left[-1] not in ".!?;:":
        left += "."
    return f"{left} {right}"


def _meaningful_note(controls: str, notes: str) -> str:
    """Remove status-only notes and text already stated by the controls cell."""
    controls = _clean(controls).rstrip(".")
    note = _clean(notes)
    if not note or STATUS_ONLY_NOTE.fullmatch(note):
        return ""
    if controls and note.casefold().rstrip(".") == controls.casefold():
        return ""
    if controls and note.casefold().startswith(controls.casefold()):
        remainder = note[len(controls):].lstrip(" .,:;-—")
        if not remainder or STATUS_ONLY_NOTE.fullmatch(remainder):
            return ""
        return remainder
    return note


def _table_note(header: str, value: str) -> str:
    """Keep explanatory table cells, not classification or confidence labels."""
    value = _clean(value)
    if not value or TABLE_METADATA_NOTE.fullmatch(value):
        return ""
    if any(term in header for term in (
        "family", "group", "layer", "confidence", "evidence",
    )):
        return ""
    return value


def _add(rows: OrderedDict[str, dict], filename: str, controls: str, notes: str,
         section: str) -> None:
    filename = _clean(filename)
    if not filename:
        return
    key = filename.casefold()
    status, integration_note, target = _coverage(filename)
    controls = _clean(controls) or f"Documented game data in the {section or 'RDR2'} inventory."
    context = _meaningful_note(controls, _join_note(notes, integration_note))
    row = {
        "filename": filename,
        "controls": controls,
        "notes": context,
        "status": status,
        "target": target,
        "openable": target is not None,
    }
    existing = rows.get(key)
    if existing is None:
        rows[key] = row
        return
    if len(row["controls"]) > len(existing["controls"]):
        existing["controls"] = row["controls"]
    if len(row["notes"]) > len(existing["notes"]):
        existing["notes"] = row["notes"]


def build_data_map(path: Path) -> dict:
    """Convert the researched Markdown inventory into four-column UI rows."""
    text = path.read_text(encoding="utf-8")
    rows: OrderedDict[str, dict] = OrderedDict()
    section = ""
    table_headers: list[str] = []
    table_file_index: int | None = None
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("## "):
            section = _clean(line[3:])
            index += 1
            continue
        if line.startswith("|") and line.count("|") >= 3:
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            next_line = lines[index + 1] if index + 1 < len(lines) else ""
            is_header = (
                next_line.startswith("|")
                and set(next_line.replace("|", "").replace(":", "").replace(" ", "")) <= {"-"}
            )
            if is_header:
                table_headers = [_clean(cell).casefold() for cell in cells]
                table_file_index = next(
                    (cell_index for cell_index, header in enumerate(table_headers)
                     if "file" in header),
                    None,
                )
                index += 1
                continue
            if len(cells) < 2:
                index += 1
                continue
            if all(set(cell) <= {"-", ":", " "} for cell in cells):
                index += 1
                continue
            if table_file_index is None or table_file_index >= len(cells):
                index += 1
                continue
            tokens = _file_tokens(cells[table_file_index])
            purpose_index = next(
                (cell_index for cell_index, header in enumerate(table_headers)
                 if cell_index != table_file_index and any(term in header for term in (
                     "system", "role", "purpose", "gameplay", "visible controls",
                     "extracted structure", "desired result",
                 ))),
                None,
            )
            if purpose_index is None or purpose_index >= len(cells):
                controls = f"Documented game data in the {section or 'RDR2'} inventory."
                notes = " ".join(
                    value for cell_index, cell in enumerate(cells)
                    if cell_index != table_file_index
                    and (value := _table_note(
                        table_headers[cell_index] if cell_index < len(table_headers) else "",
                        cell,
                    ))
                )
            else:
                controls = cells[purpose_index]
                notes = " ".join(
                    value for cell_index, cell in enumerate(cells)
                    if cell_index not in {table_file_index, purpose_index}
                    and (value := _table_note(
                        table_headers[cell_index] if cell_index < len(table_headers) else "",
                        cell,
                    ))
                )
            for token in tokens:
                _add(rows, token, controls, notes, section)
            index += 1
            continue
        if line.lstrip().startswith(("- ", "* ")):
            content, next_index = _bullet_entry(lines, index)
            parsed = _parse_bullet(content)
            if parsed:
                tokens, description = parsed
                for token in tokens:
                    _add(rows, token, description, "", section)
            index = next_index
            continue
        index += 1

    for filename, controls, notes, status, target in PROJECT_ROWS:
        rows[filename.casefold()] = {
            "filename": filename,
            "controls": controls,
            "notes": notes,
            "status": status,
            "target": target,
            "openable": True,
        }

    values = sorted(rows.values(), key=lambda row: row["filename"].casefold())
    counts = {status: sum(row["status"] == status for row in values)
              for status in ("integrated", "partial", "not-integrated")}
    return {"rows": values, "counts": counts, "path": str(path)}
