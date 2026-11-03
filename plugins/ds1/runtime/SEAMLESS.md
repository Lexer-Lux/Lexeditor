# Seamless Co-op compatibility investigation

Request: "make our loader compatible with Seamless Co-op. Look at how Crow did
it and figure out what we need to change."

Status: source investigation complete; compatibility is not implemented or
verified. Do not advertise the current DLL as compatible.

## Upstream evidence

Crow implemented support in commit
[`73d239d51da26619cebe35702151728479ea5698`](https://github.com/metal-crow/Dark-Souls-1-Overhaul/commit/73d239d51da26619cebe35702151728479ea5698),
included in our pinned Beta36 revision. The integration detects loaded
`ds1sc.dll`. It disables `getNetMessageAC` because it drops necessary Seamless
packets. It also disables its persistent lobby and P2P translation hooks,
passes through real game lobby creation, and distinguishes the Seamless master
lobby from the game lobby. The master lobby has `lobby_type` containing
`seamless`; metadata may arrive after lobby entry.

Our selected import replaced upstream networking calls and lost the conditional
around `getNetMessageAC`. Our loader has no persistent lobby or P2P translation
to disable. Copying all of ModNetworking would introduce those systems needlessly.

## Required implementation

- Detect Seamless before protection validation and installation. Confirm module
  load timing under the actual Seamless launcher; an early cached false would
  install the wrong hooks. A folder's existence is not evidence it is active.
- Skip both installation AND original-byte validation/reservation of the
  `getNetMessageAC` hook (RVA `0x50b5e6`) in Seamless sessions. Leave the other
  protections enabled only after checking their semantics against Seamless.
- Replace the adapter's last-lobby-entered assumption with master-lobby tracking.
  Handle delayed lobby metadata, additional game-lobby entry, host departure,
  disconnection and reconnect. NPC guards must use the actual session host and
  members. Vanilla server break-in notifications are not sufficient evidence
  of invader roles on a replacement transport.
- Check ownership of the `SteamAPI_RunCallbacks` import. The current adapter
  terminates if another loader changes it. Preserve a verified predecessor or
  use an integration point that does not overwrite Seamless's dispatch.
- Respect Seamless's own save namespace. Our hook only recognizes the literal
  `DRAKS0005.sl2`; it does not automatically back up Seamless saves. Confirm the
  actual filename/open path and hook order before deciding backup routing.
  Do not copy or rename either modded save into the vanilla namespace.
- Add explicit Seamless launch support without treating Steam's normal launch
  as equivalent. Verify file replacement/composition hooks under that launcher.
- Test synthetic mode selection and lobby transitions, then two-player startup,
  joining in both host roles, combat, progression, disconnect/reconnect, saving
  and restart. Observe the actual save path. Test representative data and native
  mods with identical gameplay mod sets on both machines.

## Licensing and distribution

The combined online DLL uses Crow's AGPLv3 code. Keep its AGPL-3.0-only
distribution terms, upstream notices, full license, change notices/dates and
corresponding source for our complete DLL, including adapters and build scripts.
Independent mod assets are not automatically relicensed just by sharing a ZIP;
code linked into the covered program needs compatible terms. This is a release
engineering interpretation of AGPL sections 1, 4–6 and 13, not a determination
that every possible third-party mod forms an independent work.

`runtime_package.py` ships `Loader-credits.txt` and `Loader-source.zip` with the
modified native source, build instructions, source provenance and manifest.
Keep the Python runtime license and dependency notices. The source build also
requires dearxan 0.5.6 (MIT/Apache-2.0); its source and build directions are at
https://github.com/tremwil/dearxan/tree/v0.5.6 . Check dependency availability and
reproduce the build before a public release. Do not describe the source archive
alone as a completed legal audit of all dependencies.

Seamless should remain a separately installed dependency. Supporting its launcher
does not require copying its implementation. Check its author's redistribution
permissions before ever bundling its files; Crow's license grants no rights to
Seamless. No Seamless code or binaries were imported in this investigation.
