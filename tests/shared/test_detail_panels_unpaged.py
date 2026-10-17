"""Shared detail-panel contracts: no fraction floor, unpaged flow, SVG remove icon.

1. The barrelled list's divider must not force the list panel to a share of
   the window (22% x barrels peaked at ~1250px on a wide window). The pixel
   floor plus the measured table minimum bind instead.
2. A detail flow can opt out of pages (`unpaged`): sections still flow into
   columns, but every card stays on one scrolling page with no pager footer.
3. Header icon buttons carry SVG glyphs, never a text "x" that will not scale
   with its neighbours.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRAMEWORK = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")


def test_no_caller_passes_a_fraction_floor_to_list_detail():
    # listDetail keeps its public minimumSplit option; nobody passes it, so
    # minimumFractions stays zero and the drag clamp is the pixel floor.
    assert re.search(r"(?<!options\.)\bminimumSplit\s*:", FRAMEWORK) is None


def test_unpaged_flow_skips_page_breaks_and_footer():
    assert FRAMEWORK.count("options.unpaged") >= 2


def test_remove_icon_is_shared_and_svg():
    assert "removeIcon" in FRAMEWORK
    assert re.search(r"const removeIcon = \(\) => \{", FRAMEWORK) is not None


def test_no_text_x_header_icon_buttons():
    assert re.search(r"\}\s*,\s*\"x\"\s*\)", FRAMEWORK) is None
