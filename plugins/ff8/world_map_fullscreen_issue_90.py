"""Full-screen world-map contract for GitHub issue #90.

Owner-approved design (no new drawing, no spoiler database, no fast travel):

- The map base is the game's own art: the 20 fixed ``texl.obj`` TIM textures
  (``world_textures.TEXTURE_COUNT`` slots of ``world_textures.SLOT_SIZE``
  bytes). Terrain and coastline stay always visible because they are baked
  into that art; there is no fog-of-war drawing and no separate map database.
- Discovery covers labels and markers only. A location name or point of
  interest becomes visible once visited or once a Journal entry explicitly
  reveals it. Coordinates existing in game data never reveal anything alone.
- Markers reuse data Lexeditor already parses: the 64 field-to-world
  position records (``world_map`` section 9) and the 128 fixed Draw Point
  records (``world_map`` section 34). Quest-marker targets come from Journal
  stage data, never from duplicated story checks.
- Selecting a location creates a navigation waypoint only. It never
  fast-travels, never changes story flags, party location, or vehicle
  ownership.
- The tweak requires Modern Controls. L1 (or equivalent) opens the Journal
  screen, R1 (or equivalent) opens the map.
- Safety invariants: opening/closing the map moves nothing; overlay input
  never drives live vehicle movement; discovery and the waypoint persist in
  versioned mod-owned state without touching vanilla save bytes; missing
  Journal or Modern Controls features degrade gracefully to pan/zoom over
  the base map.

No proved native overlay injection points exist yet, so this module emits no
executable bytes and activation fails closed until they do.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

from . import world_map, world_textures


DEFAULT_WORLD_MAP_FULLSCREEN = False

# No proved native overlay hooks exist, so enabling must fail closed rather
# than install guessed bytes. Flip to True only with verified injection
# points and the matching build_hext() fragment.
WORLD_MAP_FULLSCREEN_AVAILABLE = False
WORLD_MAP_FULLSCREEN_BLOCKER = (
    "The full-screen world map has no proved native overlay hooks yet, "
    "so it cannot be enabled. Discovery and waypoint state below remain "
    "editable so authored positions stay valid for the future overlay."
)

# Owner-confirmed bindings. L1 opens the Journal screen, R1 opens the map.
# Both require the Modern Controls input layer; the map must not introduce a
# second controller implementation.
JOURNAL_BUTTON = "L1"
MAP_BUTTON = "R1"
REQUIRES_MODERN_CONTROLS = True

# Base-layer facts. Terrain is always visible because it is the game's own
# texl.obj art, never a separate database this module could spoil.
MAP_TEXTURE_SLOTS = world_textures.TEXTURE_COUNT
MAP_TEXTURE_SLOT_SIZE = world_textures.SLOT_SIZE
FIELD_RETURN_SECTION = world_map.FIELD_RETURN_SECTION
DRAW_POINT_SECTION = world_map.DRAW_SECTION
EXPECTED_FIELD_RETURN_COUNT = 64
EXPECTED_DRAW_POINT_COUNT = world_map.DRAW_POINT_COUNT

STATE_VERSION = 1
STATE_RELATIVE = Path("world") / "fullscreen_map_state.json"

MARKER_KINDS = ("location", "drawPoint", "quest", "vehicle", "waypoint")


def state_path(project_root: Path) -> Path:
    """Mod-owned discovery/waypoint state; never vanilla save bytes."""
    return Path(project_root).resolve() / STATE_RELATIVE


def blank_state() -> dict:
    """Versioned empty state: nothing discovered, no waypoint."""
    return {"version": STATE_VERSION, "visited": [], "revealed": [],
            "waypoint": None}


def _clean_ids(values, label: str) -> list[str]:
    if not isinstance(values, list):
        raise ValueError(f"Full-screen map {label} must be a list")
    cleaned = []
    for value in values:
        if not isinstance(value, str) or not value:
            raise ValueError(f"Full-screen map {label} entries must be non-empty strings")
        if value not in cleaned:
            cleaned.append(value)
    return cleaned


def _clean_waypoint(value) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Full-screen map waypoint must be an object or null")
    marker_id = value.get("id")
    kind = value.get("kind")
    if not isinstance(marker_id, str) or not marker_id:
        raise ValueError("Full-screen map waypoint needs a non-empty string id")
    if kind not in MARKER_KINDS:
        raise ValueError(
            f"Full-screen map waypoint kind must be one of {', '.join(MARKER_KINDS)}")
    for axis in ("x", "y"):
        coordinate = value.get(axis)
        if not isinstance(coordinate, (int, float)) or isinstance(coordinate, bool):
            raise ValueError(f"Full-screen map waypoint {axis} must be a number")
    return {"id": marker_id, "kind": kind,
            "x": value["x"], "y": value["y"]}


def validate_state(state: dict) -> dict:
    """Return a cleaned copy; reject wrong shapes instead of guessing."""
    if not isinstance(state, dict):
        raise ValueError("Full-screen map state must be an object")
    if state.get("version") != STATE_VERSION:
        raise ValueError(
            f"Full-screen map state version must be {STATE_VERSION}")
    return {
        "version": STATE_VERSION,
        "visited": _clean_ids(state.get("visited", []), "visited"),
        "revealed": _clean_ids(state.get("revealed", []), "revealed"),
        "waypoint": _clean_waypoint(state.get("waypoint")),
    }


def load_state(path: Path) -> dict:
    """Read mod-owned state; corrupt or unknown files recover to blank."""
    try:
        return validate_state(json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return blank_state()


def save_state(path: Path, state: dict) -> dict:
    """Atomically persist validated state; return what was written."""
    cleaned = validate_state(state)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=str(destination.parent),
            prefix=destination.name + ".", suffix=".tmp",
            delete=False) as stream:
        stream.write(json.dumps(cleaned, indent=2, sort_keys=True) + "\n")
        temporary = Path(stream.name)
    temporary.replace(destination)
    return cleaned


def mark_visited(state: dict, marker_id: str) -> dict:
    """Record a visited marker; validated on write, not here."""
    cleaned = validate_state(state)
    if not isinstance(marker_id, str) or not marker_id:
        raise ValueError("Full-screen map marker id must be a non-empty string")
    if marker_id not in cleaned["visited"]:
        cleaned["visited"].append(marker_id)
    return cleaned


def mark_revealed(state: dict, marker_id: str) -> dict:
    """Record a Journal-revealed marker without implying a visit."""
    cleaned = validate_state(state)
    if not isinstance(marker_id, str) or not marker_id:
        raise ValueError("Full-screen map marker id must be a non-empty string")
    if marker_id not in cleaned["revealed"]:
        cleaned["revealed"].append(marker_id)
    return cleaned


def set_waypoint(state: dict, marker: dict) -> dict:
    """Select a marker as a navigation waypoint only.

    The waypoint is a label and coordinates. It never fast-travels, never
    changes story flags, party location, or vehicle ownership: this function
    writes the ``waypoint`` key and nothing else.
    """
    cleaned = validate_state(state)
    if not isinstance(marker, dict):
        raise ValueError("Full-screen map waypoint marker must be an object")
    cleaned["waypoint"] = _clean_waypoint({
        "id": marker.get("id"), "kind": marker.get("kind"),
        "x": marker.get("x"), "y": marker.get("y")})
    return cleaned


def clear_waypoint(state: dict) -> dict:
    """Remove the waypoint; discovery is untouched."""
    cleaned = validate_state(state)
    cleaned["waypoint"] = None
    return cleaned


def markers_from_world(parsed: dict) -> list[dict]:
    """Build markers from already-parsed world data; no new database.

    Locations come from the field-to-world records, optional points of
    interest from the Draw Point records. Terrain needs no markers: it is
    the texl.obj base layer and is always visible.
    """
    if not isinstance(parsed, dict):
        raise ValueError("Full-screen map markers need parsed world data")
    field_returns = parsed.get("fieldReturns")
    draw_points = parsed.get("drawPoints")
    if not isinstance(field_returns, list) or not isinstance(draw_points, list):
        raise ValueError(
            "Full-screen map markers need fieldReturns and drawPoints rows")
    markers = []
    for record in field_returns:
        markers.append({
            "id": f"location:{record['id']}",
            "kind": "location",
            "name": record.get("name", f"Field return {record['id']}"),
            "x": record["x"], "y": record["y"],
        })
    for record in draw_points:
        markers.append({
            "id": f"drawPoint:{record['id']}",
            "kind": "drawPoint",
            "name": record.get("name", f"Draw Point {record['id']}"),
            "x": record["x"], "y": record["y"],
        })
    return markers


def visible_markers(markers: list[dict], state: dict,
                    journal_revealed: tuple[str, ...] = ()) -> list[dict]:
    """Labels visible once visited or Journal-revealed; terrain is separate.

    Coordinates alone never reveal a label: a marker is visible only when its
    id is in visited, in revealed, or in the Journal-provided reveal set.
    """
    cleaned = validate_state(state)
    if not isinstance(markers, list):
        raise ValueError("Full-screen map markers must be a list")
    known = set(cleaned["visited"]) | set(cleaned["revealed"]) | set(journal_revealed)
    return [marker for marker in markers if marker.get("id") in known]


def requirement_errors(*, enabled: bool, modern_controls: bool) -> list[str]:
    """Activation blockers in dependency order; empty means no objection."""
    if not isinstance(enabled, bool):
        raise ValueError("Full-screen World Map must be true or false")
    if not isinstance(modern_controls, bool):
        raise ValueError("Modern Controls must be true or false")
    if not enabled:
        return []
    if not modern_controls:
        return ["Full-screen World Map requires Modern Controls"]
    if not WORLD_MAP_FULLSCREEN_AVAILABLE:
        return [WORLD_MAP_FULLSCREEN_BLOCKER]
    return []


def build_hext(enabled: bool, modern_controls: bool = False) -> str:
    """Return the Hext fragment, or no bytes while hooks are unproved.

    Enabling without Modern Controls, or while the overlay has no proved
    native hooks, raises instead of installing guessed bytes.
    """
    errors = requirement_errors(
        enabled=enabled, modern_controls=modern_controls)
    if errors:
        raise ValueError(errors[0])
    if not enabled:
        return ""
    return "# Full-screen World Map uses the proved overlay hooks; no guess bytes.\n"
