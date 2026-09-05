"""Verify issue #51's strict, default-off per-mod runtime configuration."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8.ffnx_issue_51 import runtime_config  # noqa: E402


def rejected(text: str) -> None:
    try:
        runtime_config.parse(text)
    except runtime_config.RuntimeConfigError:
        return
    raise AssertionError(f"unsafe runtime configuration was accepted: {text!r}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-shared-magic-config-", ignore_cleanup_errors=True) as temp:
        project = Path(temp) / "mod"
        default = runtime_config.load(project)
        assert default == {"schemaVersion": 1, "sharedMagicInventory": False,
                           "magicStockLimit": 100}
        target = runtime_config.write(
            project, shared_magic_inventory=True, magic_stock_limit=255,
        )
        assert target == project.resolve() / "direct" / "lexeditor" / "gameplay.toml"
        assert target.read_text(encoding="utf-8") == (
            "schemaVersion = 1\nsharedMagicInventory = true\nmagicStockLimit = 255\n"
        )
        assert runtime_config.load(project)["sharedMagicInventory"] is True
        assert runtime_config.load(project)["magicStockLimit"] == 255
        runtime_config.write(project, shared_magic_inventory=False)
        assert runtime_config.load(project)["sharedMagicInventory"] is False

    for bad in (
        "",
        "schemaVersion = 2\nsharedMagicInventory = false\nmagicStockLimit = 100\n",
        "schemaVersion = true\nsharedMagicInventory = false\nmagicStockLimit = 100\n",
        "schemaVersion = 1\nsharedMagicInventory = 1\nmagicStockLimit = 100\n",
        "schemaVersion = 1\nsharedMagicInventory = false\nmagicStockLimit = 100\nextra = true\n",
        "sharedMagicInventory = false\n",
        "schemaVersion = 1\nsharedMagicInventory = false\n",
        "schemaVersion = 1\nsharedMagicInventory = false\nmagicStockLimit = 0\n",
        "schemaVersion = 1\nsharedMagicInventory = false\nmagicStockLimit = 256\n",
    ):
        rejected(bad)
    try:
        runtime_config.build(shared_magic_inventory=1)
    except runtime_config.RuntimeConfigError:
        pass
    else:
        raise AssertionError("numeric shared-Magic value was accepted as a boolean")

    print("FF8 shared magic issue #51: strict per-mod runtime config verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
