"""Coverage of the selected DS1 archives, derived from the existing editors."""
from .formats import SUBTABS
from . import texts


def payload(store):
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
        elif table in ('BehaviorParam','Bullet'):
            row.update(coverage='view',status='partial',openable=True,
                target='enemies',sub='monsters',controls='Enemies: attack reference paths',
                notes='These records connect enemies to their attacks. The Enemies view shows those paths; it does not edit these tables.')
        rows.append(row)
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
    return {'rows':rows}
