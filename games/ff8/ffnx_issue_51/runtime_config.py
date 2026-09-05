"""Strict per-mod runtime configuration for the FF8 FFNx derivative."""

from __future__ import annotations

from pathlib import Path
import re


SCHEMA_VERSION = 1
RELATIVE_PATH = Path("direct") / "lexeditor" / "gameplay.toml"
_KEYS = {"schemaVersion", "sharedMagicInventory", "magicStockLimit"}


class RuntimeConfigError(ValueError):
    """Raised when an FF8 runtime configuration is not safe to use."""


def path(project_root: Path) -> Path:
    return Path(project_root).resolve() / RELATIVE_PATH


def _stock_limit(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 255:
        raise RuntimeConfigError("Magic stock limit must be a whole number from 1 to 255")
    return value


def build(*, shared_magic_inventory: bool, magic_stock_limit: int = 100) -> str:
    if not isinstance(shared_magic_inventory, bool):
        raise RuntimeConfigError("Shared Magic Inventory must be true or false")
    enabled = "true" if shared_magic_inventory else "false"
    limit = _stock_limit(magic_stock_limit)
    return (
        f"schemaVersion = {SCHEMA_VERSION}\n"
        f"sharedMagicInventory = {enabled}\n"
        f"magicStockLimit = {limit}\n"
    )


def parse(text: str) -> dict:
    if not isinstance(text, str):
        raise RuntimeConfigError("The FF8 runtime configuration is not valid TOML")
    data = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z][A-Za-z0-9]*)\s*=\s*(\S+)\s*", line)
        if not match or match.group(1) in data:
            raise RuntimeConfigError("The FF8 runtime configuration is not valid TOML")
        key, value = match.groups()
        if key == "schemaVersion" and re.fullmatch(r"\d+", value):
            data[key] = int(value)
        elif key == "sharedMagicInventory" and value in {"true", "false"}:
            data[key] = value == "true"
        elif key == "magicStockLimit" and re.fullmatch(r"\d+", value):
            data[key] = int(value)
        else:
            raise RuntimeConfigError("The FF8 runtime configuration is not valid TOML")
    if set(data) != _KEYS:
        raise RuntimeConfigError("The FF8 runtime configuration has unknown or missing keys")
    if data["schemaVersion"] != SCHEMA_VERSION or isinstance(data["schemaVersion"], bool):
        raise RuntimeConfigError("The FF8 runtime configuration schema is not supported")
    if not isinstance(data["sharedMagicInventory"], bool):
        raise RuntimeConfigError("Shared Magic Inventory must be true or false")
    limit = _stock_limit(data["magicStockLimit"])
    return {
        "schemaVersion": SCHEMA_VERSION,
        "sharedMagicInventory": data["sharedMagicInventory"],
        "magicStockLimit": limit,
    }


def load(project_root: Path) -> dict:
    target = path(project_root)
    if not target.is_file():
        return {"schemaVersion": SCHEMA_VERSION, "sharedMagicInventory": False,
                "magicStockLimit": 100}
    try:
        return parse(target.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError) as error:
        raise RuntimeConfigError(f"The FF8 runtime configuration could not be read: {error}") from error


def write(project_root: Path, *, shared_magic_inventory: bool,
          magic_stock_limit: int = 100) -> Path:
    target = path(project_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        build(shared_magic_inventory=shared_magic_inventory,
              magic_stock_limit=magic_stock_limit),
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(target)
    return target
