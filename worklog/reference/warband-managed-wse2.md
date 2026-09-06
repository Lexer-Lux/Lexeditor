# Managed WSE2 and Steam acceptance

## Install the shipped version

Update Lexeditor from master and restart. Select Warband in Home. A missing,
unmanaged or modified WSE2 package offers **INSTALL / REPAIR WSE2**. Close Warband
and any WSE2 launcher, then use that action. No compiler, separate download or
upstream installer is needed: Lexeditor contains package **1.1.5.1-lex1**, based
on WSE2 **v1.1.5.1**. This writes only to the game folder selected in Home, not an
old default installation.

Every shipped file is hash-verified before installation and every destination is
read back afterward. Existing destination files are backed up under the selected
game's `.lexeditor/wse2/backups/`. Original `mb_warband.exe`, `steam_api.dll`, mods,
saves and WSE 3.x are not replaced. WSE2's shared shader files and selected runtime
DLLs are managed and therefore backed up before replacement. The upstream updating
launcher is not in the package and is never run. A separate existing launcher is
left untouched; changing managed files with it makes Lexeditor refuse Play until
an explicit repair restores the pin.

An interrupted install is marked unready; retrying Install/Repair recovers its
journal before installing. Changed external files or invalid backups cause
recovery to stop rather than overwrite those changes. Retain the error and
`.lexeditor/wse2` records in that case. Opening Home, checking versions and Play
never silently repair or install a helper.

## Main-menu checker

In Developer Mode, open **I AM LEXER → HELPER VERSIONS**. WSE2 appears even when
Warband is not installed. Each helper shows pinned, installed, latest upstream,
publication date and release notes. A failed GitHub lookup keeps the pin and
local installed state visible. Opening checks upstream once per session;
**Check again** refreshes. Local installed state refreshes each opening.
**Release notes** opens an approved GitHub release in the external browser, not
inside the privileged editor. This panel never installs or updates anything.

## Prepared checks

Run `tools/Warband-checks.cmd` in the updated checkout. It tests the real bundled
WSE2 bytes in disposable folders, installation/rollback/recovery, tampering,
Steam component/AppID preservation and checker routing. It never starts the
bundled game executable or changes live Steam stats/achievements.

Installed acceptance (not established by those fixture checks):

- [ ] Install/repair WSE2 in Home and reopen the checker. It should report pinned
  `v1.1.5.1`, package `1.1.5.1-lex1` and installed `v1.1.5.1 (verified)`. No updater
  window should appear. No action in the checker should install anything.
- [ ] Start Steam signed into the account that owns Warband. Run Lexeditor and
  Steam at the same privilege level. Choose the intended installed module, press
  Play, load a save, and open the Steam overlay. Verify Steam shows the correct
  game and that playtime increases. Test screenshots and any Steam Input or
  Workshop function you actually use separately; overlay visibility does not
  prove those functions.
- [ ] During normal eligible gameplay, earn one still-locked achievement without
  cheats and verify it in the Steam client. Do not reset or force-unlock an
  achievement for this test. Record the name and whether Steam awarded it.
- [ ] After a failure, report module, runtime version and what failed. Preserve
  the current game's `rgl_log.txt`; search for `Steam API initialized.`,
  `Initializing Steam achievement manager...` and
  `Received stats and achievements from Steam`. Those log messages are separate
  initialization milestones, not proof of an achievement award. Stop must close
  only the editor-owned game session.

The bundle retains the exact publisher Steam libraries and `steam_appid.txt`
containing `48700`; it does not replace them with stubs or manipulate achievements.
An installed Steam session is required to establish actual compatibility. No
Steam-success or installation-on-Lexer's-PC claim follows from a merge or CI.
