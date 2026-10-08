/* Original Windows x64 wrapper for Lexeditor issue #856.
 * RCX = actor, EDX = stamina delta. Only the sprint-drain call is redirected.
 * The general stamina writer is unchanged. Native getters resolve battle/target.
 * Six nonvolatile registers and 56 bytes of stack are described by unwind data.
 */
.intel_syntax noprefix
.text
.global sprint_charge
.global sprint_end
.extern world_chr_man
.extern native_charge
.extern battle_getter
.extern no_battle_getter
.extern handle_accessor_vtable
.extern resolve_target

sprint_charge:
    push rbx
    push rsi
    push rdi
    push r12
    push r13
    push r14
    sub rsp, 0x38
    mov rbx, rcx
    mov DWORD PTR [rsp + 0x20], edx
    cmp edx, -1
    jne charge
    test rbx, rbx
    jz charge
    mov rsi, QWORD PTR [rip + world_chr_man]
    test rsi, rsi
    jz charge
    cmp QWORD PTR [rsi + 0x68], rbx
    jne charge
    cmp DWORD PTR [rbx + 0x3e8], 0
    jle charge

    /* Native active pool count: registry field + 2, with 29 allocated slots. */
    mov rax, QWORD PTR [rsi + 0x10]
    test rax, rax
    jz charge
    mov r14d, DWORD PTR [rax + 0x18]
    cmp r14d, 27
    ja charge
    add r14d, 2

    /* Retain ordinary costs whenever another player instance is loaded. */
    mov r12d, DWORD PTR [rsi + 0x38]
    cmp r12d, 0x4000
    ja charge
    test r12d, r12d
    jz charge
    mov rdi, QWORD PTR [rsi + 0x40]
    test rdi, rdi
    jz charge
    imul r12, r12, 0x38
    add r12, rdi
    jc charge
players:
    mov rax, QWORD PTR [rdi]
    test rax, rax
    jz next_player
    cmp rax, rbx
    jne charge
next_player:
    add rdi, 0x38
    cmp rdi, r12
    jb players

    xor r13d, r13d
pool:
    mov rax, QWORD PTR [rsi + r13*8 + 0x440]
    test rax, rax
    jz next_pool
    mov r12d, DWORD PTR [rax]
    cmp r12d, 0x4000
    ja charge
    test r12d, r12d
    jz next_pool
    mov rdi, QWORD PTR [rax + 8]
    test rdi, rdi
    jz charge
    imul r12, r12, 0x38
    add r12, rdi
    jc charge
actor:
    mov rax, QWORD PTR [rdi]
    test rax, rax
    jz next_actor
    cmp rax, rbx
    je next_actor
    cmp DWORD PTR [rax + 0x3e8], 0
    jle next_actor
    mov rcx, QWORD PTR [rax + 0x70]
    test rcx, rcx
    jz charge
    mov rax, QWORD PTR [rcx]
    test rax, rax
    jz charge
    mov rax, QWORD PTR [rax + 0xc8]
    lea rdx, [rip + no_battle_getter]
    cmp rax, rdx
    je next_actor
    lea rdx, [rip + battle_getter]
    cmp rax, rdx
    jne charge
    mov rdx, QWORD PTR [rcx + 0x230]
    test rdx, rdx
    jz charge
    mov rdx, QWORD PTR [rdx + 0x30]
    test rdx, rdx
    jz charge
    cmp DWORD PTR [rdx + 0xe0], 3
    ja charge
    mov QWORD PTR [rsp + 0x28], rdx
    call rax
    test al, al
    jz next_actor

    /* The native getter resolves a cached slot or a registry handle. */
    mov rcx, QWORD PTR [rsp + 0x28]
    cmp DWORD PTR [rcx + 0x58], 1
    jne charge
    lea rax, [rip + handle_accessor_vtable]
    cmp QWORD PTR [rcx + 0x78], rax
    jne charge
    cmp QWORD PTR [rcx + 0x80], -1
    je charge
    add rcx, 0x78
    cmp QWORD PTR [rcx + 0x10], 0
    jne target_ready
    /* Validate fallback storage before handing the handle to the native getter. */
    mov edx, DWORD PTR [rcx + 8]
    mov eax, edx
    shr eax, 14
    and eax, 0x3f
    cmp eax, r14d
    jae charge
    mov rax, QWORD PTR [rsi + rax*8 + 0x440]
    test rax, rax
    jz charge
    cmp DWORD PTR [rax], 0x4000
    ja charge
    and edx, 0x3fff
    cmp edx, DWORD PTR [rax]
    jae charge
    mov rax, QWORD PTR [rax + 8]
    test rax, rax
    jz charge
    imul rdx, rdx, 0x38
    add rax, rdx
    jc charge
target_ready:
    call resolve_target
    test rax, rax
    jz charge
    cmp rax, rbx
    je charge
next_actor:
    add rdi, 0x38
    cmp rdi, r12
    jb actor
next_pool:
    inc r13d
    cmp r13d, r14d
    jb pool
    /* Zero means no return value is relied upon by the inspected caller. */
    xor eax, eax
    add rsp, 0x38
    pop r14
    pop r13
    pop r12
    pop rdi
    pop rsi
    pop rbx
    ret
charge:
    mov rcx, rbx
    mov edx, DWORD PTR [rsp + 0x20]
    add rsp, 0x38
    pop r14
    pop r13
    pop r12
    pop rdi
    pop rsi
    pop rbx
    jmp native_charge
sprint_end:
.section .note.GNU-stack,"",@progbits
