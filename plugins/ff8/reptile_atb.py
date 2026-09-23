"""Per-mod reptile classification and ATB response for FF8 issue #323.

Reptile is Lexeditor metadata, not a bit stolen from c0m*.dat. Runtime enemy
identity uses the game's stable one-byte com_file_id, so the same project data
can be consumed by the FFNx derivative without rewriting enemy binaries.
"""
from __future__ import annotations

from pathlib import Path
import re


SCHEMA_VERSION = 1
RELATIVE_PATH = Path("direct") / "lexeditor" / "reptile-atb.toml"
FIRE_ELEMENT = 0x01
ICE_ELEMENT = 0x02
FIRE_MULTIPLIER = 1.08
ICE_MULTIPLIER = 0.92
MIN_ENEMY_ID = 0
MAX_ENEMY_ID = 254  # 0xFF is the battle engine's empty-slot sentinel.
_KEYS = {"schemaVersion", "enabled", "enemyIds"}


class ReptileAtbError(ValueError):
    """Raised when reptile metadata is malformed or unsafe."""


def path(project_root: Path) -> Path:
    return Path(project_root).resolve() / RELATIVE_PATH


def enemy_ids(values) -> list[int]:
    if values is None:
        return []
    if not isinstance(values, (list, tuple, set, frozenset)):
        raise ReptileAtbError("Reptile enemy IDs must be a list")
    result: set[int] = set()
    for value in values:
        if isinstance(value, bool):
            raise ReptileAtbError("Reptile enemy IDs must be whole numbers")
        try:
            enemy_id = int(value)
        except (TypeError, ValueError) as error:
            raise ReptileAtbError("Reptile enemy IDs must be whole numbers") from error
        if str(value).strip() != str(enemy_id) and not isinstance(value, int):
            raise ReptileAtbError("Reptile enemy IDs must be whole numbers")
        if not MIN_ENEMY_ID <= enemy_id <= MAX_ENEMY_ID:
            raise ReptileAtbError("Reptile enemy IDs must be from 0 to 254")
        result.add(enemy_id)
    return sorted(result)


def _quoted_csv(values: list[int]) -> str:
    return '"' + ",".join(str(value) for value in values) + '"'


def build(*, enabled: bool, reptile_enemy_ids=()) -> str:
    if not isinstance(enabled, bool):
        raise ReptileAtbError("Reptile ATB must be true or false")
    ids = enemy_ids(reptile_enemy_ids)
    return (
        f"schemaVersion = {SCHEMA_VERSION}\n"
        f"enabled = {'true' if enabled else 'false'}\n"
        f"enemyIds = {_quoted_csv(ids)}\n"
    )


def parse(text: str) -> dict:
    if not isinstance(text, str):
        raise ReptileAtbError("The Reptile ATB configuration is not valid TOML")
    data: dict[str, object] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z][A-Za-z0-9]*)\s*=\s*(.+?)\s*", line)
        if not match or match.group(1) in data:
            raise ReptileAtbError("The Reptile ATB configuration is not valid TOML")
        key, token = match.groups()
        if key == "schemaVersion" and re.fullmatch(r"\d+", token):
            data[key] = int(token)
        elif key == "enabled" and token in {"true", "false"}:
            data[key] = token == "true"
        elif key == "enemyIds" and len(token) >= 2 and token[0] == token[-1] == '"':
            body = token[1:-1]
            if body and not re.fullmatch(r"\d+(?:,\d+)*", body):
                raise ReptileAtbError("The Reptile ATB enemy ID list is invalid")
            data[key] = [] if not body else [int(value) for value in body.split(",")]
        else:
            raise ReptileAtbError("The Reptile ATB configuration is not valid TOML")
    if set(data) != _KEYS:
        raise ReptileAtbError("The Reptile ATB configuration has unknown or missing keys")
    if data["schemaVersion"] != SCHEMA_VERSION or isinstance(data["schemaVersion"], bool):
        raise ReptileAtbError("The Reptile ATB configuration schema is not supported")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "enabled": data["enabled"],
        "enemyIds": enemy_ids(data["enemyIds"]),
    }


def load(project_root: Path) -> dict:
    target = path(project_root)
    if not target.is_file():
        return {"schemaVersion": SCHEMA_VERSION, "enabled": False, "enemyIds": []}
    try:
        return parse(target.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError) as error:
        raise ReptileAtbError(f"The Reptile ATB configuration could not be read: {error}") from error


def write(project_root: Path, *, enabled: bool, reptile_enemy_ids=()) -> Path:
    target = path(project_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        build(enabled=enabled, reptile_enemy_ids=reptile_enemy_ids),
        encoding="utf-8", newline="\n",
    )
    temporary.replace(target)
    return target


def payload(project_root: Path) -> dict:
    data = load(project_root)
    return {
        "enabled": data["enabled"],
        "enemyIds": data["enemyIds"],
        "iceMultiplier": ICE_MULTIPLIER,
        "fireMultiplier": FIRE_MULTIPLIER,
        "path": str(path(project_root)),
    }


def after_element(current: float, element_mask: int) -> float:
    """Apply one resolved move's cumulative Reptile speed modifier."""
    result = float(current)
    mask = int(element_mask) & 0xFF
    if mask & ICE_ELEMENT:
        result *= ICE_MULTIPLIER
    if mask & FIRE_ELEMENT:
        result *= FIRE_MULTIPLIER
    return result
