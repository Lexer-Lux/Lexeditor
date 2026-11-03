.intel_syntax noprefix
# Original Lexeditor selectors. Appended routines are leaf functions:
# no calls, stack writes or nonvolatile register changes.
.section .text.classifier,"ax"
.global bands_classifier
bands_classifier:
    test r9b, r9b
    jnz forced_class
    divss xmm0, xmm1
    lea r10, [rip + bands_table]
    mov ecx, DWORD PTR [rip + bands_count]
class_scan:
    comiss xmm0, DWORD PTR [r10]
    jbe class_found
    add r10, 32
    dec ecx
    jnz class_scan
    sub r10, 32
class_found:
    mov eax, DWORD PTR [r10 + 4]
    cmp eax, 1
    jne class_done
    test r8b, r8b
    jz class_done
    cmp DWORD PTR [rip + special_enabled], 0
    je class_done
    xor eax, eax
class_done:
    ret
forced_class:
    mov eax, 4
    ret

.section .text.recovery,"ax"
.global bands_recovery
bands_recovery:
    test r9b, r9b
    jnz forced_recovery
    divss xmm0, xmm1
    lea r10, [rip + bands_table]
    mov ecx, DWORD PTR [rip + bands_count]
recovery_scan:
    comiss xmm0, DWORD PTR [r10]
    jbe recovery_found
    add r10, 32
    dec ecx
    jnz recovery_scan
    sub r10, 32
recovery_found:
    movss xmm0, DWORD PTR [r10 + 8]
    cmp DWORD PTR [r10 + 4], 1
    jne recovery_done
    test r8b, r8b
    jz recovery_done
    cmp DWORD PTR [rip + special_enabled], 0
    je recovery_done
    movss xmm0, DWORD PTR [rip + special_recovery]
recovery_done:
    ret
forced_recovery:
    movss xmm0, DWORD PTR [rip + forced_rate]
    ret

# This call site already owns the native caller's frame and shadow space.
.section .text.factor,"ax"
.global bands_factor
bands_factor:
    mov rcx, rsi
    call maximum_load
    movaps xmm1, xmm0
    movaps xmm0, xmm7
    movzx r8d, dil
    movzx r9d, bl
    call bands_recovery
    movaps xmm6, xmm0
    .org 41, 0x90

# In-place body only; preserve the existing prologue, saved xmm6 and epilogue.
.section .text.fraction,"ax"
.global bands_fraction
bands_fraction:
    movss xmm6, DWORD PTR [rip + one]
    xorps xmm5, xmm5
    divss xmm3, xmm1
    lea rcx, [rip + bands_table]
    mov eax, DWORD PTR [rip + bands_count]
fraction_scan:
    comiss xmm3, DWORD PTR [rcx]
    jbe fraction_found
    add rcx, 32
    dec eax
    jnz fraction_scan
    sub rcx, 32
fraction_found:
    movaps xmm2, xmm5
    movss xmm4, DWORD PTR [rcx + 16]
    comiss xmm4, xmm5
    je fraction_store
    movaps xmm2, xmm3
    subss xmm2, DWORD PTR [rcx + 12]
    divss xmm2, xmm4
    maxss xmm2, xmm5
    minss xmm2, xmm6
fraction_store:
    movss DWORD PTR [rsp + 0x20], xmm2
    lea rax, [rsp + 0x20]
    .org 151, 0x90
