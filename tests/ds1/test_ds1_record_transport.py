"""Bounded portable record transport, including older uncompressed releases."""
import json

import pytest

from plugins.ds1 import record_edits,texts


def packed_records():
    spec = {'kind':'texts','tables':[{'name':'Fixture_.fmg','memberId':10,'rows':[
        {'id':100,'before':'Old','after':'a'*60000},
        {'id':101,'before':'Old','after':'b'*60000}]}]}
    records = {texts.RELATIVE:spec}
    return records,record_edits.encode(records)


def test_packed_and_older_json_releases_decode_to_the_same_records():
    records,packed = packed_records()
    assert packed.startswith(record_edits.PACKED_MAGIC) and len(packed)<4096
    assert record_edits.decode(packed) == records
    legacy = json.dumps({'version':1,'files':{key.as_posix():value for key,value in records.items()}}).encode()
    assert record_edits.decode(legacy) == records


def test_oversized_declared_output_is_refused_before_decompression(monkeypatch):
    _records,packed = packed_records()
    header = record_edits.PACKED.pack(record_edits.PACKED_MAGIC,record_edits.DECODED_LIMIT+1)
    monkeypatch.setattr(record_edits.zlib,'decompressobj',lambda:pytest.fail('Must reject before decompressing'))
    with pytest.raises(ValueError,match='256 MiB'):
        record_edits.decode(header+packed[record_edits.PACKED.size:])


@pytest.mark.parametrize('damage',['truncated','trailing','checksum','size'])
def test_damaged_packed_records_are_refused(damage):
    _records,packed = packed_records()
    if damage=='truncated':
        packed = packed[:-1]
    elif damage=='trailing':
        packed += b'unexpected trailing bytes'
    elif damage=='checksum':
        packed = packed[:-1]+bytes([packed[-1]^1])
    else:
        packed = record_edits.PACKED.pack(record_edits.PACKED_MAGIC,1)+packed[record_edits.PACKED.size:]
    with pytest.raises(ValueError,match='packed record'):
        record_edits.decode(packed)


def test_non_finite_values_do_not_enter_the_portable_data_model():
    with pytest.raises(ValueError,match='Non-finite'):
        record_edits.decode(b'{"version":1,"files":{},"unexpected":NaN}')
