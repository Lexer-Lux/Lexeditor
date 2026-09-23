"""Source of plugins/ff8/flying_eva.PHYSICAL_TEMPLATE, assembled at PHYSICAL_CAVE.

verify_ff8_flying_physical.py re-assembles this and compares it with the
embedded bytes. Keystone is a development dependency only.
"""
import keystone

BASE = 0x027A2880
BONUS_MARK = 0x7B  # placeholder imm8, replaced per bonus; must not occur elsewhere

ASM = f"""
applies:
    cmp edx, 0x270
    jb applies_no
    push ecx
    mov ecx, dword ptr [edx + 0x1d27b10]
    test ecx, ecx
    jz applies_pop
    mov ecx, dword ptr [ecx]
    test byte ptr [ecx + 0xf7], 2
    jz applies_pop
    test dword ptr [eax + 0x1d27b8c], 0x1000
    jz applies_pop
    test dword ptr [eax + 0x1d27b18], 0x2000
    jnz applies_pop
    pop ecx
    mov eax, 1
    ret
applies_pop:
    pop ecx
applies_no:
    xor eax, eax
    ret

bypass:
    cmp byte ptr [0x1d2a238], 0xff
    jne bypass_none
    push edx
    mov eax, dword ptr [esp + 8]
    imul eax, eax, 0xd0
    call applies
    pop edx
    test eax, eax
    jnz bypass_none
    jmp 0x492b22
bypass_none:
    jmp 0x492b1f

roll:
    mov dl, byte ptr [ecx + 0x1d27bd2]
    push eax
    push edx
    mov edx, ecx
    mov eax, dword ptr [esp + 0xc]
    imul eax, eax, 0xd0
    call applies
    test eax, eax
    pop edx
    pop eax
    jz roll_vanilla
    sub eax, edx
    movzx ecx, byte ptr [0x1d2a238]
    add eax, ecx
    cmp eax, 100
    jle roll_clamped
    mov eax, 100
roll_clamped:
    sub eax, {BONUS_MARK}
    jmp 0x492bf6
roll_vanilla:
    jmp 0x492be6

gunblade:
    lea edx, [ebp + ebp*2]
    mov byte ptr [0x1d28e07], cl
    push eax
    push edx
    push ecx
    imul edx, ebp, 0xd0
    mov eax, dword ptr [esp + 0x14]
    imul eax, eax, 0xd0
    call applies
    test eax, eax
    jz gunblade_resume
    mov eax, dword ptr [esp + 0x14]
    imul eax, eax, 0xd0
    movzx eax, byte ptr [eax + 0x1d27bd2]
    shr eax, 1
    movzx ecx, byte ptr [edx + 0x1d27bd3]
    sub eax, ecx
    movzx ecx, byte ptr [edx + 0x1d27bd2]
    sub eax, ecx
    movzx ecx, byte ptr [0x1d2a238]
    add eax, ecx
    cmp eax, 100
    jle gunblade_clamped
    mov eax, 100
gunblade_clamped:
    sub eax, {BONUS_MARK}
    jns gunblade_scale
    xor eax, eax
gunblade_scale:
    imul eax, eax, 255
    cdq
    mov ecx, 100
    idiv ecx
    push eax
    call 0x48f020
    and eax, 0xff
    pop edx
    test edx, edx
    jz gunblade_miss
    cmp edx, eax
    jb gunblade_miss
gunblade_resume:
    pop ecx
    pop edx
    pop eax
    jmp 0x48f530
gunblade_miss:
    pop ecx
    pop edx
    pop eax
    xor eax, eax
    pop ebp
    ret
"""

ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)


def assemble():
    code, _ = ks.asm(ASM, BASE)
    code = bytes(code)
    labels = {}
    # Find each label's address by assembling the prefix up to it.
    for name in ("bypass", "roll", "gunblade"):
        prefix = ASM[:ASM.index(f"\n{name}:")]
        labels[name] = BASE + len(bytes(ks.asm(prefix, BASE)[0]))
    return code, labels


if __name__ == "__main__":
    code, labels = assemble()
    marks = [i for i in range(len(code) - 2) if code[i:i + 3] == bytes((0x83, 0xE8, BONUS_MARK))]
    print("length", hex(len(code)))
    print({k: hex(v) for k, v in labels.items()})
    print("bonus offsets", marks)
    print(code.hex(" ").upper())
