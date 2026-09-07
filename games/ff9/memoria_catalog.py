"""Complete pinned Memoria CSV catalog layered on the proven CSV reader."""
from __future__ import annotations
from typing import Any
from . import memoria_csv as base
Dataset = base.Dataset

def d(key: str, tab: str, label: str, path: str, controls: str) -> Dataset:
    return Dataset(key, tab, label, path, controls)

CORE = (
    d("items", "items", "Items", "Items/Items.csv", "Item identity, prices, equipment classes, abilities, and usability"),
    d("weapons", "weapons", "Weapons", "Items/Weapons.csv", "Weapon category, model, script, power, elements, rate, and sound"),
    d("armor", "armor", "Armor", "Items/Armors.csv", "Physical and magical defence and evasion"),
    d("item-effects", "items", "Item effects", "Items/ItemEffects.csv", "Targeting, script, power, rate, element, and status"),
    d("initial-items", "items", "Initial inventory", "Items/InitialItems.csv", "Starting item IDs and quantities"),
    d("mix-items", "synthesis", "Mix recipes", "Items/MixItems.csv", "Mix recipe results and ingredients"),
    d("item-stats", "items", "Equipment stats", "Items/Stats.csv", "Equipment stat bonuses and elemental properties"),
    d("shops", "shops", "Shop inventories", "Items/ShopItems.csv", "Shop IDs and ordered item inventories"),
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
    return d(key, "abilities", label, f"Characters/Abilities/{name}.csv", "Ability IDs and AP requirements")

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
        return [{"line": row["line"], "id": (int(row["id"]) if has_id and str(row["id"]).lstrip("-+").isdigit() else row["id"] if has_id else index + 1), "name": row["name"], "values": {key: self._public_value(value, fields[key]) for key, value in row["raw"].items()}} for index, row in enumerate(rows)]

def install() -> None:
    base.DATASETS = DATASETS
    base.DATASET_BY_KEY = DATASET_BY_KEY
    base.MemoriaCsvDocument = CompleteMemoriaCsvDocument
