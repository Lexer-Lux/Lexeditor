"""Moving a standalone folder between game/library volumes loses no inputs."""
import errno
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

from core import standalone_mods


@pytest.fixture
def move(tmp_path,monkeypatch):
    source=tmp_path/'game/mods/example'
    source.mkdir(parents=True)
    (source/'mod.json').write_text(json.dumps({'id':'example','name':'Example','enabled':True}))
    (source/'runtime.lxd').write_bytes(b'prebuilt module')
    (source/'nested').mkdir()
    (source/'nested/data.bin').write_bytes(b'unchanged payload')
    library=tmp_path/'Documents/Mods/ds1'
    rename=Path.rename
    def cross_volume(path,target):
        if path==source:
            raise OSError(errno.EXDEV,'different volumes')
        return rename(path,target)
    monkeypatch.setattr(Path,'rename',cross_volume)
    return source,library,[{'path':str(source)}]


def test_cross_volume_move_keeps_one_complete_copy(move):
    source,library,candidates=move
    expected={path.relative_to(source):path.read_bytes() for path in source.rglob('*') if path.is_file()}
    target=standalone_mods.adopt(source,library,candidates)
    assert not source.exists()
    assert {path.relative_to(target):path.read_bytes() for path in target.rglob('*') if path.is_file()}==expected
    assert list(library.iterdir())==[target]


@pytest.mark.parametrize('failure',['corrupt-copy','source-changed','no-space'])
def test_failed_cross_volume_move_keeps_source_and_never_publishes_partial_copy(move,monkeypatch,failure):
    source,library,candidates=move
    if failure=='no-space':
        monkeypatch.setattr(standalone_mods.shutil,'disk_usage',lambda _:SimpleNamespace(free=0))
    else:
        copy=standalone_mods.shutil.copy2
        def modified(before,after):
            result=copy(before,after)
            if Path(before).name=='runtime.lxd':
                Path(after if failure=='corrupt-copy' else before).write_bytes(b'changed during move')
            return result
        monkeypatch.setattr(standalone_mods.shutil,'copy2',modified)
    with pytest.raises(OSError):
        standalone_mods.adopt(source,library,candidates)
    assert source.is_dir() and (source/'nested/data.bin').read_bytes()==b'unchanged payload'
    assert list(library.iterdir())==[]
