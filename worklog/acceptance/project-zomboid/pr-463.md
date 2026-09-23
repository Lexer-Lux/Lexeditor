## Chat-mode UI audit

Audit baseline refreshed after merging current `master`
`72ee978a2ff36686a6349696b19860057356468a` into this branch. Reviewed
current-master revisions: `docs/ADDING_A_GAME.md`
`7fe6d35dd82fa3fe4e6378ca558ecbb0a316c4c0`; `docs/UI-MANUAL.md`
`14a3269992031d7e7893fcb127728a48b944e71f`; `AGENTS.md`
`41355ce0b783c55a03ad250ed279666f785c6e67`; Blank `editor.html`
`b0b235d010952bf0c7524dcce172ef72f7cf63e4`, `editor.js`
`bec94d0c192225472282c5c591d568a104073fc8`, and `editor.css`
`4e01602ce0f339781cae766d4b6d7541bb7bae89`; shared
`ui/component-catalog.js` `a11e52e31ee92bce495c6cbf54a66d4597d52139`;
`ui/framework.js` `870245fefffb7b0e9ad114d1407350cb3ef309f0`;
`plugin_http.py` `f83b4e07ed7128e8c38749ab140974e5ad68d152`; and
RDR2 `editor.html` `899bfdb45cbf25da55aed43a590db6ee476b523b`.
The new master contract now includes the component catalogue, Blank page modules,
shared `PluginRequestHandler.send_page_module(...)`, and a zero-growth shared-UI
selector budget for new plugin files. PZ was reconciled to those current examples
rather than retaining its pre-merge local HTTP/CSS compatibility code.

Requirement / gap / evidence:

- [x] markup-only PZ `editor.html`; relative `editor.js`/`editor.css`; modules
  are served through current shared `PluginRequestHandler.send_page_module`.
- [x] PZ plugin CSS has zero selectors naming shared `.lex-*` classes and no
  hand-built table rows; current shared layout/tokens own shared component geometry.
- [x] shell owns Data Map and Info; Data Map uses shared real SVG integration
  status marks.
- [x] Metadata and all eleven structured families use shared Detail controls;
  all eleven record lists use shared paged Table + Detail and semantic cell
  editors. Real ZedScript record/module identity is used; no invented row IDs.
- [x] shell Save/right-click Discard owns unsaved edits across Detail and table
  cells; repeated same-file saves refresh source identity between records.
- [x] explicit loading, empty/search-empty and error states use shared surfaces.
- [x] Script Inventory remains a shared paged read-only Table + Detail for the
  recognized families that do not have writers.
- [x] no PZ Tweaks page is applicable: the supported Build 42 schemas are record
  editors, not a separate finite settings/tweak dataset. No speculative Tweaks
  data was invented.
- [x] helper/update requirements are not silently exempted: this plugin requires
  no third-party helper. It deploys through Project Zomboid's native Build 42
  local-mod mechanism, so there is no helper binary to pin/license/install, no
  helper first-time setup, no helper Updates-drawer entry, and no helper
  auto-update path. Lexeditor's own shared update UI is unchanged.
- The 150% browser geometry mirrors the real Windows host: `windows_host.set_ui_scale`
  sets WebView2 `ZoomFactor`, so the rendered test uses the corresponding reduced
  CSS viewport rather than CSS `zoom` (which incorrectly turns a `100vh` body
  into 150vh).
- [x] scoped rendered browser acceptance covers all 15 PZ surfaces at desktop,
  820×700 narrow geometry, and the Windows host's 150% scale equivalent: 45
  rendered configurations over a 55-item multi-page fixture. It exercises
  search, sorting, selection, paging, double-click cell editing, shared dirty
  state, right-click Discard, Ctrl+S, two sequential edits in one source file,
  reopen/readback, keyboard help, empty/error/loading states, Data Map routing,
  Info, and bottom-of-panel reachability. Run 35482122511 passed after visual
  inspection exposed and fixed the narrow stacked-layout gap; the current
  screenshots show the shared master Table above Detail with the pager below
  at narrow and 150% scale.
- [x] the installed Windows candidate is gated on both OS regressions and the
  scoped browser job, then builds from the exact PR head, installs under the
  GitHub runner's temporary directory (never C:\\Lexeditor or a user install),
  and runs the installed bundled-service plus installed Project Zomboid smokes
  before upload. Exact final-head artifact identity is recorded in the PR body
  after the final documentation-only head passes this same gate.
- [x] current shared-check failures were inspected rather than treated as PZ
  failures: the shared UI contract audit passes before the unrelated FF7R
  descriptor error; shared visual acceptance stops in Blank on the inherited
  boolean-reference spacing assertion; the verifier sweep runs the scoped PZ
  browser verifier successfully and its remaining failures belong to other
  plugins/shared fixtures or unavailable private game data.
- [ ] real installed-game acceptance remains the only evidence level that Chat
  mode cannot complete: a current supported Build 42 installation must discover,
  enable and load the deployed mod, then demonstrate representative edited
  content in the live game and allow owned-deployment cleanup.


# PR #463 packaged Project Zomboid acceptance

This checklist is for the **built Windows candidate from PR #463**. It is not a
source-checkout procedure. The candidate artifact contains:

- `Lexeditor-PR463-project-zomboid-<sha>.exe` — Windows installer built from the
  exact `project-zomboid-plugin` head recorded in `candidate.json`;
- `Project-Zomboid-Acceptance-Mod/` — a ready-to-test Build 42 authoring project;
- `SHA256SUMS.txt` and `candidate.json` — installer integrity and exact source SHA.

The candidate workflow already installs the generated installer on a clean hosted
Windows runner and requires both the frozen bundled-service smoke and the frozen
Project Zomboid plugin smoke to pass before the artifact is uploaded. That is
packaging evidence, **not** installed-game acceptance.

## Human acceptance

1. Download and extract the `project-zomboid-pr463-windows-<sha>` artifact from
   the PR's **Project Zomboid checks** run. Confirm `candidate.json` names PR 463,
   branch `project-zomboid-plugin`, and the expected head SHA.
2. Run the included installer. Launch the **installed Lexeditor**, not a source
   checkout.
3. Keep `Project-Zomboid-Acceptance-Mod` outside `%USERPROFILE%\Zomboid\mods`.
   In Project Zomboid's editor, open the active-mod menu, choose **Find a Mod**,
   and select that fixture folder.
4. Open **Items** and select `LexeditorAcceptance.AcceptanceToken`. Change
   **Weight** from `0.25` to `0.75` and **Icon** from `Radio` to `Hammer`,
   then use the shell **Save** button (or Ctrl+S). Reopen the record and confirm both values persisted.
5. Open **Info** and choose **Deploy Local Mod**. Expected destination:
   `%USERPROFILE%\Zomboid\mods\Project-Zomboid-Acceptance-Mod`. Info must report
   the deployment as owned. Do not copy files into the Steam game directory.
6. Launch the current Windows Steam **Build 42 stable** installation. In the game's
   Mods UI, confirm **Lexeditor Project Zomboid Acceptance** / ID
   `LexeditorPZAcceptance` appears and enable it.
7. Start a disposable test world with the mod enabled. For a deterministic content
   check, temporarily launch Project Zomboid with its `-debug` option, open the
   Build 42 debug item list/viewer, find full type
   `LexeditorAcceptance.AcceptanceToken`, and add a **new** copy to inventory.
   Confirm it uses the Hammer icon and reports weight `0.75`.
8. A missing mod, script-load error, missing test item, unchanged Radio icon/0.25
   weight, or other incorrect behavior is a failed installed-game acceptance.
   Report the observed result plus the relevant Project Zomboid log/error text.
9. After the test, fully exit Project Zomboid and use Lexeditor **Info → Remove
   Owned Deployment**. Remove the temporary `-debug` launch option if you set it.

Do not treat the candidate workflow, source CI, passive preflight, or successful
deployment as proof that the live game loaded the mod.
