"""Author the issue #148 thermometer catalog record and general-store listing.

This intentionally remains an issue-owned, repeatable editor operation.  The
integration pass runs it once after all feature branches are merged, avoiding
concurrent edits to the 16 MB shared catalog while still making the data change
fully deterministic and verifiable.
"""

from __future__ import annotations

import argparse
import copy
import os
from pathlib import Path
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(os.environ.get("LEXEDITOR_RDR2_PROJECT", r"C:\RDR2Mod")).resolve()
DEFAULT_CATALOG = PROJECT_ROOT / "MyOverhaul" / "catalog_sp.ymt"
DEFAULT_STRINGS = PROJECT_ROOT / "MyOverhaul" / "strings.gxt2"
ITEM = "LEX_THERMOMETER"
TEMPLATE = "KIT_PLAYER_POCKETWATCH"
SHOP = "ST_GENERAL"


def text(node: ET.Element, path: str) -> str:
    child = node.find(path)
    return (child.text or "").strip() if child is not None else ""


def direct(parent: ET.Element, tag: str) -> ET.Element:
    node = parent.find(tag)
    if node is None:
        node = ET.SubElement(parent, tag)
    return node


def catalog_item(root: ET.Element, key: str) -> ET.Element | None:
    for item in root.findall("./catalog/items/item"):
        if (item.get("key") or text(item, "key")) == key:
            return item
    return None


def replace_tags(item: ET.Element) -> None:
    tags = direct(item, "tags")
    tags.clear()
    # Both pairs occur on Rockstar's KIT_PLAYER_POCKETWATCH record.  Omitting
    # CI_TAG_POCKET_WATCH is deliberate: buying this item must enable the HUD,
    # not route it into the vanilla hand-held watch interaction.
    for key in ("CI_TAG_CATEGORY_KIT", "CI_TAG_ITEM_KIT"):
        entry = ET.SubElement(tags, "item")
        ET.SubElement(entry, "key").text = key
        ET.SubElement(entry, "type").text = "0x42D03BDE"


def replace_ui(item: ET.Element) -> None:
    ui = direct(item, "ui")
    direct(ui, "key").text = ITEM
    direct(ui, "description").text = ITEM + "_DESC"
    localization = direct(ui, "localization")
    localization.clear()
    textures = direct(ui, "textures")
    textures.clear()
    # No thermometer texture or model exists in the extracted Story data.  The
    # source issue provides no shippable asset, so reuse the resolved watch
    # presentation instead of shipping a guessed dictionary/texture hash.
    for texture_id, dictionary, texture_type in (
        ("KIT_PLAYER_POCKETWATCH", "INVENTORY_ITEMS", "INVENTORY"),
        ("UI_KIT_PLAYER_POCKETWATCH", "ITEM_TEXTURES", "GRID_OF_4_LAYOUT_0"),
    ):
        entry = ET.SubElement(textures, "item")
        ET.SubElement(entry, "id").text = texture_id
        ET.SubElement(entry, "dict").text = dictionary
        ET.SubElement(entry, "type").text = texture_type


def replace_multiplicity(item: ET.Element) -> None:
    multiplicity = direct(item, "multiplicity")
    multiplicity.clear()
    rule = ET.SubElement(multiplicity, "item")
    ET.SubElement(rule, "quantity", {"value": "1"})
    ET.SubElement(rule, "slotid").text = "SLOTID_ANY"


def author_item(root: ET.Element) -> bool:
    existing = catalog_item(root, ITEM)
    if existing is not None:
        return False
    source = catalog_item(root, TEMPLATE)
    if source is None:
        raise RuntimeError(f"missing catalog template {TEMPLATE}")
    item = copy.deepcopy(source)
    item.set("key", ITEM)
    direct(item, "key").text = ITEM
    direct(item, "category").text = "CI_CATEGORY_WATCH"
    direct(item, "group").text = "PROVISION"
    direct(item, "flags").clear()
    replace_tags(item)
    # The template's proven COST_SHOP_DEFAULT price is retained.  The issue did
    # not specify a price, and this avoids inventing a new economy constant.
    direct(item, "sellprices").clear()
    replace_ui(item)
    replace_multiplicity(item)
    root.find("./catalog/items").append(item)
    return True


def add_stock(root: ET.Element) -> int:
    changed = 0
    for shop in root.findall("./shopsinventories/item"):
        if text(shop, "type") != SHOP:
            continue
        items = direct(shop, "items")
        if any(text(entry, "item") == ITEM for entry in items.findall("item")):
            continue
        entry = ET.SubElement(items, "item")
        ET.SubElement(entry, "item").text = ITEM
        ET.SubElement(entry, "requirementgroups")
        changed += 1
    if changed == 0 and not any(
        text(entry, "item") == ITEM
        for shop in root.findall("./shopsinventories/item")
        if text(shop, "type") == SHOP
        for entry in shop.findall("./items/item")
    ):
        raise RuntimeError(f"no canonical {SHOP} stock list found")
    return changed


def canonical_layout(root: ET.Element) -> ET.Element:
    matches = [shop for shop in root.findall("./cataloglayout/item")
               if text(shop, "shoptype") == SHOP]
    target = next((shop for shop in matches if text(shop, "shopid") == SHOP), None)
    if target is None and matches:
        target = max(matches, key=lambda shop: len(shop.findall("./pages/item")))
    if target is None:
        raise RuntimeError(f"no canonical {SHOP} catalog layout found")
    return target


def add_catalog_page(root: ET.Element) -> int:
    shop = canonical_layout(root)
    pages = direct(shop, "pages")
    if any(text(entry, "key") == ITEM
           for page in pages.findall("item")
           for entry in page.findall("./items/item")):
        return 0
    page = next((candidate for candidate in pages.findall("item")
                 if text(candidate, "layout") == "GRID_OF_4_LAYOUT_0"
                 and len(candidate.findall("./items/item")) < 4), None)
    if page is None:
        page = ET.SubElement(pages, "item")
        ET.SubElement(page, "key").text = "LEX_PAGE_THERMOMETER"
        ET.SubElement(page, "layout").text = "GRID_OF_4_LAYOUT_0"
        ET.SubElement(page, "flags")
        ET.SubElement(page, "items")
        for menu in shop.findall("./menus//item"):
            refs = menu.find("pages")
            nested = menu.find("menus")
            if refs is not None and (nested is None or not nested.findall("item")):
                ref = ET.SubElement(refs, "item")
                ET.SubElement(ref, "key").text = "LEX_PAGE_THERMOMETER"
                break
    entry = ET.SubElement(direct(page, "items"), "item")
    ET.SubElement(entry, "key").text = ITEM
    ET.SubElement(entry, "linkshopid")
    ET.SubElement(entry, "linkmenuid")
    return 1


def save_catalog(tree: ET.ElementTree, path: Path) -> None:
    ET.indent(tree, space="  ")
    path.write_text(
        '<?xml version="1.0" encoding="utf-8" standalone="no"?>\n'
        + ET.tostring(tree.getroot(), encoding="unicode") + "\n",
        encoding="utf-8",
    )


def author_strings(path: Path) -> int:
    content = path.read_text(encoding="utf-8")
    additions = []
    values = {
        ITEM: "Thermometer",
        ITEM + "_DESC": "Displays the ambient temperature beneath the pocket-watch readout.",
    }
    for key, value in values.items():
        if not any(line.startswith(key + " =") for line in content.splitlines()):
            additions.append(f"{key} = {value}")
    if additions:
        path.write_text(content.rstrip() + "\n" + "\n".join(additions) + "\n", encoding="utf-8")
    return len(additions)


def apply(catalog_path: Path, strings_path: Path, check_only: bool = False) -> dict[str, int]:
    tree = ET.parse(catalog_path)
    root = tree.getroot()
    changes = {
        "item": int(author_item(root)),
        "stock": add_stock(root),
        "catalogue": add_catalog_page(root),
    }
    if check_only:
        return changes
    if any(changes.values()):
        save_catalog(tree, catalog_path)
    changes["strings"] = author_strings(strings_path)
    return changes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--strings", type=Path, default=DEFAULT_STRINGS)
    parser.add_argument("--check", action="store_true",
                        help="validate the current source data without writing it")
    args = parser.parse_args()
    changes = apply(args.catalog, args.strings, args.check)
    print("thermometer issue #148:", " ".join(f"{key}={value}" for key, value in changes.items()))


if __name__ == "__main__":
    main()
