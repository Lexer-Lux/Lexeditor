// GPL-3.0-or-later. Loader-owned GF spellbook runtime for Lexeditor #93.
#include "lexeditor_ff8_gf_spellbooks.h"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>

#include "cfg.h"
#include "common.h"
#include "globals.h"
#include "log.h"
#include "patch.h"

extern "C" {
// The rejected prototype put these structures at 0x027B.... inside the process.
// Keep the already-audited layout/ABI, but let the DLL loader own their memory.
__declspec(align(16)) unsigned char lex_spell_defs[1024] = {};
unsigned char lex_spell_gf_pages[16] = {};
unsigned char lex_spell_views[480] = {};
unsigned char lex_spell_maps[384] = {};
unsigned char lex_spell_active[3] = {};
unsigned char lex_spell_party_pages[3] = {};
}

namespace {
constexpr std::uintptr_t kListBuilder = 0x004C8820;
constexpr std::uintptr_t kDebit = 0x004FE71B;
constexpr std::uintptr_t kRow = 0x004C8A0C;
constexpr std::uintptr_t kNumber = 0x004C8A47;
constexpr std::uintptr_t kColorNumber = 0x004C8A68;
constexpr std::uintptr_t kExtent = 0x004FDEB4;
constexpr std::size_t kRuntimeBytes = 8 + sizeof(lex_spell_defs) + sizeof(lex_spell_gf_pages);
bool g_installed = false;

// MSVC inline assembler cannot encode an absolute immediate as a jmp/call
// operand. Keep the reviewed FF8 continuation addresses in storage so the
// naked hooks can transfer control indirectly without borrowing a register.
std::uint32_t g_debit_loop = 0x004FE6FF;
std::uint32_t g_debit_done = 0x004FE723;
std::uint32_t g_row_done = 0x004C8A14;
std::uint32_t g_number_continue = 0x004C8A4E;
std::uint32_t g_number_empty = 0x004C8A70;
std::uint32_t g_extent_done = 0x004FDEBC;
std::uint32_t g_color_draw = 0x004A3400;
std::uint32_t g_color_native = 0x004A3570;

struct RuntimeHeader {
    char magic[4];
    std::uint8_t version;
    std::uint8_t gf_count;
    std::uint8_t max_pages;
    std::uint8_t slots_per_page;
};
static_assert(sizeof(RuntimeHeader) == 8, "GF spellbook runtime header must stay packed");

bool load_runtime()
{
    char path[MAX_PATH] = {};
    std::snprintf(path, sizeof(path), "%s/%s/lexeditor/gf-spellbooks.bin",
        basedir, direct_mode_path.c_str());
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    if (!stream) return false;
    const auto size = stream.tellg();
    if (size != static_cast<std::streamoff>(kRuntimeBytes)) {
        ffnx_warning("GF Spellbooks: invalid runtime snapshot size; native Magic retained.\n");
        return false;
    }
    stream.seekg(0);
    RuntimeHeader header{};
    unsigned char definitions[sizeof(lex_spell_defs)]{};
    unsigned char pages[sizeof(lex_spell_gf_pages)]{};
    stream.read(reinterpret_cast<char *>(&header), sizeof(header));
    stream.read(reinterpret_cast<char *>(definitions), sizeof(definitions));
    stream.read(reinterpret_cast<char *>(pages), sizeof(pages));
    if (!stream || std::memcmp(header.magic, "LXSB", 4) || header.version != 1 ||
        header.gf_count != 16 || header.max_pages != 8 || header.slots_per_page != 4) {
        ffnx_warning("GF Spellbooks: unsupported runtime snapshot; native Magic retained.\n");
        return false;
    }
    bool any = false;
    for (unsigned gf = 0; gf < 16; ++gf) {
        const unsigned page_count = pages[gf];
        if (page_count > 8) {
            ffnx_warning("GF Spellbooks: invalid page count; native Magic retained.\n");
            return false;
        }
        any = any || page_count != 0;
        bool seen[57]{};
        for (unsigned slot = 0; slot < 32; ++slot) {
            const unsigned offset = gf * 64 + slot * 2;
            const unsigned magic = definitions[offset];
            const unsigned ability = definitions[offset + 1];
            const bool active_slot = slot < page_count * 4;
            if (!active_slot) {
                if (magic != 0 || ability != 255) {
                    ffnx_warning("GF Spellbooks: data exists beyond declared pages; native Magic retained.\n");
                    return false;
                }
                continue;
            }
            if (magic == 0) {
                if (ability != 255) {
                    ffnx_warning("GF Spellbooks: empty slot has an ability gate; native Magic retained.\n");
                    return false;
                }
                continue;
            }
            if (magic > 56 || seen[magic] || (ability != 255 && (ability < 1 || ability > 115))) {
                ffnx_warning("GF Spellbooks: invalid spell or ability ID; native Magic retained.\n");
                return false;
            }
            seen[magic] = true;
        }
    }
    if (!any) return false;
    std::memcpy(lex_spell_defs, definitions, sizeof(definitions));
    std::memcpy(lex_spell_gf_pages, pages, sizeof(pages));
    std::memset(lex_spell_views, 0, sizeof(lex_spell_views));
    std::memset(lex_spell_maps, 0, sizeof(lex_spell_maps));
    std::memset(lex_spell_active, 0, sizeof(lex_spell_active));
    std::memset(lex_spell_party_pages, 0, sizeof(lex_spell_party_pages));
    return true;
}

void nop_tail(std::uintptr_t site, std::size_t original_size)
{
    for (std::size_t i = 5; i < original_size; ++i)
        patch_code_byte(static_cast<std::uint32_t>(site + i), 0x90);
}
}

// This is the old, executable-backed list-building algorithm expressed as an
// x86 DLL callback. Only its mod-owned storage symbols changed. It deliberately
// falls through to FF8's native stock list unless exactly one GF is junctioned
// and that GF has a configured spellbook.
extern "C" __declspec(dllexport) __declspec(naked) void * lexeditor_ff8_gf_spellbook_list()
{
    __asm {
        push ebx
        push ebp
        push esi
        push edi
        sub esp, 24
        mov eax, dword ptr [esp+44]
        imul ebp,eax,01D0h
        add ebp,01CFF082h
        cmp eax,2
        ja fallback
        mov byte ptr [lex_spell_active+eax],0
        movzx ecx,byte ptr [ebp+0141h]
        cmp ecx,7
        ja fallback
        imul ecx,ecx,152
        movzx ebx,word ptr [ecx+01CFE140h]
        test ebx,ebx
        jz fallback
        lea edx,[ebx-1]
        test edx,ebx
        jnz fallback
        bsf ebx,ebx
        movzx ecx,byte ptr [lex_spell_gf_pages+ebx]
        test ecx,ecx
        jz fallback
        mov byte ptr [lex_spell_active+eax],1
        mov byte ptr [lex_spell_party_pages+eax],cl
        imul edi,eax,160
        lea edi,[lex_spell_views+edi]
        mov dword ptr [esp+4],edi
        imul esi,eax,128
        lea esi,[lex_spell_maps+esi]
        imul edx,ebx,68
        add edx,01CFDCBCh
        mov dword ptr [esp],edx
        shl ebx,6
        lea ebx,[lex_spell_defs+ebx]
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
    }
}

extern "C" __declspec(dllexport) __declspec(naked) void lexeditor_ff8_gf_spellbook_debit()
{
    __asm {
        pushad
        lea eax,[ecx-1]
        sub eax,offset lex_spell_views
        cmp eax,480
        jae debit_done
        xor edx,edx
        mov ebx,5
        div ebx
        test edx,edx
        jnz debit_done
        mov edx,dword ptr [lex_spell_maps+eax*4]
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
        jge debit_exit
        jmp dword ptr [g_debit_loop]
    debit_exit:
        jmp dword ptr [g_debit_done]
    }
}

extern "C" __declspec(dllexport) __declspec(naked) void lexeditor_ff8_gf_spellbook_row()
{
    __asm {
        mov al,byte ptr [esi+1]
        mov ebx,7
        cmp esi,offset lex_spell_views
        jb row_done
        cmp esi,offset lex_spell_views+480
        jae row_done
        cmp byte ptr [esi],0
        setne al
    row_done:
        jmp dword ptr [g_row_done]
    }
}

extern "C" __declspec(dllexport) __declspec(naked) void lexeditor_ff8_gf_spellbook_number()
{
    __asm {
        add esp,01Ch
        cmp esi,offset lex_spell_views
        jb native_number
        cmp esi,offset lex_spell_views+480
        jae native_number
        jmp dword ptr [g_number_continue]
    native_number:
        test ebx,ebx
        je number_empty
        jmp dword ptr [g_number_continue]
    number_empty:
        jmp dword ptr [g_number_empty]
    }
}

extern "C" __declspec(dllexport) __declspec(naked) void lexeditor_ff8_gf_spellbook_extent()
{
    __asm {
        push ecx
        movzx ecx,byte ptr ds:[01D768EBh]
        cmp ecx,2
        ja extent_done
        cmp dword ptr ds:[01D768D0h],004C8820h
        jne extent_done
        cmp byte ptr [lex_spell_active+ecx],1
        jne extent_done
        movzx ebx,byte ptr [lex_spell_party_pages+ecx]
        shl ebx,2
        dec ebx
    extent_done:
        pop ecx
        mov eax,ebx
        mov byte ptr ds:[01D768F0h],bl
        jmp dword ptr [g_extent_done]
    }
}

extern "C" __declspec(dllexport) __declspec(naked) void lexeditor_ff8_gf_spellbook_color_number()
{
    __asm {
        cmp esi,offset lex_spell_views
        jb native_color
        cmp esi,offset lex_spell_views+480
        jae native_color
        mov eax,dword ptr ds:[01D2B100h]
        mov ecx,dword ptr [esp+010h]
        mov edx,dword ptr [esp+00Ch]
        push ebx
        push eax
        mov eax,dword ptr [esp+010h]
        push ecx
        mov ecx,dword ptr [esp+010h]
        push edx
        push eax
        push ecx
        call dword ptr [g_color_draw]
        add esp,018h
        ret
    native_color:
        jmp dword ptr [g_color_native]
    }
}

void lexeditor_ff8_gf_spellbooks_install()
{
    if (!ff8 || !FF8_US_VERSION || g_installed || !load_runtime()) return;
    const unsigned char list[]   = {0x8B,0x44,0x24,0x04,0x8D,0x0C,0xC5,0x00,0x00,0x00,0x00};
    const unsigned char debit[]  = {0x42,0x83,0xC1,0x05,0x3B,0xD6,0x7C,0xDC};
    const unsigned char row[]    = {0x8A,0x46,0x01,0xBB,0x07,0x00,0x00,0x00};
    const unsigned char number[] = {0x83,0xC4,0x1C,0x85,0xDB,0x74,0x22};
    const unsigned char color[]  = {0xE8,0x03,0xAB,0xFD,0xFF};
    const unsigned char extent[] = {0x8B,0xC3,0x88,0x1D,0xF0,0x68,0xD7,0x01};
    if (std::memcmp(reinterpret_cast<void *>(kListBuilder),list,sizeof(list)) ||
        std::memcmp(reinterpret_cast<void *>(kDebit),debit,sizeof(debit)) ||
        std::memcmp(reinterpret_cast<void *>(kRow),row,sizeof(row)) ||
        std::memcmp(reinterpret_cast<void *>(kNumber),number,sizeof(number)) ||
        std::memcmp(reinterpret_cast<void *>(kColorNumber),color,sizeof(color)) ||
        std::memcmp(reinterpret_cast<void *>(kExtent),extent,sizeof(extent))) {
        ffnx_warning("GF Spellbooks: supported hook bytes changed; native Magic retained.\n");
        return;
    }
    replace_function(static_cast<std::uint32_t>(kListBuilder), reinterpret_cast<void *>(&lexeditor_ff8_gf_spellbook_list));
    nop_tail(kListBuilder, sizeof(list));
    replace_function(static_cast<std::uint32_t>(kDebit), reinterpret_cast<void *>(&lexeditor_ff8_gf_spellbook_debit));
    nop_tail(kDebit, sizeof(debit));
    replace_function(static_cast<std::uint32_t>(kRow), reinterpret_cast<void *>(&lexeditor_ff8_gf_spellbook_row));
    nop_tail(kRow, sizeof(row));
    replace_function(static_cast<std::uint32_t>(kNumber), reinterpret_cast<void *>(&lexeditor_ff8_gf_spellbook_number));
    nop_tail(kNumber, sizeof(number));
    replace_call(static_cast<std::uint32_t>(kColorNumber), reinterpret_cast<void *>(&lexeditor_ff8_gf_spellbook_color_number));
    replace_function(static_cast<std::uint32_t>(kExtent), reinterpret_cast<void *>(&lexeditor_ff8_gf_spellbook_extent));
    nop_tail(kExtent, sizeof(extent));
    g_installed = true;
    ffnx_info("GF Spellbooks: loader-owned runtime installed; fixed 0x027B cave is unused.\n");
}

extern "C" __declspec(dllexport) unsigned int lexeditor_ff8_gf_spellbooks_contract_version()
{
    return 1;
}
