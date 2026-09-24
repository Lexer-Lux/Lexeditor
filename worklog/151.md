# #151: Duration category experiment

[Live issue and comments](https://github.com/Lexer-Lux/Lexeditor/issues/151)

## Required scope

Deliver a built and installed probe, contrasting records, timing sheet and restore path. Lexer already requested the probe. Test category independently of behavior, time and timeunits; include stacking, radial presentation and save/load. Names do not establish category behavior.

## Prepared on 2026-09-08

Source and instructions: tools/probes/rdr2_duration/README.md, catalog.py, deploy.py, probe.cpp, build.bat. Independent ASI: out/rdr2-duration-probe/DurationProbe.asi. Root built it successfully with the existing SDK; intermediate compiler files used a cleaned temporary directory. SHA-256: 1CFD436AD21D243D1750C3422F36C32349697A1F93D87DA3F389DD4EC56FF958.

The private bundle at C:/Users/Lexer/AppData/Local/Lexeditor/probes/duration-151 holds one original and one eight-case catalog candidate, totaling 102,958,804 bytes. Fresh free-space check was 61.2 GB. Installed lml/MyOverhaul resolves to C:/RDR2Mod/MyOverhaul, so installation would also affect the shared editable catalog. No installation was done.

Original SHA-256: 93fe24015dd6a733c2cb517c2677f82b96a172b2a3f0ea7ad25f495b2d4b337f. Candidate: 52cc682d87710c2a081035a3b3ac727eda77cd4c3a7ee2573641b8babce8c339.

The eight existing named tonics retain identity, icons and all non-effect fields. Each gets one unique experiment effect. Cases 1–4 hold health overpower/time/units constant and vary category 1–4; other cases vary time, units or behavior. Self-closing empty effect lists are supported. No copied proprietary data is placed in the source repository.

The ASI uses the established 32-byte inventory GUID path and count readback. It grants only on F9 when fewer than two selected items exist. F8 selects case; F10 samples. The core getter is SDK-documented. The float overpower getter follows the existing fortification_hud.cpp wrapper for 0x4C9F782180712742; its interpretation remains an observation to compare with visible timing. There are no core/rank setters. Logging is 500 ms, ten minutes per recording, 4096 rows per launch, one current and one previous file.

## Isolation and restore

The prepared tool moves the four reviewed installed ASIs (GameplayTweaks, Rampage, Banking, CollectibleCalibrator) into one bundle folder with exact-hash receipts. It keeps vfs.asi for LML. Unknown ASIs stop isolation. Restore refuses to overwrite changed files. Catalog restore requires the candidate hash; repeated prepare/isolate is refused. The timing sheet supplies explicit steps and a separate manual test slot for save/load; no save/profile file was read or changed.

## Checks and remaining work

Four executable tests pass: eight-case field preservation including unrelated bytes; missing/repeated preparation rejection; exact catalog install/restore plus changed-file guard; probe/mod exact-byte restore and changed-binary refusal. Real installed catalog preparation parsed successfully.

Root must review and install the controlled candidate before this is test-ready. No game was launched. No timing, stacking, radial, consumption or persistence result is claimed. Controls must be shown clearly in delivery; isolated game acceptance remains required.

## Ready activation coordinator

The existing private bundle now also contains Activate.cmd, Restore.cmd and Test-sheet.md. They reference the built ASI and existing single catalog bundle. The user needs no build or multi-command setup. Source coordinator: tools/probes/rdr2_duration/coordinator.py.

Activation checks the game is closed, then coordinates reviewed ASI isolation, catalog installation and probe installation. A failed step triggers all applicable recovery steps. A failed recovery retains exact receipts/backups and reports the bundle path. Repeat activation with pending recovery is refused; repeated successful restore is safe. No activation was run on real files.

Tests now pass 6 cases and 5 subtests, including each activation stage failure, repeat activation/restore, and a probe rollback failure that keeps recovery while still restoring the catalog and other ASIs. No additional catalog copy was created.

## Pinned probe and staged binary install

The existing private bundle now contains the reviewed 275,968-byte DurationProbe.asi, pinned to SHA-256 1cfd436ad21d243d1750c3422f36c32349697a1f93d87da3f389dd4ec56ff958 in its manifest. Activate/Restore reference this copy. Activation checks it before isolation, and installation checks it again before staging.

Probe installation now writes an exclusively owned staging file, checks the write count and full checksum, then promotes it atomically. An incomplete write never becomes a live ASI. Eight tests and five subtests pass, including changed prepared binary rejection with zero live writes and an injected short write with no live binary or leftover stage. No real activation was run and no extra catalog copy was made.

## Active candidate

Root activated the pinned helper and verified the installed candidate catalog hash, probe hash, all four original ASI hashes retained in disabled-asi with originals absent, and vfs.asi present. Root updated the live issue to untested with the prepared checklist and verified that label. The controlled experiment is active. Do not change the game or recovery bundle while it is pending. Human timing, stacking, radial and save/load observations remain.

