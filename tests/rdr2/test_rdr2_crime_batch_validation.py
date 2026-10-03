"""Crime batches preserve source, cache and backups until every edit validates."""
import copy
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from plugins.rdr2 import server as s
from test_rdr2_catalog_numeric_validation import fixture, snapshot

FIRST={'key':'FIRST','field':'CrimeValue','value':'9007199254740993'}
BAD=[None,{},False,'',[None],[{}],[dict(FIRST,opaque=1)],
     [dict(FIRST,key=[])],[dict(FIRST,key='UNKNOWN')],[dict(FIRST,field=[])],
     [dict(FIRST,field='Unknown')],[FIRST,FIRST]]
for field in s.CRIME_CI_FIELDS+s.CRIME_WIT_FIELDS+['ConfrontChance']:
    values=[None,[],{},'']
    if field=='Disabled':values += [1,0,'TRUE','unknown']
    else:
        values += [True,-1,float('nan'),float('inf')]
        if field in s.CRIME_INTEGER_FIELDS:values += [1.5,'1.5']
    BAD += [[{'key':'SECOND','field':field,'value':value}] for value in values]
BAD += [[{'key':'SECOND','field':'severity','value':v}] for v in [None,True,1,[],{},'','UNKNOWN']]


@pytest.fixture
def crimes(fixture):
    root,_=fixture
    fields=''.join(f'<{field} value="'+('false' if field=='Disabled' else '0')+'"/>' for field in s.CRIME_CI_FIELDS)
    witness=''.join(f'<{field} value="2"/>' for field in s.CRIME_WIT_FIELDS)
    info=f'<CrimeInformation>{fields}<Severity>Low</Severity><WitnessInformation>{witness}</WitnessInformation><Confrontation><Chances value="0.2"/></Confrontation><Opaque value="keep"/></CrimeInformation>'
    record=lambda key:f'<Item key="{key}"><Variations><Item><FilterFlags>NET</FilterFlags>{info}</Item><Item><FilterFlags>SP</FilterFlags>{info}</Item></Variations></Item>'
    path=s.data_file_path(s.CRIME_FILE,'mine');path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('<Root><!--keep--><CrimeInformations>'+record('FIRST')+record('SECOND')+'</CrimeInformations></Root>')
    s.load_file(s.CRIME_FILE)
    return root,path


@pytest.mark.parametrize('bad',BAD)
@pytest.mark.parametrize('backup',[False,True])
def test_invalid_later_edit_does_not_change_cache_files_or_backup(crimes,bad,backup):
    root,path=crimes
    if backup:path.with_suffix('.meta.bak').write_bytes(b'first backup')
    before=snapshot(root);cached=s.load_file(s.CRIME_FILE)['root']
    with pytest.raises(ValueError):s.apply_crime_edits([FIRST,*bad] if isinstance(bad,list) else bad)
    assert snapshot(root)==before
    assert s.load_file(s.CRIME_FILE)['root'] is cached


def test_http_rejects_then_all_fields_save_reload_with_other_variation_intact(crimes):
    root,path=crimes
    cached=s.load_file(s.CRIME_FILE)['root']
    net_before=copy.deepcopy(cached.find('./CrimeInformations/Item/Variations/Item'))
    http=s.create_server(0);worker=threading.Thread(target=http.serve_forever,daemon=True);worker.start()
    def post(edits):return Request(f'http://127.0.0.1:{http.server_port}/api/crime/save',data=json.dumps({'edits':edits}).encode(),headers={'Content-Type':'application/json'})
    try:
        before=snapshot(root)
        with pytest.raises(HTTPError) as error:urlopen(post([FIRST,{'key':'SECOND','field':'severity','value':'UNKNOWN'}]))
        assert error.value.code==400;assert snapshot(root)==before
        edits=[FIRST,{'key':'FIRST','field':'severity','value':'High'}]
        for field in s.CRIME_CI_FIELDS+s.CRIME_WIT_FIELDS+['ConfrontChance']:
            if field=='CrimeValue':continue
            edits.append({'key':'FIRST','field':field,'value':True if field=='Disabled' else '3' if field in s.CRIME_INTEGER_FIELDS else '0.123456789'})
        assert json.load(urlopen(post(edits)))['saved']==len(edits)
        s._files.clear();row=s.get_crime()['crimes'][0]
        assert row['CrimeValue']=='9007199254740993'
        assert row['severity']=='High';assert row['Disabled']=='true'
        assert row['ConfrontChance']=='0.123456789'
        import xml.etree.ElementTree as ET
        assert ET.tostring(s.load_file(s.CRIME_FILE)['root'].find('./CrimeInformations/Item/Variations/Item'))==ET.tostring(net_before)
        assert b'<!--keep-->' in path.read_bytes()
        assert s.load_file(s.CRIME_FILE)['root'].find('.//Opaque').get('value')=='keep'
    finally:http.shutdown();http.server_close();worker.join()


@pytest.mark.parametrize('kind',['no-sp','not-sp','duplicate-flags','duplicate-sp','duplicate-id','duplicate-field','missing-field','unknown-source'])
def test_unsupported_source_is_not_mutated(crimes,kind):
    root,_=crimes;doc=s.load_file(s.CRIME_FILE)['root'];record=doc.find('./CrimeInformations/Item')
    variation=s._sp_variation(record);node=variation.find('CrimeInformation/CrimeValue')
    if kind=='no-sp':variation.find('FilterFlags').text='NET'
    elif kind=='not-sp':variation.find('FilterFlags').text='NOT_SP'
    elif kind=='duplicate-flags':variation.append(copy.deepcopy(variation.find('FilterFlags')))
    elif kind=='duplicate-sp':record.find('Variations').append(copy.deepcopy(variation))
    elif kind=='duplicate-id':doc.find('CrimeInformations').append(copy.deepcopy(record))
    elif kind=='duplicate-field':variation.find('CrimeInformation').append(copy.deepcopy(node))
    elif kind=='missing-field':variation.find('CrimeInformation').remove(node)
    else:node.set('value','NaN')
    s.save_file(s.CRIME_FILE);before=snapshot(root)
    with pytest.raises(ValueError):s.apply_crime_edits([{'key':'SECOND','field':'severity','value':'Medium'},FIRST])
    assert snapshot(root)==before


@pytest.mark.parametrize('backup,fail_at',[(False,1),(False,2),(True,1)])
def test_failed_replacement_retains_source_cache_and_existing_backup(crimes,monkeypatch,backup,fail_at):
    root,path=crimes
    if backup:path.with_suffix('.meta.bak').write_bytes(b'first backup')
    before=snapshot(root);cached=s.load_file(s.CRIME_FILE)['root'];replace=s.os.replace;count=0
    def fail(src,dst):
        nonlocal count
        count+=1
        if count==fail_at:raise OSError('injected failure')
        return replace(src,dst)
    monkeypatch.setattr(s.os,'replace',fail)
    with pytest.raises(OSError):s.apply_crime_edits([FIRST])
    assert snapshot(root)==before;assert s.load_file(s.CRIME_FILE)['root'] is cached


def test_readonly_and_empty_batch(crimes):
    root,_=crimes;before=snapshot(root);s.DATASETS['mine']['readonly']=True
    assert s.apply_crime_edits([])==0
    with pytest.raises(ValueError,match='read-only'):s.apply_crime_edits([FIRST])
    assert snapshot(root)==before
