"""Source contract for FF8 item-icon text-relative scaling (GitHub #57)."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))
from tests.shared.plugin_ui import plugin_ui
EDITOR = plugin_ui('ff8')
SHARED_CSS = (ROOT / 'ui/framework.css').read_text(encoding='utf-8')


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require('function itemIcon(item)' in EDITOR and 'return LexeditorUI.inlineLabel(image)' in EDITOR,
        "FF8 item icons must use the shared inline image component")
require('.lex-inline-label > img { width:1.35em; height:1.35em; object-fit:contain;' in SHARED_CSS,
        "Shared inline icons must scale with the surrounding text and preserve aspect ratio")
require("max-width:22px" not in EDITOR and "max-width:28px" not in EDITOR,
        "A fixed-size FF8 item-icon rule remains")
require(".detail-head .ff8-item-icon-slot" not in EDITOR,
        "The detail heading still owns a private pixel icon override")

print("FF8 item-icon scaling issue #57 source contract passed")
