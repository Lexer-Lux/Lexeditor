/* Native call replacement at 397577. Original RDI=controller, RBX=pad.
 * Run the displaced gesture handler first. The native held-duration loop follows
 * our return, so an R2 draw has the same duration accounting as an R1 draw.
 * A real CALL, not an interior JMP, permits ordinary x64 unwind metadata.
 */
.intel_syntax noprefix
.text
.global ammo_frame_bridge
.extern game_gestures
.extern ammo_route
.seh_proc ammo_frame_bridge
ammo_frame_bridge:
    sub rsp, 0x28
    .seh_stackalloc 0x28
    .seh_endprologue
    call game_gestures
    mov rcx, rdi
    mov rdx, rbx
    lea r8, [rsp+0x30]
    call ammo_route
    add rsp, 0x28
    ret
.seh_endproc
