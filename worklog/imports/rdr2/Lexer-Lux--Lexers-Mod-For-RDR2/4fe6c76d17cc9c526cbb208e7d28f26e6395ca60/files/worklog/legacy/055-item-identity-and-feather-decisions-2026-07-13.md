# Worklog: 055 Item Identity And Feather Decisions 2026 07 13

## Item identity and feather decisions (2026-07-13)

- User-authored reworks are persisted in `MyOverhaul/strings.gxt2`: the Viking
  Comb doubles greeting honor, the Viking Hatchet makes killed enemies drop 5x
  money, and the Ancient Tomahawk returns to inventory after hitting an enemy.
  Their runtime mechanics remain TODOs; description text alone is not an
  implemented feature.
- Ordinary crafting feathers are intentionally unified as
  `PROVISION_BIRD_FEATHER_FLIGHT`: species-feather skinning yields now produce
  Flight Feathers and species-specific feather recipe costs now consume Flight
  Feathers. Exotic mission plumes remain distinct. This is built and awaiting
  in-game confirmation.
- Ammo carry upgrades use hashed multiplicity slots `0xE655E53D` and
  `0xD4774180`. LEXEDITOR must offer both for every AMMO-group item; carry caps
  are cumulative contributions, not standalone final limits.
- TODO #62 is a full carry-cap redesign, including both intentional per-family
  base limits and coherent progression from satchels, bandoliers, gun belts,
  ammo upgrades, and other multiplicity slots. Do not tune individual caps in
  isolation before Lexer decides the broader capacity progression.

