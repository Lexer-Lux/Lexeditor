"""PARAM row copies preserve every byte of existing records and names."""
import struct
import pytest

from plugins.ds3.formats import ParamView, DS3FormatError, TARGET_TABLES, load_schema
from test_ds3_plugin import _param, METADATA


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
