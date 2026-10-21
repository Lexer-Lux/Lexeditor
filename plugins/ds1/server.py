"""Loopback parameter editor; only explicit deployment writes installed data."""
from http.server import ThreadingHTTPServer
import base64
import binascii
import json
import os
from pathlib import Path
import threading
from urllib.parse import parse_qs, urlparse

from core.plugin_http import PluginRequestHandler
from . import assets, deployment, data_map, fsb, icons, shops, theme
from . import anim
from .attacks import body_hitbox, hitbox_slots
from .map_store import MapStore, parse_key
from .msb import MsbError
from .flver import FlverError
from .tae import EVENT_TYPES, TaeError
from .tae_store import TaeStore
from .native_rules import NativeRules
from .formats import FormatError, stats_fields, TABLES, FMG_TABLES
from .effects import TABLE as EFFECT_TABLE
from .store import ItemStore
from . import tweak_mods
from . import data_map
from . import viewport

# Armor shows its male icon; male and female differ only on a few pieces,
# and the male set is complete.
_ICON_KEYS = {'EquipParamWeapon': 'iconId', 'EquipParamProtector': 'iconIdM',
              'EquipParamAccessory': 'iconId', 'EquipParamGoods': 'iconId',
              'Magic': 'iconId', 'SpEffectParam': 'iconId'}
ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
LOCK = threading.RLock()
IMMUTABLE = "public, max-age=31536000, immutable"

def _warm_icon_table():
    """Parse the icon layout under the caller's lock.

    The first parse costs a second; concurrent icon requests must share
    the one parse instead of each running their own.
    """
    if STORE.game_root is None:
        return
    try:
        icons.load_icon_table(STORE.game_root)
    except Exception:
        pass
STORE = ItemStore(os.environ.get('LEXEDITOR_DS1_ROOT', r'C:\Program Files (x86)\Steam\steamapps\common\DARK SOULS REMASTERED'),
                  None if os.environ.get('LEXEDITOR_NO_MOD') == '1' else os.environ.get('LEXEDITOR_DS1_PROJECT'),
                  os.environ.get('LEXEDITOR_MOD_READ_ONLY') == '1' or os.environ.get('LEXEDITOR_NO_MOD') == '1'
                  or not os.environ.get('LEXEDITOR_DS1_PROJECT'))

RULES = NativeRules(STORE.game_root, STORE.project, STORE.read_only)
MAPSTORE = MapStore(STORE.game_root, STORE.project, STORE.read_only, STORE)
TAESTORE = TaeStore(STORE.game_root, STORE.project, STORE.read_only, STORE)
NATIVE_TABS = {"encumbrance", "encumbrance-overrides", "levelup", "misc"}
UPLOAD_BODY_LIMIT = 2100000


def _asset_bytes(relative, side):
    """The bytes the game would load: the mod's override, else the installed file."""
    relative = assets.check_relative(relative)
    if STORE.project is not None and (side or "mod") != "game":
        own = Path(STORE.project) / relative
        if own.is_file():
            return own.read_bytes(), "mod", relative.as_posix()
    if STORE.game_root is None:
        raise ValueError("Select the installed game before browsing its files")
    live = Path(STORE.game_root) / relative
    if not live.is_file():
        raise ValueError("The installed game has no such file")
    return live.read_bytes(), "game", relative.as_posix()


def _sound_bank_path(relative):
    """The bank file the game would load: the mod's override, else the installed file."""
    relative = assets.check_relative(relative)
    if assets.kind_of(relative.as_posix()) not in ("sound", "music"):
        raise ValueError("Only sound banks list their streams")
    lowered = relative.as_posix().lower()
    inner = lowered[:-4] if lowered.endswith(".dcx") else lowered
    if not inner.endswith(".fsb"):
        raise ValueError("Only sound banks list their streams")
    if STORE.project is not None:
        own = Path(STORE.project) / relative
        if own.is_file():
            return own, "mod"
    if STORE.game_root is None:
        raise ValueError("Select the installed game before browsing its files")
    live = Path(STORE.game_root) / relative
    if not live.is_file():
        raise ValueError("The installed game has no such file")
    return live, "game"


def _tweaks_flag() -> bool:
    """Whether the installed tweaks differ from the library (Save rebuilds them)."""
    try:
        return bool(tweak_mods.needs_rebuild(STORE.game_root).get("needed"))
    except (ValueError, OSError, RuntimeError):
        return False


def _rebuild_tweaks_on_save() -> dict:
    """Build changed tweaks into the installed game as part of Save.

    The project is already saved when this runs; a tweak failure is
    reported, never raised, so a broken tweak cannot block project saves.
    With the game open the rebuild waits: the flag stays set and the next
    Save (or Play) finishes it.
    """
    if not _tweaks_flag():
        return {"tweaksNeedRebuild": False}
    if not tweak_mods.game_closed():
        return {"tweaksNeedRebuild": True, "tweaksDeferred": True}
    try:
        status = tweak_mods.apply(STORE.game_root)
    except (ValueError, OSError, RuntimeError) as error:
        return {"tweaksNeedRebuild": True, "tweaksError": str(error)}
    return {"tweaksNeedRebuild": bool(status.get("needsRebuild")), "tweaksRebuilt": True}


def _deploy_tweaks_now() -> None:
    """Build and install changed tweaks at once, for a session without Save.

    A session with no writable project has no Save button, so its Tweaks
    page installs straight away. With the game open the install waits for
    the next Play.
    """
    if _tweaks_flag() and tweak_mods.game_closed():
        try:
            tweak_mods.apply(STORE.game_root)
        except (ValueError, OSError, RuntimeError) as error:
            raise ValueError(f"Settings saved, but the rebuild failed: {error}") from error


THEME_CACHE = theme.cache_root()


def theme_status() -> dict:
    """Cosmetic installed-game theme; never a readiness gate."""
    if STORE.game_root is None:
        state = theme.fallback("Select the installed game before extracting its theme.")
    else:
        try:
            state = theme.build(THEME_CACHE, Path(STORE.game_root))
        except (OSError, ValueError) as error:
            state = theme.fallback("Installed-game theme extraction failed; fallback styling remains active.")
            state["error"] = str(error)
    try:
        state["sounds"] = theme.menu_sound_rows(THEME_CACHE, STORE.game_root)
    except (OSError, ValueError) as error:
        state["sounds"] = {"ready": False, "rows": [], "error": str(error)}
    return state


class Handler(PluginRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path in ('/api/state', '/api/table', '/api/row', '/api/attacks', '/api/behaviors', '/api/shop', '/api/data-map', '/api/assets',
                    '/api/world/locate',
                    '/api/map/view', '/api/map/geometry', '/api/chr/view', '/api/chr/geometry',
                    '/api/parts/view', '/api/parts/geometry',
                    '/api/anim/list', '/api/anim/skeleton', '/api/anim/frames', '/api/theme', '/api/theme/sfx'):
            try:
                with LOCK:
                    _warm_icon_table()
                    if path == '/api/assets':
                        scope = query.get('scope', ['overrides'])[0]
                        if scope == 'game':
                            if STORE.game_root is None:
                                raise ValueError('Select the installed game before browsing its files')
                            result = {'files': assets.scan_game(STORE.game_root, STORE.project)}
                        elif scope == 'all':
                            result = {'files': assets.scan_merged(STORE.game_root, STORE.project),
                                      'hasProject': STORE.project is not None,
                                      'readOnly': STORE.read_only}
                        elif scope == 'textures':
                            side = query.get('side', ['mod'])[0]
                            data, source, name = _asset_bytes(query.get('file', [''])[0], side)
                            model = assets.model_info(data, name) \
                                if assets.kind_of(name) == 'models' else None
                            if assets.is_split_archive(name):
                                textures, reason = [], 'split-archive'
                            else:
                                try:
                                    textures, reason = assets.list_textures(data, name), None
                                except assets.AssetError:
                                    textures, reason = [], 'unreadable'
                            if model is not None and model.get('previewable') and model.get('maps'):
                                found, meta = viewport.model_strip_pngs(
                                    STORE.game_root, STORE.project, name, side,
                                    model.get('member'), model['maps'])
                                have = {tile['name'].lower() for tile in textures}
                                for stem in model['maps']:
                                    if stem in found and meta[stem]['name'].lower() not in have:
                                        tile = meta[stem]
                                        textures.append({
                                            'name': tile['name'], 'width': tile['width'],
                                            'height': tile['height'], 'format': tile['format'],
                                            'png': 'data:image/png;base64,' + base64.b64encode(
                                                found[stem]).decode('ascii')})
                            result = {'file': name, 'source': source, 'size': len(data),
                                      'textures': textures, 'reason': reason,
                                      'model': model}
                        else:
                            result = {'files': assets.scan_project(STORE.project, strict=False,
                                                                    game_root=STORE.game_root)
                                      if STORE.project is not None else [],
                                      'hasProject': STORE.project is not None,
                                      'readOnly': STORE.read_only}
                    elif path == '/api/state':
                        result = STORE.state()
                        result['animTabs'] = [{'id': 'animations', 'label': 'Animations',
                                               'table': 'Tae', 'count': len(TAESTORE.binders())}]
                        for entry in result.get('miscTabs', []):
                            try:
                                entry['count'] = len(RULES.list_rows(entry['id']))
                            except ValueError:
                                pass
                        result['theme'] = theme_status()
                    elif path == '/api/data-map':
                        result = data_map.payload(STORE, RULES.snapshot(refresh=True), theme_status())
                    elif path == '/api/theme':
                        self.send_json(theme_status())
                        return
                    elif path == '/api/theme/sfx':
                        bank = query.get('bank', [''])[0]
                        self.send_json({'bank': bank, 'streams': theme.sfx_streams(THEME_CACHE, STORE.game_root, bank)})
                        return
                    elif path == '/api/world/locate':
                        table = query.get('table', [''])[0]
                        found = MAPSTORE.locate_drop(int(query.get('id', [''])[0])) \
                            if table == 'ItemLotParam' else None
                        result = {'map': found['map'], 'key': found['key']} if found \
                            else {'map': None, 'key': None}
                    elif path == '/api/map/view':
                        result = viewport.map_view(MAPSTORE, query.get('map', [''])[0])
                    elif path == '/api/map/geometry':
                        document = MAPSTORE.get(query.get('map', [''])[0])
                        model = next((entry for entry in document.models
                                      if entry['name'] == query.get('model', [''])[0]), None)
                        if model is None:
                            raise MsbError('Unknown map model')
                        result = viewport.model_geometry(
                            MAPSTORE.game_root, MAPSTORE.project, document.map_name, model,
                            frozenset(filter(None, query.get('known', [''])[0].split(','))) or None)
                    elif path == '/api/chr/view':
                        npc = int(query.get('npc', [''])[0])
                        document = STORE.get()
                        links = MAPSTORE.npc_models().get(npc, [])
                        chrs = []
                        for chr_id in links:
                            try:
                                info = viewport.chr_dummies(MAPSTORE.game_root, MAPSTORE.project, chr_id)
                            except (FormatError, OSError) as error:
                                chrs.append({'id': chr_id, 'available': False, 'reason': str(error)})
                            else:
                                chrs.append({'id': chr_id, 'available': True, 'meshes': info['meshes'],
                                             'bones': info['bones'], 'dummies': info['dummies']})
                        name = document.display_name('NpcParam', npc)
                        # The list thumbnail needs only links and a name; attacks and
                        # hitboxes stay on the full view, so a broken behavior table
                        # cannot take the thumbnail down with it.
                        if query.get('view', [''])[0] == 'thumb':
                            result = {'npc': npc, 'name': name, 'chrs': chrs}
                        else:
                            attacks = []
                            for entry in document.attack_references().list(npc)['rows']:
                                attack = entry['id']
                                attacks.append({'id': attack, 'name': entry['name'],
                                                'source': document.value('AtkParam_Npc', attack, 'hitSourceType'),
                                                'slots': hitbox_slots(document, attack)})
                            result = {'npc': npc, 'name': name,
                                      'body': body_hitbox(document, npc), 'chrs': chrs, 'attacks': attacks}
                    elif path == '/api/chr/geometry':
                        result = viewport.chr_geometry(MAPSTORE.game_root, MAPSTORE.project,
                                                       query.get('chr', [''])[0],
                                                       query.get('skin', [''])[0] == '1')
                    elif path == '/api/parts/view':
                        table = query.get('table', [''])[0]
                        row_id = int(query.get('id', [''])[0])
                        info = STORE.get().part_model(table, row_id)
                        if not info['available']:
                            result = {'table': table, 'id': row_id, 'available': False,
                                      'reason': info['reason']}
                        else:
                            stems, reason = viewport.part_candidates(
                                table, info['category'], info['gender'], info['model_id'])
                            if stems is None:
                                result = {'table': table, 'id': row_id, 'available': False,
                                          'reason': reason}
                            else:
                                models = []
                                for stem, variant in stems:
                                    entry = viewport.part_view(MAPSTORE.game_root,
                                                             MAPSTORE.project, stem)
                                    entry['variant'] = variant
                                    models.append(entry)
                                result = {'table': table, 'id': row_id, 'models': models,
                                          'available': any(entry['available'] for entry in models)}
                                if not result['available']:
                                    missing = ', '.join(entry['stem'] + '.partsbnd.dcx'
                                                        for entry in models)
                                    result['reason'] = (f'The {missing} model file is not in the game or the mod.'
                                                        if len(models) == 1 else
                                                        f'Neither model file is installed: {missing}.')
                    elif path == '/api/parts/geometry':
                        table = query.get('table', [''])[0]
                        row_id = int(query.get('id', [''])[0])
                        want = query.get('variant', ['M'])[0]
                        info = STORE.get().part_model(table, row_id)
                        if not info['available']:
                            raise FlverError(info['reason'])
                        stems, reason = viewport.part_candidates(
                            table, info['category'], info['gender'], info['model_id'])
                        if stems is None:
                            raise FlverError(reason)
                        picked = next((stem for stem, variant in stems if variant == want), stems[0][0])
                        result = viewport.part_geometry(MAPSTORE.game_root, MAPSTORE.project, picked)
                    elif path == '/api/anim/list':
                        result = anim.list_anims(MAPSTORE.game_root, MAPSTORE.project,
                                                 query.get('chr', [''])[0], TAESTORE)
                    elif path == '/api/anim/skeleton':
                        result = anim.skeleton(MAPSTORE.game_root, MAPSTORE.project,
                                               query.get('chr', [''])[0])
                    elif path == '/api/anim/frames':
                        result = anim.anim_frames(MAPSTORE.game_root, MAPSTORE.project,
                                                  query.get('chr', [''])[0],
                                                  query.get('binder', [''])[0],
                                                  query.get('anim', [''])[0], TAESTORE)
                    elif path == '/api/attacks':
                        result = STORE.get().attack_references().list(int(query.get('monster', [''])[0]), query.get('all', ['0'])[0] == '1')
                        result['dirtyCount'] = STORE.get().dirty_count
                    elif path == '/api/behaviors':
                        npc = int(query.get('monster', [''])[0])
                        document = STORE.get()
                        if not (document.is_monster(npc) or document.is_friend(npc)
                                or document.is_merchant(npc) or document.is_boss(npc)):
                            raise ValueError('Select a reviewed monster or NPC')
                        variation = document.value('NpcParam', npc, 'behaviorVariationId')
                        references = document.attack_references()
                        result = {'rows': references.moves(variation), 'variation': variation,
                                  'behaviorCount': len(references.by_variation[variation])}
                        result['dirtyCount'] = STORE.get().dirty_count
                    elif path == '/api/shop':
                        result = {'rows': shops.stock(STORE.get(), query.get('npc', [''])[0])}
                    elif path == '/api/table':
                        tab = query.get('tab', [''])[0]
                        if tab == 'placements':
                            result = {'rows': MAPSTORE.list_rows()}
                        elif tab == 'viewport':
                            counts = MAPSTORE.map_counts()
                            rows = []
                            for name in MAPSTORE.maps():
                                rows.append({'id': name, 'table': 'MapView', 'name': MAPSTORE.display_name(name),
                                             'values': counts.get(name, {'npcs': 0, 'drops': 0, 'enemies': 0})})
                            result = {'rows': rows}
                        elif tab == 'playback':
                            labels = TAESTORE.char_names()
                            rows = []
                            for chr_id in anim.list_chars(MAPSTORE.game_root, MAPSTORE.project):
                                rows.append({'id': chr_id, 'table': 'AnimPlayback',
                                             'name': labels.get(chr_id, chr_id),
                                             'values': {'binder': f'{chr_id}.anibnd.dcx'}})
                            result = {'rows': rows}
                        elif tab == 'animations':
                            scope = query.get('scope', ['chars'])[0]
                            if scope == 'anims':
                                result = {'rows': TAESTORE.list_anims(query.get('binder', [''])[0])}
                            elif scope == 'events':
                                result = {'rows': TAESTORE.list_events(query.get('binder', [''])[0],
                                                                       query.get('tae', [''])[0],
                                                                       query.get('anim', [''])[0])}
                            elif scope == 'eventTypes':
                                result = {'types': [{'type': type_id, 'label': spec[1]}
                                                    for type_id, spec in sorted(EVENT_TYPES.items())]}
                            else:
                                result = {'rows': TAESTORE.list_chars()}
                        else:
                            result = {'rows': RULES.list_rows(tab) if tab in NATIVE_TABS else STORE.get().list_rows(tab)}
                            if tab == 'drops':
                                links = MAPSTORE.lot_maps()
                                displays = MAPSTORE.place_display_names()
                                for row in result['rows']:
                                    row['values']['maps'] = links.get(row['id'], [])
                                    row['values'].update(MAPSTORE.describe_drop(
                                        row['name'], links.get(row['id'], []), displays))
                            elif tab == 'treasure':
                                stems = MAPSTORE.stem_display_names()
                                for row in result['rows']:
                                    row['values'].update(
                                        MAPSTORE.describe_treasure(row['name'], stems))
                    else:
                        table = query.get('table', [''])[0]
                        if table.endswith('.msb'):
                            result = {'row': MAPSTORE.read(table, query.get('id', [''])[0])}
                        elif table.endswith('.anibnd.dcx'):
                            result = {'row': TAESTORE.read(table, query.get('id', [''])[0])}
                        else:
                            row_id = int(query.get('id', [''])[0])
                            only = stats_fields(query.get('sub', [''])[0], table)
                            result = {'row': RULES.read_row(row_id) if table == 'NativeRules'
                                      else STORE.get().read_row(table, row_id, only=only, game_root=STORE.game_root)}
                    result['dirtyCount'] = STORE.get().dirty_count + RULES.dirty_count + MAPSTORE.dirty_count + TAESTORE.dirty_count
                    result['changes'] = STORE.get().pending_changes() + MAPSTORE.pending_changes() + TAESTORE.pending_changes()
                    result['nativeRules'] = RULES.snapshot()
                    result['tweaksNeedRebuild'] = _tweaks_flag()
                    self.send_json(result)
            except (FormatError, RuntimeError, ValueError, OSError, KeyError, UnicodeError) as error:
                self.send_json({'error': str(error)}, 400)
            return
        if path in ('/api/icon', '/api/label'):
            try:
                if STORE.game_root is None:
                    raise ValueError('Select the installed game before showing its icons')
                if path == '/api/label':
                    png = icons.label_png(STORE.game_root, query.get('name', [''])[0])
                else:
                    table = query.get('table', [''])[0]
                    key = _ICON_KEYS.get(table)
                    if key is None:
                        raise ValueError('That record has no item picture')
                    try:
                        row_id = int(query.get('id', [''])[0])
                    except ValueError:
                        raise ValueError('An item picture needs a numeric record') from None
                    # Only the record read takes the lock. The PNG work reads
                    # immutable game files through thread-safe caches, so icon
                    # requests run side by side instead of queueing behind it.
                    with LOCK:
                        _warm_icon_table()
                        icon_id = STORE.get().value(table, row_id, key)
                    if not isinstance(icon_id, int) or icon_id <= 0:
                        raise LookupError('That record has no item picture')
                    png = icons.icon_png(STORE.game_root, icon_id)
                self.send_bytes(png, 'image/png', cache=IMMUTABLE)
            except LookupError as error:
                self.send_json({'error': str(error)}, 404)
            except (FormatError, icons.IconError, RuntimeError, ValueError, OSError,
                    KeyError, UnicodeError) as error:
                self.send_json({'error': str(error)}, 400)
            return
        if path == '/api/assets/preview':
            try:
                with LOCK:
                    data, _source, name = _asset_bytes(query.get('file', [''])[0],
                                                       query.get('side', ['mod'])[0])
                    try:
                        index = int(query.get('index', ['0'])[0])
                    except ValueError:
                        raise ValueError('A texture preview needs a numeric texture') from None
                    self.send_bytes(assets.texture_png(data, name, query.get('member', [''])[0], index),
                                    'image/png')
            except (FormatError, RuntimeError, ValueError, OSError, KeyError, UnicodeError) as error:
                self.send_json({'error': str(error)}, 400)
            return
        if path == '/api/assets/geometry':
            try:
                with LOCK:
                    relative = assets.check_relative(query.get('file', [''])[0])
                    if assets.kind_of(relative.as_posix()) != 'models':
                        raise ValueError('Only model files have geometry to preview')
                    self.send_json(viewport.asset_geometry(
                        STORE.game_root, STORE.project, relative,
                        query.get('side', ['mod'])[0],
                        query.get('member', [''])[0] or None))
            except (FormatError, RuntimeError, ValueError, OSError, KeyError, UnicodeError) as error:
                self.send_json({'error': str(error)}, 400)
            return
        if path == '/api/sounds':
            try:
                with LOCK:
                    kind = query.get('kind', ['sfx'])[0]
                    if kind not in ('sfx', 'music'):
                        raise ValueError("Sounds list 'sfx' or 'music'")
                    streams = assets.list_streams(STORE.game_root, STORE.project)
                    rows = [{"table": "SoundStream", "id": f"{entry['bank']}::{entry['name']}",
                             "name": entry["name"], "bank": entry["bank"],
                             "duration": entry["duration"], "size": entry["size"]}
                            for entry in (streams["music"] if kind == "music" else streams["sound"])]
                    self.send_json({"rows": rows, "unreadable": streams["unreadable"]})
            except (FormatError, RuntimeError, ValueError, OSError, KeyError, UnicodeError) as error:
                self.send_json({'error': str(error)}, 400)
            return
        if path == '/api/sound/bank':
            try:
                with LOCK:
                    bank, source = _sound_bank_path(query.get('file', [''])[0])
                    self.send_json({'file': bank.name, 'source': source,
                                      'streams': [{"name": entry["name"],
                                                   "duration": entry["duration"],
                                                   "size": entry["size"]}
                                                  for entry in fsb.parse_table(bank)]})
            except (FormatError, RuntimeError, ValueError, OSError, KeyError, UnicodeError) as error:
                self.send_json({'error': str(error)}, 400)
            return
        if path == '/api/sound/stream':
            try:
                with LOCK:
                    bank, _source = _sound_bank_path(query.get('file', [''])[0])
                    wanted = query.get('stream', [''])[0]
                    table = fsb.parse_table(bank)
                    entry = next((item for item in table if item["name"] == wanted), None)
                    if entry is None:
                        raise ValueError("Unknown sound stream")
                    self.send_bytes(fsb.extract_mp3(bank, entry), "audio/mpeg")
            except (FormatError, RuntimeError, ValueError, OSError, KeyError, UnicodeError) as error:
                self.send_json({'error': str(error)}, 400)
            return
        if path in ('/api/deployment', '/api/tweaks'):
            try:
                with LOCK:
                    self.send_json(tweak_mods.status(STORE.game_root) if path == '/api/tweaks'
                                   else RULES.deployment_status())
            except (RuntimeError, ValueError, OSError, KeyError) as error:
                self.send_json({'error': str(error)}, 400)
            return
        if path == "/":
            self.send_file(PLUGIN_ROOT / "editor.html")
        elif path == "/api/plugin":
            self.send_json({"apiVersion": 1, "pluginId": "ds1",
                            "name": "Dark Souls Remastered", "hosted": True,
                            "capabilities": ["data-map", "items", "monster-resistances", "monster-stats", "enemy-attacks", "project-export", "byte-preserving-roundtrip", "mod-deployment", "executable-tweaks", "effects", "stats", "encumbrance", "levelup-gains", "native-stamina", "map-placements", "animation-events", "world", "asset-replacement", "map-viewport"]})
        elif self.send_page_module(PLUGIN_ROOT, path):
            return
        elif path.startswith("/shared/"):
            shared = (ROOT / "ui").resolve()
            target = (shared / path.removeprefix("/shared/")).resolve()
            if shared in target.parents and target.is_file():
                self.send_file(target)
            elif path == '/shared/distribution-notices.json':
                self.send_json([])
            else:
                self.send_json({"error": "Not found"}, 404)
        elif path.startswith("/theme/"):
            try:
                self.send_file(theme.asset_path(THEME_CACHE, path.removeprefix("/theme/")))
            except FileNotFoundError:
                self.send_json({"error": "Not found"}, 404)
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path not in ('/api/edit', '/api/rename', '/api/save', '/api/discard', '/api/bands/add', '/api/bands/delete', '/api/tae/add', '/api/tae/remove', '/api/rows/add', '/api/rows/remove', '/api/placements/add', '/api/placements/remove', '/api/placements/create', '/api/assets/upload', '/api/assets/remove', '/api/deployment/apply', '/api/deployment/disable',
                            '/api/tweaks/save', '/api/tweaks/restore', '/api/tweaks/debug'):
                self.send_json({'error': 'Not found'}, 404)
                return
            origin = self.headers.get('Origin')
            if origin and origin != f"http://{self.headers.get('Host')}":
                raise PermissionError('Cross-origin writes are not permitted')
            length = int(self.headers.get('Content-Length', '0'))
            limit = UPLOAD_BODY_LIMIT if path == '/api/assets/upload' else 65536
            if not 0 < length <= limit:
                raise ValueError('Invalid request size')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict): raise ValueError('Expected an object')
            with LOCK:
                if path == '/api/edit':
                    only = stats_fields(payload.get('sub', ''), payload.get('table'))
                    extra = {}
                    if payload.get('table') == 'NativeRules':
                        row = RULES.edit_row(payload.get('id'), payload.get('field'), payload.get('value'))
                        extra = {'modified': RULES.row_modified(payload.get('id'))}
                    elif str(payload.get('table', '')).endswith('.msb'):
                        row = MAPSTORE.edit(payload.get('table'), payload.get('id'), payload.get('field'), payload.get('value'))
                        values, display, name = MAPSTORE.row_values(
                            payload.get('table'), payload.get('id'))
                        extra = {'values': values, 'display': display, 'name': name,
                                 'modified': MAPSTORE.get(payload.get('table')).placement_modified(
                                     parse_key(payload.get('id')))}
                    elif str(payload.get('table', '')).endswith('.anibnd.dcx'):
                        row = TAESTORE.edit(payload.get('table'), payload.get('id'), payload.get('field'), payload.get('value'))
                    else:
                        table = payload.get('table')
                        row = STORE.edit(table, payload.get('id'), payload.get('field'), payload.get('value'), only=only)
                        # The table's pinned columns read row values, so the
                        # edit hands back the row's fresh ones; without them
                        # the table keeps showing what the field just replaced.
                        if table == 'MenuText':
                            label = next((field['value'] for field in row['fields']
                                          if field['key'] == 'label'), None)
                            if label is not None:
                                extra = {'values': {'label': label}, 'display': {},
                                         'modified': STORE.get().text_row_modified(table, payload.get('id'))}
                        elif table in FMG_TABLES:
                            text = next((field['value'] for field in row['fields']
                                         if field['key'] == 'text'), None)
                            if text is not None:
                                extra = {'values': {'text': text}, 'display': {},
                                         'modified': STORE.get().text_row_modified(table, payload.get('id'))}
                        elif table in TABLES:
                            values, display = STORE.get().row_values(table, payload.get('id'))
                            extra = {'values': values, 'display': display,
                                     'refreshRows': table == EFFECT_TABLE,
                                     'modified': STORE.get().row_modified(table, payload.get('id'))}
                    result = {'row': row, 'dirtyCount': STORE.get().dirty_count, **extra}
                elif path == '/api/rename':
                    only = stats_fields(payload.get('sub', ''), payload.get('table'))
                    row = STORE.rename(payload.get('table'), payload.get('id'), payload.get('name'), only=only)
                    result = {'row': row, 'dirtyCount': STORE.get().dirty_count,
                              'modified': STORE.get().row_modified(payload.get('table'), payload.get('id'))}
                elif path == '/api/tae/add':
                    for key in ('table', 'tae', 'anim', 'type', 'start', 'end'):
                        if key not in payload:
                            raise ValueError('An event needs a character, animation, type and timing')
                    row = TAESTORE.add_event(payload['table'], payload['tae'], payload['anim'],
                                             payload['type'], payload['start'], payload['end'],
                                             payload.get('values'))
                    result = {'row': row, 'events': TAESTORE.list_events(
                        payload['table'], payload['tae'], payload['anim'])}
                elif path == '/api/tae/remove':
                    for key in ('table', 'id'):
                        if key not in payload:
                            raise ValueError('An event needs a character and identity')
                    result = {'events': TAESTORE.remove_event(payload['table'], payload['id'])}
                elif path == '/api/assets/upload':
                    if STORE.read_only or STORE.project is None:
                        raise PermissionError('Replacing assets needs a writable mod project')
                    for key in ('id', 'relative', 'total', 'offset', 'data'):
                        if key not in payload:
                            raise ValueError('An upload needs a transfer, target, size, offset and data')
                    try:
                        raw = base64.b64decode(payload['data'], validate=True)
                    except (binascii.Error, ValueError):
                        raise ValueError('That upload piece is not valid data') from None
                    stored = assets.receive_chunk(STORE.project, payload['id'], payload['relative'],
                                                  payload['total'], payload['offset'], raw,
                                                  bool(payload.get('final')))
                    if payload.get('final') and assets.kind_of(payload['relative']) in ("sound", "music"):
                        assets.clear_sound_cache()
                    result = {'upload': stored,
                              'files': assets.scan_merged(STORE.game_root, STORE.project)}
                elif path == '/api/assets/remove':
                    if STORE.read_only or STORE.project is None:
                        raise PermissionError('Replacing assets needs a writable mod project')
                    if 'relative' not in payload:
                        raise ValueError('Removing an override needs its file')
                    if assets.kind_of(payload['relative']) in ("sound", "music"):
                        assets.clear_sound_cache()
                    result = {'removed': assets.remove_override(STORE.project, payload['relative']),
                              'files': assets.scan_merged(STORE.game_root, STORE.project)}
                elif path == '/api/rows/add':
                    for key in ('table', 'id'):
                        if key not in payload:
                            raise ValueError('Duplicating a record needs its table and ID')
                    result = {'row': STORE.add_row(payload['table'], payload['id'], payload.get('newId'))}
                elif path == '/api/rows/remove':
                    for key in ('table', 'id'):
                        if key not in payload:
                            raise ValueError('Removing a record needs its table and ID')
                    result = {'removed': STORE.remove_row(payload['table'], payload['id'])}
                elif path == '/api/placements/add':
                    for key in ('map', 'id'):
                        if key not in payload:
                            raise ValueError('Duplicating a placement needs its map and identity')
                    result = {'row': MAPSTORE.add_placement(payload['map'], payload['id'])}
                elif path == '/api/placements/create':
                    for key in ('map', 'model', 'pos', 'rot'):
                        if key not in payload:
                            raise ValueError('Placing a model needs its map, model, position and rotation')
                    result = {'row': MAPSTORE.create_placement(payload['map'], payload['model'],
                                                               payload['pos'], payload['rot'],
                                                               payload.get('npc'))}
                elif path == '/api/placements/remove':
                    for key in ('map', 'id'):
                        if key not in payload:
                            raise ValueError('Removing a placement needs its map and identity')
                    result = {'removed': MAPSTORE.remove_placement(payload['map'], payload['id'])}
                elif path in ('/api/bands/add', '/api/bands/delete'):
                    action = path.rsplit('/', 1)[-1]
                    allowed = {'id', 'revision', 'at'} if action == 'add' else {'id', 'revision', 'neighbour', 'keep'}
                    if set(payload) != allowed:
                        raise ValueError('Unsupported load-band operation')
                    result = {'row': RULES.band_action(action, payload['id'], revision=payload['revision'],
                              at=payload.get('at'), neighbour=payload.get('neighbour'), keep=payload.get('keep'))}
                elif path == '/api/save':
                    RULES.validate_save()
                    STORE.validate_save()
                    MAPSTORE.validate_save()
                    TAESTORE.validate_save()
                    result = STORE.save()
                    MAPSTORE.save()
                    TAESTORE.save()
                    RULES.save()
                    result.update(_rebuild_tweaks_on_save())
                elif path == '/api/discard':
                    result = STORE.discard()
                    MAPSTORE.discard()
                    TAESTORE.discard()
                    RULES.discard()
                # Tweaks are library mods, not part of the selected project, so
                # they save at once; the rebuild rides on Save, or installs straight
                # away when the session has no writable project.
                elif path == '/api/tweaks/save':
                    tweak_mods.save(payload.get('tweaks'))
                    if STORE.read_only:
                        _deploy_tweaks_now()
                    result = tweak_mods.status(STORE.game_root)
                elif path == '/api/tweaks/restore':
                    result = tweak_mods.restore(STORE.game_root)
                elif path == '/api/tweaks/debug':
                    # Takes effect at the next Save or Play.
                    tweak_mods.set_debug_mode(payload.get('on'))
                    if STORE.read_only:
                        _deploy_tweaks_now()
                    result = tweak_mods.status(STORE.game_root)
                elif path == '/api/deployment/apply':
                    result = RULES.apply(STORE)
                else:
                    result = RULES.restore()
                if not path.startswith('/api/tweaks/'):
                    result['tweaksNeedRebuild'] = _tweaks_flag()
                    result['dirtyCount'] = STORE.get().dirty_count + RULES.dirty_count + MAPSTORE.dirty_count + TAESTORE.dirty_count
                    result['changes'] = STORE.get().pending_changes() + MAPSTORE.pending_changes() + TAESTORE.pending_changes()
                    result['nativeRules'] = RULES.snapshot()
                self.send_json(result)
        except PermissionError as error:
            self.send_json({'error': str(error)}, 403)
        except (FormatError, RuntimeError, ValueError, OSError, KeyError, TypeError) as error:
            self.send_json({'error': str(error)}, 400)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("LEXEDITOR_PORT", "0"))), Handler).serve_forever()
