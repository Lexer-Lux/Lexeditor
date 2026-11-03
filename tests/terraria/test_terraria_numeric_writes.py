import pytest

from plugins.terraria.structured_content import (
    create_structured_content, structured_content_state, update_structured_content,
)


def test_structured_numbers_reject_nonfinite_and_fractional_integer_writes(tmp_path):
    project = tmp_path / "NumericMod"
    project.mkdir()
    for values in ({"damage": 1.5}, {"knockBack": float("nan")},
                   {"knockBack": float("inf")}, {"damage": True}):
        with pytest.raises(ValueError):
            create_structured_content(project, "item", "Example", values)
        assert not list(project.iterdir())

    saved = create_structured_content(project, "item", "Example", {"damage": 10, "knockBack": 1.25})
    snapshots = {path: path.read_bytes() for path in project.rglob("*") if path.is_file()}
    for key, value in (("damage", 2.5), ("knockBack", float("nan")),
                       ("knockBack", float("-inf"))):
        values = dict(saved["values"], **{key: value})
        with pytest.raises(ValueError):
            update_structured_content(project, saved["path"], values, saved["sha256"])
        assert all(path.read_bytes() == data for path, data in snapshots.items())
    values = dict(saved["values"], damage=42.0, knockBack=2.75)
    update_structured_content(project, saved["path"], values, saved["sha256"])
    reloaded = structured_content_state(project, saved["path"])
    assert reloaded["values"]["damage"] == 42
    assert reloaded["values"]["knockBack"] == 2.75
