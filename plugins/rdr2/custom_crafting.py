"""Issue #22 custom-crafting storage and vanilla snapshot helpers.

The live custom recipes are deliberately independent of catalog_sp.ymt.  The
runtime consumes the same tab-separated schema for both the read-only vanilla
snapshot and the editable custom file, so recipe and ingredient counts are not
bounded by Rockstar's four named catalog cost slots.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


FIELDS = (
    "recipe_id", "category", "title", "description", "station",
    "output_item", "output_quantity", "ingredients", "unlock",
)


@dataclass
class Ingredient:
    item: str
    quantity: int = 1


@dataclass
class Recipe:
    recipe_id: str
    category: str
    title: str
    description: str
    station: str
    output_item: str
    output_quantity: int = 1
    ingredients: list[Ingredient] = field(default_factory=list)
    unlock: str = ""


def _clean(value: str | None) -> str:
    return (value or "").replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()


def encode_ingredients(parts: Iterable[Ingredient]) -> str:
    return ";".join(f"{_clean(part.item)}*{int(part.quantity)}" for part in parts)


def decode_ingredients(value: str) -> list[Ingredient]:
    result: list[Ingredient] = []
    for token in value.split(";"):
        token = token.strip()
        if not token:
            continue
        item, separator, quantity = token.rpartition("*")
        if not separator:
            item, quantity = token, "1"
        result.append(Ingredient(_clean(item), int(quantity)))
    return result


def validate_recipes(recipes: Iterable[Recipe], catalog_items: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for index, recipe in enumerate(recipes, 1):
        prefix = recipe.recipe_id or f"row {index}"
        if not recipe.recipe_id:
            errors.append(f"{prefix}: recipe_id is required")
        elif recipe.recipe_id in seen:
            errors.append(f"{prefix}: duplicate recipe_id")
        seen.add(recipe.recipe_id)
        if not recipe.title:
            errors.append(f"{prefix}: title is required")
        if not recipe.output_item:
            errors.append(f"{prefix}: output_item is required")
        if recipe.output_quantity < 1:
            errors.append(f"{prefix}: output_quantity must be positive")
        if not recipe.ingredients:
            errors.append(f"{prefix}: at least one ingredient is required")
        for part in recipe.ingredients:
            if not part.item or part.quantity < 1:
                errors.append(f"{prefix}: every ingredient needs an item and positive quantity")
            if catalog_items is not None and part.item not in catalog_items:
                errors.append(f"{prefix}: unknown ingredient {part.item}")
        if catalog_items is not None and recipe.output_item not in catalog_items:
            errors.append(f"{prefix}: unknown output {recipe.output_item}")
    return errors


def load_recipes(path: str | Path) -> list[Recipe]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = csv.DictReader(stream, delimiter="\t")
        missing = set(FIELDS) - set(rows.fieldnames or ())
        if missing:
            raise ValueError(f"{path}: missing columns: {', '.join(sorted(missing))}")
        result = []
        for row in rows:
            if not any((value or "").strip() for value in row.values()):
                continue
            result.append(Recipe(
                recipe_id=_clean(row["recipe_id"]), category=_clean(row["category"]),
                title=_clean(row["title"]), description=_clean(row["description"]),
                station=_clean(row["station"]), output_item=_clean(row["output_item"]),
                output_quantity=int(row["output_quantity"]),
                ingredients=decode_ingredients(row["ingredients"]), unlock=_clean(row["unlock"]),
            ))
    return result


def save_recipes(path: str | Path, recipes: Iterable[Recipe]) -> None:
    """Validate, then atomically replace a custom recipe file."""
    path = Path(path)
    materialized = list(recipes)
    errors = validate_recipes(materialized)
    if errors:
        raise ValueError("\n".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
            writer.writeheader()
            for recipe in materialized:
                writer.writerow({
                    "recipe_id": _clean(recipe.recipe_id), "category": _clean(recipe.category),
                    "title": _clean(recipe.title), "description": _clean(recipe.description),
                    "station": _clean(recipe.station), "output_item": _clean(recipe.output_item),
                    "output_quantity": recipe.output_quantity,
                    "ingredients": encode_ingredients(recipe.ingredients), "unlock": _clean(recipe.unlock),
                })
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _text(node: ET.Element | None, path: str, default: str = "") -> str:
    if node is None:
        return default
    found = node.find(path)
    return _clean(found.text if found is not None else default)


def catalog_item_keys(catalog_path: str | Path) -> set[str]:
    root = ET.parse(catalog_path).getroot()
    return {item.get("key", "") for item in root.findall(".//items/item") if item.get("key")}


def export_vanilla_snapshot(catalog_path: str | Path, localization_path: str | Path) -> list[Recipe]:
    localization = json.loads(Path(localization_path).read_text(encoding="utf-8"))
    root = ET.parse(catalog_path).getroot()
    recipes: list[Recipe] = []
    for item in root.findall(".//items/item"):
        output = _clean(item.get("key"))
        if not output:
            continue
        name_key = _text(item, "name") or output
        title = _clean(localization.get(name_key, name_key))
        description_key = _text(item, "description")
        description = _clean(localization.get(description_key, description_key))
        category = _text(item, "category")
        costs = item.find("acquirecosts")
        if costs is None:
            continue
        ordinal = 0
        for cost in costs.findall("item"):
            if _text(cost, "costtype") != "COST_TYPE_CRAFT":
                continue
            ordinal += 1
            station = _text(cost, "key")
            parts = [Ingredient(_text(part, "item"), int(part.find("quantity").get("value", "1")))
                     for part in cost.findall("./items/item")]
            unlocks = [_clean(node.text) for node in cost.findall("./unlocks/item") if _clean(node.text)]
            recipes.append(Recipe(
                recipe_id=f"vanilla:{output}:{station}:{ordinal}", category=category,
                title=title, description=description, station=station, output_item=output,
                output_quantity=int(cost.find("quantity").get("value", "1")),
                ingredients=parts, unlock=";".join(unlocks),
            ))
    return recipes


def export_item_labels(catalog_path: str | Path, localization_path: str | Path,
                       output_path: str | Path) -> int:
    """Write the runtime lookup that keeps catalog IDs out of the crafting HUD."""
    localization = json.loads(Path(localization_path).read_text(encoding="utf-8"))
    root = ET.parse(catalog_path).getroot()
    labels: dict[str, str] = {}
    for item in root.findall(".//catalog/items/item"):
        key = _clean(item.get("key"))
        name_key = _text(item, "name") or _text(item, "ui/key") or key
        label = _clean(localization.get(key, localization.get(name_key, name_key)))
        if key and label and label not in {key, name_key}:
            labels[key] = label
    labels.update({
        "LEX_BRASS": "Brass", "LEX_GOLD": "Gold", "LEX_SILVER": "Silver",
        "LEX_WATER_BOTTLE": "Reusable Canteen",
    })
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        stream.write("item_id\tdisplay_name\n")
        for key in sorted(labels):
            stream.write(f"{key}\t{labels[key]}\n")
    return len(labels)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export-vanilla")
    export.add_argument("catalog", type=Path)
    export.add_argument("localization", type=Path)
    export.add_argument("output", type=Path)
    labels = sub.add_parser("export-labels")
    labels.add_argument("catalog", type=Path)
    labels.add_argument("localization", type=Path)
    labels.add_argument("output", type=Path)
    validate = sub.add_parser("validate")
    validate.add_argument("recipes", type=Path)
    validate.add_argument("--catalog", type=Path)
    args = parser.parse_args()
    if args.command == "export-vanilla":
        recipes = export_vanilla_snapshot(args.catalog, args.localization)
        save_recipes(args.output, recipes)
        print(f"wrote {len(recipes)} vanilla recipes to {args.output}")
        return 0
    if args.command == "export-labels":
        count = export_item_labels(args.catalog, args.localization, args.output)
        print(f"wrote {count} item labels to {args.output}")
        return 0
    recipes = load_recipes(args.recipes)
    errors = validate_recipes(recipes, catalog_item_keys(args.catalog) if args.catalog else None)
    if errors:
        print("\n".join(errors))
        return 1
    print(f"validated {len(recipes)} recipes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
