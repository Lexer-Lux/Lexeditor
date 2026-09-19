"""GF HP Casting: native battle-menu hooks, separate from stock consumption."""
BASE=0x027A7000
HP=BASE
TOTAL=BASE+0x100
ALLOW=BASE+0x200
ROW=BASE+0x300
NUMBER=BASE+0x400
SELECT=BASE+0x500
COMMIT=BASE+0x600
COSTS=BASE+0x800
SOURCES={
HP:f'''
xor edi,edi
movzx eax,byte ptr [0x1d768eb]
cmp eax,2
ja done
mov esi,eax
movzx eax,byte ptr [eax+0x1cfe74c]
cmp eax,10
ja done
imul eax,eax,152
movzx ecx,word ptr [eax+0x1cfe140]
test ecx,ecx
jz done
lea edx,[ecx-1]
test edx,ecx
jnz done
bsf ecx,ecx
imul eax,ecx,68
test byte ptr [eax+0x1cfdcb9],1
jz done
lea edi,[eax+0x1cfdcba]
imul esi,esi,0x1d0
test byte ptr [esi+0x1cff01c],1
jz done
movzx eax,byte ptr [esi+0x1cff01d]
sub eax,0x40
cmp eax,ecx
jne done
lea edi,[esi+0x1cff018]
done:
ret
''',
TOTAL:f'''
movsx eax,byte ptr [0x1d768eb]
push eax
call dword ptr [0x1d768d0]
add esp,4
mov esi,eax
movzx ecx,byte ptr [0x1d768f4]
cmp ecx,32
ja invalid
xor ebx,ebx
xor edx,edx
loop_start:
cmp edx,ecx
jae done
movzx eax,byte ptr [edx+0x1d76904]
test eax,eax
jz next
cmp eax,3
ja invalid
movzx ebp,byte ptr [esi]
cmp ebp,57
jae invalid
movzx ebp,word ptr [{COSTS}+ebp*2]
imul eax,ebp
add ebx,eax
next:
add esi,5
inc edx
jmp loop_start
invalid:
mov ebx,0x7fffffff
done:
ret
''',
ALLOW:f'''
push eax
call {HP}
pop eax
test edi,edi
jz deny
movzx eax,byte ptr [eax]
cmp eax,57
jae deny
movzx eax,word ptr [{COSTS}+eax*2]
push edi
push eax
call {TOTAL}
pop eax
pop edi
add eax,ebx
jc deny
movzx ecx,word ptr [edi]
cmp ecx,eax
jb deny
mov eax,1
ret
deny:
xor eax,eax
ret
''',
ROW:f'''
pushfd
pushad
mov eax,esi
call {ALLOW}
test eax,eax
popad
jz denied
popfd
test byte ptr [esi+4],2
jz ready
xor ebx,ebx
ready:
jmp 0x4c8a2a
denied:
popfd
xor ebx,ebx
jmp 0x4c8a2a
''',
NUMBER:f'''
movzx edx,byte ptr [esi]
cmp edx,57
jae unknown
movzx edx,word ptr [{COSTS}+edx*2]
jmp ready
unknown:
xor edx,edx
ready:
add ecx,0x70
jmp 0x4c8a59
''',
SELECT:f'''
cmp dword ptr [0x1d768d0],0x4c8820
jne native
pushfd
pushad
call {ALLOW}
test eax,eax
popad
jz denied
popfd
cmp byte ptr [eax+1],0
je reject
test byte ptr [eax+4],2
jnz reject
jmp 0x4fe2c3
native:
cmp esi,ebp
jle reject
test byte ptr [eax+4],2
jnz reject
jmp 0x4fe2c3
denied:
popfd
reject:
jmp 0x4fe2e5
''',
COMMIT:f'''
cmp dword ptr [0x1d768d0],0x4c8820
jne native
pushfd
pushad
call {HP}
test edi,edi
jz denied
push edi
call {TOTAL}
pop edi
movzx eax,word ptr [edi]
cmp eax,ebx
jb denied
sub eax,ebx
mov word ptr [edi],ax
popad
popfd
native:
mov esi,dword ptr [esp+0x1c]
xor edx,edx
jmp 0x4fe658
denied:
popad
popfd
call 0x4bb570
push 5
call 0x4a9780
add esp,4
push eax
push ecx
xor eax,eax
clear:
mov byte ptr [eax+0x1d76904],0
inc eax
cmp eax,32
jb clear
pop ecx
pop eax
mov byte ptr [esp+0x10],6
jmp 0x4fe768
'''
}
