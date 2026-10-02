"""All documented DS1 effect fields use the existing round-trip codecs."""
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ds1_fixture import make_archive
from ds1_effects_fixture import make_effects_archive, mutate_effect_header, wrap
from plugins.ds1.formats import ItemDocument, FormatError, inflate, schema
from plugins.ds1.effects import TABLE, RECOVERY_KEY
from plugins.ds1.store import ItemStore, RELATIVE, MARKER
from plugins.ds1.plugin import DS1Session
from plugins.ds1 import deployment


def project(tmp_path):
    game, mod = tmp_path / "game", tmp_path / "mod"
    (game / RELATIVE).parent.mkdir(parents=True)
    (game / RELATIVE).write_bytes(make_effects_archive())
    mod.mkdir()
    (mod / MARKER).touch()
    return game, mod


def field(document, key, row_id=6890):
    return next(f for f in document.read_row(TABLE, row_id)["fields"] if f["key"] == key)


def test_schema_shape_and_noop():
    raw = make_effects_archive()
    doc = ItemDocument(raw)
    definition = schema(TABLE)
    assert definition["size"] == 368
    assert len(definition["fields"]) == 173
    assert sum(f["editable"] for f in definition["fields"]) == 153
    assert doc.export() == raw and doc.dirty_count == 0
    assert doc.value(TABLE, 6890, RECOVERY_KEY) == 10
    assert doc.read_row(TABLE, 6890)["name"] == "Grass Crest Shield"
    assert len(doc.list_rows("effects-all")) == 62
    assert next(f["spec"].offset for f in definition["fields"] if f["spec"].key == RECOVERY_KEY) == 0xB8


EDITABLE = [f["spec"].key for f in schema(TABLE)["fields"] if f["editable"]]


@pytest.mark.parametrize("key", EDITABLE)
def test_every_editable_field_changes_only_its_own_bits_and_roundtrips(key):
    raw = make_effects_archive()
    doc = ItemDocument(raw)
    spec = next(f["spec"] for f in schema(TABLE)["fields"] if f["spec"].key == key)
    cell = field(doc, key)
    old = cell["value"]
    if cell["type"] == "bool":
        value = 0 if old else 1
    elif cell["type"] == "enum":
        value = next(int(k) for k in cell["enum"] if int(k) != old)
    else:
        value = min(max(old + 1, cell["minimum"]), cell["maximum"])
        if value == old:
            value = cell["minimum"] if old != cell["minimum"] else cell["maximum"]
    doc.edit(TABLE, 6890, key, value)
    reopened = ItemDocument(doc.export())
    assert reopened.value(TABLE, 6890, key) == pytest.approx(value)
    before, after = inflate(raw), inflate(doc.export())
    start = doc._row(TABLE, 6890)[1] + spec.offset
    size = {"s8":1, "u8":1, "s16":2, "u16":2, "s32":4, "u32":4, "f32":4}[spec.dtype]
    changes = [(i, a ^ b) for i, (a,b) in enumerate(zip(before,after)) if a != b]
    assert changes and all(start <= i < start + size for i, _ in changes)
    assert len(before) == len(after)
    if spec.bit_size:
        mask = ((1 << spec.bit_size) - 1) << spec.bit_offset
        assert all(delta & ~mask == 0 for _, delta in changes)
    assert doc.dirty_count == 1
    doc.edit(TABLE, 6890, key, old)
    assert doc.export() == raw and doc.dirty_count == 0


@pytest.mark.parametrize("key", [f["spec"].key for f in schema(TABLE)["fields"] if not f["editable"]])
def test_protected_fields_remain_unchanged(key):
    raw = make_effects_archive()
    doc = ItemDocument(raw)
    with pytest.raises(FormatError, match="protected"):
        doc.edit(TABLE, 6890, key, 1)
    assert doc.export() == raw


@pytest.mark.parametrize("value", [-101, 101, .25, float("nan"), float("inf"),
                                  float("-inf"), True, False, "4", None, [], 10**1000])
def test_invalid_recovery_does_not_write(value):
    raw = make_effects_archive()
    doc = ItemDocument(raw)
    with pytest.raises(FormatError):
        doc.edit(TABLE, 6890, RECOVERY_KEY, value)
    assert doc.export() == raw


def test_effect_options_validate_and_reflect_actual_consumers():
    doc = ItemDocument(make_effects_archive())
    assert field(doc,"replaceSpEffectId")["enum"]["-1"] == "None"
    assert "Grass Crest Shield" in field(doc,"replaceSpEffectId")["enum"]["6890"]
    assert field(doc,"spCategory")["type"] == "enum"
    assert field(doc,"disablePoison")["type"] == "bool"
    with pytest.raises(FormatError):
        doc.edit(TABLE,6890,"replaceSpEffectId",1234567)
    with pytest.raises(FormatError):
        doc.edit(TABLE,6890,"spCategory",123)
    doc.edit(TABLE,6890,"replaceSpEffectId",6920)
    assert any(u["id"]==6890 for u in doc.read_row(TABLE,6920)["effectUsage"])
    doc.edit(TABLE,6890,"replaceSpEffectId",-1)
    assert not any(u["table"]==TABLE and u["id"]==6890 for u in doc.read_row(TABLE,6920)["effectUsage"])
    users=doc.read_row(TABLE,6890)["effectUsage"]
    assert {(u["table"],u["id"]) for u in users} == {("EquipParamWeapon",100),("EquipParamAccessory",100)}
    assert not doc.read_row("EquipParamAccessory",101)["effectLinks"]
    doc.edit("EquipParamWeapon",100,"residentSpEffectId",99001)
    assert next(link["id"] for link in doc.read_row("EquipParamWeapon",100)["effectLinks"]
                if link["field"] == "residentSpEffectId") == 99001
    assert len(doc.read_row(TABLE,6890)["effectUsage"]) == 1
    doc.edit("EquipParamAccessory",101,"refCategory",2)
    assert len(doc.read_row(TABLE,6890)["effectUsage"]) == 2
    assert {r["id"] for r in doc.list_rows("effects-spells")} == {2013}
    assert {r["id"] for r in doc.list_rows("effects-items")} == {3040}
    assert 99001 in {r["id"] for r in doc.list_rows("effects-equipment")}


def test_missing_effect_table_keeps_old_projects_usable():
    raw = make_archive()
    doc = ItemDocument(raw)
    assert TABLE not in doc.params and doc.export() == raw
    assert doc.list_rows("weapons")
    with pytest.raises(FormatError,match="missing"):
        doc.list_rows("effects-all")


@pytest.mark.parametrize("options", [{"version":2},{"effect_size":364},{"effect_size":372}])
def test_wrong_layout_rejected(options):
    with pytest.raises(FormatError):
        ItemDocument(make_effects_archive(**options))


@pytest.mark.parametrize("offset,fmt,value",[
    (0,"<I",1),(10,"<H",0),(60,"<i",40),(64,"<I",48+12*62),(44,"<B",1)])
def test_bad_header_or_row_boundaries(offset,fmt,value):
    with pytest.raises(FormatError):
        ItemDocument(mutate_effect_header(make_effects_archive(),offset,fmt,value))


def test_nonfinite_and_unknown_values_are_preserved_not_silently_repaired():
    import struct
    raw = make_effects_archive()
    doc = ItemDocument(raw)
    start = doc._row(TABLE,6890)[1]
    struct.pack_into("<f",doc.plain,start+8,float("nan"))
    spec=next(f["spec"] for f in schema(TABLE)["fields"] if f["spec"].key=="spCategory")
    struct.pack_into("<H",doc.plain,start+spec.offset,55555)
    raw = wrap(doc.plain,raw)
    doc=ItemDocument(raw)
    assert doc.export()==raw
    assert field(doc,"effectEndurance")["editable"] is False
    assert field(doc,"effectEndurance")["value"]=="nan"
    assert field(doc,"spCategory")["value"]==55555
    assert "55555" not in field(doc,"spCategory")["enum"]
    doc.edit(TABLE,6890,RECOVERY_KEY,4)
    assert field(ItemDocument(doc.export()),"effectEndurance")["value"]=="nan"


def test_project_save_discard_readonly_stale_write_and_deployment(tmp_path):
    game,mod=project(tmp_path)
    raw=(game/RELATIVE).read_bytes()
    store=ItemStore(game,mod,False)
    assert store.state()["effectsAvailable"] and len(store.state()["effectTabs"])==4
    store.edit(TABLE,6890,RECOVERY_KEY,4)
    store.edit(TABLE,6890,"effectEndurance",30)
    store.save()
    assert (game/RELATIVE).read_bytes()==raw
    assert ItemStore(game,mod,False).get().value(TABLE,6890,RECOVERY_KEY)==4
    store.edit(TABLE,6890,RECOVERY_KEY,7)
    store.discard()
    assert store.get().value(TABLE,6890,RECOVERY_KEY)==4
    with pytest.raises(PermissionError):
        ItemStore(game).edit(TABLE,6890,RECOVERY_KEY,1)
    (game/"DarkSoulsRemastered.exe").touch()
    deployment.apply(game,mod)
    assert ItemDocument((game/RELATIVE).read_bytes()).value(TABLE,6890,RECOVERY_KEY)==4
    deployment.disable(game)
    assert (game/RELATIVE).read_bytes()==raw
    store.edit(TABLE,6890,RECOVERY_KEY,8)
    (mod/RELATIVE).write_bytes(raw)
    with pytest.raises(ValueError,match="changed outside"):
        store.save()


def test_service_effects_and_cross_origin_readonly_validation(tmp_path):
    game,mod=project(tmp_path)
    env={"LEXEDITOR_DS1_ROOT":str(game),"LEXEDITOR_DS1_PROJECT":str(mod),
         "LEXEDITOR_MOD_READ_ONLY":"0","LEXEDITOR_NO_MOD":"0"}
    session=DS1Session(env)
    def request(path,payload=None,origin=None):
        headers={"Content-Type":"application/json"}
        if origin: headers["Origin"]=origin
        req=Request(session.url.rstrip("/")+path,
                    data=None if payload is None else json.dumps(payload).encode(),headers=headers)
        with urlopen(req) as reply:return json.load(reply)
    try:
        session.start()
        assert request("/api/state")["effectsAvailable"]
        assert "effects" in request("/api/plugin")["capabilities"]
        assert len(request("/api/table?tab=effects-all")["rows"])==62
        assert request("/api/data-map")["rows"]
        body={"table":TABLE,"id":6890,"field":"effectEndurance","value":30}
        assert request("/api/edit",body)["dirtyCount"]==1
        assert request("/api/save",{})["saved"]
        request("/api/discard",{})
        row=request("/api/row?table=SpEffectParam&id=6890")["row"]
        assert next(f["value"] for f in row["fields"] if f["key"]=="effectEndurance")==30
        with pytest.raises(HTTPError) as e:request("/api/edit",body,"http://other.example")
        assert e.value.code==403
        session.stop()
        session=DS1Session({**env,"LEXEDITOR_NO_MOD":"1","LEXEDITOR_MOD_READ_ONLY":"1"})
        session.start()
        with pytest.raises(HTTPError) as e:request("/api/edit",body)
        assert e.value.code==403
    finally:
        session.stop()
