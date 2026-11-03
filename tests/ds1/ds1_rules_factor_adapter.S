.intel_syntax noprefix
.text
.global call_factor
call_factor:
 push r14
 mov r14d, esi
 sub rsp, 32
 call rdi
 add rsp, 32
 pop r14
 ret
.section .note.GNU-stack,"",@progbits
