.intel_syntax noprefix
# SysV entry: rdi=code, rsi=player, xmm0=weight, edx=special, ecx=forced.
# Recreate an interior native frame with aligned calls and separate shadow space.
# The test-only continuation moves xmm6 to xmm0 and jumps to r12.
.text
.global bands_factor
.type bands_factor, @function
bands_factor:
    push rbx
    push r12
    mov r11, rdi
    movzx ebx, cl
    mov edi, edx
    movaps xmm7, xmm0
    sub rsp, 40
    lea r12, [rip + factor_return]
    jmp r11
factor_return:
    add rsp, 40
    pop r12
    pop rbx
    ret
.size bands_factor, .-bands_factor
.section .note.GNU-stack,"",@progbits
