/* Isolated SysV test shim. The game is not executed by this fixture. */
.intel_syntax noprefix
.text
.global shim_start, shim_resume, shim_patch, shim_vanilla
shim_start:
    push rbx
    push rbp
    push r12
    push r13
    push r14
    push r15
    push rsi
    sub rsp, 0x40
    mov r12, rsi
    mov rsi, rdi
    mov r8, 0x11223344
    mov r9, 0x55667788
    mov rbx, 0x13579
    mov rbp, 0x24680
    mov r13, 0x13571357
    mov r14, 0x24682468
    mov r15, 0x31415926
    pcmpeqd xmm6, xmm6
    pcmpeqd xmm7, xmm7
    pcmpeqd xmm8, xmm8
    mov QWORD PTR [rsp+0x20], -1
    mov QWORD PTR [r12+96], rsp
    jmp shim_patch
shim_resume:
    mov QWORD PTR [r12], rdx
    mov rax, QWORD PTR [rsp+0x20]
    mov QWORD PTR [r12+8], rax
    mov QWORD PTR [r12+16], r8
    mov QWORD PTR [r12+24], r9
    mov QWORD PTR [r12+32], rbx
    mov QWORD PTR [r12+40], rbp
    mov QWORD PTR [r12+48], r13
    mov QWORD PTR [r12+56], r14
    mov QWORD PTR [r12+64], r15
    movq QWORD PTR [r12+72], xmm6
    movq QWORD PTR [r12+80], xmm7
    movq QWORD PTR [r12+88], xmm8
    mov QWORD PTR [r12+104], rsp
    add rsp, 0x40
    pop rsi
    pop r15
    pop r14
    pop r13
    pop r12
    pop rbp
    pop rbx
    ret
    .balign 16,0
shim_patch:
    .zero 174
shim_vanilla:
    .short 37,115,47,37,115,0
.section .note.GNU-stack,"",@progbits
