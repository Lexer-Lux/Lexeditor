# PyLibDrawable model decoder

LEXEDITOR uses PyLibDrawable and libdrawable by Sage of Mirrors under the MIT
license in `LICENSE` to read RDR2 YDR geometry and shader references.

`pylibdrawable.pyd` is built for CPython 3.10 from PyLibDrawable commit
`a42e4d8df7f9e35ee81a88cbdf7cb51ae15a3c4a` and its pinned libdrawable commit
`f44016f07a7308347b62ee861bbfb10270817fc1`. LEXEDITOR adds one small extension:
the binding exposes the external texture names already stored in each shader.
Its SHA-256 is
`9DF27F2AF114E95AB4619798B578104D74D4A74610D9AFFAD6EA113C071D6E70`.

`pylibdrawable_geometry_beta2.pyd` preserves the prior unmodified
RedDead2Blend v0.0.2 binary. Its SHA-256 is
`F32D78F5302B79DAB392557F0319F7BE3E5267686D2196A52DA8A22D63F94021`.

Sources:

- https://github.com/Sage-of-Mirrors/PyLibDrawable
- https://github.com/Sage-of-Mirrors/librdr3
- https://github.com/Sage-of-Mirrors/RedDead2Blend/releases/tag/v0.0.2
