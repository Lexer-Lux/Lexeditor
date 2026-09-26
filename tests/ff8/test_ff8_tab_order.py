"""The FF8 page strip lists its pages in alphabetical order.

Lexer: "also. the tabs aren't alphabetically sorted anymore. wtf?" The shell
keeps the order a plugin declares, so the order lives in the plugin's own page
list. This reads that list and checks the reader meets the pages in the
alphabetical order every other editor uses.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def declared_pages() -> list[tuple[str, str]]:
    source = (ROOT / "plugins" / "ff8" / "boot.js").read_text(encoding="utf-8")
    match = re.search(r"tabs:\[(.*?)\]\.map\(", source, re.S)
    assert match, "the FF8 page list was not found in boot.js"
    return [(identifier, label) for identifier, label
            in re.findall(r'\["([a-z0-9_]+)","([^"]+)"\]', match.group(1))]


def test_pages_are_alphabetical():
    pages = declared_pages()
    assert len(pages) >= 18, pages
    labels = [label for _identifier, label in pages]
    # Tweaks is the tab the shell sets apart at the end, so it is not part of
    # the alphabetical run the reader scans.
    run = [label for label in labels if label != "Tweaks"]
    assert run == sorted(run, key=str.lower), run
    assert labels[-1] == "Tweaks", labels


def test_every_page_is_declared_once():
    pages = declared_pages()
    identifiers = [identifier for identifier, _label in pages]
    assert len(identifiers) == len(set(identifiers)), identifiers
    assert "starting" in identifiers, identifiers
    assert {"cards", "items", "world", "gfs", "textures"} <= set(identifiers), identifiers
