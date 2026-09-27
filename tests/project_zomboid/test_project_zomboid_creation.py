"""New script records preserve their template and refuse stale/colliding writes."""
import pytest
from plugins.project_zomboid import core, zedscript


@pytest.fixture
def script(tmp_path):
    path=tmp_path/'42/media/scripts/items.txt'
    path.parent.mkdir(parents=True)
    path.write_bytes(b'\xef\xbb\xbfmodule Example\r\n{\r\n  item Original { Weight = 1, /* } */ component X { value = 9, } }\r\n}\r\n')
    return tmp_path,path


def test_copy_preserves_nested_unknown_fields_comments_and_bom(script):
    root,path=script
    before=path.read_bytes()
    row=zedscript.create_copy(root,'42/media/scripts/items.txt','Example','item','Original','Copied',core.sha256_bytes(before))
    assert row['name']=='Copied'
    after=path.read_bytes()
    assert after.startswith(b'\xef\xbb\xbf')
    assert after.count(b'Weight = 1, /* } */ component X { value = 9, }')==2
    assert before[:-3] in after
    assert {r['name'] for r in zedscript.inventory(root)['rows']}=={'Original','Copied'}


@pytest.mark.parametrize('name', ['Original','bad name','New\nitem Injected','../Escape'])
def test_copy_rejects_invalid_names_without_writing(script,name):
    root,path=script
    before=path.read_bytes()
    with pytest.raises(core.ProjectZomboidError):
        zedscript.create_copy(root,'42/media/scripts/items.txt','Example','item','Original',name,core.sha256_bytes(before))
    assert path.read_bytes()==before


def test_copy_refuses_stale_source(script):
    root,path=script
    expected=core.sha256_file(path)
    path.write_bytes(path.read_bytes()+b'// External edit\n')
    before=path.read_bytes()
    with pytest.raises(core.ProjectZomboidError,match='changed outside'):
        zedscript.create_copy(root,'42/media/scripts/items.txt','Example','item','Original','Copied',expected)
    assert path.read_bytes()==before
