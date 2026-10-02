# Test-only ABI adapter. Executes Lexeditor payload bytes, never game code.
.intel_syntax noprefix
.text
.global entry
entry:
    push rbx
    push r12
    push r13
    push rsi
    sub rsp, 72
.ifdef WINDOWS
    mov r11, rcx
    mov rsi, rdx
    mov r12, r8
.else
    mov r11, rdi
    mov r12, rdx
.endif
    mov r13, rsp
    stmxcsr [rsp+56]
    ldmxcsr [r12+44]
    mov rax, 0x123456789abcdef0
    mov r8, 0x1122334455667788
    mov r9, 0x8877665544332211
    movdqu xmm0, [r12]
    movdqu xmm1, [r12+16]
    mov qword ptr [rsp+32], -1
    mov qword ptr [rsp+40], -1
    pushfq
    pop qword ptr [r12+32]
    stmxcsr [r12+40]
    lea rbx, [rip+capture]
    mov [r12+48], rbx
    jmp r11
capture:
    pushfq
    pop qword ptr [r12+56]
    stmxcsr [r12+64]
    mov [r12+72], rax
    mov [r12+80], r8
    mov [r12+88], r9
    movdqu [r12+96], xmm0
    movdqu [r12+112], xmm1
    mov [r12+128], rdx
    mov rax, [rsp+32]
    mov [r12+136], rax
    mov [r12+144], rsp
    mov [r12+152], r13
    mov rax, [rsp+40]
    mov [r12+160], rax
    ldmxcsr [rsp+56]
    add rsp, 72
    pop rsi
    pop r13
    pop r12
    pop rbx
    ret
# Explicit tail padding keeps ELF and PE/COFF section bytes identical.
# It is outside the adapter's return and never executed.
    .fill (16 - ((. - entry) % 16)) % 16, 1, 0x90
