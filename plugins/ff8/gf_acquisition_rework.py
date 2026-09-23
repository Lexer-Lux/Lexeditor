"""Guardian Force acquisition without Draw for GitHub issue #318.

Owner-approved rule (a tweak named "GF Acquisition Rework"):

- The six drawable GFs are awarded automatically on winning the fight that
  makes them available in vanilla, when they are not already owned: Siren on
  Elvoret, Carbuncle on Iguion, Leviathan on NORG, Pandemona on Fujin,
  Alexander on Edea, and Eden on Ultima Weapon.
- A GF missed at its primary fight is recovered at the game's existing Disc 4
  recovery boss instead of through Draw: Siren on Tri-Point, Carbuncle on
  Krysta, Leviathan on Trauma, Pandemona on Red Giant, Alexander on
  Catoblepas, and Eden on Tiamat.
- While the tweak is on, formerly drawable GFs are not offered as Draw
  results; ordinary spell Draw is unaffected.
- Awards use the normal GF-owned state, so they never duplicate or reset
  learned abilities, and disabling the tweak later never revokes a GF.
- Every other GF keeps its native acquisition path; this is not a giveaway.

Boss labels below are the canonical names from the approved acquisition map.
No proved battle-victory hook, Draw-list filter hook, or GF-owned save
offsets exist yet, so this module owns the separable decision logic and its
tests, while activation fails closed until the native points are proved.
"""

from __future__ import annotations

TWEAK_NAME = "GF Acquisition Rework"

DEFAULT_GF_ACQUISITION_REWORK = False

# No proved battle-victory award hook, Draw-list filter hook, or GF-owned
# save offsets exist, so enabling must fail closed rather than install
# guessed bytes. Flip to True only with verified injection points and the
# matching build_hext() fragment.
GF_ACQUISITION_AVAILABLE = False
GF_ACQUISITION_BLOCKER = (
    "GF Acquisition Rework has no proved battle-victory or Draw-list hooks "
    "yet, so it cannot be enabled. The acquisition map below stays valid "
    "for the future hooks."
)

# Drawable in vanilla; awarded on victory while the tweak is on.
PRIMARY_VICTORY = {
    "Siren": "Elvoret",
    "Carbuncle": "Iguion",
    "Leviathan": "NORG",
    "Pandemona": "Fujin",
    "Alexander": "Edea",
    "Eden": "Ultima Weapon",
}

# The game's existing Disc 4 recovery bosses, minus the Draw dependency.
RECOVERY_VICTORY = {
    "Siren": "Tri-Point",
    "Carbuncle": "Krysta",
    "Leviathan": "Trauma",
    "Pandemona": "Red Giant",
    "Alexander": "Catoblepas",
    "Eden": "Tiamat",
}

# Native acquisition paths; the tweak never touches these.
UNCHANGED_GFS = (
    "Quezacotl", "Shiva", "Ifrit", "Brothers", "Diablos", "Cerberus",
    "Doomtrain", "Cactuar", "Tonberry", "Bahamut",
)

DRAWN_GFS = tuple(PRIMARY_VICTORY)
KNOWN_GFS = frozenset(DRAWN_GFS) | frozenset(UNCHANGED_GFS)


def _clean_owned(owned) -> set[str]:
    """Validate an owned-GF collection; reject unknown names."""
    if isinstance(owned, str) or not isinstance(owned, (list, tuple, set, frozenset)):
        raise ValueError("Owned GFs must be a collection of GF names")
    cleaned = set()
    for name in owned:
        if not isinstance(name, str) or name not in KNOWN_GFS:
            raise ValueError(f"Unknown GF: {name!r}")
        cleaned.add(name)
    return cleaned


def _clean_defeated(defeated: str) -> str:
    if isinstance(defeated, bool) or not isinstance(defeated, str) or not defeated:
        raise ValueError("Defeated boss must be a non-empty name")
    return defeated


def awards_for_victory(defeated: str, owned) -> list[str]:
    """Return GFs the victory awards: missing and owed at this boss.

    Unknown bosses award nothing; an unknown encounter must never grant a
    GF. Owned GFs are never re-awarded, so abilities are never reset.
    """
    boss = _clean_defeated(defeated)
    have = _clean_owned(owned)
    awards = []
    for gf in DRAWN_GFS:
        if gf in have:
            continue
        if PRIMARY_VICTORY[gf] == boss or RECOVERY_VICTORY[gf] == boss:
            awards.append(gf)
    return awards


def apply_victory(owned, defeated: str) -> list[str]:
    """Return owned plus the victory awards, preserving owned order.

    Awards only append; nothing is ever removed, so disabling the tweak
    later keeps every legitimately acquired GF.
    """
    boss = _clean_defeated(defeated)
    have = _clean_owned(owned)
    ordered = [name for name in owned if name in have]
    for gf in awards_for_victory(boss, have):
        ordered.append(gf)
    return ordered


def filter_draw_entries(entries: list[dict]) -> list[dict]:
    """Drop GF entries from a Draw list; ordinary spell entries keep order.

    Unknown entry kinds raise instead of passing through: a GF under an
    unrecognized label must not slip back into the Draw results.
    """
    if not isinstance(entries, list):
        raise ValueError("Draw entries must be a list")
    kept = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Draw entries must be objects")
        kind = entry.get("kind")
        entry_id = entry.get("id")
        if kind not in ("spell", "gf"):
            raise ValueError(f"Unknown Draw entry kind: {kind!r}")
        if not isinstance(entry_id, str) or not entry_id:
            raise ValueError("Draw entries need a non-empty string id")
        if kind == "spell":
            kept.append(entry)
    return kept


def requirement_errors(*, enabled: bool) -> list[str]:
    """Activation blockers; empty means no objection."""
    if not isinstance(enabled, bool):
        raise ValueError(f"{TWEAK_NAME} must be true or false")
    if not enabled:
        return []
    if not GF_ACQUISITION_AVAILABLE:
        return [GF_ACQUISITION_BLOCKER]
    return []


def build_hext(enabled: bool) -> str:
    """Return the Hext fragment, or no bytes while hooks are unproved.

    Enabling while the battle-victory and Draw-list hooks are unproved
    raises instead of installing guessed bytes.
    """
    errors = requirement_errors(enabled=enabled)
    if errors:
        raise ValueError(errors[0])
    if not enabled:
        return ""
    return "# GF Acquisition Rework uses the proved victory and Draw hooks; no guess bytes.\n"
