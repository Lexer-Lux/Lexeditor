# #222: Casing pickup path

[Live issue](https://github.com/Lexer-Lux/Lexeditor/issues/222)

## Required behavior

Hold E, a ground-pickup animation and the casing acquisition card. Never grant live ammunition. Longarm-held ground reach remains unfinished.

## Source-only repair on 2026-09-08

The current collection code posted the acquisition card and sound, then deleted the casing even when inventory addition failed. The new casing_acquisition.h helper uses count readback to commit acquisition. A failed grant keeps the prop and posts no success card or sound. An unreadable post-grant count keeps the transaction pending without another add. World cleanup can settle an old pending item before a different acquisition begins.

Changed runtime source: GameplayTweaks/modules/items_casings.cpp and new modules/casing_acquisition.h. No game binary or experiment files were changed. This also repairs the false acquisition notification in #174.

Executable harness tools/verify_rdr2_casing_acquisition.py passes the production helper and rejects three mutations: trusting the native flag, forgetting the pending grant and reporting unchanged quantity as success. It covers failed grants, false native flags with successful count change, unreadable counts and repeated pending attempts. The existing casing collection verifier was updated for the helper and passes all 16 contracts.

## Animation evidence and remaining scope

The retained animation index confirms mech_pickup@system@lh contains ground_near, matching the known right-hand dictionary. That proves a left-hand clip exists; it does not prove a raw full-body clip preserves a held rifle pose. No speculative clip substitution was made. The rejected hand-to-mouth consumable interaction remains unused. Longarm animation proof and full delivery/game acceptance remain open.

The #151 experiment is active, so this source patch must not be installed until its original runtime configuration is restored.

## Transaction ownership repair

The pending grant now belongs to a unique token in each SpentCasing state. It cannot be credited to a replacement prop, even for the same item. Every removal path cancels that owner's state; the collection path checks that its object still exists before completing. A second casing cannot grant while another owner's count is unresolved. The world_economy.cpp change is only the helper include and per-casing state member.

The executable test now covers original-prop cleanup, replacement with the same and a different item, state reuse and two live pending casings. Production passes; four mutations are rejected. The 16 collection contracts pass.

Correction to the earlier readback wording: INVENTORY_ITEM_COUNT wraps native 0xE787F05DFC977BDE, documented as returning int but with no documented negative-on-failure contract. Negative-value scenarios test defensive handling only; they do not prove the native signals read failure that way. Actual success still requires observed count growth. No game or experiment files were changed.

Root integrated and built this source with the independent Recon radii. Development build passed, ASI SHA-256 `8AE9385498F96437AFB504381F6B8E34491E3A740D8993C539D89C21B3D7BB2E`. The small candidate is held under `out/rdr2-after-duration`; it is not installed because #151 remains active. No game acceptance is claimed.
