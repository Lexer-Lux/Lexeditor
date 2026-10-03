"""Every batch route rejects malformed collections before creating output."""
import json
import struct
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.chrono_trigger.archive import ResourcesBin
from plugins.chrono_trigger.project import digest
from plugins.chrono_trigger.plugin import ChronoTriggerSession
import test_chrono_trigger_replacement as fixtures


ROUTES = [
    ('messages', 'Localize/en/msg/cmes0.txt'),
    ('scene-map', 'Game/field/MapTable/MapTable_0006.dat'),
    ('scene-properties', 'Game/field/MapTable/MapTable_0006.dat'),
    ('palette', 'Game/field/palette_bin/plt4.bin'),
    ('exits', 'Game/common/MapJumpDataTbl.dat'),
    ('treasure', 'Game/common/TakaraDataTbl.dat'),
    ('worlds', 'Game/common/bankc6.bin'),
    ('world-navigation', 'Game/world/EventTable/EventTable_0004.dat'),
    ('chip-animations', 'Game/field/BGAnime/bganimeinfo_4.dat'),
    ('world-map', 'Game/world/Map/Map_0000.dat'),
    ('world-properties', 'Game/world/Id/Id_0000.dat'),
    ('world-music', 'Game/world/SeId/SeId_0000.dat'),
    ('world-colors', 'Game/world/colanim_bin/0_colanim.bin'),
    ('tile-assemblies', 'Game/field/ChipTable/ChipTable_0004.dat'),
    ('sprite-assemblies', 'Game/chara/cell/c005.cel'),
    ('weapons', 'Game/common/WeaponDataTable.dat'),
    ('armor', 'Game/common/ArmorDataTable.dat'),
    ('helmets', 'Game/common/HelmetDataTable.dat'),
]


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('route,path', ROUTES)
def test_batch_route_rejects_non_arrays_and_accepts_real_array(tmp_path, route, path):
    fixture = tmp_path / 'fixture'
    fixture.mkdir()
    archive, _ = fixtures.FreshChronoTriggerTests().fixture(fixture)
    source = ResourcesBin(archive)
    resources = [(name, source.extract(name)) for name in source.paths()]
    for filename, count, width in (('Weapon', 111, 5), ('Armor', 50, 3), ('Helmet', 39, 3)):
        resources.append(('Game/common/' + filename + 'DataTable.dat', struct.pack('<I', count) + b'\xA5' * (count * width) + b'OPAQUE'))
    payloads = dict(resources)
    game = tmp_path / 'game'
    game.mkdir()
    fixtures.build_archive(game / 'resources.bin', resources)
    (game / 'Chrono Trigger.exe').write_bytes(b'authored executable marker')
    project = tmp_path / 'mod'
    vanilla = snapshot(game)
    body = dict(path=path, sha256=digest(payloads[path]))
    if route in ('exits', 'treasure'):
        offset_path = 'Game/common/' + ('MapJumpOffsetTbl.dat' if route == 'exits' else 'TakaraOffsetTbl.dat')
        body.update(dataSha256=digest(payloads[path]), offsetSha256=digest(payloads[offset_path]))
    with ChronoTriggerSession({'LEXEDITOR_CHRONO_TRIGGER_ROOT': str(game),
                               'LEXEDITOR_CHRONO_TRIGGER_PROJECT': str(project)}) as session:
        def request(edits):
            return Request(session.url + 'api/' + route + '/save', data=json.dumps(body | dict(edits=edits)).encode(), headers={'Content-Type': 'application/json'})
        for existing in (False, True):
            if existing:
                # Prove the same body/resource/checksum reaches and completes the writer.
                with urlopen(request([]), timeout=5) as response:
                    assert isinstance(json.load(response), dict)
                assert (project / path).read_bytes() == payloads[path]
            for edits in (None, False, True, 0, 1, {}, '', 'token'):
                before = snapshot(project)
                with pytest.raises(HTTPError) as failure:
                    urlopen(request(edits), timeout=5)
                assert failure.value.code == 400
                assert json.load(failure.value)['error'] == 'Chrono Trigger edits must be an array'
                failure.value.close()
                assert snapshot(project) == before
                assert snapshot(game) == vanilla
    assert session.wait_closed()
