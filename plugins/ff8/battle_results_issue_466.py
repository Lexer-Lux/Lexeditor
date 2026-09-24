"""Three-column battle-results layout contract for GitHub issue #466.

Requested behavior: the battle reward screen shows Item, Quantity and Help
columns so every received item's help text is visible at once. The separate
selected-item HELP box goes away and the reward table uses the freed space.
Reward amounts, inventory updates and confirmation behavior are preserved,
and descriptions come from the current item text (including mod edits),
never from hard-coded strings.

Help-text source: kernel.bin item text. Battle items (IDs 0-32) read text
section 39, non-battle items read text section 40; slot 1 of each record is
the description (``kernel_text``). ``item_text_from_kernel`` builds the
lookup from ``formats.kernel_text_rows()`` output, so mod edits flow
through without new plumbing.

No proved results-screen drawing hooks exist yet, so this module emits no
executable bytes and activation fails closed until they do. The layout and
award models below are pure and tested headless.
"""

from __future__ import annotations

import textwrap


DEFAULT_BATTLE_RESULTS_HELP = False

# No proved results-screen drawing hooks exist, so enabling must fail closed
# rather than install guessed bytes. Flip to True only with a verified
# HELP-box removal plus available-space analysis and the matching
# build_hext() fragment.
BATTLE_RESULTS_HELP_AVAILABLE = False
BATTLE_RESULTS_HELP_BLOCKER = (
    "The three-column battle reward screen has no proved native drawing "
    "hooks yet, so it cannot be enabled. The layout model below stays "
    "available so reward rows keep validating against live item text."
)

BATTLE_ITEM_TEXT_SECTION = 39
NON_BATTLE_ITEM_TEXT_SECTION = 40
BATTLE_ITEM_COUNT = 33
ITEM_COUNT = 200
NAME_SLOT = 0
HELP_SLOT = 1

MIN_HELP_WIDTH = 10
MAX_HELP_WIDTH = 80
DEFAULT_HELP_WIDTH = 40


def _clean_item_id(item_id) -> int:
    if isinstance(item_id, bool) or not isinstance(item_id, int):
        raise ValueError("Battle reward item id must be a whole number")
    if not 0 <= item_id < ITEM_COUNT:
        raise ValueError(
            f"Battle reward item id must be from 0 to {ITEM_COUNT - 1}")
    return item_id


def _clean_quantity(quantity) -> int:
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise ValueError("Battle reward quantity must be a whole number")
    if quantity < 1:
        raise ValueError("Battle reward quantity must be at least 1")
    return quantity


def _clean_reward(reward: dict) -> dict:
    if not isinstance(reward, dict):
        raise ValueError("Battle rewards must be objects")
    return {
        "itemId": _clean_item_id(reward.get("itemId")),
        "quantity": _clean_quantity(reward.get("quantity")),
    }


def _clean_help_width(width) -> int:
    if isinstance(width, bool) or not isinstance(width, int):
        raise ValueError(
            f"Battle reward help width must be from {MIN_HELP_WIDTH} "
            f"to {MAX_HELP_WIDTH}")
    if not MIN_HELP_WIDTH <= width <= MAX_HELP_WIDTH:
        raise ValueError(
            f"Battle reward help width must be from {MIN_HELP_WIDTH} "
            f"to {MAX_HELP_WIDTH}")
    return width


def item_text_from_kernel(kernel_rows: dict) -> dict:
    """Build ``{"names": ..., "helps": ...}`` keyed by item id.

    ``kernel_rows`` is ``formats.kernel_text_rows()`` output for the current
    dataset, so mod edits are already reflected. Battle-text section 39 maps
    record N to item N; non-battle section 40 maps record N to item 33 + N.
    """
    if not isinstance(kernel_rows, dict) or not isinstance(
            kernel_rows.get("rows"), list):
        raise ValueError("Battle reward item text needs kernel text rows")
    names: dict[int, str] = {}
    helps: dict[int, str] = {}
    for row in kernel_rows["rows"]:
        if not isinstance(row, dict):
            raise ValueError("Battle reward item text rows must be objects")
        section = row.get("sectionId")
        if section not in (BATTLE_ITEM_TEXT_SECTION, NON_BATTLE_ITEM_TEXT_SECTION):
            continue
        record = row.get("recordId")
        slot = row.get("slot")
        value = row.get("value")
        if (isinstance(record, bool) or not isinstance(record, int)
                or record < 0 or slot not in (NAME_SLOT, HELP_SLOT)
                or not isinstance(value, str)):
            raise ValueError("Battle reward item text rows must carry record text")
        item_id = record if section == BATTLE_ITEM_TEXT_SECTION else (
            BATTLE_ITEM_COUNT + record)
        if not 0 <= item_id < ITEM_COUNT:
            raise ValueError(f"Battle reward item id is out of range: {item_id}")
        if slot == NAME_SLOT:
            names[item_id] = value
        else:
            helps[item_id] = value
    return {"names": names, "helps": helps}


def wrap_description(text: str, width: int = DEFAULT_HELP_WIDTH) -> list[str]:
    """Word-wrap one help text; long words break so nothing is cut off."""
    if not isinstance(text, str):
        raise ValueError("Battle reward help text must be a string")
    lines = textwrap.wrap(
        " ".join(text.split()), width=_clean_help_width(width),
        break_long_words=True, break_on_hyphens=False)
    return lines or [""]


def build_reward_rows(rewards: list[dict], names: dict, helps: dict, *,
                      help_width: int = DEFAULT_HELP_WIDTH) -> list[dict]:
    """Build one laid-out row per reward: name, quantity and wrapped help.

    Every row carries its own help lines, so no selection is needed to read
    them. Amounts pass through untouched.
    """
    if not isinstance(rewards, list):
        raise ValueError("Battle rewards must be a list")
    if not isinstance(names, dict) or not isinstance(helps, dict):
        raise ValueError("Battle reward names and help must be lookups")
    width = _clean_help_width(help_width)
    rows = []
    for reward in rewards:
        cleaned = _clean_reward(reward)
        item_id = cleaned["itemId"]
        name = names.get(item_id)
        help_text = helps.get(item_id)
        if not isinstance(name, str) or not name:
            raise ValueError(f"Battle reward item {item_id} has no name")
        if not isinstance(help_text, str) or not help_text:
            raise ValueError(f"Battle reward item {item_id} has no help text")
        lines = wrap_description(help_text, width)
        rows.append({
            "itemId": item_id,
            "name": name,
            "quantity": cleaned["quantity"],
            "helpLines": lines,
            "height": len(lines),
        })
    return rows


def layout_table(rows: list[dict], *, name_width: int = 24,
                 quantity_width: int = 8,
                 help_width: int = DEFAULT_HELP_WIDTH) -> dict:
    """Stack laid-out rows into Item/Quantity/Help columns without overlap.

    Row origins accumulate from row heights, so wrapped descriptions size
    their own row and can neither overlap the next row nor be cut off.
    """
    if not isinstance(rows, list):
        raise ValueError("Battle reward rows must be a list")
    for width, label in ((name_width, "name"), (quantity_width, "quantity")):
        if isinstance(width, bool) or not isinstance(width, int) or width < 1:
            raise ValueError(f"Battle reward {label} width must be at least 1")
    help_columns = _clean_help_width(help_width)
    columns = [
        {"id": "item", "x": 0, "width": name_width},
        {"id": "quantity", "x": name_width, "width": quantity_width},
        {"id": "help", "x": name_width + quantity_width,
         "width": help_columns},
    ]
    positioned = []
    offset = 0
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("height"), int):
            raise ValueError("Battle reward rows must be laid out first")
        height = row["height"]
        if height < 1:
            raise ValueError("Battle reward rows must be at least one line tall")
        positioned.append({**row, "y": offset})
        offset += height
    return {"columns": columns, "rows": positioned, "totalHeight": offset}


def apply_rewards(inventory: dict, rewards: list[dict]) -> dict:
    """Model confirmation: add every reward quantity exactly once.

    The input inventory is not mutated; the returned mapping holds the new
    stock. Duplicate item entries in one fight sum, matching separate rows.
    """
    if not isinstance(inventory, dict):
        raise ValueError("Battle reward inventory must be a mapping")
    stock = {}
    for item_id, quantity in inventory.items():
        cleaned_id = _clean_item_id(item_id)
        if (isinstance(quantity, bool) or not isinstance(quantity, int)
                or quantity < 0):
            raise ValueError("Battle reward stock must be zero or more")
        stock[cleaned_id] = quantity
    if not isinstance(rewards, list):
        raise ValueError("Battle rewards must be a list")
    for reward in rewards:
        cleaned = _clean_reward(reward)
        stock[cleaned["itemId"]] = stock.get(cleaned["itemId"], 0) + cleaned["quantity"]
    return stock


def requirement_errors(*, enabled: bool) -> list[str]:
    """Activation blockers; empty means no objection."""
    if not isinstance(enabled, bool):
        raise ValueError("Battle Results Item Help must be true or false")
    if not enabled:
        return []
    if not BATTLE_RESULTS_HELP_AVAILABLE:
        return [BATTLE_RESULTS_HELP_BLOCKER]
    return []


def build_hext(enabled: bool) -> str:
    """Return the Hext fragment, or no bytes while hooks are unproved.

    Enabling without proved results-screen drawing hooks raises instead of
    installing guessed bytes.
    """
    errors = requirement_errors(enabled=enabled)
    if errors:
        raise ValueError(errors[0])
    if not enabled:
        return ""
    return "# Battle Results Item Help uses the proved results-screen hooks; no guess bytes.\n"
