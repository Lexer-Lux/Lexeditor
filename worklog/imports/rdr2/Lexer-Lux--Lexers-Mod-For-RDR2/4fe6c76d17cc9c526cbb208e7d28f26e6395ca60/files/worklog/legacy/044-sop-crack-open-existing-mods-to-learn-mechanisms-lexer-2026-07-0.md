# Worklog: 044 Sop Crack Open Existing Mods To Learn Mechanisms Lexer 2026 07 0

## SOP: crack open existing mods to learn mechanisms (Lexer, 2026-07-09)

When figuring out HOW to change something, first find an existing mod that
does it, download it, and read its files to learn which game files/fields it
touches — then make our own change from vanilla extracts. Lexer explicitly
authorized downloading mods for this. Reference only; NEVER ship their
contents; log each one in CREDITS.txt. Practical notes: Nexus gates downloads
behind login (don't use Lexer's account); rdr2mods.com sometimes serves
directly; some modders host on GitHub. If a mod is Nexus-only, ask Lexer to
grab it (like the 1899 file) rather than stalling.

- Online Content Unlocker 3.0 and Red Dead Offline 1.3.3 were inspected on
  2026-07-15. OCU is data-only but not a trivial tuning mod: it replaces eleven
  DLC/title-update `content.xml` manifests so online RPFs and their models,
  animations, weapon metadata, textures, audio, etc. mount under Story Mode
  conditions. RDO supplies the second layer: Story Mode catalog/shop,
  localization, compendium, and weapon records, plus `loader.asi` handling
  special online weapons/assets (its binary names bolas, moonshine jug, poison
  bottle, and MP texture dictionaries). Broad RDO functionality therefore
  needs both asset mounting and SP registration/behavior; neither layer alone
  is equivalent to the complete mod.

