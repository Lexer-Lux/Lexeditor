/* Test-only writer spy. Does not modify the actor or its stamina. */
.intel_syntax noprefix
.text
.global writer_spy
.extern trace
writer_spy:
    lea rax, [rip + trace]
    inc QWORD PTR [rax]
    mov QWORD PTR [rax + 8], rcx
    mov DWORD PTR [rax + 16], edx
    mov QWORD PTR [rax + 24], rsp
    mov eax, 0x5a
    ret
.section .note.GNU-stack,"",@progbits
