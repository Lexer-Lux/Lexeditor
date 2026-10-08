"""Coverage of the selected DS1 archives, derived from the existing editors."""
from .formats import SUBTABS, EFFECT_TABLE
from . import texts

TAB_LABELS = {'items':'Items', 'enemies':'Enemies', 'attacks':'Attacks', 'effects':'Effects',
              'misc':'Misc.', 'encumbrance':'Encumbrance'}


def payload(store, native_rules=None):
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
            row.update(coverage='structured',status='partial',openable=True,
                target='items',sub=tabs[0][0],controls='Items: '+', '.join(label for _,label in tabs),
                notes='Edit the reviewed properties in Items. Unidentified fields stay read-only.')
        elif table == 'NpcParam':
            row.update(coverage='structured',status='partial',openable=True,
                target='enemies',sub='monsters',controls='Enemies: resistances and attack references',
                notes='Edit reviewed monster resistances and follow their attack references. Other properties stay read-only.')
        elif table == 'AtkParam_Npc':
            row.update(coverage='structured',status='partial',openable=True,
                target='attacks',sub='attacks',controls='Attacks: enemy attack damage',
                notes='Edit reviewed attack properties. An attack may be shared by several enemies.')
        elif table == EFFECT_TABLE:
            editable = [f for f in document.schemas.get(table, {}).get('fields', []) if f['editable']]
            row.update(coverage='structured',status='partial',openable=True,
                target='effects',sub='effects-all',controls='Effects: buffs, debuffs and equipment passives',
                notes=f'{len(editable)} documented properties are editable. Other properties and unknown bytes are preserved.')
        elif table in ('BehaviorParam','Bullet'):
            row.update(coverage='view',status='partial',openable=True,
                target='enemies',sub='monsters',controls='Enemies: attack reference paths',
                notes='These records connect enemies to their attacks. The Enemies view shows those paths; it does not edit these tables.')
        rows.append(row)
    if EFFECT_TABLE not in document.params:
        rows.append({'id':'effects-missing', 'filename':EFFECT_TABLE + '.param', 'path':str(store.source),
            'coverage':'unavailable', 'status':'not-integrated', 'openable':False,
            'controls':'Effects: buffs, debuffs and equipment passives',
            'notes':'Open a complete Remastered parameter archive to edit effects.'})
    for table, filename in texts.NAME_TABLES.items():
        tabs = item_tables[table]
        available = document.texts is not None and document.texts.renamable(table)
        rows.append({'id':f'name:{table}', 'filename':filename,
            'path':str(store.text_source or store.game_root/texts.RELATIVE),
            'coverage':'structured' if available else 'unavailable',
            'status':'partial' if available else 'not-integrated', 'openable':available,
            'target':'items' if available else '', 'sub':tabs[0][0],
            'controls':'Items: '+', '.join(label for _,label in tabs),
            'notes':'Rename items through their detail headings. Other message text has no editor.' if available
                    else 'The item-name archive is missing. Item names cannot be renamed.'})
    if document.texts is not None:
        extra = {entry.name.replace('\\','/').rsplit('/',1)[-1] for entry in document.texts.entries} - set(texts.NAME_TABLES.values())
        for filename in sorted(extra):
            rows.append({'id':f'message:{filename}', 'filename':filename, 'path':str(store.text_source),
                'coverage':'unavailable','status':'not-integrated','openable':False,
                'controls':'No editor', 'notes':'This message table has no editor. Its original bytes are preserved when item names are saved.'})
    # Values the game keeps in its executable, changed by Lexeditor's native rules.
    available = bool(native_rules and native_rules['native']['available'])
    for key, label in (('misc', 'Misc.: base stamina regeneration'),
                       ('encumbrance', 'Encumbrance: load bands, movement profiles and stamina recovery')):
        rows.append({'id':'native-' + key, 'filename':'DarkSoulsRemastered.exe', 'path':str(store.game_root / 'DarkSoulsRemastered.exe'),
            'coverage':'structured', 'status':'partial', 'openable':available,
            'target':key if available else '', 'sub':key, 'controls':label,
            'notes':'Save and Apply with the game closed. Only the fingerprinted build is supported.'
                    if available else 'The installed executable is not the supported build, so these rules cannot be applied.'})
    # The Data Map names its open buttons from these labels ("Open Effects").
    for row in rows:
        if row.get('target'):
            row['targets'] = [{'id':row['target'], 'label':TAB_LABELS[row['target']]}]
    return {'rows':rows}
