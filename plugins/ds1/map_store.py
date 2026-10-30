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

# MSB event fields that point into the parameter archive. Part and region
# references are already named by the MSB document itself.
EVENT_PARAM_LINKS = {
    **{f'itemLot{i}': ('drop', 'ItemLotParam') for i in range(1, 6)},
    'activationItem': ('goods', 'EquipParamGoods'),
    'activationParam': ('catalog', 'ObjActParam'),
}


def parse_key(key):
    """A placement identity from its "type:id" form."""
    try:
        ptype, pid = str(key).split(":")
        if ptype == 'region' or re.fullmatch(r'event(?:[1-9]|1[0-2])', ptype):
            return ptype, int(pid)
        return int(ptype), int(pid)
    except (TypeError, ValueError) as error:
        raise MsbError("Select an enemy or player-start placement") from error


# Smithbox reference names pin a lot's owner and ground into the name:
# '[Hollow - New Londo Ruins] None', '[Anor Londo] Great Magic Weapon'.
# The directory shows owner, item and map in their own columns instead.
_BRACKET = re.compile(r'\A\[([^\]]+)\](.*)\Z')
_TREASURE_STEM = re.compile(r'\A\?{0,2}m(\d{2})_(\d{2})(?:_|\s)')

# Informal area spellings in reference names, to the area id whose map
# file names the directory's Map column. 'Royal Garden' has no id: the
# names use it across both m12 files, so it shows as written.
_PLACE_ALIASES = {'firelink': 1020, 'painted world': 1100, 'asylum': 1810,
                  'catacombs': 1300, 'tomb of giants': 1310,
                  'royal garden': None}


def _norm_place(text):
    """' The Depths) ' -> 'depths': area spellings compare without case,
    a leading The, or the stray closing paren in some Sen's Fortress
    reference names."""
    cleaned = (text or '').strip()
    while cleaned.endswith(')') and cleaned.count(')') > cleaned.count('('):
        cleaned = cleaned[:-1].strip()
    lowered = cleaned.lower()
    return lowered[4:] if lowered.startswith('the ') else lowered


def split_owner_place(inside):
    """'Hollow - New Londo Ruins' -> ('Hollow', 'New Londo Ruins');
    'Vagrant' -> ('Vagrant', None). Splits on the last dash, so an
    owner carrying its own dash keeps it."""
    owner, dash, place = (inside or '').rpartition(' - ')
    if not dash or not owner.strip() or not place.strip():
        return (inside or '').strip(), None
    return owner.strip(), place.strip()


def describe_directory_name(name, displays):
    """Owner, item and map of a Smithbox reference name.

    displays maps normalized area spellings to the map list's display
    name (MapStore.place_display_names). A bracket holding only a
    place ('[Anor Londo] ...') has no owner; a ' - suffix' that names
    no area stays with the owner ('Ingward - Have Lordvessel',
    'Vagrant (Aggressive) - 1'). The map is the bracket's area as the
    map list spells it, or as written when it names no single map.
    """
    match = _BRACKET.match(name or '')
    if not match:
        return '', name or '', ''
    inside, item = match.group(1).strip(), match.group(2).strip()
    owner, place = split_owner_place(inside)
    if place is None:
        if _norm_place(inside) in displays:
            return '', item, displays[_norm_place(inside)] or inside
        return inside, item, ''
    if _norm_place(place) in displays:
        return owner, item, displays[_norm_place(place)] or place
    return inside, item, ''


def strip_owner_suffix(text, displays):
    """A placement owner's name without its map: 'Griggs of Vinheim
    (Hollow) - Blighttown' -> 'Griggs of Vinheim (Hollow)'. Suffixes
    that name no area stay ('Forest Hunter - Bandit'); names without
    a dash ('Drake (Flying)') pass through."""
    owner, place = split_owner_place(text or '')
    if place is not None and _norm_place(place) in displays:
        return owner
    return text or ''


def describe_treasure_name(name, stems):
    """Item and map of a treasure reference name: 'm10_01_ church gate
    lever' -> ('church gate lever', 'Undead Burg'). stems maps the
    map-stem prefix to the map list's display name
    (MapStore.stem_display_names); names without a stem keep the whole
    name and no map."""
    match = _TREASURE_STEM.match(name or '')
    if not match:
        return name or '', ''
    return ((name or '')[match.end():].strip(),
            stems.get((match.group(1), match.group(2)), ''))


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
        """'Undead Burg', 'Test map m99_80_00_00' for the m99 test block
        without area text, or the bare id otherwise."""
        match = _MAP_AREA.match(map_id or '')
        document = getattr(self.item_store, 'document', None)
        texts = document.texts if document is not None else None
        if match and texts is not None:
            first = int(match.group(1)) * 100 + int(match.group(2)) * 10
            for area_id in range(first, first + 10):
                name = texts.place_name(area_id)
                if name:
                    return name
        if match and match.group(1) == '99':
            return f'Test map {map_id[:-len(".msb")]}'
        return map_id

    def stem_display_names(self):
        """('10','01') -> 'Undead Burg': map-stem prefixes to the map
        list's names, for treasure reference names."""
        stems = {}
        for map_id in self.maps():
            match = _MAP_AREA.match(map_id)
            if match:
                stems.setdefault((match.group(1), match.group(2)),
                                 self.display_name(map_id))
        return stems

    def place_display_names(self):
        """Normalized area spellings to the map list's display names.

        Canonical map names first, then every numbered area (1000-1999)
        under its map file's name ('Valley of Drakes' -> 'New Londo
        Ruins'), then the reference names' informal spellings
        ('Firelink' -> 'Firelink Shrine'). Warp-only names (2000+) stay
        out: '[Daughter of Chaos]' names the covenant, not the bonfire.
        """
        displays = {}
        for map_id in self.maps():
            displays[_norm_place(self.display_name(map_id))] = self.display_name(map_id)
        stems = self.stem_display_names()
        document = getattr(self.item_store, 'document', None)
        texts = document.texts if document is not None else None
        if texts is not None:
            for area_id in range(1000, 2000):
                name = texts.place_name(area_id)
                if not name:
                    continue
                display = stems.get((f'{area_id // 100:02d}',
                                     f'{(area_id % 100) // 10:02d}'))
                if display is not None:
                    displays.setdefault(_norm_place(name), display)
        for alias, area_id in _PLACE_ALIASES.items():
            if area_id is None:
                displays.setdefault(alias, None)
                continue
            display = stems.get((f'{area_id // 100:02d}',
                                 f'{(area_id % 100) // 10:02d}'))
            if display is not None:
                displays.setdefault(alias, display)
        return displays

    def describe_drop(self, name, link_ids, displays=None):
        """A drop row's directory columns: owner, item and map names.
        Links name real placements, so linked maps win; the bracket's
        area is the fallback for gifts and corpse lots no enemy drops."""
        if displays is None:
            displays = self.place_display_names()
        owner, item, place = describe_directory_name(name, displays)
        if link_ids:
            ordered = []
            for map_id in link_ids:
                display = self.display_name(map_id)
                if display not in ordered:
                    ordered.append(display)
            return {'owner': owner, 'item': item, 'mapNames': ordered}
        return {'owner': owner, 'item': item, 'mapNames': [place] if place else []}

    def describe_treasure(self, name, stems=None, link_ids=()):
        """A treasure row's directory columns: item and map names. The
        reference names carry their map as a stem prefix ('m10_01_
        church gate lever'); names without one keep the whole name."""
        if stems is None:
            stems = self.stem_display_names()
        item, display = describe_treasure_name(name, stems)
        if link_ids:
            return {'owner': '', 'item': item,
                    'mapNames': list(dict.fromkeys(self.display_name(map_id) for map_id in link_ids))}
        return {'owner': '', 'item': item, 'mapNames': [display] if display else []}

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

    def locate_drop(self, lot_id, prefer_map=None):
        """A placement of an enemy dropping this lot, for go-to.

        ItemLotParam rows name no map, but NpcParam rows name their lots,
        and placements name their NPC. Without readable parameters there is
        nothing to resolve, so the directory shows no go-to button.
        prefer_map names the open map: a dropper standing there wins over
        the first alphabetical match, so go-to focuses in place instead
        of mounting another map's whole viewport as a side effect.
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
        names = self.maps()
        ordered = [prefer_map] + [name for name in names if name != prefer_map] \
            if prefer_map in names else names
        for map_name in ordered:
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

    def activation_maps(self):
        """Interaction rows used by each map's explicit or inherited activations."""
        from .msb_events import activation_parameter
        links = {}
        for map_name in self.maps():
            try:
                document = self.get(map_name)
            except (MsbError, OSError):
                continue
            for item in document.events:
                try:
                    parameter = activation_parameter(document, item)
                except MsbError:
                    continue
                if parameter is not None:
                    links.setdefault(parameter, set()).add(map_name)
        return {parameter: sorted(maps) for parameter, maps in links.items()}

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

    def chr_binder(self, stem):
        """The live character binder for a model stem, mod override first."""
        name = f"{stem}.chrbnd.dcx"
        if self.project is not None:
            own = self.project / "chr" / name
            if own.is_file():
                return own
        live = self.game_root / "chr" / name
        return live if live.is_file() else None

    def npc_models(self):
        """Each placed NPC ID with the character models it wears.

        Links come from every map's enemy parts. One map's broken bytes
        must not hide every other map's links, so unreadable maps are
        skipped. NPC swaps and placement edits invalidate the cache.
        NPCs no map places (event and online spawns name no model)
        fall back to their same-hundred character binder when one
        exists; placements always win."""
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
            known, _names, _types = self._npc()
            for npc in known:
                if npc in links:
                    continue
                stem = f"c{npc // 100}"
                if self.chr_binder(stem) is not None:
                    links[npc] = {stem}
            self._npc_models = {npc: sorted(models) for npc, models in links.items()}
        return self._npc_models

    def _who(self, part_name, npc, names):
        """Who stands there: the enemy's name, the bare part name for
        things without an NPC id, or an Unknown fallback."""
        if npc is None:
            return part_name
        return names.get(npc, "") or f"Unknown ({npc})"

    def _title(self, part_name, npc, names, displays):
        """A placement's title: who stands there, never the map. The map
        belongs in the list's own Map column (values "mapNames"). The
        bare part name stays pinnable under values, never in the title."""
        return strip_owner_suffix(self._who(part_name, npc, names), displays)

    def _placement_row(self, map_name, placement, names, types, displays=None):
        npc = placement.get("npc")
        if displays is None:
            displays = self.place_display_names()
        enemy = names.get(npc, "") if npc is not None else ""
        who = self._title(placement["name"], npc, names, displays)
        values = {"map": map_name, "part": placement["name"], "kind": placement["kind"],
                  "model": placement["model"],
                  "posX": placement["pos"][0], "posY": placement["pos"][1], "posZ": placement["pos"][2],
                  "rotX": placement["rot"][0], "rotY": placement["rot"][1], "rotZ": placement["rot"][2],
                  "scaleX": placement["scale"][0], "scaleY": placement["scale"][1], "scaleZ": placement["scale"][2],
                  "npcId": npc, "npcType": types.get(npc) if npc is not None else None,
                  "who": who,
                  "mapNames": [self.display_name(map_name)]}
        display = {"npcId": enemy if enemy else (f"Unknown ({npc})" if npc is not None else "")}
        if 'hitFilter' in placement:
            values['hitFilter'] = placement['hitFilter']
        if placement['type'] == 'region' or str(placement['type']).startswith('event') or placement['type'] == 5:
            fields = self.get(map_name).read_placement((placement['type'], placement['partId']))['fields']
            self._event_param_links(fields)
            for field in fields:
                values[field['key']] = field['value']
                if field['enum']:
                    display[field['key']] = field['enum'].get(str(field['value']), str(field['value']))
        modified = self.get(map_name).placement_modified((placement["type"], placement["partId"]))
        return {"id": f"{placement['type']}:{placement['partId']}", "table": map_name,
                "name": who,
                "range": placement["name"], "values": values, "display": display,
                "modified": modified}

    def list_rows(self):
        _ids, names, types = self._npc()
        displays = self.place_display_names()
        rows = []
        for map_name in self.maps():
            for placement in self.get(map_name).placements():
                rows.append(self._placement_row(map_name, placement, names, types, displays))
        return rows

    def _light_row(self, map_name, light):
        values = {"map": map_name, "part": light["part"], "kind": "Light",
                  "posX": light["pos"][0], "posY": light["pos"][1], "posZ": light["pos"][2],
                  "preset": light["preset"], "point": light["point"],
                  "who": light["name"],
                  "mapNames": [self.display_name(map_name)]}
        modified = self.get(map_name).light_modified(("light", light["seq"]))
        return {"id": light["key"], "table": map_name,
                "name": light["name"],
                "range": light["name"], "values": values, "display": {},
                "modified": modified}

    def light_rows(self):
        rows = []
        for map_name in self.maps():
            for light in self.get(map_name).lights():
                rows.append(self._light_row(map_name, light))
        return rows

    def _message_row(self, map_name, message):
        values = {"map": map_name, "part": message["partName"], "kind": "Message",
                  "text": message["textId"], "point": message["point"],
                  "flag": message["flag"], "who": message["name"],
                  "mapNames": [self.display_name(map_name)]}
        if message["pos"] is not None:
            values.update({"posX": message["pos"][0], "posY": message["pos"][1],
                           "posZ": message["pos"][2]})
        modified = self.get(map_name).message_modified(("message", message["seq"]))
        return {"id": message["key"], "table": map_name,
                "name": message["name"],
                "range": message["name"], "values": values, "display": {},
                "modified": modified}

    def row_values(self, map_name, key):
        """One placement's list values, display names and title, fresh after
        an edit, so undo can patch the lists without re-reading the map."""
        if str(key).startswith("message:"):
            message = next((entry for entry in self.get(map_name).messages()
                            if entry["key"] == key), None)
            if message is None:
                raise MsbError("Unknown message")
            row = self._message_row(map_name, message)
            return row["values"], row["display"], row["name"]
        if str(key).startswith("light:"):
            light = next((entry for entry in self.get(map_name).lights()
                          if entry["key"] == key), None)
            if light is None:
                raise MsbError("Unknown light")
            row = self._light_row(map_name, light)
            return row["values"], row["display"], row["name"]
        _ids, names, types = self._npc()
        part_key = parse_key(key)
        placement = next((entry for entry in self.get(map_name).placements()
                          if (entry["type"], entry["partId"]) == part_key), None)
        if placement is None:
            raise MsbError("Unknown placement")
        row = self._placement_row(map_name, placement, names, types,
                                  self.place_display_names())
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

    def _event_param_links(self, fields):
        linked = [field for field in fields if field['key'] in EVENT_PARAM_LINKS]
        if not linked:
            return []
        try:
            document = self.item_store.get() if self.item_store else None
        except (OSError, FormatError):
            document = None
        links = []
        for field in linked:
            kind, table = EVENT_PARAM_LINKS[field['key']]
            choices = document.link_choices(kind, table) if document else {'-1': 'None'}
            value = field['value']
            field.update(type='enum', enum=choices)
            empty = value < 0 or choices.get(str(value)) == 'None'
            link = {'kind': kind, 'table': table, 'id': value, 'field': field['key'],
                    'resolved': not empty and str(value) in choices,
                    'name': 'None' if empty else choices.get(str(value), f'Missing record ({value})')}
            if table == 'ObjActParam':
                link.update(tab='maps', sub='treasure')
            links.append(link)
        return links

    def read(self, map_name, key):
        if str(key).startswith("message:"):
            return self.read_message(map_name, key)
        if str(key).startswith("light:"):
            return self.read_light(map_name, key)
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
        row["shortName"] = self._title(row["name"], npc, names, self.place_display_names())
        row["name"] = row["shortName"]
        for item in row["fields"]:
            if item["key"] in originals:
                item["vanilla"] = originals[item["key"]]
            if item["key"] == "npcId":
                item["type"] = "enum"
                item["enum"] = {str(row_id): names[row_id] for row_id in sorted(names)}
        row["recordLinks"] = self._event_param_links(row['fields'])
        if npc is not None:
            tab, sub = self._npc_tab(npc, types)
            row["recordLinks"].append({'kind': 'npc', 'table': 'NpcParam', 'id': npc,
                                       'field': 'npcId', 'resolved': npc in names,
                                       'name': names.get(npc, f'Missing NPC {npc}'),
                                       'tab': tab, 'sub': sub})
        return row

    def read_message(self, map_name, key):
        seq = int(str(key).split(":")[1])
        row = self.get(map_name).read_message(("message", seq))
        try:
            originals = {item["key"]: item["value"]
                         for item in self._vanilla_doc(map_name).read_message(
                             ("message", seq))["fields"]}
        except MsbError:
            originals = {}
        row.update(id=key, table=map_name, map=map_name)
        row["shortName"] = row["name"]
        for item in row["fields"]:
            if item["key"] in originals:
                item["vanilla"] = originals[item["key"]]
        row["recordLinks"] = []
        return row

    def read_light(self, map_name, key):
        seq = int(str(key).split(":")[1])
        row = self.get(map_name).read_light(("light", seq))
        try:
            originals = {item["key"]: item["value"]
                         for item in self._vanilla_doc(map_name).read_light(("light", seq))["fields"]}
        except MsbError:
            originals = {}
        row.update(id=key, table=map_name, map=map_name)
        row["shortName"] = row["name"]
        for item in row["fields"]:
            if item["key"] in originals:
                item["vanilla"] = originals[item["key"]]
        row["recordLinks"] = []
        return row

    def row_modified(self, map_name, key):
        """Whether this session changed the placement, light or message."""
        if str(key).startswith("message:"):
            return self.get(map_name).message_modified(
                ("message", int(str(key).split(":")[1])))
        if str(key).startswith("light:"):
            return self.get(map_name).light_modified(("light", int(str(key).split(":")[1])))
        return self.get(map_name).placement_modified(parse_key(key))

    def edit(self, map_name, key, field, value):
        self.writable()
        if str(key).startswith("message:"):
            seq = int(str(key).split(":")[1])
            self.get(map_name).edit_message(("message", seq), field, value)
            return self.read(map_name, key)
        if str(key).startswith("light:"):
            seq = int(str(key).split(":")[1])
            self.get(map_name).edit_light(("light", seq), field, value)
            return self.read(map_name, key)
        self.writable()
        ids, _names, _types = self._npc()
        self.get(map_name).edit(parse_key(key), field, value, ids if field == "npcId" else None)
        self._npc_models = None
        return self.read(map_name, key)

    def add_placement(self, map_name, key):
        self.writable()
        if str(key).startswith('light:'):
            from . import msb_events
            row = msb_events.duplicate(self.get(map_name), ('event0', int(str(key).split(':')[1])))
            return self.read(map_name, row['key'])
        if str(key).startswith("message:"):
            row = self.get(map_name).add_message(
                ("message", int(str(key).split(":")[1])))
            return self.read(map_name, row["key"])
        row = self.get(map_name).add_placement(parse_key(key))
        self._npc_models = None
        return self.read(map_name, f"{row['type']}:{row['partId']}")

    def create_placement(self, map_name, model, pos, rot, npc=None, part_type=None):
        self.writable()
        row = self.get(map_name).create_placement(model, pos, rot, npc, part_type)
        self._npc_models = None
        return self.read(map_name, row.get('key') or f"{row['type']}:{row['partId']}")

    def remove_placement(self, map_name, key):
        self.writable()
        self._npc_models = None
        if str(key).startswith('light:'):
            from . import msb_events
            return msb_events.remove(self.get(map_name), ('event0', int(str(key).split(':')[1])))
        if str(key).startswith("message:"):
            return self.get(map_name).remove_message(
                ("message", int(str(key).split(":")[1])))
        return self.get(map_name).remove_placement(parse_key(key))

    @property
    def dirty_count(self):
        return sum(document.dirty_count for document in self.docs.values())

    def pending_changes(self):
        _ids, names, _types = self._npc()
        changes = []
        for map_name, document in self.docs.items():
            known = {(part["type"], part["id"]): part["name"] for part in document.parts}
            known.update({('region', point['index']): point['name'] for point in document.points})
            known.update({(f"event{event['type']}", event['seq']): event['name'] for event in document.events})
            for (ptype, pid), field in sorted(document.dirty, key=str):
                if ptype == "message":
                    row = document.read_message((ptype, pid))
                    message_label = next(
                        message["name"] for message in document.messages()
                        if message["seq"] == pid)
                    item = next(entry for entry in row["fields"] if entry["key"] == field)
                    changes.append({"label": f"{map_name} {message_label}, {item['label']}",
                                    "before": item["vanilla"], "after": item["value"]})
                    continue
                if ptype == "light":
                    row = document.read_light((ptype, pid))
                    light_label = next(
                        light["name"] for light in document.lights() if light["seq"] == pid)
                    item = next(entry for entry in row["fields"] if entry["key"] == field)
                    changes.append({"label": f"{map_name} {light_label}, {item['label']}",
                                    "before": item["vanilla"], "after": item["value"]})
                    continue
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
