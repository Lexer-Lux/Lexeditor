# GitHub #121 — Dev-only F2/F3 authoring safety

## Requested

- Limit F2 collectible relocation to a configurable maximum distance.
- Restore the accidentally relocated Vistas of America Card 6 marker.
- Compile F2 collectible relocation and F3 campsite placement/removal only in development builds.

## Implementation

- Added `[CollectibleMap] DeveloperMoveMaxDistance`, defaulting to 150 metres.
- F2 now reports and logs a refusal without changing or persisting a marker beyond the limit.
- Wrapped the raw F2 and F3 authoring input paths in `GAMEPLAYTWEAKS_DEV_MODE`; ordinary builds compile them out while `build-dev.bat` retains them.
- Removed the accidental `Vistas of America Card 6` fixup at `-4497.327,-4355.641` from the installed state file, restoring its base CSV position on the next load.

## Verification remaining

- Static/build verification.
- In-game acceptance from the GitHub issue remains required after installation.
