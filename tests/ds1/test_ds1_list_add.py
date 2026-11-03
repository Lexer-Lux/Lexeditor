"""DS1 record lists show no add button; creation lives in headers.

Records duplicate from the detail header, and asset files join the
mod through + in the file header, so the list's own add button -
which sat dead on every record tab - is gone.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ds1_value_undo import running_app  # noqa: E402


def test_record_list_has_no_add_button():
    with running_app() as (page, errors):
        assert page.locator("#main .lex-table-add").count() == 0
        assert page.locator('#main [data-row-action="duplicate"]').count() >= 1
        assert errors == [], errors[:3]


def test_asset_detail_header_offers_upload():
    with running_app() as (page, errors):
        page.evaluate("navigate('textures')")
        upload = page.locator(
            '#main .lex-detail-panel-actions [aria-label="Add file to mod"]')
        upload.wait_for(timeout=15000)
        assert page.locator("#main .lex-table-add").count() == 0
        assert errors == [], errors[:3]
