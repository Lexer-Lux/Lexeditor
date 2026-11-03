"""Repeated application preserves identical installed files and still validates ownership."""
import pytest
import hashlib
import json
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


def test_only_changed_outputs_are_parsed_again(tmp_path, monkeypatch):
    game, mod = project(tmp_path)
    payload = make_archive(field_values={'EquipParamGoods': {100: {'basicPrice': 17}}})
    deployment.apply(game, mod, composed={RELATIVE: payload})
    parsed = []
    original = dict(deployment.FILES)[RELATIVE]
    def parse(data):
        parsed.append(data)
        return original(data)
    monkeypatch.setattr(deployment, 'FILES', tuple(
        (relative, parse if relative == RELATIVE else reader) for relative, reader in deployment.FILES))
    deployment.apply(game, mod, composed={RELATIVE: payload})
    assert not parsed
    changed = make_archive(field_values={'EquipParamGoods': {100: {'basicPrice': 18}}})
    deployment.apply(game, mod, composed={RELATIVE: changed})
    assert parsed == [changed]
    with pytest.raises(ValueError):
        deployment.apply(game, mod, composed={RELATIVE: b'broken output'})
    assert parsed[-1] == b'broken output'
    assert (game/RELATIVE).read_bytes() == changed


def test_external_change_after_comparison_is_still_preserved(tmp_path, monkeypatch):
    from contextlib import contextmanager
    game, mod = project(tmp_path)
    payload = make_archive(field_values={'EquipParamGoods': {100: {'basicPrice': 17}}})
    deployment.apply(game, mod, composed={RELATIVE: payload})
    transaction = deployment._data_transaction
    @contextmanager
    def changed_during_save(root, desired):
        (game/RELATIVE).write_bytes(b'external edit')
        with transaction(root, desired) as state:
            yield state
    monkeypatch.setattr(deployment, '_data_transaction', changed_during_save)
    with pytest.raises(RuntimeError):
        deployment.apply(game, mod, composed={RELATIVE: payload})
    assert (game/RELATIVE).read_bytes() == b'external edit'


@pytest.mark.parametrize('combined', [False, True])
def test_transformed_payload_keeps_distinct_source_and_installed_identities(tmp_path, combined):
    game, mod = project(tmp_path)
    source = make_archive(field_values={'EquipParamGoods': {100: {'basicPrice': 17}}})
    transformed = make_archive(field_values={'EquipParamGoods': {100: {'basicPrice': 18}}})
    (mod / RELATIVE).parent.mkdir(parents=True, exist_ok=True)
    (mod / RELATIVE).write_bytes(source)
    options = {'composed': {RELATIVE: source}} if combined else {}
    result = deployment.apply(game, mod, transform=lambda _payload: transformed, **options)
    marker = json.loads(deployment._marker_path(game, RELATIVE).read_text())
    assert marker['sourceHash'] == hashlib.sha256(source).hexdigest()
    assert marker['activeHash'] == hashlib.sha256(transformed).hexdigest()
    assert (game / RELATIVE).read_bytes() == transformed
    assert result['enabled'] and not result['stale']


@pytest.mark.parametrize('operation', ['restore', 'apply_without_mod'])
def test_repeated_restore_validates_without_rewriting_originals(tmp_path, monkeypatch, operation):
    game, mod = project(tmp_path)
    payload = make_archive(field_values={'EquipParamGoods': {100: {'basicPrice': 17}}})
    deployment.apply(game, mod, composed={RELATIVE: payload})
    deployment.disable(game)
    writes = []
    original = deployment.atomic_write
    def write(path, data):
        writes.append(path)
        return original(path, data)
    monkeypatch.setattr(deployment, 'atomic_write', write)
    def repeat():
        return (deployment.disable(game) if operation == 'restore'
                else deployment.apply(game, mod, composed={}))
    result = repeat()
    assert result['matchesOriginal'] and not result['enabled']
    assert not writes
    # An already disabled receipt still cannot authorize overwriting a later
    # external edit or trusting a damaged preserved original.
    for target in (game/RELATIVE, deployment._backup_path(game, RELATIVE)):
        before = target.read_bytes()
        target.write_bytes(b'external edit')
        with pytest.raises(RuntimeError):
            repeat()
        assert target.read_bytes() == b'external edit'
        assert not writes
        target.write_bytes(before)
