from pathlib import Path
import shutil

import pytest

from games.ff7r.lockon_tweaks import (
    BETTER_LOCKON_ASSET,
    BETTER_LOCKON_SCHEMA_VERSION,
    load_config,
    load_virtual_package,
    materialize_better_lockon,
    resource_spec,
    save_config,
    save_virtual_edits,
)
from games.ff7r.plugin import _test_text_package
from games.ff7r.textresource import TextResourcePackage


def _text_pair(language: str, prompt: str, *, ambiguous: bool = False):
    uasset, uexp = _test_text_package()
    package = TextResourcePackage.from_bytes(uasset, uexp)
    package.language = language
    package.entries[0].id = "$LockPrompt"
    package.entries[0].text = prompt
    package.entries[0].subentries = []
    package.entries[1].id = "$Other"
    package.entries[1].text = "LOCK ON" if ambiguous else f"Other {language}"
    package.entries[1].subentries = []
    package._rebuild()
    return bytes(package.uasset_bytes), bytes(package.uexp_bytes)


def _fixture(tmp_path: Path, *, ambiguous_us: bool = False):
    fixture = tmp_path / "fixture"
    rows = []
    translations = {"US": "LOCK ON", "FR": "VERROUILLAGE", "DE": "ANVISIEREN"}
    for language, prompt in translations.items():
        directory = fixture / "End" / "Content" / "GameContents" / "Text" / language
        directory.mkdir(parents=True, exist_ok=True)
        uasset, uexp = _text_pair(
            language, prompt, ambiguous=(ambiguous_us and language == "US"))
        uasset_path = directory / "Resident_TxtRes.uasset"
        uexp_path = directory / "Resident_TxtRes.uexp"
        uasset_path.write_bytes(uasset)
        uexp_path.write_bytes(uexp)
        asset = f"End/Content/GameContents/Text/{language}/Resident_TxtRes"
        rows.append({
            "asset": asset,
            "name": "Resident_TxtRes",
            "language": language,
            "group": "Text",
            "uasset": {"fixture": uasset_path.as_posix()},
            "uexp": {"fixture": uexp_path.as_posix()},
        })
    return {
        "schema": 2,
        "signature": {"fixture": str(fixture)},
        "signatureId": "lockon-text-fixture",
        "pakVersions": {},
        "assets": [],
        "textAssets": rows,
    }


def _staged_package(staging: Path, asset: str):
    return TextResourcePackage(
        staging / f"{asset}.uasset",
        staging / f"{asset}.uexp",
        asset=asset,
    )


def test_virtual_resource_exposes_prompt_readiness_but_not_red_reticle(monkeypatch, tmp_path):
    index = _fixture(tmp_path)
    package, source_sha, using_project = load_virtual_package(
        tmp_path / "game", tmp_path / "data", tmp_path / "project", index)
    payload = package.api_payload(source_sha256=source_sha, using_project=using_project)
    props = {row["name"]: row for row in payload["properties"]}
    values = payload["records"][0]["values"]

    assert payload["asset"] == BETTER_LOCKON_ASSET
    assert props["RemovePrompt"]["editable"] is True
    assert props["RedReticleReady"]["editable"] is False
    assert values["PromptTextIdResolved"] is True
    assert values["PromptTextId"] == "$LockPrompt"
    assert values["LocalizedResources"] == 3
    assert values["RedReticleReady"] is False


def test_enabling_prompt_removal_requires_proven_installed_text_id(tmp_path):
    index = _fixture(tmp_path, ambiguous_us=True)
    project = tmp_path / "project"
    spec = resource_spec(tmp_path / "game", tmp_path / "data", project, index)
    assert spec["evidence"]["labelTextIdResolved"] is False

    with pytest.raises(RuntimeError, match="ownership is not fully validated"):
        save_virtual_edits(
            tmp_path / "game", tmp_path / "data", project, index,
            source_sha256=spec["sourceSha256"],
            active_sha256=spec["activeSha256"],
            edits=[{"entry": 0, "property": "RemovePrompt", "value": True}],
        )
    assert load_config(project)["removePrompt"] is False


def test_prompt_materializer_blanks_only_proven_id_in_all_languages_and_preserves_sources(tmp_path):
    index = _fixture(tmp_path)
    game = tmp_path / "game"
    data = tmp_path / "data"
    project = tmp_path / "project"
    staging = tmp_path / "staging"
    save_config(project, {
        "schemaVersion": BETTER_LOCKON_SCHEMA_VERSION,
        "removePrompt": True,
    })
    source_before = {
        row["asset"]: (
            Path(row["uasset"]["fixture"]).read_bytes(),
            Path(row["uexp"]["fixture"]).read_bytes(),
        )
        for row in index["textAssets"]
    }

    result = materialize_better_lockon(game, data, project, index, staging)

    assert len(result) == 3
    assert {row["language"] for row in result} == {"US", "FR", "DE"}
    assert all(row["textId"] == "$LockPrompt" and row["newText"] == "" for row in result)
    for row in index["textAssets"]:
        asset = row["asset"]
        staged = _staged_package(staging, asset)
        texts = {entry.id: entry.text for entry in staged.entries}
        assert texts["$LockPrompt"] == ""
        assert texts["$Other"] == f"Other {row['language']}"
        assert Path(row["uasset"]["fixture"]).read_bytes() == source_before[asset][0]
        assert Path(row["uexp"]["fixture"]).read_bytes() == source_before[asset][1]
    assert not (project / "content").exists()


def test_materializer_composes_over_existing_staged_project_text_edit(tmp_path):
    index = _fixture(tmp_path)
    project = tmp_path / "project"
    staging = tmp_path / "staging"
    save_config(project, {
        "schemaVersion": BETTER_LOCKON_SCHEMA_VERSION,
        "removePrompt": True,
    })

    us = next(row for row in index["textAssets"] if row["language"] == "US")
    target_uasset = staging / f"{us['asset']}.uasset"
    target_uexp = staging / f"{us['asset']}.uexp"
    target_uasset.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(us["uasset"]["fixture"], target_uasset)
    shutil.copy2(us["uexp"]["fixture"], target_uexp)
    package = TextResourcePackage(target_uasset, target_uexp, asset=us["asset"])
    other_index = next(index for index, entry in enumerate(package.entries) if entry.id == "$Other")
    package.apply_edits([{"entry": other_index, "text": "Project Overlay Text"}])
    package.write_pair(target_uasset, target_uexp)

    materialize_better_lockon(
        tmp_path / "game", tmp_path / "data", project, index, staging)
    staged = _staged_package(staging, us["asset"])
    texts = {entry.id: entry.text for entry in staged.entries}
    assert texts == {"$LockPrompt": "", "$Other": "Project Overlay Text"}


def test_disabled_better_lockon_does_not_touch_staging(tmp_path):
    index = _fixture(tmp_path)
    staging = tmp_path / "staging"
    result = materialize_better_lockon(
        tmp_path / "game", tmp_path / "data", tmp_path / "project", index, staging)
    assert result == []
    assert not staging.exists()


def test_incomplete_existing_staging_pair_fails_closed(tmp_path):
    index = _fixture(tmp_path)
    project = tmp_path / "project"
    staging = tmp_path / "staging"
    save_config(project, {
        "schemaVersion": BETTER_LOCKON_SCHEMA_VERSION,
        "removePrompt": True,
    })
    us = next(row for row in index["textAssets"] if row["language"] == "US")
    target = staging / f"{us['asset']}.uasset"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(Path(us["uasset"]["fixture"]).read_bytes())

    with pytest.raises(RuntimeError, match="incomplete package pair"):
        materialize_better_lockon(
            tmp_path / "game", tmp_path / "data", project, index, staging)
