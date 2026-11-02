"""Repeated application preserves identical installed files and still validates ownership."""
import pytest
from test_ds1_deployment import project, make_archive, RELATIVE
from plugins.ds1 import deployment


def test_repeated_apply_does_not_rewrite_identical_archives(tmp_path, monkeypatch):
    game, mod = project(tmp_path)
    payload = make_archive(field_values={'EquipParamGoods': {100: {'basicPrice': 17}}})
    deployment.apply(game, mod, composed={RELATIVE: payload})
    writes = []
    original = deployment.atomic_write
    def write(path, data):
        writes.append(path)
        return original(path, data)
    monkeypatch.setattr(deployment, 'atomic_write', write)
    deployment.apply(game, mod, composed={RELATIVE: payload})
    assert game/RELATIVE not in writes
    assert deployment._marker_path(game, RELATIVE) not in writes
    assert (game/RELATIVE).read_bytes() == payload
    changed = make_archive(field_values={'EquipParamGoods': {100: {'basicPrice': 18}}})
    deployment.apply(game, mod, composed={RELATIVE: changed})
    assert game/RELATIVE in writes
    assert (game/RELATIVE).read_bytes() == changed


@pytest.mark.parametrize('damage', ['live', 'backup'])
def test_unchanged_output_still_rejects_damaged_installation(tmp_path, damage):
    game, mod = project(tmp_path)
    payload = make_archive(field_values={'EquipParamGoods': {100: {'basicPrice': 17}}})
    deployment.apply(game, mod, composed={RELATIVE: payload})
    target = game/RELATIVE if damage == 'live' else deployment._backup_path(game, RELATIVE)
    target.write_bytes(b'foreign bytes')
    with pytest.raises(RuntimeError):
        deployment.apply(game, mod, composed={RELATIVE: payload})
    assert target.read_bytes() == b'foreign bytes'
