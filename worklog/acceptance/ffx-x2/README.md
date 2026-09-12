# FFX/X-2 Steam collection — real-install acceptance

This checklist covers the evidence CI cannot provide for #461 / PR #462. Keep PR #462 draft until these checks are performed against a real Steam app 359870 installation.

## Safety boundary

- Do not modify either installed VBF.
- Do not use the Square Enix collection launcher for Lexeditor Play acceptance.
- Keep all replacement files under the Lexeditor project and its owned Fahrenheit mod.
- Prefer a byte-identical extracted file for the first EFL startup check; gameplay changes are unnecessary to prove the loader path.
- Capture the verifier JSON and full source VBF SHA-256 values before any deploy/launch test.

## 1. Read-only inventory verification

From the Lexeditor repository root on the Windows machine with the game installed:

```powershell
python -m games.ffx_x2.verify_install --game-root "D:\SteamLibrary\steamapps\common\FINAL FANTASY FFX&FFX-2 HD Remaster" --require-fahrenheit --hash-archives --json > ffx-x2-install-verification.json
```

The recommended shortcut runs that strict command and writes the report directly into this acceptance folder:

```powershell
.\worklog\acceptance\ffx-x2\run-verifier.ps1 -GameRoot "D:\SteamLibrary\steamapps\common\FINAL FANTASY FFX&FFX-2 HD Remaster"
```

Use the actual Steam library path if different. `run-verifier.ps1` writes `worklog/acceptance/ffx-x2/install-verification.json` by default and exits with an error unless the report has the expected contract and `acceptanceReady: true`. `--hash-archives` deliberately reads the complete large VBF files, so it is optional during ordinary development but required for the draft-exit baseline.

For automatic before/after immutability proof, keep the baseline and current report separate:

```powershell
.\worklog\acceptance\ffx-x2\run-verifier.ps1 -GameRoot "D:\SteamLibrary\steamapps\common\FINAL FANTASY FFX&FFX-2 HD Remaster" -OutputPath ".\worklog\acceptance\ffx-x2\baseline.json"

.\worklog\acceptance\ffx-x2\run-verifier.ps1 -GameRoot "D:\SteamLibrary\steamapps\common\FINAL FANTASY FFX&FFX-2 HD Remaster" -BaselinePath ".\worklog\acceptance\ffx-x2\baseline.json" -OutputPath ".\worklog\acceptance\ffx-x2\after.json"
```

The second command fails if either installed VBF's header MD5 or full SHA-256 differs from the baseline. It also refuses to use the same path for baseline and output, so the baseline cannot be overwritten accidentally.

`verificationPassed` describes the requested verifier invocation; ordinary read-only verification can pass without full archive hashing. `acceptanceReady` is deliberately stricter: it requires validated structured/archive coverage, full SHA-256 values for both installed VBFs, and ready Fahrenheit Stage 0/Stage 1 plus both fixed game executables.

Acceptance requirements:

- `acceptanceReady` is `true`.
- `archiveHashesIncluded` is `true`.
- Both `archives.x.ready` and `archives.x2.ready` are `true` and each has a full-file `sha256`.
- Every one of the 15 `structured[]` rows has `status: "validated"`.
- FFX `a_ability.bin` reports `0x6C` records.
- FFX `ply_save.bin` reports `0x94` records.
- The four FFX animation tables report:
  - `command`: `0x60` records;
  - `item`: `0x60` records;
  - `monmagic1`: `0x5C` records;
  - `monmagic2`: `0x5C` records.
- FFX-2 command reports `0x8C` records.
- FFX-2 accessory reports `0x54` records and a zero-based range as required by its parser.
- Fahrenheit Stage 0, Stage 1, FFX.exe and FFX-2.exe all report ready.

Attach or transcribe the JSON results into this acceptance folder before taking the PR out of draft. The report contains paths/hashes/record metadata, not proprietary game payload bytes.

## 2. Full-catalog UI smoke

Open the FFX/X-2 plugin against the real install.

Acceptance requirements:

- Dashboard shows both archives available and finite file counts.
- Archive Browser can search both games without UI lock-up.
- Data Map renders all supported structured rows.
- Each structured editor opens its full real table without parser errors.
- **FFX Abilities** can switch among Commands, Items, Monster Magic 1 and Monster Magic 2 and shows the expected record size for each.
- **FFX Auto-Abilities** opens `a_ability.bin`, shows Fire/Ice/Thunder/Water/Holy controls for Strike/Absorb/Immune/Resist/Weak, and does not expose SOS/status/effect/icon/group fields.
- **FFX Base Stats** opens `ply_save.bin` and exposes only base HP, base MP, Strength, Defense, Magic, Magic Defense, Agility, Luck, Evasion and Accuracy. It must not expose text/name metadata, AP, current HP/MP, current stats or any field at/after record `+0x14`.
- No project file is created merely by browsing/refreshing.

Record any unexpectedly large table or UI delay before changing data.

## 3. Byte-identical Fahrenheit EFL startup — FFX

Use Archive Browser to extract one small FFX file to its canonical project path **without editing it**. This creates a byte-identical project overlay while leaving `FFX_Data.vbf` untouched.

Then:

1. Confirm the project copy SHA-256 matches the extracted source bytes reported by the same read path.
2. Deploy the Lexeditor project.
3. Confirm unrelated Fahrenheit `loadorder` entries remain present and `lexeditor-ffx-x2` is added exactly once.
4. Use **Play FFX**.
5. Confirm FFX reaches normal startup/title flow through Stage 0 with the file-only mod enabled.
6. Revert the Lexeditor deployment.
7. Confirm the owned mod is removed and unrelated loadorder entries remain unchanged.
8. Re-run the verifier with `--hash-archives`; `archives.x.sha256` must exactly match the pre-test baseline.

This first acceptance deliberately uses unchanged replacement bytes so the test exercises the EFL/deploy/launch route without introducing a gameplay-format variable.

## 4. Byte-identical Fahrenheit EFL startup — FFX-2

Repeat the same procedure for one small FFX-2 archive entry under canonical `efl/x2/FFX2_Data/...`, then use **Play FFX-2**.

Acceptance requirements mirror FFX:

- normal Stage 0 startup/title flow;
- `archives.x2.sha256` remains identical to the baseline;
- one Lexeditor loadorder entry while deployed;
- clean revert preserving unrelated mods.

## 5. Harmless structured round-trip

Only after byte-identical EFL startup passes, test one reversible structured edit in each game.

For FFX, `a_ability.bin` remains a useful conservative acceptance candidate because the editor can toggle one known elemental bit while preserving the rest of the record. If using it:

1. Save the original mask and table SHA-256.
2. Toggle exactly one known element flag in one behavior.
3. Confirm the project-file diff is confined to the selected record byte at `+0x11..+0x15` and that bits `0xE0` of that byte are unchanged.
4. Do not modify SOS, status/effect, icon/group or any other field.

If testing `ply_save.bin` instead, use only a base-stat field and confirm the project diff is confined to the selected record `+0x04..+0x13`; bytes before `+0x04` and all bytes from `+0x14` onward must remain identical.

For every selected structured table:

1. Save the original field value and table SHA-256.
2. Make one small valid change through its structured control.
3. Confirm only the documented writable bytes differ in the project file.
4. Deploy and launch the corresponding game.
5. Confirm the game accepts the replacement and the intended value is observable if practical.
6. Restore the original value through Lexeditor, deploy/retest if needed, then revert the deployment.
7. Re-run `verify_install --hash-archives` and confirm both installed VBF hashes are unchanged.

Do not use an unknown field or a generic byte edit for acceptance.

## Draft exit record

Before marking PR #462 ready, record:

- Steam install path used;
- verifier JSON/report date;
- `FFX_Data.vbf` header MD5 and full SHA-256 before/after acceptance;
- `FFX2_Data.vbf` header MD5 and full SHA-256 before/after acceptance;
- FFX byte-identical EFL startup result;
- FFX-2 byte-identical EFL startup result;
- one structured round-trip result for FFX;
- one structured round-trip result for FFX-2;
- **Play FFX** Stage 0 result;
- **Play FFX-2** Stage 0 result;
- deploy/revert and unrelated-loadorder preservation result.

CI remains necessary but is not a substitute for this record.
