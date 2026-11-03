# ModEngine2 launcher source fixture

`modengine2_launcher.cpp` is an unmodified, MIT-licensed upstream source fixture,
not a proprietary game file or a compiled runtime.

- Source: https://github.com/AltimorTASDK/ModEngine2/blob/76690e95d5022ba6f8d1bc24faea1f1bfde2ec6d/launcher/launcher.cpp
- Upstream revision: `76690e95d5022ba6f8d1bc24faea1f1bfde2ec6d`
- Git blob: `6e79759da92f0a12a7bcefb5a469e85c3414298a`
- License: upstream `LICENSE-MIT`, retained verbatim in
  `plugins/ds1/modengine/LICENSE-MIT`.
- Authors: the ModEngine2 project and contributors, including the DSR fork by
  AltimorTASDK. Upstream source is preserved byte-for-byte for drift detection.

The fixture tests source preparation, not runtime injection. The separately
compiled path helper tests path derivation only. A passing test is not evidence
that ModEngine2 launched Dark Souls Remastered or redirected any game file.
