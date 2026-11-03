"""Bannerlord Gauntlet prefabs and elements can be created, as copies.

A new prefab copies an existing one into the same folder and never
overwrites; a new element copies an element, with everything inside it, to
just after itself, leaving the rest of the prefab's text exactly as it was.
"""
from pathlib import Path

import pytest

from plugins.bannerlord.gauntlet_data import BLANK_PREFAB, create_prefab, duplicate_element, read_prefab

PREFAB = (
    "<Prefab>\r\n"
    "  <!-- the shop window -->\r\n"
    "  <Window>\r\n"
    "    <Widget Id=\"Panel\" WidthSizePolicy=\"Fixed\">\r\n"
    "      <TextWidget Text=\"@Title\" />\r\n"
    "    </Widget>\r\n"
    "  </Window>\r\n"
    "</Prefab>\r\n"
)


@pytest.fixture()
def project(tmp_path):
    root = tmp_path / "Module"
    prefabs = root / "GUI" / "Prefabs" / "Shop"
    prefabs.mkdir(parents=True)
    (prefabs / "ShopWindow.xml").write_bytes(PREFAB.encode("utf-8"))
    return root


def test_a_new_prefab_is_a_copy_beside_its_template(project):
    created = create_prefab(project, "GUI/Prefabs/Shop/ShopWindow.xml", "ShopWindowCopy")
    assert created["relativePath"] == "GUI/Prefabs/Shop/ShopWindowCopy.xml"
    assert (project / created["relativePath"]).read_bytes() == PREFAB.encode("utf-8")


def test_a_mod_without_prefabs_starts_a_blank_one(tmp_path):
    created = create_prefab(tmp_path / "Empty", "", "FirstWindow")
    assert created["relativePath"] == "GUI/Prefabs/FirstWindow.xml"
    assert (tmp_path / "Empty" / created["relativePath"]).read_bytes() == BLANK_PREFAB.encode("utf-8")
    assert [element["tag"] for element in created["elements"]] == ["Prefab", "Window", "Widget"]


@pytest.mark.parametrize("name", ["ShopWindow", "ShopWindow.xml", "../Escape", "", "bad/name"])
def test_a_taken_or_bad_prefab_name_is_refused(project, name):
    with pytest.raises(ValueError):
        create_prefab(project, "GUI/Prefabs/Shop/ShopWindow.xml", name)
    assert (project / "GUI/Prefabs/Shop/ShopWindow.xml").read_bytes() == PREFAB.encode("utf-8")


def test_an_element_copy_follows_it_and_nothing_else_changes(project):
    snapshot = read_prefab(project, "GUI/Prefabs/Shop/ShopWindow.xml")
    widget = next(row for row in snapshot["elements"] if row["tag"] == "Widget")
    result = duplicate_element(project, "GUI/Prefabs/Shop/ShopWindow.xml", widget["path"],
                               source_hash=snapshot["sourceHash"])
    block = ("    <Widget Id=\"Panel\" WidthSizePolicy=\"Fixed\">\r\n"
             "      <TextWidget Text=\"@Title\" />\r\n"
             "    </Widget>")
    text = (project / "GUI/Prefabs/Shop/ShopWindow.xml").read_bytes().decode("utf-8")
    assert text == PREFAB.replace(block, block + "\r\n" + block)
    assert result["created"] == "Prefab[0]/Window[0]/Widget[1]"
    assert [row["tag"] for row in result["elements"]].count("TextWidget") == 2


def test_the_root_and_stale_copies_are_refused(project):
    snapshot = read_prefab(project, "GUI/Prefabs/Shop/ShopWindow.xml")
    with pytest.raises(ValueError):
        duplicate_element(project, "GUI/Prefabs/Shop/ShopWindow.xml", "Prefab[0]")
    with pytest.raises(ValueError):
        duplicate_element(project, "GUI/Prefabs/Shop/ShopWindow.xml", "Prefab[0]/Nothing[0]")
    path = project / "GUI/Prefabs/Shop/ShopWindow.xml"
    path.write_bytes(PREFAB.replace("Panel", "Other").encode("utf-8"))
    with pytest.raises(Exception):
        duplicate_element(project, "GUI/Prefabs/Shop/ShopWindow.xml", "Prefab[0]/Window[0]/Widget[0]",
                          source_hash=snapshot["sourceHash"])
