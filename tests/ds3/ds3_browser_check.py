"""Rendered Dark Souls III acceptance against the synthetic regulation fixture."""
from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

from plugins.ds3.formats import encrypt_regulation
from core.service_session import LocalPluginSession, request_json
from test_ds3_plugin import _bnd4, _row_ids


TABLES = (
    ("EquipParamWeapon", "weapons"),
    ("EquipParamProtector", "armor"),
    ("EquipParamAccessory", "rings"),
    ("Magic", "spells"),
    ("SpEffectParam", "effects"),
    ("NpcParam", "enemies"),
)


def field_value(row: dict, key: str):
    return next(field["value"] for field in row["fields"] if field["key"] == key)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    output = Path(argv[0]).resolve() if argv else Path(__import__("tempfile").gettempdir()) / "lexeditor-dev" / "ds3-browser"
    output.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    response_failures: list[str] = []

    with tempfile.TemporaryDirectory(prefix="lexeditor-ds3-browser-") as temp_name:
        temp = Path(temp_name)
        source = temp / "installed-Data0.bdt"
        project = temp / "project"
        project.mkdir()
        (project / ".lexeditor-ds3-project").write_text(
            '{"schema":1,"game":"Dark Souls III"}\n', encoding="utf-8"
        )
        source.write_bytes(encrypt_regulation(_bnd4(), iv=b"\x51" * 16))
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        environment = {
            "LEXEDITOR_DS3_SOURCE": str(source),
            "LEXEDITOR_DS3_PROJECT": str(project),
            "LEXEDITOR_DS3_ROOT": str(temp / "game"),
        }

        session = LocalPluginSession(
            module="plugins.ds3.server",
            plugin_id="ds3",
            app_root=ROOT,
            check=lambda: [],
            extra_env=environment,
        )
        session.start()
        try:
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                page.on("pageerror", lambda error: errors.append(f"pageerror: {error}"))
                page.on(
                    "response",
                    lambda response: response_failures.append(
                        f"{response.status} {response.url}"
                    ) if response.status >= 400 else None,
                )
                page.on(
                    "console",
                    lambda message: errors.append(f"console {message.type}: {message.text}")
                    if message.type == "error" else None,
                )
                page.goto(session.url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_selector('body[data-ds3-ready="true"]', timeout=20000)
                page.wait_for_selector(".lex-column-list .lex-list-row", timeout=10000)

                page.wait_for_selector('[data-ds3-field="atkBasePhysics"]', timeout=10000)
                if page.locator('input[type="checkbox"][data-ds3-field]').count() < 1:
                    raise RuntimeError("Weapons detail did not render boolean checkboxes")
                if page.locator("select[data-ds3-field]").count() < 1:
                    raise RuntimeError("Weapons detail did not render enum selects")

                weapon_id, _ = _row_ids("EquipParamWeapon")
                damage = page.locator('[data-ds3-field="atkBasePhysics"]')
                damage.fill("321")
                damage.press("Tab")
                try:
                    page.wait_for_function(
                        "() => { const button=document.querySelector('#global-save'); return button && !button.disabled; }",
                        timeout=10000,
                    )
                except PlaywrightTimeoutError as error:
                    diagnostics = page.evaluate(
                        """() => ({
                          dirty: typeof state === 'object' ? state.dirty : null,
                          saveDisabled: document.querySelector('#global-save')?.disabled ?? null,
                          saveTitle: document.querySelector('#global-save')?.title ?? null,
                          fieldValue: document.querySelector('[data-ds3-field="atkBasePhysics"]')?.value ?? null,
                          ready: document.body.dataset.ds3Ready || null
                        })"""
                    )
                    diagnostics["apiDirty"] = request_json(session.url + "api/state").get("dirtyCount")
                    diagnostics["browserErrors"] = list(errors)
                    raise RuntimeError(f"DS3 edit did not enable Save: {diagnostics}") from error
                page.screenshot(path=str(output / "weapons-edited.png"), full_page=True)
                page.locator("#global-save").click()
                page.wait_for_function(
                    """() => {
                      const button=document.querySelector('#global-save');
                      return button && button.disabled &&
                        !document.body.classList.contains('lex-save-busy');
                    }""",
                    timeout=10000,
                )
                saved = project / "Data0.bdt"
                if not saved.is_file():
                    raise RuntimeError("Rendered Save did not export project/Data0.bdt")
                row = request_json(
                    session.url + f"api/row?table=EquipParamWeapon&id={weapon_id}"
                )["row"]
                if field_value(row, "atkBasePhysics") != 321:
                    raise RuntimeError("Saved weapon damage did not read back as 321")

                for table, name in TABLES:
                    page.locator(f'button[data-tab="{table}"]').click()
                    page.wait_for_selector(".lex-column-list .lex-list-row", timeout=10000)
                    page.wait_for_selector("#main [data-ds3-field]", timeout=10000)
                    page.screenshot(path=str(output / f"{name}.png"), full_page=True)
                    if table == "Magic" and page.locator("select[data-ds3-field]").count() < 1:
                        raise RuntimeError("Spells screen did not expose enum choices")

                page.locator("#plugin-data-map").click()
                page.wait_for_selector(".lex-data-map", timeout=10000)
                page.screenshot(path=str(output / "data-map.png"), full_page=True)

                page.locator("#plugin-info").click()
                page.wait_for_selector(".lex-information-panel", timeout=10000)
                page.screenshot(path=str(output / "info.png"), full_page=True)

                page.set_viewport_size({"width": 900, "height": 620})
                page.locator('button[data-tab="EquipParamWeapon"]').click()
                page.wait_for_selector(".lex-column-list .lex-list-row", timeout=10000)
                page.screenshot(path=str(output / "weapons-900x620.png"), full_page=True)
                body_overflow = page.evaluate(
                    "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
                )
                if body_overflow > 2:
                    raise RuntimeError(f"DS3 page overflows the 900px viewport by {body_overflow}px")
                browser.close()
        finally:
            session.stop()

        if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
            raise RuntimeError("Browser acceptance modified the installed/source Data0.bdt")

        with LocalPluginSession(
            module="plugins.ds3.server",
            plugin_id="ds3",
            app_root=ROOT,
            check=lambda: [],
            extra_env=environment,
        ) as reopened:
            snapshot = request_json(reopened.url + "api/state")
            if Path(snapshot["source"]).resolve() != (project / "Data0.bdt").resolve():
                raise RuntimeError("Reopen did not prefer the project Data0.bdt")
            row = request_json(
                reopened.url + f"api/row?table=EquipParamWeapon&id={weapon_id}"
            )["row"]
            if field_value(row, "atkBasePhysics") != 321:
                raise RuntimeError("Fresh service did not reopen the exported weapon edit")

    if response_failures:
        errors.extend(f"response: {value}" for value in response_failures)
    if errors:
        print("Browser console/page failures:")
        for error in errors:
            print(" -", error)
        return 1
    print("PASS: DS3 rendered six Table+Detail editors, Data Map and Info")
    print("PASS: semantic checkbox/enum/number controls rendered")
    print("PASS: rendered weapon edit exported through global Save and reopened in a fresh service")
    print("PASS: source Data0.bdt remained byte-identical")
    print(f"PASS: screenshots: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
