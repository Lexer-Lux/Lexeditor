from types import SimpleNamespace

from games.ff7r import lockon_text_probe as probe


def _package(entries):
    return SimpleNamespace(entries=[
        SimpleNamespace(id=text_id, text=text, subentries=[])
        for text_id, text in entries
    ])


def _index(*languages):
    return {
        "textAssets": [
            {
                "asset": f"End/Content/GameContents/Text/{language}/Resident_TxtRes",
                "language": language,
            }
            for language in languages
        ]
    }


def test_unique_us_lock_on_id_is_correlated_across_localized_resources(monkeypatch):
    packages = {
        "US": _package([
            ("$LockPrompt", "LOCK ON"),
            ("$LockStatus", "LOCKED ON"),
        ]),
        "FR": _package([
            ("$LockPrompt", "VERROUILLAGE"),
            ("$LockStatus", "CIBLE VERROUILLÉE"),
        ]),
        "DE": _package([
            ("$LockPrompt", "ANVISIEREN"),
        ]),
    }

    def load(_game, _data, _project, _index, asset, *, vanilla):
        assert vanilla is True
        language = asset.split("/")[-2]
        return packages[language], None, None, False

    monkeypatch.setattr(probe, "load_text_package", load)
    result = probe.discover_lockon_prompt_texts("g", "d", "p", _index("US", "FR", "DE"))

    assert result["anchorTextId"] == "$LockPrompt"
    assert result["labelTextIdResolved"] is True
    assert result["blockers"] == []
    assert {row["language"] for row in result["localizedPromptEntries"]} == {"US", "FR", "DE"}
    assert next(row for row in result["localizedPromptEntries"] if row["language"] == "FR")["text"] == "VERROUILLAGE"
    assert result["lockedOnStatusCandidates"][0]["textId"] == "$LockStatus"


def test_locked_on_status_phrase_is_not_mistaken_for_small_lock_on_prompt(monkeypatch):
    monkeypatch.setattr(
        probe,
        "load_text_package",
        lambda *_args, **_kwargs: (_package([("$Status", "LOCKED ON")]), None, None, False),
    )
    result = probe.discover_lockon_prompt_texts("g", "d", "p", _index("US"))

    assert result["anchorCandidates"] == []
    assert result["anchorTextId"] == ""
    assert result["labelTextIdResolved"] is False
    assert "exact-us-lock-on-label-not-found" in result["blockers"]
    assert result["lockedOnStatusCandidates"][0]["textId"] == "$Status"


def test_ambiguous_us_lock_on_values_fail_closed(monkeypatch):
    package = _package([
        ("$PromptA", "LOCK ON"),
        ("$PromptB", "  LOCK   ON  "),
    ])
    monkeypatch.setattr(
        probe,
        "load_text_package",
        lambda *_args, **_kwargs: (package, None, None, False),
    )
    result = probe.discover_lockon_prompt_texts("g", "d", "p", _index("US"))

    assert result["anchorTextId"] == ""
    assert result["labelTextIdResolved"] is False
    assert "exact-us-lock-on-label-ambiguous" in result["blockers"]


def test_missing_same_text_id_in_one_language_blocks_cross_language_ownership(monkeypatch):
    packages = {
        "US": _package([("$LockPrompt", "LOCK ON")]),
        "FR": _package([("$Other", "AUTRE")]),
    }

    def load(_game, _data, _project, _index, asset, *, vanilla):
        language = asset.split("/")[-2]
        return packages[language], None, None, False

    monkeypatch.setattr(probe, "load_text_package", load)
    result = probe.discover_lockon_prompt_texts("g", "d", "p", _index("US", "FR"))

    assert result["anchorTextId"] == "$LockPrompt"
    assert result["labelTextIdResolved"] is False
    assert result["missingLanguages"] == ["FR"]
    assert "lock-on-text-id-missing-in-localized-resource" in result["blockers"]


def test_text_scan_error_is_reported_and_blocks_resolution(monkeypatch):
    def load(_game, _data, _project, _index, asset, *, vanilla):
        if "/FR/" in asset:
            raise ValueError("synthetic text parse failure")
        return _package([("$LockPrompt", "LOCK ON")]), None, None, False

    monkeypatch.setattr(probe, "load_text_package", load)
    result = probe.discover_lockon_prompt_texts("g", "d", "p", _index("US", "FR"))

    assert result["labelTextIdResolved"] is False
    assert "resident-text-scan-errors" in result["blockers"]
    assert "synthetic text parse failure" in result["scanErrors"][0]
