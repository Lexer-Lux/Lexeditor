.intel_syntax noprefix
# Original Lexeditor fixed-span replacements. No game code is reproduced.
# Existing prologue, stack frame, saved registers and epilogue remain intact.
.section .text.factor,"ax"
.global factor_start, factor_values, overload_limit
factor_start:
    lea rcx, [rip + factor_values]
    movss xmm6, DWORD PTR [rcx + r14*4]
    jmp factor_end
    .org 16, 0x90
factor_values:
    .float 1.0, 1.0, 1.0, 0.8, 0.7
overload_limit:
    .float 1.0
    .org 41, 0x90
factor_end:

.section .text.fraction,"ax"
.global fraction_start
fraction_start:
    movss xmm6, DWORD PTR [rip + one]
    xorps xmm5, xmm5
    divss xmm3, xmm1
    movaps xmm2, xmm5
    comiss xmm3, DWORD PTR [rip + overload_limit]
    ja store_fraction
    movss xmm4, DWORD PTR [rip + medium_limit]
    movss xmm1, DWORD PTR [rip + light_limit]
    movaps xmm2, xmm3
    comiss xmm3, xmm4
    ja heavy_fraction
    comiss xmm3, xmm1
    ja medium_fraction
    divss xmm2, xmm1
    jmp clamp_fraction
medium_fraction:
    subss xmm2, xmm1
    subss xmm4, xmm1
    divss xmm2, xmm4
    jmp clamp_fraction
heavy_fraction:
    subss xmm2, xmm4
    movss xmm1, DWORD PTR [rip + overload_limit]
    subss xmm1, xmm4
    divss xmm2, xmm1
clamp_fraction:
    comiss xmm5, xmm2
    jbe upper_fraction
    movaps xmm2, xmm5
upper_fraction:
    comiss xmm2, xmm6
    jbe store_fraction
    movaps xmm2, xmm6
store_fraction:
    movss DWORD PTR [rsp+0x20], xmm2
    lea rax, [rsp+0x20]
    .org 151, 0x90
