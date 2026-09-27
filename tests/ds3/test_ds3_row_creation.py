"""PARAM row copies preserve every byte of existing records and names."""
import struct
import pytest

from plugins.ds3.formats import ParamView, DS3FormatError, TARGET_TABLES, load_schema, RegulationDocument
from test_ds3_plugin import _param, _bnd4, _installed_regulation, METADATA


@pytest.mark.parametrize('table', TARGET_TABLES)
def test_param_copy_retains_payloads_and_names(table):
    schema=load_schema(METADATA,table)
    data=bytearray(_param(table))
    original=ParamView(bytes(data))
    for index,row in enumerate(original.rows):
        data[row.data_offset:row.data_offset+schema.row_size]=bytes([index+41])*schema.row_size
    struct.pack_into('<I',data,0x30+8,len(data))
    data.extend(b'Original name\0opaque trailing bytes')
    original=ParamView(bytes(data))
    new_id=max(row.row_id for row in original.rows)+1
    result=original.copy_row(original.rows[0].row_id,new_id,'Copied row',schema.row_size)
    copied=ParamView(result)
    assert len(copied.rows)==len(original.rows)+1
    assert copied.row(new_id).name=='Copied row'
    assert copied.rows[0].name=='Original name'
    assert b'opaque trailing bytes' in result
    for row in original.rows:
        current=copied.row(row.row_id)
        assert result[current.data_offset:current.data_offset+schema.row_size]==data[row.data_offset:row.data_offset+schema.row_size]
    new=copied.row(new_id)
    assert result[new.data_offset:new.data_offset+schema.row_size]==bytes([41])*schema.row_size
    with pytest.raises(DS3FormatError,match='already exists'):
        copied.copy_row(new_id,new_id,'Duplicate',schema.row_size)


def test_param_copy_rejects_overlapping_data_and_invalid_identity():
    data=_param('Magic');param=ParamView(data);source=param.rows[0].row_id
    with pytest.raises(DS3FormatError,match='32-bit'):
        param.copy_row(source,2**31,'Too large',4)
    with pytest.raises(DS3FormatError,match='name'):
        param.copy_row(source,123456,'Bad\0name',4)
    with pytest.raises(DS3FormatError,match='overlaps'):
        param.copy_row(source,123456,'Too big',len(data))


@pytest.mark.parametrize('endian', ['<','>'])
def test_long_offset_unicode_rows_preserve_unknown_directory_words(endian):
    encoding='utf-16-le' if endian=='<' else 'utf-16-be'
    data=bytearray(128)
    struct.pack_into(endian+'I',data,0,128)
    struct.pack_into(endian+'H',data,10,2)
    data[12:16]=b'TEST'
    data[44]=0 if endian=='<' else 255
    data[45:47]=bytes([4,1])
    struct.pack_into(endian+'q',data,48,112)
    struct.pack_into(endian+'iiqq',data,64,10,0x1234,112,128)
    struct.pack_into(endian+'iiqq',data,88,20,0x5678,120,0)
    data[112:128]=b'ABCDEFGHabcdefgh'
    data.extend('Original\0'.encode(encoding))
    original=ParamView(bytes(data))
    result=original.copy_row(10,30,'Copied Ω',8)
    parsed=ParamView(result)
    assert parsed.row(30).name=='Copied Ω'
    assert parsed.row(10).name=='Original'
    assert result[parsed.row(30).data_offset:parsed.row(30).data_offset+8]==b'ABCDEFGH'
    assert struct.unpack_from(endian+'i',result,68)[0]==0x1234
    assert struct.unpack_from(endian+'i',result,92)[0]==0x5678


def test_regulation_creation_preserves_other_members_and_survives_export():
    document=RegulationDocument(_bnd4(),METADATA)
    original={name:document.binder.member_bytes(entry) for name,entry in document.entries.items()}
    for table in ('Magic','EquipParamWeapon'):
        source=document.params[table].rows[0].row_id
        new_id=max(row.row_id for row in document.params[table].rows)+1
        document.create_row(table,source,new_id,'Copied '+table)
        field=next(f for f in document.read_row(table,new_id)['fields']
                   if f['type']=='number' and f['minimum'] <= 0 and f['maximum'] >= 1)
        document.edit(table,new_id,field['key'],1)
        document.edit(table,new_id,field['key'],0)
        # Editing an existing row after relocation compares its original ID,
        # not an offset that belonged to the smaller archive.
        document.edit(table,source,field['key'],1)
        document.edit(table,source,field['key'],0)
    assert document.dirty_count==2
    for table in set(TARGET_TABLES)-{'Magic','EquipParamWeapon'}:
        assert document.binder.member_bytes(document.entries[table])==original[table]
    reloaded=RegulationDocument(document.export(),METADATA)
    for table in ('Magic','EquipParamWeapon'):
        assert len(reloaded.params[table].rows)==3
        assert reloaded.params[table].rows[-1].name=='Copied '+table
    assert reloaded.dirty_count==0
    reloaded.identify_created_rows(_bnd4())
    assert sum(row['created'] for table in TARGET_TABLES for row in reloaded.list_rows(table))==2
    assert reloaded.dirty_count==0


def test_installed_regulation_creation_is_memory_only_and_preserves_members():
    source=_installed_regulation()
    if source is None:
        pytest.skip('Installed DS3 regulation is unavailable; synthetic coverage still runs')
    original_bytes=source.read_bytes()
    document=RegulationDocument(original_bytes,METADATA)
    original={entry.index:document.binder.member_bytes(entry) for entry in document.binder.entries}
    table='Magic';entry_index=document.entries[table].index
    rows=document.params[table].rows
    new_id=max(row.row_id for row in rows)+1
    document.create_row(table,rows[0].row_id,new_id,'Lexeditor test copy')
    reloaded=RegulationDocument(document.export(),METADATA)
    assert reloaded.params[table].row(new_id).name=='Lexeditor test copy'
    for entry in reloaded.binder.entries:
        if entry.index!=entry_index:
            assert reloaded.binder.member_bytes(entry)==original[entry.index]
    assert source.read_bytes()==original_bytes


def test_project_save_keeps_created_marker_after_reload(tmp_path,monkeypatch):
    from plugins.ds3 import server
    original=_bnd4()
    source=tmp_path/'source.bdt';source.write_bytes(original)
    project=tmp_path/'project';project.mkdir()
    (project/server.PROJECT_MARKER).write_text('{}')
    for key,value in {'PROJECT':project,'GAME_ROOT':tmp_path/'game','SOURCE_OVERRIDE':str(source),
                      '_DOCUMENT':None,'_SOURCE_PATH':None,'_SOURCE_HASH':None,'_OUTPUT_HASH_AT_LOAD':None}.items():
        monkeypatch.setattr(server,key,value)
    document=server._reload()
    source_id=document.params['Magic'].rows[0].row_id
    new_id=max(row.row_id for row in document.params['Magic'].rows)+1
    document.create_row('Magic',source_id,new_id,'Saved copy')
    assert server._save()['saved'] is True
    rows=server._reload().list_rows('Magic')
    assert next(row for row in rows if row['id']==new_id)['created'] is True
    assert next(row for row in rows if row['id']==source_id)['created'] is False
    assert source.read_bytes()==original
    # An unavailable/unsupported baseline cannot invalidate the saved project.
    source.write_bytes(b'unsupported source')
    reloaded=server._reload()
    assert reloaded.read_row('Magic',new_id)['name']=='Saved copy'
    assert not any(row['created'] for row in reloaded.list_rows('Magic'))
