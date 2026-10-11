"""Mod project overlay for map files: vanilla bytes or the project's saved
edits, one document per map, with the same save/discard/stale rules as the
parameter archive."""
import hashlib
from pathlib import Path

from core.plugin_files import atomic_write

from . import deployment
from .formats import FormatError
from .msb import ENEMY_TYPES, MAP_DIR, MAX_FILE as MAX_MAP, MsbDocument, MsbError, PLAYER_TYPE
from .store import MARKER, digest


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
        if document is not None and "NpcParam" in document.params:
            for row in document.params["NpcParam"].rows:
                names[row.row_id] = document.display_name("NpcParam", row.row_id, row)
        return set(names), names

    def list_rows(self):
        _ids, names = self._npc()
        rows = []
        for map_name in self.maps():
            for placement in self.get(map_name).placements():
                npc = placement.get("npc")
                enemy = names.get(npc, "") if npc is not None else ""
                values = {"map": map_name, "kind": placement["kind"], "model": placement["model"],
                          "posX": placement["pos"][0], "posY": placement["pos"][1], "posZ": placement["pos"][2],
                          "rotX": placement["rot"][0], "rotY": placement["rot"][1], "rotZ": placement["rot"][2],
                          "npcId": npc}
                display = {"npcId": enemy if enemy else (f"Unknown ({npc})" if npc is not None else "")}
                rows.append({"id": f"{placement['type']}:{placement['partId']}", "table": map_name,
                             "name": placement["name"], "values": values, "display": display})
        return rows

    def read(self, map_name, key):
        _ids, names = self._npc()
        part_key = parse_key(key)
        row = self.get(map_name).read_placement(part_key)
        try:
            originals = {item["key"]: item["value"]
                         for item in self._vanilla_doc(map_name).read_placement(part_key)["fields"]}
        except MsbError:
            originals = {}
        row.update(id=f"{part_key[0]}:{part_key[1]}", table=map_name, map=map_name)
        for item in row["fields"]:
            if item["key"] in originals:
                item["vanilla"] = originals[item["key"]]
            if item["key"] == "npcId":
                item["type"] = "enum"
                item["enum"] = {str(row_id): names[row_id] for row_id in sorted(names)}
        return row

    def edit(self, map_name, key, field, value):
        self.writable()
        ids, _names = self._npc()
        self.get(map_name).edit(parse_key(key), field, value, ids if field == "npcId" else None)
        return self.read(map_name, key)

    def add_placement(self, map_name, key):
        self.writable()
        row = self.get(map_name).add_placement(parse_key(key))
        return self.read(map_name, f"{row['type']}:{row['partId']}")

    def remove_placement(self, map_name, key):
        self.writable()
        return self.get(map_name).remove_placement(parse_key(key))

    @property
    def dirty_count(self):
        return sum(document.dirty_count for document in self.docs.values())

    def pending_changes(self):
        _ids, names = self._npc()
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
        return {"saved": True, "dirtyCount": 0}

    def discard(self):
        self.docs = {}
        self.vanilla_docs = {}
        self.hashes = {}
        return {"discarded": True}
