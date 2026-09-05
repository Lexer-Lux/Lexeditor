# FF8 Better Targeting renderer fix

FFNx replaces native `FF8_EN.exe` function `004B75B0` with
`ff8_draw_icon_or_key3`. The old Hext patch at native address `004B7622`
therefore never ran. Apply this source change to pinned FFNx revision
`1e291885da4ddb482188b81a5198d56a1915fde6` before building the Lexeditor
derivative.

The selected-target wrapper changes the native red Target label (icon 15) to
the hand (icon 0) and marks only that call in bit 31 of `a6`. FFNx already masks
`a6` to 26 bits. The replacement consumes that otherwise discarded marker and
omits the SP1 descriptor's bit-25 semi-transparency contribution. Other hand
icons are unchanged. The setting is `enable_ff8_better_targeting` and defaults
to false.

Static checks prove the call, marker, FFNx replacement, and final primitive
construction. A live battle test is still required to confirm that the selected
hand is solid on screen. This work does not install or launch the game.
