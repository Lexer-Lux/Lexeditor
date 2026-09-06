# GitHub #27 — Remove Startup Movies/Disclaimers

## Implementation

- Added an isolated LML package under `SkipStartup/`.
- Replaced `update:/common/movies/rockstar_logos.bk2` and its 4K variant with
  an original silent black Bink 2 movie: 640x480, 30 fps, 3 frames, 0.1 seconds.
- Generated the movie from a synthetic black AVI using the official RAD Video
  Tools 2026.06 encoder downloaded from Epic/RAD. The downloaded archive's SHA-1
  matched the publisher's listed `76e7b8e41c36edf9aba68ebc6d872871f5a1c5c5`.
- Copied the current vanilla update `ui/durations.xml` and changed only
  `LEGAL_SCREENS_DURATION`, from `4` to `0.00001` seconds.
- Used LML's required doubled local Bink extension (`.bk2.bk2`).

## Static verification

- Both replacement movies were byte-identical and SHA-256
  `5F6329343B88E3932C666AC5CFED6A5B5FACA88D932AC37D0EC4F6F314090201`.
- RAD Video Tools decoded the generated Bink back to a 640x480, three-frame,
  0.1-second raw AVI successfully.
- `install.xml` and `durations.xml` parsed as XML.
- A structural comparison against the vanilla update file showed the legal
  duration value as the only XML leaf change.

## Integration and runtime boundary

- No files were installed into the game and RDR2 was not launched.
- Runtime acceptance requires a cold game launch at both ordinary and 4K/HDR
  startup quality: no Rockstar movie, no readable legal/disclaimer hold, and no
  boot hang or loss of startup audio after the menu appears.
- `durations.xml` is a whole-file replacement. The currently installed
  third-party `SnappyUI` package already replaces the same path, already sets
  `LEGAL_SCREENS_DURATION` to `0.00001`, and carries 14 other deliberate timing
  changes. Integration therefore left SnappyUI as the sole live owner and
  removed the duration mapping from `SkipStartup/install.xml`; the retained
  vanilla-derived file is a standalone reference only.

The compatible package was installed under `lml/SkipStartup`. Both installed
movie replacements match SHA-256
`5F6329343B88E3932C666AC5CFED6A5B5FACA88D932AC37D0EC4F6F314090201`;
the installed descriptor hash is
`5200EF3A5FD27B7DB2704E18B5F5E82625C51C4028DDC7EF411BD1FEA8C261E2`.
