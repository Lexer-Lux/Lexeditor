"""Auditable x86 source for issue93; assembled only by its verifier/build tool."""
BASE = 0x027B0000
CALLBACK = BASE
DEBIT = BASE + 0x400
ROW = BASE + 0x500
NUMBER = BASE + 0x600
EXTENT = BASE + 0x700
DEFS = BASE + 0x1000
PAGES = BASE + 0x1400
VIEWS = BASE + 0x1800
MAPS = BASE + 0x1A00
ACTIVE = BASE + 0x1C00
PAGE_COUNTS = BASE + 0x1C10

SOURCES = {
CALLBACK: f"""
push ebx
push ebp
push esi
push edi
sub esp, 24
mov eax, dword ptr [esp+44]
imul ebp,eax,0x1d0
add ebp,0x1cff082
cmp eax,2
ja fallback
mov byte ptr [{ACTIVE}+eax],0
movzx ecx,byte ptr [ebp+0x141]
cmp ecx,7
ja fallback
imul ecx,ecx,0x98
movzx ebx,word ptr [ecx+0x1cfe140]
test ebx,ebx
jz fallback
lea edx,[ebx-1]
test edx,ebx
jnz fallback
bsf ebx,ebx
movzx ecx,byte ptr [{PAGES}+ebx]
test ecx,ecx
jz fallback
mov byte ptr [{ACTIVE}+eax],1
mov byte ptr [{PAGE_COUNTS}+eax],cl
imul edi,eax,160
add edi,{VIEWS}
mov dword ptr [esp+4],edi
imul esi,eax,128
add esi,{MAPS}
imul edx,ebx,68
add edx,0x1cfdcbc
mov dword ptr [esp],edx
shl ebx,6
add ebx,{DEFS}
mov dword ptr [esp+20],ebx
mov dword ptr [esp+8],0
slot:
mov dword ptr [edi],0
mov byte ptr [edi+4],2
mov dword ptr [esi],0
mov ecx,dword ptr [esp+8]
mov ebx,dword ptr [esp+20]
movzx eax,byte ptr [ebx+ecx*2]
test eax,eax
jz next_slot
mov byte ptr [edi],al
movzx ebx,byte ptr [ebx+ecx*2+1]
mov dword ptr [esp+12],ebx
mov edx,ebp
mov ecx,32
find_stock:
cmp byte ptr [edx],al
je copy_stock
add edx,5
dec ecx
jnz find_stock
jmp gate
copy_stock:
mov eax,dword ptr [edx]
mov dword ptr [edi],eax
mov al,byte ptr [edx+4]
mov byte ptr [edi+4],al
mov dword ptr [esi],edx
gate:
mov eax,dword ptr [esp+12]
cmp eax,255
je quantity
mov edx,dword ptr [esp]
bt dword ptr [edx],eax
jc quantity
or byte ptr [edi+4],2
quantity:
cmp byte ptr [edi+1],0
jne next_slot
or byte ptr [edi+4],2
next_slot:
add edi,5
add esi,4
inc dword ptr [esp+8]
cmp dword ptr [esp+8],32
jb slot
mov eax,dword ptr [esp+4]
jmp done
fallback:
mov eax,ebp
done:
add esp,24
pop edi
pop esi
pop ebp
pop ebx
ret
""",
DEBIT: f"""
pushad
lea eax,[ecx-1]
sub eax,{VIEWS}
cmp eax,480
jae debit_done
xor edx,edx
mov ebx,5
div ebx
test edx,edx
jnz debit_done
mov edx,dword ptr [{MAPS}+eax*4]
test edx,edx
jz debit_done
mov al,byte ptr [ecx]
mov byte ptr [edx+1],al
test al,al
jnz debit_done
mov byte ptr [edx],0
debit_done:
popad
inc edx
add ecx,5
cmp edx,esi
jl 0x4fe6ff
jmp 0x4fe723
""",
ROW: f"""
mov al,byte ptr [esi+1]
mov ebx,7
cmp esi,{VIEWS}
jb row_done
cmp esi,{VIEWS+480}
jae row_done
cmp byte ptr [esi],0
setne al
row_done:
jmp 0x4c8a14
""",
NUMBER: f"""
add esp,0x1c
cmp esi,{VIEWS}
jb native_number
cmp esi,{VIEWS+480}
jae native_number
jmp 0x4c8a4e
native_number:
test ebx,ebx
je 0x4c8a70
jmp 0x4c8a4e
""",
EXTENT: f"""
push ecx
movzx ecx,byte ptr [0x1d768eb]
cmp ecx,2
ja extent_done
cmp dword ptr [0x1d768d0],0x4c8820
jne extent_done
cmp byte ptr [{ACTIVE}+ecx],1
jne extent_done
movzx ebx,byte ptr [{PAGE_COUNTS}+ecx]
shl ebx,2
dec ebx
extent_done:
pop ecx
mov eax,ebx
mov byte ptr [0x1d768f0],bl
jmp 0x4fdebC
""",
}

COLOR_NUMBER = BASE + 0x800
SOURCES[COLOR_NUMBER] = f"""
cmp esi,{VIEWS}
jb native_color
cmp esi,{VIEWS+480}
jae native_color
mov eax,dword ptr [0x1d2b100]
mov ecx,dword ptr [esp+0x10]
mov edx,dword ptr [esp+0xc]
push ebx
push eax
mov eax,dword ptr [esp+0x10]
push ecx
mov ecx,dword ptr [esp+0x10]
push edx
push eax
push ecx
call 0x4a3400
add esp,0x18
ret
native_color:
jmp 0x4a3570
"""
