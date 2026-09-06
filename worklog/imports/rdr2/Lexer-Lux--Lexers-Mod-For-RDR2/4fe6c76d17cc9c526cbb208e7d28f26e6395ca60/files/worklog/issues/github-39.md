# GitHub #39 — Remove RDO Button

## Reference inspection

- The requested reference was WesternSpace's **Online Button Remover 1.0.0**:
  <https://www.rdr2mods.com/downloads/rdr2/other/351-online-button-remover/>.
- Its archive was downloaded for inspection only. SHA-256:
  `9BBBEB6ED9AB03B967AB71C9E5C97C7159312D6449A4D0EFAB3E5D0667F29605`.
- The package contained `install.xml` plus
  `data/ui/screens/0xA900038B.ymt`. Its manifest mapped the complete
  `update:/x64/data/ui/screens` directory through LML.
- The YMT defined the `ROOT_INDEX` / `pause_root_index` stack, retained eleven
  non-Online entries including Social Club, and omitted the Online entry. Its
  SHA-256 was
  `A0607998A5093AB0F365F963DD1E5839B00520046B8A0766CD26DE8509728FFD`.
- The reference was published in March 2023. Its Nexus permissions explicitly
  prohibited re-upload, modification without permission, and asset reuse
  without permission, so its files were not added to this repository.

## Current-vanilla extraction attempt

- The current game install exposed the update UI screen archive as
  `update_platform:/x64/data/ui/screens.rpf`, physical cache entry
  `0xFB77933A.rpf`.
- The project's current RPF8 CLI and extracted `pfm.dat`/nested update archive
  could open the cache record but could not resolve `0xA900038B.ymt`. Its key
  dump produced invalid-looking entry sizes/offsets, and a bulk extraction did
  not complete within the time box. Direct base/update archive attempts also
  did not resolve the asset.
- OpenIV is installed, but it exposes no command-line extraction operation;
  opening its GUI would violate the no-visible-control rule for this worker.
- Therefore no current-vanilla `0xA900038B.ymt` was obtained, and no package was
  created. Reconstructing the whole screen from the restricted 2023 reference
  would be an unverified stale override and would violate project release
  policy.

## Installed-mod conflict audit

- The live `lml/mods.xml` had no Online-button package.
- `SnappyUI` replaced only `update:/common/data/ui/durations.xml`; it did not
  touch `update:/x64/data/ui/screens/0xA900038B.ymt`.
- No installed LML `install.xml` targeted this screen asset, so there was no
  direct file conflict at the time of inspection.
- `mods.xml` still listed several packages whose directories were temporarily
  absent from `lml`; those stale entries did not provide an asset-level
  conflict result and must be rechecked when those packages are restored.

## Handoff and acceptance boundary

- Required next step: with the game closed, export the current
  `update:/x64/data/ui/screens/0xA900038B.ymt` through OpenIV, remove only the
  Online `UITemplateInstancingItem`, and map that exact file through an isolated
  LML package.
- Static acceptance: the derived file differs from current vanilla by exactly
  one removed Online item; Social Club and every other pause-root item remain;
  both XML files parse; no other installed package targets the same game path.
- Runtime acceptance: in Story Mode, open Pause and confirm the Online entry is
  absent, all neighboring entries still select and navigate correctly, Social
  Club remains available, Back resumes the game, and reopening Pause remains
  stable.
- Nothing was installed, RDR2 was not launched, and GitHub state was not
  changed.
