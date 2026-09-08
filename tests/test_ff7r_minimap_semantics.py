from types import SimpleNamespace

import pytest

from games.ff7r.dataobject import BOOLEAN_BYTE, INT32, Property
from games.ff7r import minimap_semantics as subject


ASSET = "End/Content/GameContents/DataObject/Resident/EnemyTerritory"
INDEX = {"assets": [{"asset": ASSET, "name": "EnemyTerritory"}]}


class FakePackage:
    def __init__(self, prop=None):
        self.properties = [prop] if prop is not None else []
        self.entries = [
            SimpleNamespace(index=0, tag="TERRITORY_A", values={"HideNavimap": True}),
            SimpleNamespace(index=1, tag="TERRITORY_B", values={"HideNavimap": False}),
        ]

    def api_payload(self):
        return {"activeSha256": "active-sha"}


def install_package(monkeypatch, package):
    monkeypatch.setattr(
        subject,
        "load_package",
        lambda *_args, **_kwargs: (package, "source-sha", False),
    )


def test_payload_fails_closed_when_enemy_territory_is_absent():
    payload = subject.minimap_visibility_payload(None, None, None, {"assets": []})
    assert payload["available"] is False
    assert "EnemyTerritory" in payload["reason"]


def test_payload_requires_exact_editable_scalar_bool(monkeypatch):
    install_package(monkeypatch, FakePackage())
    payload = subject.minimap_visibility_payload(None, None, None, INDEX)
    assert payload["available"] is False
    assert "HideNavimap is absent" in payload["reason"]

    install_package(monkeypatch, FakePackage(Property("HideNavimap", INT32, False)))
    payload = subject.minimap_visibility_payload(None, None, None, INDEX)
    assert payload["available"] is False
    assert "scalar boolean" in payload["reason"]


def test_payload_reports_authored_forced_hides(monkeypatch):
    install_package(monkeypatch, FakePackage(Property("HideNavimap", BOOLEAN_BYTE, False)))
    payload = subject.minimap_visibility_payload(None, None, None, INDEX)
    assert payload["available"] is True
    assert payload["forcedHideCount"] == 1
    assert payload["rows"] == [
        {"entry": 0, "id": "TERRITORY_A", "hideNavimap": True},
        {"entry": 1, "id": "TERRITORY_B", "hideNavimap": False},
    ]


def test_save_only_maps_boolean_hide_navimap(monkeypatch):
    install_package(monkeypatch, FakePackage(Property("HideNavimap", BOOLEAN_BYTE, False)))
    captured = {}

    def fake_save(*_args, **kwargs):
        captured.update(kwargs)
        return {"saved": len(kwargs["edits"]), "activeSha256": "new-sha"}

    monkeypatch.setattr(subject, "save_edits", fake_save)
    result = subject.save_minimap_visibility_edits(
        None, None, None, INDEX, ASSET,
        source_sha256="source-sha",
        active_sha256="active-sha",
        edits=[{"entry": 0, "hideNavimap": False}],
    )
    assert result["surface"] == "minimap-visibility"
    assert captured["edits"] == [
        {"entry": 0, "property": "HideNavimap", "value": False},
    ]


def test_save_rejects_wrong_table_and_non_boolean_values(monkeypatch):
    install_package(monkeypatch, FakePackage(Property("HideNavimap", BOOLEAN_BYTE, False)))
    with pytest.raises(ValueError, match="limited to EnemyTerritory"):
        subject.save_minimap_visibility_edits(
            None, None, None, INDEX, "Resident/Other",
            source_sha256="source-sha", active_sha256="active-sha", edits=[],
        )
    with pytest.raises(ValueError, match="must be boolean"):
        subject.save_minimap_visibility_edits(
            None, None, None, INDEX, ASSET,
            source_sha256="source-sha", active_sha256="active-sha",
            edits=[{"entry": 0, "hideNavimap": 0}],
        )
