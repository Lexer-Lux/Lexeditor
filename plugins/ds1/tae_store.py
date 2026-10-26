"""Mod project overlay for character animation binders: vanilla bytes or
the project's saved edits, one parsed binder at a time, with the same
save/discard/stale rules as the parameter archive."""
import hashlib
from pathlib import Path

from core.plugin_files import atomic_write

from . import assets
from . import deployment
from .formats import FormatError, deflate, inflate, members, pack
from .msb import MsbDocument
from .store import MARKER, digest
from .tae import ATTACK_TYPES, CHR_DIR, EVENT_TYPES, MAX_BINDER, TaeDocument, TaeError

EFFECT_TABLE = "SpEffectParam"
PLAYER_CHAR = "c0000"


def parse_key(key):
    """An event identity from its "ev:tae|anim|event" row form."""
    try:
        text = str(key)
        if text.startswith("ev:"):
            text = text[3:]
        tae, anim, event = text.split("|")
        if not tae.endswith(".tae"):
            raise ValueError
        return tae, int(anim), int(event)
    except (TypeError, ValueError) as error:
        raise TaeError("Select an animation event") from error


class TaeStore:
    def __init__(self, game_root, project=None, read_only=True, item_store=None):
        from .tweak_mods import checked
        self.game_root = checked(Path(game_root)).resolve()
        self.project = checked(Path(project)).resolve() if project else None
        self.read_only = read_only or self.project is None
        self.item_store = item_store
        self.docs = {}
        self.vanilla_docs = {}
        self.hashes = {}
        self._char_names = None

    def writable(self):
        if self.read_only:
            raise PermissionError("Create or select a mod before editing Vanilla.")
        if self.project == self.game_root or self.game_root in self.project.parents:
            raise ValueError("The mod project must be outside the game installation.")
        from .tweak_mods import checked
        checked(self.project / MARKER)
        if not (self.project / MARKER).is_file():
            raise ValueError("Select a valid Dark Souls mod project.")

    def binders(self):
        live = self.game_root / CHR_DIR
        if not live.is_dir():
            return []
        return sorted(path.name for path in live.glob("*.anibnd.dcx"))

    def char_names(self):
        """Character labels from map placements: model cXXXX plus the
        enemy most often placed in it. Cached; without readable maps
        or parameters every binder keeps its own ID."""
        if self._char_names is not None:
            return self._char_names
        names = {}
        try:
            document = self.item_store.get() if self.item_store else None
        except (OSError, FormatError):
            document = None
        try:
            if document is not None and "NpcParam" in document.params:
                from collections import Counter
                votes = {}
                live = self.game_root / "map/MapStudio"
                if live.is_dir():
                    for path in sorted(live.glob("*.msb")):
                        try:
                            msb = MsbDocument(path.read_bytes(), path.name)
                        except FormatError:
                            continue
                        for part in msb.parts:
                            if part["type"] not in (2, 10) or part["npc"] is None:
                                continue
                            model = msb.models[part["model"]]["name"]
                            votes.setdefault(model, Counter())[part["npc"]] += 1
                rows = {row.row_id for row in document.params["NpcParam"].rows}
                for model, counter in votes.items():
                    npc = counter.most_common(1)[0][0]
                    if npc in rows:
                        names[model] = document.display_name(
                            "NpcParam", npc,
                            next(r for r in document.params["NpcParam"].rows if r.row_id == npc))
        except (OSError, FormatError):
            pass
        names[PLAYER_CHAR] = "Player"
        self._char_names = names
        return names

    def _load(self, binder):
        from .tweak_mods import checked
        if "/" in binder or "\\" in binder or not binder.endswith(".anibnd.dcx"):
            raise TaeError("Unknown character file")
        output = self.project / CHR_DIR / binder if self.project else None
        vanilla = deployment.vanilla_source(self.game_root, CHR_DIR / binder)
        source = output if output and output.is_file() else vanilla
        checked(source)
        if source.stat().st_size > MAX_BINDER:
            raise ValueError("The character file is too large.")
        try:
            raw = source.read_bytes()
            plain = bytearray(inflate(raw))
            owned = members(plain)
        except FormatError as error:
            raise TaeError(f"Cannot open {binder}: {error}") from error
        taes = {}
        for name in sorted(owned):
            if not name.endswith(".tae"):
                continue
            member = owned[name]
            try:
                taes[name] = TaeDocument(bytes(plain[member.offset:member.offset + member.size]), name)
            except TaeError as error:
                raise TaeError(f"Cannot open {binder}: {name}: {error}") from error
        self.docs[binder] = {"raw": raw, "plain": plain, "members": owned, "taes": taes}
        self.hashes[binder] = {"source": source, "output": output, "vanilla": vanilla,
                               "source_hash": hashlib.sha256(raw).hexdigest(),
                               "vanilla_hash": digest(vanilla),
                               "output_hash": digest(output) if output else None}

    def get(self, binder):
        if binder not in self.binders():
            raise TaeError("Unknown character file")
        if binder not in self.docs:
            self._load(binder)
        return self.docs[binder]

    def _vanilla_tae(self, binder, tae):
        key = (binder, tae)
        if key not in self.vanilla_docs:
            vanilla = deployment.vanilla_source(self.game_root, CHR_DIR / binder)
            plain = inflate(vanilla.read_bytes())
            member = members(plain)[tae]
            self.vanilla_docs[key] = TaeDocument(
                bytes(plain[member.offset:member.offset + member.size]), tae)
        return self.vanilla_docs[key]

    def _speffects(self):
        """SpEffectParam row IDs and display names for effect links.

        Without readable parameters the animations still list and
        timings still edit; effects show as IDs and swaps are refused.
        """
        try:
            document = self.item_store.get() if self.item_store else None
        except (OSError, FormatError):
            document = None
        names = {}
        if document is not None and EFFECT_TABLE in document.params:
            for row in document.params[EFFECT_TABLE].rows:
                names[row.row_id] = document.display_name(EFFECT_TABLE, row.row_id, row)
        return set(names), names

    def list_chars(self):
        """Binders holding animation events, skipping binder forms this
        version cannot open. Skipped binders never appear as rows; the
        tab help names the limitation."""
        labels = self.char_names()
        rows = []
        for binder in self.binders():
            try:
                taes = self.get(binder)["taes"]
            except (TaeError, ValueError):
                continue
            if not taes:
                continue
            char = binder.split(".")[0]
            modified = any(doc.dirty_count for doc in self.get(binder)["taes"].values())
            rows.append({"id": f"char:{binder}", "table": binder, "tae": None,
                         "name": labels.get(char, char),
                         "values": {"binder": binder}, "display": {},
                         "modified": modified})
        return rows

    def list_anims(self, binder):
        """A binder's animations across its .tae files."""
        taes = self.get(binder)["taes"]
        rows = []
        for tae in sorted(taes):
            for anim in taes[tae].list_anims():
                rows.append({"id": f"anim:{tae}|{anim['index']}", "table": binder,
                             "tae": tae, "name": f"{anim['name']}",
                             "values": {"tae": tae, "animId": anim["id"],
                                        "events": anim["events"]}, "display": {},
                             "modified": taes[tae].anim_modified(anim["index"])})
        return rows

    def list_events(self, binder, tae, anim_index):
        """One animation's events in file order."""
        try:
            anim_index = int(anim_index)
        except (TypeError, ValueError) as error:
            raise TaeError("Select an animation from this file") from error
        taes = self.get(binder)["taes"]
        if tae not in taes:
            raise TaeError("Select an animation file from this character")
        rows = []
        for event in taes[tae].list_events(anim_index):
            rows.append({"id": f"ev:{tae}|{anim_index}|{event['index']}", "table": binder,
                         "tae": tae,
                         "name": f"{event['label']} at {event['start']:.2f}s",
                         "values": {"tae": tae, "anim": anim_index, "type": event["type"],
                                    "label": event["label"], "start": event["start"],
                                    "end": event["end"]}, "display": {},
                         "modified": taes[tae].event_modified(anim_index, event["index"])})
        return rows

    def read(self, binder, key):
        _ids, effect_names = self._speffects()
        tae, anim, event = parse_key(key)
        taes = self.get(binder)["taes"]
        if tae not in taes:
            raise TaeError("Select an animation file from this character")
        row = taes[tae].read_event(anim, event)
        try:
            vanilla = row.get("vanillaIndex")
            originals = {item["key"]: item["value"] for item in
                         self._vanilla_tae(binder, tae).read_event(anim, vanilla)["fields"]} \
                if vanilla is not None else {}
        except TaeError:
            originals = {}
        row.update(id=f"ev:{tae}|{anim}|{event}", table=binder, tae=tae, binder=binder)
        start = next(item["value"] for item in row["fields"] if item["key"] == "start")
        row["name"] = f"{row['label']} at {start:.2f}s"
        for item in row["fields"]:
            if item["key"] in originals:
                item["vanilla"] = originals[item["key"]]
            if item["key"] == "attackType":
                item["type"] = "enum"
                item["enum"] = {str(type_id): label for type_id, label in sorted(ATTACK_TYPES.items())}
            if item["key"] == "effect":
                item["type"] = "enum"
                item["enum"] = {str(row_id): effect_names[row_id] for row_id in sorted(effect_names)}
        row["recordLinks"] = self._sound_links(row)
        return row

    def _sound_links(self, row):
        """A Play-sound event Sound as a record link.

        The bank holding its number derives by search across the
        installed banks, so the reader picks sounds, never banks.
        Numbers no installed bank holds (and games without readable
        banks) stay unresolved links, never errors.
        """
        if not any(item["key"] == "soundId" for item in row["fields"]):
            return []
        sound_id = next(item["value"] for item in row["fields"] if item["key"] == "soundId")
        try:
            found = assets.find_sound(self.game_root, self.project, sound_id)
        except (OSError, FormatError):
            found = []
        if not found:
            return [{"kind": "sound", "table": "SoundStream", "id": sound_id,
                     "field": "soundId", "resolved": False,
                     "name": f"Unknown sound {sound_id}"}]
        first = found[0]
        return [{"kind": "sound", "table": "SoundStream", "id": sound_id,
                 "field": "soundId", "resolved": True, "name": first["stream"],
                 "bank": first["bank"], "stream": first["stream"], "sub": first["sub"],
                 "duration": first["duration"], "size": first["size"]}]

    def edit(self, binder, key, field, value):
        self.writable()
        tae, anim, event = parse_key(key)
        taes = self.get(binder)["taes"]
        if tae not in taes:
            raise TaeError("Select an animation file from this character")
        ids, _names = self._speffects()
        taes[tae].edit(anim, event, field, value, ids if field == "effect" else None)
        return self.read(binder, key)

    def add_event(self, binder, tae, anim_index, etype, start, end, values=None):
        self.writable()
        taes = self.get(binder)["taes"]
        if tae not in taes:
            raise TaeError("Select an animation file from this character")
        try:
            anim_index = int(anim_index)
        except (TypeError, ValueError) as error:
            raise TaeError("Select an animation from this file") from error
        if type(etype) is not int or isinstance(etype, bool):
            raise TaeError("Choose a documented event type")
        if values is not None and not isinstance(values, dict):
            raise TaeError("Unknown event field")
        ids, _names = self._speffects()
        index = taes[tae].add_event(anim_index, etype, start, end, values, ids)
        return self.read(binder, f"ev:{tae}|{anim_index}|{index}")

    def remove_event(self, binder, key):
        self.writable()
        tae, anim, event = parse_key(key)
        taes = self.get(binder)["taes"]
        if tae not in taes:
            raise TaeError("Select an animation file from this character")
        taes[tae].remove_event(anim, event)
        return self.list_events(binder, tae, anim)

    @property
    def dirty_count(self):
        return sum(tae.dirty_count for doc in self.docs.values() for tae in doc["taes"].values())

    def pending_changes(self):
        _ids, effect_names = self._speffects()
        changes = []
        for binder, doc in self.docs.items():
            for tae, document in doc["taes"].items():
                for anim_index, event_index, field in sorted(document.dirty):
                    row = document.read_event(anim_index, event_index)
                    item = next(entry for entry in row["fields"] if entry["key"] == field)
                    before, after = item["vanilla"], item["value"]
                    if field == "effect":
                        before = effect_names.get(before, before)
                        after = effect_names.get(after, after)
                    changes.append({"label": (f"{binder} {tae} {row['animName']} "
                                              f"event {event_index}, {item['label']}"),
                                    "before": before, "after": after})
                for gone in document.removed:
                    changes.append({"label": (f"{binder} {tae} {gone['animName']} "
                                              f"event {gone['event']}, {gone['label']} (removed)"),
                                    "before": f"{gone['start']:.2f}-{gone['end']:.2f}s",
                                    "after": "removed"})
        return changes

    def validate_save(self):
        from .tweak_mods import checked
        self.writable()
        for binder, doc in self.docs.items():
            entry = self.hashes[binder]
            vanilla = deployment.vanilla_source(self.game_root, CHR_DIR / binder)
            for path in (entry["source"], vanilla, entry["output"]):
                if path is not None:
                    checked(path)
            if digest(entry["source"]) != entry["source_hash"] or digest(vanilla) != entry["vanilla_hash"]:
                raise ValueError("The character file changed outside Lexeditor. Reopen it before saving.")
            if digest(entry["output"]) != entry["output_hash"]:
                raise ValueError("The mod character file changed outside Lexeditor. Reopen it before saving.")
        return True

    def save(self):
        self.validate_save()
        from .tweak_mods import checked
        for binder, doc in self.docs.items():
            if not any(tae.dirty_count for tae in doc["taes"].values()):
                continue
            payloads = {}
            for name, tae in doc["taes"].items():
                member = doc["members"][name]
                payloads[name] = tae.export() if tae.dirty_count else bytes(
                    doc["plain"][member.offset:member.offset + member.size])
            if any(len(payloads[name]) != doc["members"][name].size for name in payloads):
                items = {name: bytes(doc["plain"][found.offset:found.offset + found.size])
                         for name, found in doc["members"].items()}
                items.update(payloads)
                plain = pack(bytes(doc["plain"]), items)
            else:
                plain = bytearray(doc["plain"])
                for name, payload in payloads.items():
                    member = doc["members"][name]
                    plain[member.offset:member.offset + member.size] = payload
                plain = bytes(plain)
            output = self.project / CHR_DIR / binder
            resolved = checked(output).resolve()
            if self.game_root in resolved.parents or self.project not in resolved.parents:
                raise ValueError("The output path leaves the mod project or enters the installed game.")
            # Re-parse the rebuilt binder before writing it.
            rebuilt = inflate(deflate(doc["raw"], plain))
            check = members(rebuilt)
            for name, tae in doc["taes"].items():
                if tae.dirty_count:
                    member = check[name]
                    TaeDocument(bytes(rebuilt[member.offset:member.offset + member.size]), name)
            output.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(output, deflate(doc["raw"], plain))
        self.docs = {}
        self.vanilla_docs = {}
        self.hashes = {}
        self._char_names = None
        return {"saved": True, "dirtyCount": 0}

    def discard(self):
        self.docs = {}
        self.vanilla_docs = {}
        self.hashes = {}
        self._char_names = None
        return {"discarded": True}
