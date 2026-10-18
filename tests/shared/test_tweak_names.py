"""Tweaks tab panels carry the mod's own name, as the Mods tab does."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def ui():
    return (ROOT / 'ui' / 'framework.js').read_text(encoding='utf-8', errors='replace')


def test_tweak_heading_uses_mod_name():
    source = ui()
    assert 'tweakPanel(row.name, schema.help, toggle, body, blocker)' in source
    assert 'schema.title || row.name' not in source
