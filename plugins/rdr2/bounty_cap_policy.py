"""Configurable maximum-bounty policy contract (#228).

Issue 228 asks for configurable bounty maxima. The recovered vanilla
path selects story-progression caps of 30000, 50000 and 150000 (network
mode returns -1) and clamps through func_790 before the live and
persisted writes, so a working replacement must drive both layers from
one configured amount. No verified hook exists yet.

This module records the vanilla reference values and validates a
cap-policy configuration: bounded per-region currency maxima with an
explicit conversion, one amount reaching both engine and regional clamp,
preserved existing bounties on disable, and fail-closed unknown builds.
No gameplay claim: the tag198 extraction path, the guarded patch design
and game-side proof are still owed.
"""

from __future__ import annotations

from collections.abc import Mapping
import copy

# Vanilla cap selector reference (short_update func_2107): story
# progression selects one of these; network mode returns -1.
VANILLA_CAPS = (30000, 50000, 150000)
NETWORK_CAP = -1

# Sane absolute bound for a configured maximum, in whole dollars.
MAX_CONFIGURED_CAP = 1000000


def vanilla_caps() -> list[int]:
    """Return an independent copy of the vanilla cap reference."""
    return list(VANILLA_CAPS)


def validate_cap_policy(config: Mapping) -> list[str]:
    """Check a maximum-bounty policy configuration."""
    errors: list[str] = []
    if not isinstance(config, Mapping):
        return ["Cap policy must be a mapping."]
    if config.get("build_fingerprint") in (None, ""):
        errors.append(
            "Cap policy must name a supported script fingerprint and "
            "fail closed on unknown builds."
        )
    maxima = config.get("maxima")
    if not isinstance(maxima, Mapping) or not maxima:
        return errors + ["Cap policy must map at least one region to a maximum."]
    for region, amount in maxima.items():
        if not isinstance(amount, int) or isinstance(amount, bool):
            errors.append(
                f"Region {region!r} maximum must be whole dollars."
            )
            continue
        if amount <= 0 or amount > MAX_CONFIGURED_CAP:
            errors.append(
                f"Region {region!r} maximum must stay within "
                f"1..{MAX_CONFIGURED_CAP} dollars."
            )
    if config.get("conversion") in (None, ""):
        errors.append(
            "Cap policy must state the explicit currency conversion."
        )
    if config.get("applies_to") != ("engine", "regional_clamp"):
        errors.append(
            "One configured amount must reach both the engine and the "
            "regional clamp; driving one layer alone is overwritten."
        )
    if config.get("on_disable") != "preserve":
        errors.append(
            "Disabling must preserve existing bounties, never zero them."
        )
    return errors

def validate_enforcement_proof(proof: Mapping) -> list[str]:
    """Check game-side proof that a configured cap clamps both layers."""
    errors: list[str] = []
    if not isinstance(proof, Mapping):
        return ["Enforcement proof must be a mapping."]
    configured = proof.get("configured_maximum")
    if not isinstance(configured, int) or isinstance(configured, bool):
        return ["Enforcement proof must state the configured whole-dollar maximum."]
    if configured <= 0 or configured > MAX_CONFIGURED_CAP:
        errors.append(
            f"Configured maximum must stay within 1..{MAX_CONFIGURED_CAP} dollars."
        )
    layers = proof.get("layers")
    if not isinstance(layers, Mapping):
        return errors + ["Enforcement proof must record both clamp layers."]
    for layer in ("engine", "regional_clamp"):
        if layers.get(layer) != configured:
            errors.append(
                f"Layer {layer} must clamp at the configured {configured} dollars."
            )
    if proof.get("pre_existing_bounties") != "preserved":
        errors.append("Pre-existing bounties must be preserved, never zeroed.")
    return errors
