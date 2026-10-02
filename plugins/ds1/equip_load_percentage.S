/* Equip-load display island for the reviewed Remastered build.
 * Entered by JMP at RVA 006B3E58, with RSI = the native menu snapshot.
 * R8/R9 already point to the game's formatted current/max strings.
 * Do not change RSP, the strings, or any nonvolatile register.
 * Only the existing formatter call receives a fifth variadic argument.
 */
.intel_syntax noprefix
.text
.global patch_start, fallback_disp, resume_disp, percentage_format
patch_start:
    mov r10d, DWORD PTR [rsi+0x14]
    mov eax, DWORD PTR [rsi+0x40]
    cmp eax, 0x80000000
    jne current_sign
    xor eax, eax
current_sign:
    test eax, eax
    js current_ready
    mov r10d, eax
current_ready:
    mov r11d, DWORD PTR [rsi+0x18]
    mov eax, DWORD PTR [rsi+0x44]
    cmp eax, 0x80000000
    jne maximum_sign
    xor eax, eax
maximum_sign:
    test eax, eax
    js maximum_ready
    mov r11d, eax
maximum_ready:
    /* Reject negative, infinite or NaN values without FP comparisons. */
    test r10d, r10d
    js vanilla
    cmp r10d, 0x7f800000
    jae vanilla
    test r11d, r11d
    jle vanilla
    cmp r11d, 0x7f800000
    jae vanilla
    movd xmm0, r10d
    cvtss2sd xmm0, xmm0
    movd xmm1, r11d
    cvtss2sd xmm1, xmm1
    divsd xmm0, xmm1
    mulsd xmm0, QWORD PTR [rip+hundred]
    movq QWORD PTR [rsp+0x20], xmm0
    lea rdx, [rip+percentage_format]
    jmp resume
vanilla:
    .byte 0x48,0x8d,0x15
fallback_disp:
    .long 0
resume:
    .byte 0xe9
resume_disp:
    .long 0
    .balign 8,0
hundred:
    .double 100.0
percentage_format:
    .short 37,115,47,37,115,32,40,37,46,49,102,37,37,41,0
