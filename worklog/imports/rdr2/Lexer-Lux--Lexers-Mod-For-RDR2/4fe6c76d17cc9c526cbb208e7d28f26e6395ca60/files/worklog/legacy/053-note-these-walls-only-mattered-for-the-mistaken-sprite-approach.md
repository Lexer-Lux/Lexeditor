# Worklog: 053 Note These Walls Only Mattered For The Mistaken Sprite Approach

## (NOTE: these walls only mattered for the mistaken sprite approach — moot now)

- **OpenIV 4.1 CANNOT author RDR2 .ytd textures.** It errors "not able to
  create archives for RDR2 yet" on Create Archive, and "Edit" is greyed on a
  loose .ytd (texture edit only works for a ytd inside an editable RPF — which
  you can't create). So the DRAW_SPRITE vignette's texture cannot be made in
  OpenIV. Path forward = CodeWalker (not installed; downloading/running an exe
  needs Lexer's OK) OR reconsider the timecycle-modifier vignette (no tooling,
  but single vignette / most-empty-core-wins, not independent 3-way stack).
- OpenIV CAN still: browse, extract, and Export-to-XML (used it fine).
- **Skip-movies #6 dead-ended:** extracted startup.ymt (data_0.rpf/data) — it
  only loads scaleform/UI rpfs at boot, does NOT reference the intro videos.
  Rockstar-logo/Title_GameIntro are .bik in movies_0.rpf; skipping them needs
  replacing those .bik (proprietary Bink encoder, no open tool). Blocked.
- Loose-file workflow that DID work for reading: OpenIV File > Open folder ->
  the loose folder, double-click ytd -> viewer (Export only). Good for
  inspecting/exporting, not creating.

