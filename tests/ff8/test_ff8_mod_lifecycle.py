"""One FF8 mod lifecycle headless: install, combine, order, remove.

A folder mod and an installed .iroj archive edit overlapping item prices.
Both load orders compose per record (the Potion collision follows priority
while independent edits survive), the manifest names the winner, and
removing the archive restores the surviving mod's view. Installed-game
acceptance stays uncovered here (see worklog/100.md).
"""
import json
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from plugins.ff8 import iroj_archive, runtime_layout  # noqa: E402

PRICE = "direct/menu/price.bin"


def _price(vanilla: bytes, edits: dict[int, int]) -> bytes:
    raw = bytearray(vanilla)
    for item_id, gil in edits.items():
        raw[item_id * 4:item_id * 4 + 2] = (gil // 10).to_bytes(2, "little")
    return bytes(raw)


def _gil(payload: bytes, item_id: int) -> int:
    return int.from_bytes(payload[item_id * 4:item_id * 4 + 2], "little") * 10


def _write_folder_mod(root: Path, mod_id: str, payload: bytes) -> None:
    (root / "direct" / "menu").mkdir(parents=True, exist_ok=True)
    (root / PRICE).write_bytes(payload)
    (root / runtime_layout.MOD_FILE).write_text(json.dumps({
        "id": mod_id, "name": mod_id.title(), "order": 0, "enabled": True,
    }), encoding="utf-8")


def _archive(path: Path, members: list[tuple[str, bytes]]) -> None:
    # Uncompressed members only; mirrors verify_ff8_iroj_loader._archive.
    encoded = [(name, name.encode("utf-16-le"), plain) for name, plain in members]
    offset = 20 + sum(20 + len(name) for _, name, _ in encoded)
    records, payload = bytearray(), bytearray()
    for _name, name, plain in encoded:
        records += (struct.pack("<HH", 20 + len(name), len(name)) + name
                    + struct.pack("<IqI", 0, offset, len(plain)))
        payload += plain
        offset += len(plain)
    path.write_bytes(struct.pack("<IIIIi", iroj_archive.SIGNATURE, 0x10002, 0, 16, len(encoded))
                     + bytes(records) + bytes(payload))


def test_install_combine_order_remove_cycle(tmp_path):
    project, mods, active = tmp_path / "project", tmp_path / "mods", tmp_path / "active"
    baseline = tmp_path / "baseline"
    (baseline / "menu").mkdir(parents=True)
    vanilla = bytes(8 * 4)
    (baseline / "menu" / "price.bin").write_bytes(vanilla)
    (project / runtime_layout.MOD_FILE).parent.mkdir(parents=True, exist_ok=True)
    (project / runtime_layout.MOD_FILE).write_text(json.dumps({
        "id": "project", "name": "Project", "order": -1, "enabled": True,
    }), encoding="utf-8")

    low_payload = _price(vanilla, {1: 1230, 3: 5670})
    _write_folder_mod(mods / "low", "low", low_payload)
    high_payload = _price(vanilla, {1: 4560, 7: 8910})
    source = tmp_path / "high.iroj"
    _archive(source, [
        ("mod.xml", b"<ModInfo><ID>high</ID><Name>High</Name></ModInfo>"),
        ("direct/menu/price.bin", high_payload),
    ])

    # Install: the archive lands in the library disabled, then catalogs.
    installed = runtime_layout.install_iroj(source, project, mods)
    assert installed["id"] == "high" and installed["enabled"] is False
    assert sorted(row["id"] for row in runtime_layout.catalog(project, mods)) == [
        "high", "low", "project"]

    # Combine: independent edits coexist, the collision follows priority.
    rows = runtime_layout.configure(project, mods, ["project", "low", "high"],
                                    {"project": True, "low": True, "high": True})
    result = runtime_layout.compose(project, active, rows, baseline_root=baseline)
    price = (active / PRICE).read_bytes()
    assert (_gil(price, 1), _gil(price, 3), _gil(price, 7)) == (4560, 5670, 8910)
    conflict = next(row for row in result["conflicts"] if row["path"] == PRICE)
    assert conflict["mode"] == "semantic merge" and conflict["claimants"] == ["low", "high"]
    unit = next(unit for unit in conflict["units"] if unit["unit"].endswith(":record:1:buy_price"))
    assert unit["winner"] == "high" and unit["claimants"] == ["low", "high"]

    # Order: reversing priority flips only the collision.
    rows = runtime_layout.configure(project, mods, ["project", "high", "low"],
                                    {"project": True, "low": True, "high": True})
    result = runtime_layout.compose(project, active, rows, baseline_root=baseline)
    price = (active / PRICE).read_bytes()
    assert (_gil(price, 1), _gil(price, 3), _gil(price, 7)) == (1230, 5670, 8910)
    conflict = next(row for row in result["conflicts"] if row["path"] == PRICE)
    unit = next(unit for unit in conflict["units"] if unit["unit"].endswith(":record:1:buy_price"))
    assert unit["winner"] == "low"

    # Remove: deleting the archive restores the surviving mod's view.
    (mods / "high.iroj").unlink()
    for sidecar in mods.glob("high.iroj.*"):
        sidecar.unlink()
    assert "high" not in {row["id"] for row in runtime_layout.catalog(project, mods)}
    rows = runtime_layout.configure(project, mods, ["project", "low"],
                                    {"project": True, "low": True})
    result = runtime_layout.compose(project, active, rows, baseline_root=baseline)
    price = (active / PRICE).read_bytes()
    assert (_gil(price, 1), _gil(price, 3), _gil(price, 7)) == (1230, 5670, 0)
    assert [row for row in result["conflicts"] if row["path"] == PRICE] == []

    # Disable: with no claimant the file leaves the runtime.
    rows = runtime_layout.configure(project, mods, ["project", "low"],
                                    {"project": True, "low": False})
    runtime_layout.compose(project, active, rows, baseline_root=baseline)
    assert not (active / PRICE).exists()

    # The library keeps the surviving folder mod intact.
    assert (mods / "low" / PRICE).read_bytes() == low_payload
    shutil.rmtree(mods / "low", ignore_errors=True)
