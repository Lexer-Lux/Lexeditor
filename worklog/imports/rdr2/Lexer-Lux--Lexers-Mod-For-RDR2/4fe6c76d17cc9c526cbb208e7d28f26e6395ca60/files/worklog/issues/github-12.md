# GitHub #12 — separate activated/deactivated campsite icons

The campsite runtime already persisted an `activated` flag and refreshed its
map blip immediately after activation. Its old icon pair was wrong for the
requested presentation: inactive used `BLIP_CAMPFIRE`, while active used
`BLIP_CAMPFIRE_FULL`, whose artwork adds an unwanted stove.

Added a campsite-icon topic module. Activated campsites now resolve to the
simple vanilla `BLIP_CAMPFIRE`; inactive campsites resolve to
`LEX_BLIP_CAMPFIRE_INACTIVE`, using Lexer's exact 32x32 issue attachment with
the fire blacked out. The helper requests the non-resident `lex_blips`
dictionary before assigning the custom icon and never releases it because the
markers persist for the session.

Added a reproducible nine-texture `lex_blips` preparation/build path. It keeps
the six collectible glyphs and two 40%-alpha looted-marker glyphs already in
the dictionary, then adds the inactive-campfire glyph. A blipdata fragment is
included for the integration agent to place in the shared blip registry.

Those source, registry, YTD, build, and install steps landed, but the first
in-game test reported that the inactive marker was a black square.

The custom-art preparation was not the regression. The 32x32 RGBA source still
has transparency, its DDS is DXT5, the blipdata linkage points at `lex_blips`,
and the built and streamed YTDs match. The lifecycle repeated the project's
already-known nonresident-dictionary failure in a subtler form: the campsite
helper requested `lex_blips` only while creating or changing a marker. That
request is asynchronous, but it assigned the custom linkage immediately and
never reassigned the existing blip after loading finished. The proven
collectible path instead owns the dictionary for the whole session.

The campsite helper now uses that proven lifetime owner. Until the dictionary
reports loaded, an inactive campsite temporarily receives vanilla
`BLIP_CAMPFIRE` rather than an unresolved black square. The per-frame campsite
updater keeps servicing the request and, on the first loaded frame, reassigns
every inactive marker to `LEX_BLIP_CAMPFIRE_INACTIVE`. It repeats that repair if
the dictionary ever transitions from unavailable to ready again. Activated
campsites remain the simple vanilla `BLIP_CAMPFIRE`; the rejected stove icon is
not used.

Static verifier:
`python tools/reverse-engineering/verify_campfire_icons_issue_12.py`.

Runtime acceptance after integration build/install:

- Load a save with an inactive authored campsite: its marker is the supplied
  unlit-fire glyph, never a black square.
- Activate that campsite: the same marker changes immediately to vanilla's
  simple lit campfire, with no stove.
- Save/reload: inactive and activated sites retain their distinct correct
  icons, and no other `lex_blips` collectible/looted marker regresses.

The custom `lex_blips` dictionary still rendered as a black square in Story
Mode. The exact inactive-fire texture was moved into the complete resident
`INVENTORY_ITEMS_MP` replacement used by the casing icons. The rebuilt YTD
preserves all 432 Rockstar textures and contains all five custom textures.
