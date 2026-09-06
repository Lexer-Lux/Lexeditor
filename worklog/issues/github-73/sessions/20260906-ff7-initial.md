# #73 — FF7 portion only

Branch: `fix/ff7-data-and-tweaks-20260906`.

FF7/2013 now filter out FF8-only FFNx settings on read, reject those keys on
save and filter the writer response. Tweaks works independently of kernel
loading. An absent configuration is detected after installation without
restarting the page; unsaved edits and in-flight refresh races are guarded.
A Reload settings action recovers from external changes with explicit discard
confirmation. No shared parser, FF8 or FF9 implementation was changed.

Validation: the 19-test backend suite includes typed controls' metadata,
comment/order/unknown-line preservation, backup bytes, absent-runtime behavior,
stale/invalid/FF8-only writes and a simulated game-running refusal. Four page
logic tests include configuration discovery, stale-save recovery, failed kernel
requests and a refresh arriving after an edit. See #79 worklog for test doubles
and limitations. Actual Windows process probing and visual/player acceptance
are not claimed; other games' acceptance status is unchanged.

- [ ] Open Tweaks in both FF7 editions; shared/FF7 settings should appear, not
      FF8-only settings. An absent FFNx.toml should show its expected path.
- [ ] With the game closed, change a harmless setting, save and reopen; confirm
      persistence and FFNx.toml.lexeditor.bak, then restore the original value.
- [ ] Make an unsaved tweak, switch focus away/back, and confirm it remains.
      Change the file externally and confirm Save refuses the stale snapshot;
      Reload settings must ask before discarding the pending edit.
- [ ] Confirm saving runtime settings is refused while FF7 is genuinely
      running. Report edition, setting name and exact error on any failure.
