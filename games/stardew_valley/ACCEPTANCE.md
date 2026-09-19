# Stardew Valley PR #465 installed acceptance

This checklist is for the delivered candidate from branch `stardew-valley-plugin`. It does not expand the plugin's feature scope.

## Candidate

Use the GitHub Actions artifact named `Lexeditor-Stardew-Valley-PR465-<commit SHA>` from the latest successful **Stardew Valley checks** run for PR #465 / branch `stardew-valley-plugin`.

The artifact is the exact tracked Lexeditor source at that commit plus:
- `START-STARDEW-PR465.cmd`, which opens Lexeditor directly on the Stardew Valley plugin;
- `STARDEW-PR465-CANDIDATE.txt`, which records the exact commit and test boundary.

Do not substitute GitHub's generic source archive for this acceptance candidate.

## Prerequisites

- Windows + Steam Stardew Valley **1.6.15**.
- SMAPI **4.4.0 or newer**.
- Content Patcher **2.9.0 or newer**.
- Python 3 available as `python` on PATH for Lexeditor's existing first-run environment setup.

StardewXnbHack's `Content (unpacked)/Data/Objects.json` is optional. It makes vanilla object names/values visible, but the project override path works without it.

## Install the candidate

1. Download the candidate artifact for the exact PR head commit.
2. Extract its contents so the launcher is exactly `C:\Lexeditor\Lexeditor.cmd`. The current Lexeditor installer contract uses `C:\Lexeditor`.
3. Run `C:\Lexeditor\START-STARDEW-PR465.cmd`.
4. On first launch, Lexeditor may create `.venv` and install its pinned Python dependencies automatically. Lexer does not need to build the plugin.

## Representative acceptance edit

Use this exact edit so the test is reproducible:

- asset: `Data/Objects`
- object ID: `390` (Stone)
- field: `Price`
- override value: `77`

If the optional vanilla source is present, search for object 390 / Stone. If it is absent, add a `Data/Objects` patch row with object ID `390`. Enable the **Price** override, enter `77`, and save the project.

## Installed acceptance

1. Open **Information** and click **Deploy Project**.
2. Confirm deployment reports **Lexeditor-managed**.
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
- the Lexeditor content pack listed as loaded **for Content Patcher**;
- a fresh `Data/Objects` export containing object `390` with `Price = 77`;
- installed `Content/Data/Objects.xnb` still byte-identical to the pre-run baseline;
- no project-specific loader error and no stale deployment/project evidence blocker.

If verification fails, report the blocker text shown in Lexeditor, the candidate commit from `STARDEW-PR465-CANDIDATE.txt`, and the SMAPI log path shown in the Information panel. Do not reinterpret a failed verification as acceptance.

## Cleanup

Use **Revert Lexeditor Mod** to remove only the Lexeditor-managed deployed content pack. Clear the test override from the project if it is no longer wanted.
