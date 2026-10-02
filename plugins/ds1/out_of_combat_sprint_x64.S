/* Issue #856. Original Windows x64 leaf wrapper, not extracted game code.
 * RCX = actor, EDX = native stamina delta. Only the sprint call is redirected.
 * No stack changes, nonvolatile registers, floating-point state or extra calls.
 * All externals are relative symbols resolved by the source reproducibility test.
 */
.intel_syntax noprefix
.text
.global sprint_charge
.extern world_chr_man
.extern native_charge
.extern battle_getter
.extern no_battle_getter
.extern handle_accessor_vtable

sprint_charge:
    cmp edx, -1
    jne native_charge
    mov r8, QWORD PTR [rip + world_chr_man]
    test r8, r8
    jz charge
    cmp QWORD PTR [r8 + 0x68], rcx
    jne charge
    test rcx, rcx
    jz charge
    cmp DWORD PTR [rcx + 0x3e8], 0
    jle charge

    /* The native multiplayer-player pool. Another loaded player keeps vanilla. */
    mov r11d, DWORD PTR [r8 + 0x38]
    cmp r11d, 0x4000
    ja charge
    test r11d, r11d
    jz charge
    mov r10, QWORD PTR [r8 + 0x40]
    test r10, r10
    jz charge
    imul r11, r11, 0x38
    add r11, r10
    jc charge
players:
    mov rdx, QWORD PTR [r10]
    test rdx, rdx
    jz next_player
    cmp rdx, rcx
    jne charge
next_player:
    add r10, 0x38
    cmp r10, r11
    jb players

    /* Constructor and pool registration both bound this array to 29 pools. */
    xor r9d, r9d
pool:
    mov rax, QWORD PTR [r8 + r9*8 + 0x440]
    test rax, rax
    jz next_pool
    mov r11d, DWORD PTR [rax]
    cmp r11d, 0x4000
    ja charge
    test r11d, r11d
    jz next_pool
    mov r10, QWORD PTR [rax + 8]
    test r10, r10
    jz charge
    imul r11, r11, 0x38
    add r11, r10
    jc charge
actor:
    mov rdx, QWORD PTR [r10]
    test rdx, rdx
    jz next_actor
    cmp rdx, rcx
    je next_actor
    cmp DWORD PTR [rdx + 0x3e8], 0
    jle next_actor
    mov rdx, QWORD PTR [rdx + 0x70]
    test rdx, rdx
    jz next_actor
    mov rax, QWORD PTR [rdx]
    test rax, rax
    jz charge
    mov rax, QWORD PTR [rax + 0xc8]
    lea rdx, [rip + no_battle_getter]
    cmp rax, rdx
    je next_actor
    lea rdx, [rip + battle_getter]
    cmp rax, rdx
    jne charge
    mov rdx, QWORD PTR [r10]
    mov rdx, QWORD PTR [rdx + 0x70]
    mov rdx, QWORD PTR [rdx + 0x230]
    test rdx, rdx
    jz next_actor
    mov rdx, QWORD PTR [rdx + 0x30]
    test rdx, rdx
    jz next_actor
    cmp DWORD PTR [rdx + 0xe0], 3
    jb next_actor
    ja charge

    /* A battle target we cannot resolve is NOT permission for free stamina. */
    cmp DWORD PTR [rdx + 0x58], 1
    jne charge
    lea rax, [rip + handle_accessor_vtable]
    cmp QWORD PTR [rdx + 0x78], rax
    jne charge
    cmp DWORD PTR [rdx + 0x80], -1
    je charge
    mov rax, QWORD PTR [rdx + 0x88]
    test rax, rax
    jnz resolved_slot

    /* The native handle fallback: pool bits 14..19, slot bits 0..13. */
    mov edx, DWORD PTR [rdx + 0x80]
    mov eax, edx
    shr eax, 14
    and eax, 0x3f
    cmp eax, 29
    jae charge
    mov rax, QWORD PTR [r8 + rax*8 + 0x440]
    test rax, rax
    jz charge
    and edx, 0x3fff
    cmp edx, DWORD PTR [rax]
    jae charge
    mov rax, QWORD PTR [rax + 8]
    test rax, rax
    jz charge
    imul rdx, rdx, 0x38
    add rax, rdx
    jc charge
resolved_slot:
    mov rax, QWORD PTR [rax]
    test rax, rax
    jz charge
    cmp rax, rcx
    je charge
next_actor:
    add r10, 0x38
    cmp r10, r11
    jb actor
next_pool:
    inc r9d
    cmp r9d, 29
    jb pool
    ret
charge:
    mov edx, -1
    jmp native_charge
