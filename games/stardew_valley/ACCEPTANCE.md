# Stardew Valley PR #465 installed acceptance

This checklist is for the delivered candidate from branch `stardew-valley-plugin`. It does not expand the plugin's feature scope.

## Candidate

Use the GitHub Actions artifact named `Lexeditor-Stardew-Valley-PR465-<commit SHA>` from the latest successful **Stardew Valley checks** run for PR #465 / branch `stardew-valley-plugin`.

The acceptance package is staged from that exact Stardew branch commit. Its shared `ui/framework.js` and `ui/framework.css` are then replaced with the exact current-`master` shared-UI revision that passed the same workflow's merge-target rendered acceptance. `STARDEW-PR465-CANDIDATE.txt` records both revisions. The normal production `Lexeditor.cmd` and `install.ps1` entry points are intentionally omitted.

The artifact adds:
- `START-STARDEW-PR465.cmd`, the only launcher to use for this acceptance candidate;
- `PREPARE-STARDEW-PR465.ps1`, which creates a candidate-local Python environment and isolated Stardew project;
- `STARDEW-PR465-CANDIDATE.txt`, which records the exact commit and isolation boundary.

Do not substitute GitHub's generic source archive for this acceptance candidate.

## Prerequisites

- Windows + Steam Stardew Valley **1.6.15**.
- SMAPI **4.4.0 or newer**.
- Content Patcher **2.9.0 or newer**.
- Python 3 available through `py -3` or `python`.

For the strongest acceptance match, use the currently audited **SMAPI 4.5.2** and **Content Patcher 2.9.1**. The plugin's declared compatibility minimums remain SMAPI 4.4.0 and Content Patcher 2.9.0.

This candidate does **not** install, replace, or update SMAPI or Content Patcher. Lexeditor's current shared helper API exposes only one managed helper/update row per game, while Stardew requires both independently versioned runtimes; Content Patcher also has no official GitHub release binary to pin and download in this environment. Do not build either helper for this test. If the required runtimes are absent, that is the recorded helper-delivery blocker rather than evidence that the Stardew editor itself failed.

StardewXnbHack's `Content (unpacked)/Data/Objects.json` is optional. It makes vanilla object names/values visible, but the project override path works without it.

## Isolated candidate location

Do **not** extract the candidate into `C:\Lexeditor` and do not replace anything in that workspace.

Use a separate writable folder, for example:

`C:\Lexeditor-Candidates\Stardew-PR465-<short SHA>\`

Any other folder outside the active Lexeditor workspace is also valid. The candidate launcher is location-independent.

The launcher keeps candidate state isolated:
- Python environment: `<candidate>\.venv-pr465\`
- Lexeditor user data: `<candidate>\candidate-data\LocalAppData\Lexeditor\`
- Stardew project: `<candidate>\candidate-data\stardew-pr465-<short SHA>\`

It does **not** create Desktop/Start Menu shortcuts, invoke the normal `install.ps1`, or write into the active `C:\Lexeditor` workspace.

The SHA-specific Stardew project name also gives the deployed Content Patcher pack its own target folder, avoiding reuse of an existing Lexeditor Stardew deployment.

## Start the candidate

1. Download the candidate artifact for the exact PR head commit.
2. Extract it to the isolated folder above.
3. Run `START-STARDEW-PR465.cmd`.
4. On first launch, the candidate creates its own `.venv-pr465`, installs the pinned Python requirements there, and initializes its isolated Stardew project. Lexer does not build code or run the repository installer.
5. Open `STARDEW-PR465-CANDIDATE.txt` if you need to confirm both the Stardew branch commit and the tested current-`master` shared-UI commit.

## Representative acceptance edit

Use this exact edit so the test is reproducible:

- asset: `Data/Objects`
- object ID: `390` (Stone)
- field: `Price`
- override value: `77`

If the optional vanilla source is present, search for object 390 / Stone. If it is absent, add a `Data/Objects` patch row with object ID `390`. Enable the **Price** override, enter `77`, and save the project.

## Installed acceptance

1. Open **Information** and click **Deploy Project**.
2. Confirm deployment reports **Lexeditor-managed** and that its target uses the candidate's SHA-specific project name.
3. Click **Begin Acceptance**.
4. Launch Stardew through Lexeditor's Play control; it must launch `StardewModdingAPI.exe`, not the unmodded executable.
5. Reach the title screen, then load any existing save to normal gameplay. This is the real-game load boundary; source/API/CI checks do not replace it.
6. In the SMAPI console run:
   `patch export "Data/Objects"`
7. Return to Lexeditor and click **Verify Acceptance Evidence**.

## Pass criteria

The Information panel must report **Accepted** with:
- Stardew **1.6.15** on Windows in the fresh SMAPI runtime evidence;
- Content Patcher detected in that run;
- the SHA-specific Lexeditor content pack listed as loaded **for Content Patcher**;
- a fresh `Data/Objects` export containing object `390` with `Price = 77`;
- installed `Content/Data/Objects.xnb` still byte-identical to the pre-run baseline;
- no project-specific loader error and no stale deployment/project evidence blocker.

If verification fails, report the blocker text shown in Lexeditor, the candidate commit from `STARDEW-PR465-CANDIDATE.txt`, and the SMAPI log path shown in the Information panel. Do not reinterpret a failed verification as acceptance.

## Cleanup

Use **Revert Lexeditor Mod** before deleting the candidate folder. This removes only the candidate's Lexeditor-managed SHA-specific content pack. After that, the isolated candidate folder can be deleted without affecting the active Lexeditor workspace or its normal user data.
