"""Mod project overlay for map files: vanilla bytes or the project's saved
edits, one document per map, with the same save/discard/stale rules as the
parameter archive."""
import hashlib
import re
from pathlib import Path

from core.plugin_files import atomic_write

from . import deployment
from .formats import FormatError
from .msb import ENEMY_TYPES, MAP_DIR, MAX_FILE as MAX_MAP, MsbDocument, MsbError, PLAYER_TYPE
from .store import MARKER, digest


# A map file carries the areas numbered for it: mAA_BB_*.msb owns the
# place ids AA*100+BB*10 through +9 (m12_01 owns 1210-1219, the Oolacile
# set), and the lowest named one is the name on the door. Verified against
# the shipped Place_name_ table, which holds every map's areas.
_MAP_AREA = re.compile(r'm(\d{2})_(\d{2})_\d{2}_\d{2}\.msb\Z')


def parse_key(key):
    """A placement identity from its "type:id" form."""
    try:
        ptype, pid = str(key).split(":")
        return int(ptype), int(pid)
    except (TypeError, ValueError) as error:
        raise MsbError("Select an enemy or player-start placement") from error


class MapStore:
    def __init__(self, game_root, project=None, read_only=True, item_store=None):
        from .tweak_mods import checked
        self.game_root = checked(Path(game_root)).resolve()
        self.project = checked(Path(project)).resolve() if project else None
        self.read_only = read_only or self.project is None
        self.item_store = item_store
        self.docs = {}
        self.vanilla_docs = {}
        self.hashes = {}
        self._npc_models = None

    def writable(self):
        if self.read_only:
            raise PermissionError("Create or select a mod before editing Vanilla.")
        if self.project == self.game_root or self.game_root in self.project.parents:
            raise ValueError("The mod project must be outside the game installation.")
        from .tweak_mods import checked
        checked(self.project / MARKER)
        if not (self.project / MARKER).is_file():
            raise ValueError("Select a valid Dark Souls mod project.")

    def maps(self):
        live = self.game_root / MAP_DIR
        if not live.is_dir():
            return []
        return sorted(path.name for path in live.glob("*.msb"))

    def display_name(self, map_id: str) -> str:
        """'Undead Burg (m10_01_00_00.msb)', 'Test map (...)' for the m99
        test block without area text, or the bare id otherwise."""
        match = _MAP_AREA.match(map_id or '')
        document = getattr(self.item_store, 'document', None)
        texts = document.texts if document is not None else None
        if match and texts is not None:
            first = int(match.group(1)) * 100 + int(match.group(2)) * 10
            for area_id in range(first, first + 10):
                name = texts.place_name(area_id)
                if name:
                    return f'{name} ({map_id})'
        if match and match.group(1) == '99':
            return f'Test map ({map_id})'
        return map_id

    def _load(self, map_name):
        from .tweak_mods import checked
        output = self.project / MAP_DIR / map_name if self.project else None
        vanilla = deployment.vanilla_source(self.game_root, MAP_DIR / map_name)
        source = output if output and output.is_file() else vanilla
        checked(source)
        if source.stat().st_size > MAX_MAP:
            raise ValueError("The map file is too large.")
        raw = source.read_bytes()
        self.docs[map_name] = MsbDocument(raw, map_name)
        self.hashes[map_name] = {"source": source, "output": output, "vanilla": vanilla,
                                 "source_hash": hashlib.sha256(raw).hexdigest(),
                                 "vanilla_hash": digest(vanilla),
                                 "output_hash": digest(output) if output else None}

    def get(self, map_name):
        if map_name not in self.maps():
            raise MsbError("Unknown map file")
        if map_name not in self.docs:
            self._load(map_name)
        return self.docs[map_name]

    def _vanilla_doc(self, map_name):
        if map_name not in self.vanilla_docs:
            vanilla = deployment.vanilla_source(self.game_root, MAP_DIR / map_name)
            self.vanilla_docs[map_name] = MsbDocument(vanilla.read_bytes(), map_name)
        return self.vanilla_docs[map_name]

    def _npc(self):
        """NpcParam row IDs and display names for enemy links.

        Without readable parameters the maps still list and positions
        still edit; enemies show as IDs and NPC swaps are refused.
        """
        try:
            document = self.item_store.get() if self.item_store else None
        except (OSError, FormatError):
            document = None
        names = {}
        types = {}
        if document is not None and "NpcParam" in document.params:
            for row in document.params["NpcParam"].rows:
                names[row.row_id] = document.display_name("NpcParam", row.row_id, row)
                try:
                    types[row.row_id] = document.value("NpcParam", row.row_id, "npcType")
                except (FormatError, KeyError, StopIteration):
                    continue
        return set(names), names, types

    def locate_drop(self, lot_id):
        """The first placement of an enemy dropping this lot, for go-to.

        ItemLotParam rows name no map, but NpcParam rows name their lots,
        and placements name their NPC. Without readable parameters there is
        nothing to resolve, so the directory shows no go-to button.
        """
        try:
            document = self.item_store.get() if self.item_store else None
        except (OSError, FormatError):
            document = None
        if document is None or "NpcParam" not in document.params:
            return None
        fields = [f"itemLotId_{index}" for index in range(1, 7)] + ["humanityLotId"]
        droppers = set()
        for row in document.params["NpcParam"].rows:
            for field in fields:
                try:
                    hit = document.value("NpcParam", row.row_id, field) == lot_id
                except (FormatError, KeyError, StopIteration):
                    continue
                if hit:
                    droppers.add(row.row_id)
                    break
        if not droppers:
            return None
        for map_name in self.maps():
            try:
                placements = self.get(map_name).placements()
            except (MsbError, OSError):
                continue
            for placement in placements:
                if placement.get("npc") in droppers:
                    return {"map": map_name, "key": f"{placement['type']}:{placement['partId']}"}
        return None

    def lot_maps(self):
        """Every drop lot with the maps whose placed enemies drop it.

        ItemLotParam rows name no map, but NpcParam rows name their lots
        and placements name their NPC: the same links as locate_drop,
        inverted once for the directory's Local filter. Without readable
        parameters there is nothing to resolve, so the filter finds no lots.
        """
        try:
            document = self.item_store.get() if self.item_store else None
        except (OSError, FormatError):
            document = None
        if document is None or "NpcParam" not in document.params:
            return {}
        fields = [f"itemLotId_{index}" for index in range(1, 7)] + ["humanityLotId"]
        npc_lots = {}
        for row in document.params["NpcParam"].rows:
            lots = set()
            for field in fields:
                try:
                    lot = document.value("NpcParam", row.row_id, field)
                except (FormatError, KeyError, StopIteration):
                    continue
                if lot:
                    lots.add(lot)
            if lots:
                npc_lots[row.row_id] = lots
        if not npc_lots:
            return {}
        links = {}
        for map_name in self.maps():
            try:
                placements = self.get(map_name).placements()
            except (MsbError, OSError):
                continue
            for placement in placements:
                for lot in npc_lots.get(placement.get("npc"), ()):
                    links.setdefault(lot, set()).add(map_name)
        return {lot: sorted(maps) for lot, maps in links.items()}

    def map_counts(self):
        """Per-map NPC, enemy and drop counts for the Maps list.

        A placed Enemy of npcType 2 is an NPC; every other placed Enemy
        is an enemy, mirroring the directory's own predicates. Drops
        count the lots whose dropping NPCs stand in the map. Unreadable
        maps report zeros rather than hiding the readable ones.
        """
        _ids, _names, types = self._npc()
        drops: dict[str, int] = {}
        for maps in self.lot_maps().values():
            for map_name in maps:
                drops[map_name] = drops.get(map_name, 0) + 1
        counts = {}
        for map_name in self.maps():
            try:
                placements = self.get(map_name).placements()
            except (MsbError, OSError):
                placements = ()
            npcs = enemies = 0
            for placement in placements:
                if placement.get('kind') not in ('Enemy', 'Dummy enemy'):
                    continue
                if types.get(placement.get('npc')) == 2:
                    npcs += 1
                else:
                    enemies += 1
            counts[map_name] = {'npcs': npcs, 'drops': drops.get(map_name, 0),
                                'enemies': enemies}
        return counts

    def npc_models(self):
        """Each placed NPC ID with the character models it wears.

        Links come from every map's enemy parts. One map's broken bytes
        must not hide every other map's links, so unreadable maps are
        skipped. NPC swaps and placement edits invalidate the cache."""
        if self._npc_models is None:
            links = {}
            for map_name in self.maps():
                try:
                    document = self.get(map_name)
                except (MsbError, OSError):
                    continue
                for part in document.parts:
                    if part['type'] in ENEMY_TYPES:
                        links.setdefault(part['npc'], set()).add(
                            document.models[part['model']]['name'])
            self._npc_models = {npc: sorted(models) for npc, models in links.items()}
        return self._npc_models

    def _who(self, part_name, npc, names):
        """Who stands there: the enemy's name, the bare part name for
        things without an NPC id, or an Unknown fallback."""
        if npc is None:
            return part_name
        return names.get(npc, "") or f"Unknown ({npc})"

    def _title(self, map_name, part_name, npc, names):
        """A placement's title: who stands there and in which map. The
        bare part name stays pinnable under values, never in the title."""
        return f"{self._who(part_name, npc, names)} \u2014 {self.display_name(map_name)}"

    def _placement_row(self, map_name, placement, names, types):
        npc = placement.get("npc")
        enemy = names.get(npc, "") if npc is not None else ""
        values = {"map": map_name, "part": placement["name"], "kind": placement["kind"],
                  "model": placement["model"],
                  "posX": placement["pos"][0], "posY": placement["pos"][1], "posZ": placement["pos"][2],
                  "rotX": placement["rot"][0], "rotY": placement["rot"][1], "rotZ": placement["rot"][2],
                  "scaleX": placement["scale"][0], "scaleY": placement["scale"][1], "scaleZ": placement["scale"][2],
                  "npcId": npc, "npcType": types.get(npc) if npc is not None else None}
        display = {"npcId": enemy if enemy else (f"Unknown ({npc})" if npc is not None else "")}
        modified = self.get(map_name).placement_modified((placement["type"], placement["partId"]))
        return {"id": f"{placement['type']}:{placement['partId']}", "table": map_name,
                "name": self._title(map_name, placement["name"], npc, names),
                "range": placement["name"], "values": values, "display": display,
                "modified": modified}

    def list_rows(self):
        _ids, names, types = self._npc()
        rows = []
        for map_name in self.maps():
            for placement in self.get(map_name).placements():
                rows.append(self._placement_row(map_name, placement, names, types))
        return rows

    def row_values(self, map_name, key):
        """One placement's list values, display names and title, fresh after
        an edit, so undo can patch the lists without re-reading the map."""
        _ids, names, types = self._npc()
        part_key = parse_key(key)
        placement = next((entry for entry in self.get(map_name).placements()
                          if (entry["type"], entry["partId"]) == part_key), None)
        if placement is None:
            raise MsbError("Unknown placement")
        row = self._placement_row(map_name, placement, names, types)
        return row["values"], row["display"], row["name"]

    def _npc_tab(self, npc, types):
        if types.get(npc) == 2:
            return 'npcs', 'npcs'
        try:
            document = self.item_store.get() if self.item_store else None
        except (OSError, FormatError):
            document = None
        if document is not None:
            try:
                if document.is_boss(npc):
                    return 'enemies', 'bosses'
            except (FormatError, KeyError, StopIteration):
                pass
        return 'enemies', 'monsters'

    def read(self, map_name, key):
        _ids, names, types = self._npc()
        part_key = parse_key(key)
        row = self.get(map_name).read_placement(part_key)
        try:
            originals = {item["key"]: item["value"]
                         for item in self._vanilla_doc(map_name).read_placement(part_key)["fields"]}
        except MsbError:
            originals = {}
        row.update(id=f"{part_key[0]}:{part_key[1]}", table=map_name, map=map_name)
        npc = next((item["value"] for item in row["fields"] if item["key"] == "npcId"), None)
        row["shortName"] = self._who(row["name"], npc, names)
        row["name"] = self._title(map_name, row["name"], npc, names)
        for item in row["fields"]:
            if item["key"] in originals:
                item["vanilla"] = originals[item["key"]]
            if item["key"] == "npcId":
                item["type"] = "enum"
                item["enum"] = {str(row_id): names[row_id] for row_id in sorted(names)}
        row["recordLinks"] = []
        if npc is not None:
            tab, sub = self._npc_tab(npc, types)
            row["recordLinks"].append({'kind': 'npc', 'table': 'NpcParam', 'id': npc,
                                       'field': 'npcId', 'resolved': npc in names,
                                       'name': names.get(npc, f'Missing NPC {npc}'),
                                       'tab': tab, 'sub': sub})
        return row

    def edit(self, map_name, key, field, value):
        self.writable()
        ids, _names, _types = self._npc()
        self.get(map_name).edit(parse_key(key), field, value, ids if field == "npcId" else None)
        self._npc_models = None
        return self.read(map_name, key)

    def add_placement(self, map_name, key):
        self.writable()
        row = self.get(map_name).add_placement(parse_key(key))
        self._npc_models = None
        return self.read(map_name, f"{row['type']}:{row['partId']}")

    def create_placement(self, map_name, model, pos, rot, npc=None):
        self.writable()
        row = self.get(map_name).create_placement(model, pos, rot, npc)
        self._npc_models = None
        return self.read(map_name, f"{row['type']}:{row['partId']}")

    def remove_placement(self, map_name, key):
        self.writable()
        self._npc_models = None
        return self.get(map_name).remove_placement(parse_key(key))

    @property
    def dirty_count(self):
        return sum(document.dirty_count for document in self.docs.values())

    def pending_changes(self):
        _ids, names, _types = self._npc()
        changes = []
        for map_name, document in self.docs.items():
            known = {(part["type"], part["id"]): part["name"] for part in document.parts}
            for (ptype, pid), field in sorted(document.dirty):
                row = document.read_placement((ptype, pid))
                item = next(entry for entry in row["fields"] if entry["key"] == field)
                before, after = item["vanilla"], item["value"]
                if field == "npcId":
                    before = names.get(before, before)
                    after = names.get(after, after)
                changes.append({"label": f"{map_name} {known[(ptype, pid)]}, {item['label']}",
                                "before": before, "after": after})
            for gone in document.removed:
                changes.append({"label": f"{map_name} {gone['name']}, {gone['kind']} (removed)",
                                "before": f"{gone['type']}:{gone['id']}", "after": "removed"})
        return changes

    def validate_save(self):
        from .tweak_mods import checked
        self.writable()
        for map_name, document in self.docs.items():
            entry = self.hashes[map_name]
            vanilla = deployment.vanilla_source(self.game_root, MAP_DIR / map_name)
            for path in (entry["source"], vanilla, entry["output"]):
                if path is not None:
                    checked(path)
            if digest(entry["source"]) != entry["source_hash"] or digest(vanilla) != entry["vanilla_hash"]:
                raise ValueError("The map changed outside Lexeditor. Reopen it before saving.")
            if digest(entry["output"]) != entry["output_hash"]:
                raise ValueError("The mod map changed outside Lexeditor. Reopen it before saving.")
        return True

    def save(self):
        self.validate_save()
        from .tweak_mods import checked
        for map_name, document in self.docs.items():
            if not document.dirty_count:
                continue
            output = self.project / MAP_DIR / map_name
            resolved = checked(output).resolve()
            if self.game_root in resolved.parents or self.project not in resolved.parents:
                raise ValueError("The output path leaves the mod project or enters the installed game.")
            payload = document.export()
            MsbDocument(payload, map_name)
            output.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(output, payload)
        self.docs = {}
        self.vanilla_docs = {}
        self.hashes = {}
        self._npc_models = None
        return {"saved": True, "dirtyCount": 0}

    def discard(self):
        self.docs = {}
        self.vanilla_docs = {}
        self.hashes = {}
        self._npc_models = None
        return {"discarded": True}
