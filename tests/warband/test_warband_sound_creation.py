"""Sound copies preserve existing IDs, samples and untouched source bytes."""
import hashlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.warband.module_records import create_sound, dataset_data


@pytest.mark.parametrize('ending', ['', ','])
@pytest.mark.parametrize('encoding,newline', [('utf-8','\n'), ('utf-8-sig','\r\n')])
def test_sound_copy_preserves_template_and_original_records(tmp_path, ending, encoding, newline):
    original = ('# custom flags survive\n'
                'sounds=[("click", custom_flags | 2, ["click.ogg", ["alt.wav", sf_vol_8]]),\n'
                ' ("other", 0, ["other.ogg"])' + ending + ']\n# tail\n').replace('\n',newline).encode(encoding)
    source=tmp_path/'module_sounds.py';source.write_bytes(original)
    before=dataset_data(tmp_path,'sounds')
    result=create_sound(tmp_path,before['sha256'],0,'click','custom_click')
    after=dataset_data(tmp_path,'sounds')
    assert [row['id'] for row in after['rows']]==['click','other','custom_click']
    assert after['rows'][-1]['fields']['flags']==before['rows'][0]['fields']['flags']
    assert after['rows'][-1]['audioSamples']==['click.ogg','alt.wav']
    assert after['rows'][:2]==before['rows']
    assert source.read_bytes().endswith((']\n# tail\n').replace('\n',newline).encode('utf-8'))
    assert Path(result['backup']).read_bytes()==original
    assert result['recordIndex']==2
    assert result['sha256']==hashlib.sha256(source.read_bytes()).hexdigest()


@pytest.mark.parametrize('index,old,new,hash_override', [
    (0,'click','click',None), (0,'wrong','new',None),
    (True,'click','new',None), (9,'click','new',None),
    (0,'click','invalid id',None), (0,'click','new','stale')])
def test_sound_copy_rejects_unsafe_requests_without_writing(tmp_path,index,old,new,hash_override):
    source=tmp_path/'module_sounds.py'
    raw=b'sounds=[("click",0,["click.ogg"])]\n';source.write_bytes(raw)
    with pytest.raises(ValueError):
        create_sound(tmp_path,hash_override or hashlib.sha256(raw).hexdigest(),index,old,new)
    assert source.read_bytes()==raw
    assert not source.with_name(source.name+'.lexeditor.bak').exists()
