"""Bad declarations remain individual rows; saves cannot create unreadable ones."""
import json
from pathlib import Path
import pytest
from core import mod_metadata,mod_library,mods_service


def folder(root,name):
    result=root/name;result.mkdir(parents=True)
    (result/'mod.json').write_text(json.dumps({'id':name,'name':name,'enabled':True}))
    return result


def test_library_metadata_uses_one_coherent_declaration(tmp_path,monkeypatch):
    root=folder(tmp_path,'one')
    read=mod_metadata._stored
    calls=[]
    def changed_after_read(path):
        result=read(path);calls.append(path)
        (path/'mod.json').write_text('{"id":"two","name":"two"}')
        return result
    monkeypatch.setattr(mod_metadata,'_stored',changed_after_read)
    value=mod_library.metadata(root)
    assert len(calls)==1 and value['id']==value['name']=='one'


def test_excessive_metadata_is_only_an_error_row(tmp_path,monkeypatch):
    healthy=folder(tmp_path,'healthy');broken=folder(tmp_path,'broken')
    monkeypatch.setattr(mod_metadata,'MAX_BYTES',128)
    (broken/'mod.json').write_bytes(b' '*129)
    rows={row['folder']:row for row in mods_service.library_rows(tmp_path)}
    assert rows['healthy']['enabled'] and not rows['healthy']['error']
    assert not rows['broken']['enabled'] and 'metadata limit' in rows['broken']['error']
    assert mod_library.metadata(healthy)['enabled']


def test_decoder_recursion_cannot_escape_library_or_standalone_discovery(tmp_path,monkeypatch):
    healthy=folder(tmp_path,'healthy');broken=folder(tmp_path,'broken')
    original=json.loads
    def nested(raw,*args,**kwargs):
        if '"broken"' in raw:
            raise RecursionError('nested declaration')
        return original(raw,*args,**kwargs)
    monkeypatch.setattr(mod_metadata.json,'loads',nested)
    rows={row['folder']:row for row in mods_service.library_rows(tmp_path)}
    assert rows['healthy']['enabled'] and 'nested declaration' in rows['broken']['error']
    from plugins.ds1.standalone_runtime import discover
    assert [row['id'] for row in discover([tmp_path])]==['healthy']


def test_oversized_save_preserves_the_previous_readable_declaration(tmp_path,monkeypatch):
    root=folder(tmp_path,'healthy')
    previous=(root/'mod.json').read_bytes()
    monkeypatch.setattr(mod_metadata,'MAX_BYTES',128)
    with pytest.raises(mod_metadata.MetadataError,match='metadata limit'):
        mod_metadata.write(root,{'name':'healthy','description':'x'*200})
    assert (root/'mod.json').read_bytes()==previous
    assert mod_library.metadata(root)['enabled']
