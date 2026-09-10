# FFX/X-2 Steam collection — real-install acceptance

This checklist covers the evidence CI cannot provide for #461 / PR #462. Keep PR #462 draft until these checks are performed against a real Steam app 359870 installation.

## Safety boundary

- Do not modify either installed VBF.
- Do not use the Square Enix collection launcher for Lexeditor Play acceptance.
- Keep all replacement files under the Lexeditor project and its owned Fahrenheit mod.
- Prefer a byte-identical extracted file for the first EFL startup check; gameplay changes are unnecessary to prove the loader path.
- Capture the verifier JSON and the source VBF hashes before any deploy/launch test.

## 1. Read-only inventory verification

From the Lexeditor repository root on the Windows machine with the game installed:

```powershell
python -m games.ffx_x2.verify_install --game-root "D:\SteamLibrary\steamapps\common\FINAL FANTASY FFX&FFX-2 HD Remaster" --require-fahrenheit --json > ffx-x2-install-verification.json
```

Use the actual Steam library path if different.

Acceptance requirements:

- `acceptanceReady` is `true`.
- Both `archives.x.ready` and `archives.x2.ready` are `true`.
- Every `structured[]` row has `status: "validated"`.
- The four FFX ability tables report:
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
8. Re-run the read-only verifier or otherwise re-hash `FFX_Data.vbf`; it must be byte-identical to its pre-test state.

This first acceptance deliberately uses unchanged replacement bytes so the test exercises the EFL/deploy/launch route without introducing a gameplay-format variable.

## 4. Byte-identical Fahrenheit EFL startup — FFX-2

Repeat the same procedure for one small FFX-2 archive entry under canonical `efl/x2/FFX2_Data/...`, then use **Play FFX-2**.

Acceptance requirements mirror FFX:

- normal Stage 0 startup/title flow;
- no installed-VBF mutation;
- one Lexeditor loadorder entry while deployed;
- clean revert preserving unrelated mods.

## 5. Harmless structured round-trip

Only after byte-identical EFL startup passes, test one reversible structured edit in each game.

For each selected table:

1. Save the original field value and table SHA-256.
2. Make one small valid change through its structured control.
3. Confirm only the documented writable bytes differ in the project file.
4. Deploy and launch the corresponding game.
5. Confirm the game accepts the replacement and the intended value is observable if practical.
6. Restore the original value through Lexeditor, deploy/retest if needed, then revert the deployment.
7. Confirm the installed VBF hash never changed.

Do not use an unknown field or a generic byte edit for acceptance.

## Draft exit record

Before marking PR #462 ready, record:

- Steam install path used;
- verifier JSON/report date;
- `FFX_Data.vbf` header MD5 and file hash before/after acceptance;
- `FFX2_Data.vbf` header MD5 and file hash before/after acceptance;
- FFX byte-identical EFL startup result;
- FFX-2 byte-identical EFL startup result;
- one structured round-trip result for FFX;
- one structured round-trip result for FFX-2;
- **Play FFX** Stage 0 result;
- **Play FFX-2** Stage 0 result;
- deploy/revert and unrelated-loadorder preservation result.

CI remains necessary but is not a substitute for this record.
