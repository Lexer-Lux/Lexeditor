# Third-party references and tools

## FF7 Remake Data Editor

The narrow `DataObject` package reader/writer in this plugin is a clean Python
implementation based on the documented behavior and MIT-licensed source of
Jordan Tucker's **FF7 Remake Data Editor**:

- https://github.com/jordanbtucker/ff7r-data-editor
- License: MIT

That project established the FF7R DataObject `.uasset` name/export-table shape,
the `.uexp` property type codes and fixed-row layout, and the safe same-size
editing model used here. Lexeditor does not bundle its application or proprietary
game data.

## FF7R Text Tool

The `GameContents/Text/<language>/*_TxtRes` reader/writer is a clean Python
implementation based on the documented behavior and MIT-licensed source of
MatyaModding's **ff7r-text-tool**:

- https://github.com/matyamod/ff7r-text-tool
- License: MIT

That project documents the FF7R text-resource entry/sub-entry layout, Unreal
FString encoding, name-map references and the paired `.uasset` serialized-size
field required when variable-length text changes. Lexeditor does not bundle the
tool or any extracted game text.

## FF7R Font Mod Tools

The local-only menu-font theming path is a narrow Python implementation based on
the documented layouts and MIT-licensed source of MatyaModding's
**FF7R-font-mod-tools**:

- https://github.com/matyamod/FF7R-font-mod-tools
- License: MIT

That project documents the `GameContents/Menu/Resident/Font/JP/SystemFont*4K`
glyph UEXP record shape and the matching
`GameContents/Menu/Billboard/Common/U_Com_JP_SystemFont*4K-01` 2048x2048 BC5
bitmap-atlas layout. Lexeditor validates those exact installed assets, decodes
`SystemFontNormal` only into the user's private cache, and uses the resulting
atlas/glyph metrics for editor chrome. It does not bundle or publish Square Enix
font assets.

## repak

Lexeditor bundles the exact upstream **repak v0.2.3** release archives used by
the FF7R plugin. Install/Repair extracts the platform executable locally; it
does not download repak at setup time.

- https://github.com/trumank/repak
- License: dual Apache-2.0 / MIT
- Pinned release: v0.2.3
- Upstream release commit: `e215472c51db69328b1ce77be2db24d24c1d646b`
- Windows release archive SHA-256:
  `6720d602144d75df477a99d5bedb6ea780997546afc335901d4937cafeaa73fa`
- Linux release archive SHA-256:
  `933bdb8e26f34e8fd70ea50201efca39df041de58aa83b1cd6eb83da124a2046`

Release/provenance audit (2026-09-23): GitHub's v0.2.3 release metadata
reports those same archive SHA-256 digests, and the annotated v0.2.3 tag resolves
to commit `e215472c51db69328b1ce77be2db24d24c1d646b`. Upstream
`Cargo.toml` declares `MIT OR Apache-2.0`. The MIT and Apache-2.0 license
texts inlined at the end of this file are byte-identical to that tag
(`LICENSE-MIT` `f42304c8413d57a70da5d9ea7e82b13dec063b08`; `LICENSE-APACHE`
`1b5ec8b78e237b5c3b3d812a7c0a6589d0f7161d`), and the tagged repository
contains no separate `NOTICE` file.

The unchanged release archives and manifest live under
`plugins/ff7r/runtime/repak/v0.2.3/`. The installer verifies
both the archive and extracted executable hashes before an atomic install. The
shared Updates view may report a newer upstream release, but neither Lexeditor
nor repak automatically updates the pinned helper.

repak reads installed Unreal Engine PAK indexes/files on demand and packs the
separate Lexeditor project tree into a mod PAK. FF7R's `../../../` mount point
is passed explicitly when listing, extracting and packing. For Oodle-compressed
game data, Lexeditor uses an already-present explicit/game-owned Oodle library;
the repak fallback is never allowed to fetch Oodle silently.

## Public FF7R mod-set compatibility reference

akitaonrails' **distrobox-gaming** repository is used only as public
interoperability evidence for real-world Remake PAK deployment and conflicts:

- https://github.com/akitaonrails/distrobox-gaming
- Reviewed revision: `114a092ae593e30b80e3f7e36fa062a319feb75f`
- No repository license file was present at the reviewed revision.

Its FF7R role installs ordinary UE4 `.pak` mods under
`End/Content/Paks/~mods` and documents a concrete incompatibility between its
Equipment Rebalance (#85) and Gameplay Enhancement (#586) selections because
both replace equipment data. Lexeditor copies no code or mod payloads from this
repository. The reference is used to exercise the same package layout and
exact-asset conflict policy with synthetic repak-built fixtures; third-party mod
bytes and installed-game behavior remain separate acceptance evidence.

## Improved Keyboard and Mouse Controls / Native Mod Loader research

The FF7R native-runtime probe uses independently implemented compatibility checks
informed by TheUnlocked's maintained, MIT-licensed **ff7r-kbm-hook**:

- https://github.com/TheUnlocked/ff7r-kbm-hook
- License: MIT

That project provides public evidence for the Native Mod Loader `Init()` export
contract and current FF7R byte signatures around map control and raw-input
initialization. Lexeditor uses those signatures only as compatibility probes. It
does not copy the hook implementation and does not treat those known addresses as
the cutscene-speed or minimap-toggle hook sites required by #413/#414.

## FinalFantasy7Remake-Menu interoperability research

The guarded HP runtime implementation is informed by public interoperability
information in xCENTx's **FinalFantasy7Remake-Menu** repository:

- https://github.com/xCENTx/FinalFantasy7Remake-Menu
- No repository license file was present when this reference was recorded.

Lexeditor does not copy or bundle that project's implementation. It uses factual
process-layout information (the `AGameState` / `APlayerStats` field layout and a
RIP-relative game-state lookup instruction shape) as a research reference, then
independently validates the installed executable at runtime. No fixed RVA from
that project is shipped or trusted.

## EndGameProj generated Remake API research

Public generated Remake headers in narknon's **EndGameProj** are used only as
interoperability/research evidence for reflected type, property, enum and function
names such as `EGameSpeed_CUT`, `AEndGameState::SetGameSpeed`, ATB DataObject
fields, and menu widget settings:

- https://github.com/narknon/EndGameProj

These generated declarations are not bundled into Lexeditor and are not treated
as current installed-build offsets or validated hook addresses. Installed-game
probes must still establish the concrete target before a runtime mutation can be
enabled.

## repak — MIT License

MIT License

Copyright 2024 Truman Kilen, spuds

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## repak — Apache License 2.0

Apache License
                        Version 2.0, January 2004
                     http://www.apache.org/licenses/

TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

1. Definitions.

   "License" shall mean the terms and conditions for use, reproduction,
   and distribution as defined by Sections 1 through 9 of this document.

   "Licensor" shall mean the copyright owner or entity authorized by
   the copyright owner that is granting the License.

   "Legal Entity" shall mean the union of the acting entity and all
   other entities that control, are controlled by, or are under common
   control with that entity. For the purposes of this definition,
   "control" means (i) the power, direct or indirect, to cause the
   direction or management of such entity, whether by contract or
   otherwise, or (ii) ownership of fifty percent (50%) or more of the
   outstanding shares, or (iii) beneficial ownership of such entity.

   "You" (or "Your") shall mean an individual or Legal Entity
   exercising permissions granted by this License.

   "Source" form shall mean the preferred form for making modifications,
   including but not limited to software source code, documentation
   source, and configuration files.

   "Object" form shall mean any form resulting from mechanical
   transformation or translation of a Source form, including but
   not limited to compiled object code, generated documentation,
   and conversions to other media types.

   "Work" shall mean the work of authorship, whether in Source or
   Object form, made available under the License, as indicated by a
   copyright notice that is included in or attached to the work
   (an example is provided in the Appendix below).

   "Derivative Works" shall mean any work, whether in Source or Object
   form, that is based on (or derived from) the Work and for which the
   editorial revisions, annotations, elaborations, or other modifications
   represent, as a whole, an original work of authorship. For the purposes
   of this License, Derivative Works shall not include works that remain
   separable from, or merely link (or bind by name) to the interfaces of,
   the Work and Derivative Works thereof.

   "Contribution" shall mean any work of authorship, including
   the original version of the Work and any modifications or additions
   to that Work or Derivative Works thereof, that is intentionally
   submitted to Licensor for inclusion in the Work by the copyright owner
   or by an individual or Legal Entity authorized to submit on behalf of
   the copyright owner. For the purposes of this definition, "submitted"
   means any form of electronic, verbal, or written communication sent
   to the Licensor or its representatives, including but not limited to
   communication on electronic mailing lists, source code control systems,
   and issue tracking systems that are managed by, or on behalf of, the
   Licensor for the purpose of discussing and improving the Work, but
   excluding communication that is conspicuously marked or otherwise
   designated in writing by the copyright owner as "Not a Contribution."

   "Contributor" shall mean Licensor and any individual or Legal Entity
   on behalf of whom a Contribution has been received by Licensor and
   subsequently incorporated within the Work.

2. Grant of Copyright License. Subject to the terms and conditions of
   this License, each Contributor hereby grants to You a perpetual,
   worldwide, non-exclusive, no-charge, royalty-free, irrevocable
   copyright license to reproduce, prepare Derivative Works of,
   publicly display, publicly perform, sublicense, and distribute the
   Work and such Derivative Works in Source or Object form.

3. Grant of Patent License. Subject to the terms and conditions of
   this License, each Contributor hereby grants to You a perpetual,
   worldwide, non-exclusive, no-charge, royalty-free, irrevocable
   (except as stated in this section) patent license to make, have made,
   use, offer to sell, sell, import, and otherwise transfer the Work,
   where such license applies only to those patent claims licensable
   by such Contributor that are necessarily infringed by their
   Contribution(s) alone or by combination of their Contribution(s)
   with the Work to which such Contribution(s) was submitted. If You
   institute patent litigation against any entity (including a
   cross-claim or counterclaim in a lawsuit) alleging that the Work
   or a Contribution incorporated within the Work constitutes direct
   or contributory patent infringement, then any patent licenses
   granted to You under this License for that Work shall terminate
   as of the date such litigation is filed.

4. Redistribution. You may reproduce and distribute copies of the
   Work or Derivative Works thereof in any medium, with or without
   modifications, and in Source or Object form, provided that You
   meet the following conditions:

   (a) You must give any other recipients of the Work or
       Derivative Works a copy of this License; and

   (b) You must cause any modified files to carry prominent notices
       stating that You changed the files; and

   (c) You must retain, in the Source form of any Derivative Works
       that You distribute, all copyright, patent, trademark, and
       attribution notices from the Source form of the Work,
       excluding those notices that do not pertain to any part of
       the Derivative Works; and

   (d) If the Work includes a "NOTICE" text file as part of its
       distribution, then any Derivative Works that You distribute must
       include a readable copy of the attribution notices contained
       within such NOTICE file, excluding those notices that do not
       pertain to any part of the Derivative Works, in at least one
       of the following places: within a NOTICE text file distributed
       as part of the Derivative Works; within the Source form or
       documentation, if provided along with the Derivative Works; or,
       within a display generated by the Derivative Works, if and
       wherever such third-party notices normally appear. The contents
       of the NOTICE file are for informational purposes only and
       do not modify the License. You may add Your own attribution
       notices within Derivative Works that You distribute, alongside
       or as an addendum to the NOTICE text from the Work, provided
       that such additional attribution notices cannot be construed
       as modifying the License.

   You may add Your own copyright statement to Your modifications and
   may provide additional or different license terms and conditions
   for use, reproduction, or distribution of Your modifications, or
   for any such Derivative Works as a whole, provided Your use,
   reproduction, and distribution of the Work otherwise complies with
   the conditions stated in this License.

5. Submission of Contributions. Unless You explicitly state otherwise,
   any Contribution intentionally submitted for inclusion in the Work
   by You to the Licensor shall be under the terms and conditions of
   this License, without any additional terms or conditions.
   Notwithstanding the above, nothing herein shall supersede or modify
   the terms of any separate license agreement you may have executed
   with Licensor regarding such Contributions.

6. Trademarks. This License does not grant permission to use the trade
   names, trademarks, service marks, or product names of the Licensor,
   except as required for reasonable and customary use in describing the
   origin of the Work and reproducing the content of the NOTICE file.

7. Disclaimer of Warranty. Unless required by applicable law or
   agreed to in writing, Licensor provides the Work (and each
   Contributor provides its Contributions) on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
   implied, including, without limitation, any warranties or conditions
   of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
   PARTICULAR PURPOSE. You are solely responsible for determining the
   appropriateness of using or redistributing the Work and assume any
   risks associated with Your exercise of permissions under this License.

8. Limitation of Liability. In no event and under no legal theory,
   whether in tort (including negligence), contract, or otherwise,
   unless required by applicable law (such as deliberate and grossly
   negligent acts) or agreed to in writing, shall any Contributor be
   liable to You for damages, including any direct, indirect, special,
   incidental, or consequential damages of any character arising as a
   result of this License or out of the use or inability to use the
   Work (including but not limited to damages for loss of goodwill,
   work stoppage, computer failure or malfunction, or any and all
   other commercial damages or losses), even if such Contributor
   has been advised of the possibility of such damages.

9. Accepting Warranty or Additional Liability. While redistributing
   the Work or Derivative Works thereof, You may choose to offer,
   and charge a fee for, acceptance of support, warranty, indemnity,
   or other liability obligations and/or rights consistent with this
   License. However, in accepting such obligations, You may act only
   on Your own behalf and on Your sole responsibility, not on behalf
   of any other Contributor, and only if You agree to indemnify,
   defend, and hold each Contributor harmless for any liability
   incurred by, or claims asserted against, such Contributor by reason
   of your accepting any such warranty or additional liability.

END OF TERMS AND CONDITIONS
