"""Coverage of the selected DS1 archives, derived from the existing editors."""
from .formats import SUBTABS, EFFECT_TABLE, GRAPH_TABLE
from . import assets, texts

TAB_LABELS = {'items':'Items', 'enemies':'Enemies', 'ai':'AI', 'attacks':'Attacks', 'effects':'Effects',
              'stats':'Stats', 'misc':'Misc.',
              'maps':'Maps', 'animations':'Animations', 'text':'Text',
              'npcs':'NPCs',
              'models':'Models', 'textures':'Textures', 'sound':'Sound effects',
              'music':'Music'}


# Asset folders open on the file tab that holds their kind. msg/ holds the
# message archives the Text tab edits; font/ textures list with the
# textures and cutscene binders list with the models. Folders with no
# tab keep an unavailable row below instead of a target.
ASSET_TARGETS = {'chr': ('models', 'files'),
                 'facegen': ('models', 'files'), 'font': ('textures', 'files'),
                 'map': ('models', 'files'), 'menu': ('textures', 'files'),
                 'msg': ('text', 'menu-labels'),
                 'obj': ('models', 'files'),
                 'parts': ('models', 'files'),
                 'remo': ('models', 'files'),
                 'sound': ('sound', 'files')}
# Folders whose files no tab lists: movies, scripts and the like have no
# browser, but Apply still installs files a mod carries there.
UNTARGETED_ASSETS = {'event': 'event scripts', 'movww': 'movies',
                     'mtd': 'material data', 'other': 'these files',
                     'script': 'scripts', 'sfx': 'visual effects',
                     'shader': 'shaders'}


def payload(store, native_rules=None, theme=None):
    document = store.get()
    item_tables = {}
    for sub, label, table in SUBTABS:
        item_tables.setdefault(table, []).append((sub, label))
    rows = []
    for filename in sorted(document.members):
        table = filename.removesuffix('.param')
        row = {'id':f'param:{filename}', 'filename':filename, 'path':str(store.source),
               'coverage':'unavailable', 'status':'not-integrated', 'openable':False,
               'controls':'No editor', 'notes':'This table has no editor. Its original bytes are preserved when the archive is saved.'}
        if table in item_tables:
            tabs = item_tables[table]
            notes = 'Edit the reviewed properties in Items. Unidentified fields stay read-only.'
            if table == 'EquipParamWeapon':
                notes = ('Edit the reviewed properties in Items. Upgrade path, materials, reinforcement '
                         'cost and ascension live under the Upgrades tab. Unidentified fields stay read-only.')
            elif table == 'EquipParamProtector':
                notes = ('Edit the reviewed properties in Items. Upgrade path, materials and reinforcement '
                         'cost live under the Upgrades tab. Unidentified fields stay read-only.')
            row.update(coverage='structured',status='partial',openable=True,
                target='items',sub=tabs[0][0],controls='Items: '+', '.join(label for _,label in tabs),
                notes=notes)
        elif table == 'NpcParam':
            row.update(coverage='structured',status='partial',openable=True,
                target='enemies',sub='monsters',controls='Enemies: stats, drops, effects and attack references',
                notes='Edit reviewed monster stats and follow their attack references. Friendly characters live under NPCs. Other properties stay read-only.')
        elif table == 'BehaviorParam':
            row.update(coverage='structured',status='partial',openable=True,
                target='ai',sub='behaviors',controls='AI: behavior costs and call targets',
                notes='Edit what behaviors cost and which attack, projectile or effect they call.')
        elif table == 'Bullet':
            row.update(coverage='structured',status='partial',openable=True,
                target='attacks',sub='projectiles',controls='Attacks: projectile flight and damage',
                notes='Edit how projectiles fly, what they hit with, and which attack they deal.')
        elif table == 'NpcThinkParam':
            row.update(coverage='structured',status='partial',openable=True,
                target='ai',sub='ai',controls='AI: senses, distances and goals',
                notes='Edit how enemies sense, approach and answer the player.')
        elif table == 'AtkParam_Npc':
            row.update(coverage='structured',status='partial',openable=True,
                target='attacks',sub='attacks',controls='Attacks: enemy attack damage and hitboxes',
                notes='Edit reviewed damage and hitbox properties. An attack may be shared by several enemies.')
        elif table == 'AtkParam_Pc':
            row.update(coverage='structured',status='partial',openable=True,
                target='attacks',sub='player-attacks',controls='Attacks: player attack damage and hitboxes',
                notes='Edit reviewed damage and hitbox properties. An attack may be shared by several player moves.')
        elif table == 'ReinforceParamWeapon':
            row.update(coverage='structured',status='integrated',openable=True,
                target='stats',sub='weapon-upgrades',controls='Stats: weapon upgrade multipliers',
                notes='Edit every weapon upgrade level, from Normal +0 to the special paths.')
        elif table == 'ReinforceParamProtector':
            row.update(coverage='structured',status='integrated',openable=True,
                target='stats',sub='armor-upgrades',controls='Stats: armor upgrade multipliers',
                notes='Edit every armor upgrade level.')
        elif table == 'EquipMtrlSetParam':
            row.update(coverage='structured',status='integrated',openable=True,
                target='stats',sub='upgrade-materials',controls='Stats: upgrade material sets',
                notes='Edit the items each upgrade level spends, and how many of each.')
        elif table == 'CharaInitParam':
            row.update(coverage='structured',status='partial',openable=True,
                target='stats',sub='starting-classes',controls='Stats: starting classes and gifts',
                notes='Edit starting classes and what each starting gift grants. Other rows in this table stay read-only.')
        elif table == 'ItemLotParam':
            row.update(coverage='structured',status='integrated',openable=True,
                target='maps',sub='drops',controls='Maps: enemy and corpse drops',
                notes='Edit dropped items and their rates in the directory. One lot may be shared by several enemies.')
        elif table == 'ShopLineupParam':
            row.update(coverage='structured',status='integrated',openable=True,
                target='npcs',sub='npcs',controls='NPCs: merchant stock and prices',
                notes="Edit what each merchant sells, and at what price, on their NPC page under the Shop tab. Lines no merchant serves list under the Unowned shops subtab.")
        elif table == 'ObjActParam':
            row.update(coverage='structured',status='integrated',openable=True,
                target='maps',sub='treasure',controls='Maps: treasure and pickup behavior',
                notes='Edit how treasure chests and pickups behave in the directory.')
        elif table == EFFECT_TABLE:
            editable = [f for f in document.schemas.get(table, {}).get('fields', []) if f['editable']]
            row.update(coverage='structured',status='partial',openable=True,
                target='effects',sub='effects-all',controls='Effects: buffs, debuffs and equipment passives',
                notes=f'{len(editable)} documented properties are editable. Other properties and unknown bytes are preserved.')
        elif table == GRAPH_TABLE:
            editable = [f for f in document.schemas[table]['fields'] if f['editable']]
            row.update(coverage='structured',status='integrated',openable=True,
                target='stats',sub='curves',controls='Stats: weapon, level-up and resistance scaling curves',
                notes=f'{len(editable)} curve properties are editable. The multiplayer level-sync rows keep the game\'s own reference names.')
        rows.append(row)
    if EFFECT_TABLE not in document.params:
        rows.append({'id':'effects-missing', 'filename':EFFECT_TABLE + '.param', 'path':str(store.source),
            'coverage':'unavailable', 'status':'not-integrated', 'openable':False,
            'controls':'Effects: buffs, debuffs and equipment passives',
            'notes':'Open a complete Remastered parameter archive to edit effects.'})
    if GRAPH_TABLE not in document.params:
        rows.append({'id':'curves-missing', 'filename':GRAPH_TABLE + '.param', 'path':str(store.source),
            'coverage':'unavailable', 'status':'not-integrated', 'openable':False,
            'controls':'Stats: weapon, level-up and resistance scaling curves',
            'notes':'Open a complete Remastered parameter archive to edit scaling curves.'})
    for table, filename in texts.NAME_TABLES.items():
        tabs = item_tables[table]
        available = document.texts is not None and document.texts.renamable(table)
        rows.append({'id':f'name:{table}', 'filename':filename,
            'path':str(store.text_source or store.game_root/texts.RELATIVE),
            'coverage':'structured' if available else 'unavailable',
            'status':'partial' if available else 'not-integrated', 'openable':available,
            'target':'items' if available else '', 'sub':tabs[0][0],
            'controls':'Items: '+', '.join(label for _,label in tabs),
            'notes':'Rename items through their detail headings. NPC, place and feature text has no editor.' if available
                    else 'The item-text archive is missing. Item names cannot be renamed.'})
    for table, files in texts.DESC_TABLES.items():
        tabs = item_tables[table]
        available = document.texts is not None and document.texts.describable(table)
        for role, filename in (('description', files[0]), ('full description', files[1])):
            rows.append({'id':f'desc:{table}:{role}', 'filename':filename,
                'path':str(store.text_source or store.game_root/texts.RELATIVE),
                'coverage':'structured' if available else 'unavailable',
                'status':'integrated' if available else 'not-integrated', 'openable':available,
                'target':'items' if available else '', 'sub':tabs[0][0],
                'controls':'Items: '+', '.join(label for _,label in tabs),
                'notes':f'Edit the {role} in the Description section of each item.' if available
                        else 'The item-text archive is missing. Item descriptions cannot be edited.'})
    menu_available = document.menu_texts is not None
    rows.append({'id': 'menu:labels', 'filename': texts.MENU_LABEL_FILE,
        'path': str(store.menu_source or store.game_root/texts.MENU_RELATIVE),
        'coverage': 'structured' if menu_available else 'unavailable',
        'status': 'integrated' if menu_available else 'not-integrated', 'openable': menu_available,
        'target': 'text' if menu_available else '', 'sub': 'menu-labels',
        'controls': 'Text: Menu labels',
        'notes': 'Edit the equipment defense labels.' if menu_available
                else 'The menu-text archive is missing. Menu labels cannot be edited.'})
    if menu_available:
        from .formats import FMG_SUBTABS
        present = set(document.menu_texts.files())
        for tab_id, label, filename in FMG_SUBTABS:
            have = filename in present
            rows.append({'id': f'menu:{tab_id}', 'filename': filename,
                'path': str(store.menu_source or store.game_root/texts.MENU_RELATIVE),
                'coverage': 'structured' if have else 'unavailable',
                'status': 'integrated' if have else 'not-integrated', 'openable': have,
                'target': 'text' if have else '', 'sub': tab_id,
                'controls': f'Text: {label}',
                'notes': f'Edit every {label.lower()} line.' if have
                        else f'The menu archive has no {filename}.'})
    if document.texts is not None:
        known = set(texts.NAME_TABLES.values()) | {filename for pair in texts.DESC_TABLES.values() for filename in pair}
        extra = {entry.name.replace('\\','/').rsplit('/',1)[-1] for entry in document.texts.entries} - known
        for filename in sorted(extra):
            rows.append({'id':f'message:{filename}', 'filename':filename, 'path':str(store.text_source),
                'coverage':'unavailable','status':'not-integrated','openable':False,
                'controls':'No editor', 'notes':'This message table has no editor. Its original bytes are preserved when item text is saved.'})
    # Values the game keeps in its executable, changed by Lexeditor's native rules.
    available = bool(native_rules and native_rules['native']['available'])
    for key, target, label in (('misc', 'misc', 'Misc.: base stamina regeneration'),
                              ('encumbrance', 'misc', 'Misc.: load bands, movement profiles and stamina recovery'),
                              ('levelup', 'stats', 'Stats: level-up defense gains')):
        rows.append({'id':'native-' + key, 'filename':'DarkSoulsRemastered.exe', 'path':str(store.game_root / 'DarkSoulsRemastered.exe'),
            'coverage':'structured', 'status':'partial', 'openable':available,
            'target':target if available else '', 'sub':key, 'controls':label,
            'notes':'Save and Apply with the game closed. Only the fingerprinted build is supported.'
                    if available else 'The installed executable is not the supported build, so these rules cannot be applied.'})
    # Area data beyond the parameter archive. Maps open the Maps tab;
    # characters open the Animations tab.
    map_path = store.game_root / 'map'
    if map_path.is_dir():
        rows.append({'id': 'area:maps', 'filename': 'map/', 'path': str(map_path),
            'coverage': 'structured', 'status': 'partial', 'openable': True,
            'target': 'maps', 'sub': 'placements', 'controls': 'Maps: enemy placements',
            'notes': 'Move placements and swap which enemy appears. Anything else in the map is left untouched.'})
    chr_path = store.game_root / 'chr'
    if chr_path.is_dir():
        rows.append({'id': 'area:characters', 'filename': 'chr/', 'path': str(chr_path),
            'coverage': 'structured', 'status': 'partial', 'openable': True,
            'target': 'animations', 'sub': 'animations', 'controls': 'Animations: event timing, settings, adding and removing',
            'notes': 'Retime animation events, change their settings, and add or remove documented events. The 3D models themselves stay untouched.'})
    # Whole-file asset overrides: every data folder outside the structured editors.
    # Weapon and armor models also preview in their Items drawers, so parts/ says so.
    # Folders with no tab keep an unavailable row: their files have no
    # browser, but Apply still installs files a mod carries there.
    for top in assets.ASSET_ROOTS:
        folder = store.game_root / top
        if not folder.is_dir():
            continue
        if top not in ASSET_TARGETS:
            rows.append({'id': 'assets:' + top, 'filename': top + '/', 'path': str(folder),
                'coverage': 'unavailable', 'status': 'not-integrated', 'openable': False,
                'controls': 'No editor',
                'notes': f'No browser shows {UNTARGETED_ASSETS[top]}. Apply still installs files the mod carries here.'})
            continue
        controls = 'Assets: whole-file replacement with previews'
        notes = 'Add game files to the mod to replace them. Models and textures preview; sounds replace without one. Files owned by another editor change there instead.'
        if top == 'parts':
            controls = 'Assets: whole-file replacement; models preview in Items'
            notes = ('Add game files to the mod to replace them. Models and textures preview; weapon and armor models also preview '
                     'in their Items detail. Files owned by another editor change there instead.')
        rows.append({'id': 'assets:' + top, 'filename': top + '/', 'path': str(folder),
            'coverage': 'structured', 'status': 'partial', 'openable': True,
            'target': ASSET_TARGETS[top][0], 'sub': ASSET_TARGETS[top][1],
            'controls': controls, 'notes': notes})
    # The cosmetic theme, drawn from the installed game into a private cache.
    parts = []
    if isinstance(theme, dict):
        if theme.get('title', {}).get('ready'):
            parts.append('title art active')
        if theme.get('font', {}).get('recognized'):
            parts.append(f"{theme['font']['recognized']} font source(s) recognized")
        if theme.get('sfx', {}).get('recognizedBanks'):
            parts.append(f"{theme['sfx']['recognizedBanks']} sound bank(s) recognized")
    rows.append({'id': 'theme:installed-game',
        'filename': 'menu/ + font/ + sound/ (theme)',
        'path': str(store.game_root) if store.game_root else '',
        'coverage': 'game-derived-theme', 'openable': False,
        'controls': 'Private installed-game theme cache',
        'notes': '; '.join(parts) or 'Theme extraction falls back safely when cosmetic source assets are unavailable.',
        'status': 'partial' if isinstance(theme, dict) and theme.get('source') == 'installed-game' else 'not-integrated'})
    # The Data Map names its open buttons from these labels ("Open Effects").
    for row in rows:
        if row.get('target'):
            # A missing label falls back to the tab id: one row must never 400 the map.
            row['targets'] = [{'id':row['target'],
                               'label':TAB_LABELS.get(row['target'], row['target'].title())}]
    return {'rows':rows}
