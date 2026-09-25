"""Complete pinned Memoria CSV catalog layered on the proven CSV reader."""
from __future__ import annotations
from typing import Any
import re
from . import memoria_csv as base
Dataset = base.Dataset

def d(key: str, tab: str, label: str, path: str, controls: str,
      field_labels: tuple[tuple[str, str], ...] = ()) -> Dataset:
    return Dataset(key, tab, label, path, controls, field_labels=field_labels)

CORE = (
    # Items.csv is the one table whose "Price" is what a shop charges and whose
    # "SellingPrice" is what a shop pays back. Synthesis.csv also has a "Price",
    # and there it means the recipe's own charge, so the rename stays here.
    d("items", "items", "Items", "Items/Items.csv", "Item identity, prices, equipment classes, abilities, and usability",
      field_labels=(("Price", "Buy price"), ("SellingPrice", "Sell price"))),
    d("weapons", "weapons", "Weapons", "Items/Weapons.csv", "Weapon category, model, script, power, elements, rate, and sound"),
    d("armor", "armor", "Armor", "Items/Armors.csv", "Physical and magical defence and evasion"),
    d("item-effects", "items", "Item effects", "Items/ItemEffects.csv", "Targeting, script, power, rate, element, and status"),
    d("initial-items", "items", "Initial inventory", "Items/InitialItems.csv", "Starting item IDs and quantities"),
    d("mix-items", "synthesis", "Mix recipes", "Items/MixItems.csv", "Mix recipe results and ingredients"),
    d("item-stats", "items", "Equipment stats", "Items/Stats.csv", "Equipment stat bonuses and elemental properties"),
    d("shops", "shops", "Shop inventories", "Items/ShopItems.csv", "Shop names, each stocked item with its buy and sell price, and the ordered item ids"),
    d("synthesis", "synthesis", "Synthesis recipes", "Items/Synthesis.csv", "Recipe shops, price, result, and ingredients"),
    d("abilities", "abilities", "Support abilities", "Characters/Abilities/AbilityGems.csv", "Support-ability gem costs and boosted versions"),
    d("characters", "characters", "Character base stats", "Characters/BaseStats.csv", "Base dexterity, strength, magic, will, and gem capacity"),
    d("battle-parameters", "characters", "Battle parameters", "Characters/BattleParameters.csv", "Models, animations, battle geometry, status anchors, and weapon sounds"),
    d("character-parameters", "characters", "Character parameters", "Characters/CharacterParameters.csv", "Starting row, victory pose, category, command/equipment sets, model formula, and name keyword"),
    d("command-sets", "characters", "Command sets", "Characters/CommandSets.csv", "Per-character command set assignments"),
    d("commands", "characters", "Commands", "Characters/Commands.csv", "Battle command types and ability lists"),
    d("default-equipment", "characters", "Starting equipment", "Characters/DefaultEquipment.csv", "Initial weapon, headgear, wristwear, armor, and accessory"),
    d("leveling", "characters", "Level growth", "Characters/Leveling.csv", "Experience thresholds and HP/MP growth for levels 1 through 99"),
    d("actions", "magic", "Battle actions", "Battle/Actions.csv", "Battle action targeting, animation, script, power, status, MP, and type"),
    d("magic-sword-sets", "magic", "Magic Sword sets", "Battle/MagicSwordSets.csv", "Supporter, beneficiary, and ability-set mapping"),
    d("status-data", "magic", "Status data", "Battle/StatusData.csv", "Status priority, timing, colors, and tick behavior"),
    d("status-sets", "magic", "Status sets", "Battle/StatusSets.csv", "Named status-set membership"),
    d("sfx-shp", "effects", "SHP definitions", "SpecialEffects/Common/SHP.csv", "Shape-particle definitions and textures"),
    d("sfx-sps", "effects", "SPS definitions", "SpecialEffects/Common/SPS.csv", "Sprite-particle definitions, textures, colors, and timing"),
    d("tetra-cards", "tetra-master", "Tetra Master cards", "TetraMaster/TripleTriad.csv", "Card attack, defence, type, and arrow data"),
    d("world-transport", "world", "Transport controls", "World/TransportControls.csv", "World transport movement and collision parameters"),
    d("world-weather", "world", "Weather colors", "World/WeatherColors.csv", "World light, fog, and ambient weather colors"),
)
_ABILITY_FILES = ("Amarant","Beatrix1","Beatrix2","Blank1","Blank2","Cinna1","Cinna2","Eiko","Freya","Garnet","Marcus1","Marcus2","Quina","Steiner","Vivi","Zidane")

def _ability_dataset(name: str) -> Dataset:
    suffix = name[-1] if name[-1:].isdigit() else ""
    stem = name[:-1] if suffix else name
    key = "ability-" + stem.lower() + ("-" + suffix if suffix else "")
    label = stem + " abilities" + (" " + suffix if suffix else "")
    return d(key, "abilities", label, f"Characters/Abilities/{name}.csv", "Ability ids, AP requirements, and the MP cost of the linked battle action")

DATASETS = CORE + tuple(_ability_dataset(name) for name in _ABILITY_FILES)
DATASET_BY_KEY = {dataset.key: dataset for dataset in DATASETS}

class CompleteMemoriaCsvDocument(base.MemoriaCsvDocument):
    def _find_schema(self) -> tuple[list[str], list[str]]:
        for index, line in enumerate(self.lines[:-1]):
            if not line.startswith("#") or ";" not in line or line.startswith("#!"):
                continue
            columns = [value.strip() for value in base._parse_csv_line(line[1:].strip())]
            type_line = self.lines[index + 1]
            if not type_line.startswith("#") or ";" not in type_line or type_line.startswith("#!"):
                continue
            types = [value.strip() for value in base._parse_csv_line(type_line[1:].strip())]
            width = 0
            for candidate in self.lines[index + 2:]:
                if not candidate or candidate.lstrip().startswith("#"):
                    continue
                values = base._parse_csv_line(candidate)
                width = next((i for i, value in enumerate(values) if value.lstrip().startswith("#")), len(values))
                break
            if width and width <= len(columns) and width <= len(types):
                columns, types = columns[:width], types[:width]
            while columns and not columns[-1]: columns.pop()
            types = types[:len(columns)]
            if len(columns) >= 2 and len(types) == len(columns):
                if len(set(columns)) != len(columns) or any(not name for name in columns):
                    raise ValueError(f"Memoria CSV has duplicate or empty column names: {self.path}")
                return columns, types
        raise ValueError(f"Memoria CSV schema header was not found: {self.path}")

    def public_rows(self, dataset: Dataset) -> list[dict[str, Any]]:
        rows = self.rows
        if dataset.filter_column:
            rows = [row for row in rows if row["raw"].get(dataset.filter_column) == dataset.filter_value]
        fields = {field["key"]: field for field in self.fields}
        has_id = any(column.casefold() == "id" for column in self.columns)

        def source_identity(row: dict[str, Any]) -> Any:
            if has_id:
                value = row["id"]
                return int(value) if str(value).lstrip("-+").isdigit() else value
            # Level is real domain identity even though the upstream leveling
            # file stores it in the source comment instead of a dedicated Id
            # column. Other no-Id tables deliberately expose no synthetic ID.
            if dataset.key == "leveling":
                match = re.fullmatch(r"Level\s+(\d+)", str(row["name"]).strip(), flags=re.IGNORECASE)
                if match:
                    return int(match.group(1))
            return None

        public = [{"line": row["line"], "id": source_identity(row), "name": row["name"],
                   "values": {key: self._public_value(value, fields[key]) for key, value in row["raw"].items()}}
                  for row in rows]
        # An ability file's schema says "Use 0 for a void ability": the shipped
        # file pads the character's learn list with id-0 rows, and Beatrix1.csv
        # alone carries 37 of them. They are real rows in the file and stay
        # visible, but "Void" repeated 37 times tells a reader nothing, so each
        # unused slot gets a number it can be recognised by.
        if dataset.key.startswith("ability-"):
            empty = 0
            for row in public:
                if str(row["values"].get("Id", "")).strip() == "0":
                    empty += 1
                    row["name"] = f"Empty slot {empty}"
        return public


# An ability file stores "AA:149" or "SA:5" and nothing else about the ability,
# so the numbers that decide what an ability costs live in Battle/Actions.csv.
# Measured against the pinned release, every AA id in every character's ability
# file names the same thing as the battle action with that id (156 ids compared;
# the only two differences are Memoria's own spellings "Frost"/"Freeze" and
# "Armor Break"/"Armour Break"). SA ids index the support-ability table instead,
# so they are never matched to an action.
ABILITY_ACTION_FIELD = "Id"
MP_COST_FIELD = {
    "key": "mp", "label": "MP cost", "declaredType": "DERIVED",
    "kind": "integer", "editable": False, "min": 0, "max": 65535,
}


def _action_cost(action: dict[str, Any] | None) -> Any:
    """The MP column of a battle action, however that file spells the name."""
    if not action:
        return ""
    for column, value in action.get("values", {}).items():
        if column.casefold() == "mp":
            return value
    return ""


class CompleteMemoriaDataStore(base.MemoriaDataStore):
    """The pinned catalog plus the links that only exist between two files."""

    def load(self, key: str) -> dict[str, Any]:
        payload = super().load(key)
        dataset = DATASET_BY_KEY.get(key)
        if dataset is None:
            return payload
        if key.startswith("ability-"):
            return self.with_ability_costs(payload)
        if key == "shops":
            return self.with_shop_stock(payload)
        return payload

    def _linked_rows(self, key: str) -> dict[Any, dict[str, Any]] | None:
        """Another dataset's rows by identity, or None when it is unavailable."""
        try:
            payload = super().load(key)
        except (OSError, KeyError, ValueError):
            return None
        return {row["id"]: row for row in payload["rows"]}

    def with_ability_costs(self, payload: dict[str, Any]) -> dict[str, Any]:
        actions = self._linked_rows("actions")
        linked = False
        for row in payload["rows"]:
            raw = str(row["values"].get(ABILITY_ACTION_FIELD, "")).strip()
            kind, _, number = raw.partition(":")
            action = None
            if actions is not None and kind == "AA" and number.isdigit():
                action = actions.get(int(number))
            row["values"]["mp"] = _action_cost(action)
            row["action"] = action["name"] if action else None
            linked = linked or action is not None
        # A character whose list is all support abilities gains no MP column
        # from this link, so do not add a field that would always read blank.
        if linked:
            payload["fields"] = payload["fields"] + [dict(MP_COST_FIELD)]
        return payload

    def with_shop_stock(self, payload: dict[str, Any]) -> dict[str, Any]:
        items = self._linked_rows("items")
        for row in payload["rows"]:
            raw = str(row["values"].get("Items", ""))
            stock = []
            for token in raw.split(","):
                token = token.strip()
                if not token.isdigit():
                    continue
                item_id = int(token)
                item = (items or {}).get(item_id)
                values = (item or {}).get("values", {})
                stock.append({"id": item_id,
                              "name": item["name"] if item else f"Item {item_id}",
                              "buyPrice": values.get("Price", ""),
                              "sellPrice": values.get("SellingPrice", ""),
                              "resolved": item is not None})
            row["stock"] = stock
        return payload

def install() -> None:
    base.DATASETS = DATASETS
    base.DATASET_BY_KEY = DATASET_BY_KEY
    base.MemoriaCsvDocument = CompleteMemoriaCsvDocument
    base.MemoriaDataStore = CompleteMemoriaDataStore
