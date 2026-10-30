/* Prebuilt native module linking. Included by the loader so all application
 * paths share lx_apply's checks, memory protections and deferred hooks. */
#include <stdint.h>
#include <limits.h>
#include <stdlib.h>
#include <shlobj.h>

#define LX_MOD_HEADER 32u
#define LX_MAX_MODS 128u
#define LX_MAX_CLAIMS 8192u
#define LX_MAX_TOTAL (64u * 1024u * 1024u)

static unsigned lx_crc32(const unsigned char *data, size_t size)
{
    unsigned crc = ~0u;
    while (size--) {
        crc ^= *data++;
        for (int bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1)));
    }
    return ~crc;
}

/* Allocates a private linked patch. All offsets remain relative to the image,
 * including unwind metadata. The caller frees the returned buffer. */
int lx_link_module(const unsigned char *data, size_t size, unsigned base,
                   unsigned char **output, size_t *output_size, char *message, size_t capacity)
{
    *output = NULL;
    *output_size = 0;
    if (size < LX_MOD_HEADER + 28 || size > MAX_PATCH || memcmp(data, "LXD1MOD\0", 8) ||
        read32(data + 8) != 1 || read32(data + 24) > 1 || read32(data + 28) > 1 ||
        lx_crc32(data, size - 4) != read32(data + size - 4))
        return fail(message, capacity, "Damaged or unsupported prebuilt mod");
    unsigned length = read32(data + 12), fixes = read32(data + 16), claims = read32(data + 20);
    if (length < 24 || fixes > 65536 || claims > MAX_RECORDS ||
        LX_MOD_HEADER + (uint64_t)length + 8ull * (fixes + claims) + 4 != size)
        return fail(message, capacity, "Invalid prebuilt mod directory");
    const unsigned char *patch = data + LX_MOD_HEADER;
    if (memcmp(patch, "LXD1PAT\0", 8) || read32(patch + 8) != VERSION || read32(patch + 20) > MAX_RECORDS)
        return fail(message, capacity, "Unsupported prebuilt patch");
    size_t at = 24;
    unsigned old_base = 0;
    for (unsigned i = 0; i < read32(patch + 20); ++i) {
        if (at + 12 > length)
            return fail(message, capacity, "Truncated prebuilt patch");
        unsigned kind = read32(patch + at), rva = read32(patch + at + 4), count = read32(patch + at + 8);
        uint64_t payload = kind == KIND_HOOK ? 2ull * count : kind == KIND_BLOCK ? count :
            kind == KIND_FUNCTIONS ? 12ull * count : kind == KIND_WRITABLE || kind == KIND_DELAY ? 0 : UINT64_MAX;
        if (payload == UINT64_MAX || payload > length - at - 12)
            return fail(message, capacity, "Invalid prebuilt patch record");
        if (kind == KIND_BLOCK) {
            if (old_base || rva < read32(patch + 12) || rva % 65536 || !count)
                return fail(message, capacity, "Invalid prebuilt code block");
            old_base = rva;
        }
        at += 12 + (size_t)payload;
    }
    if (at != length || (old_base && base % 65536))
        return fail(message, capacity, "Invalid prebuilt code address");
    int64_t delta = old_base ? (int64_t)base - old_base : 0;
    if (delta && read32(data + 24))
        return fail(message, capacity, "This mod requires its fixed code address");
    const unsigned char *directory = patch + length;
    for (unsigned i = 0; i < claims; ++i) {
        unsigned rva = read32(directory + (fixes + i) * 8), count = read32(directory + (fixes + i) * 8 + 4);
        if (!count || (uint64_t)rva + count > read32(patch + 12))
            return fail(message, capacity, "Invalid prebuilt state claim");
    }
    unsigned char *result = (unsigned char *)HeapAlloc(GetProcessHeap(), 0, length);
    unsigned char *seen = (unsigned char *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, (length + 7u) / 8u);
    int okay = result && seen;
    if (result)
        memcpy(result, patch, length);
    for (unsigned i = 0; okay && i < fixes; ++i) {
        unsigned offset = read32(directory + i * 8), kind = read32(directory + i * 8 + 4);
        if ((uint64_t)offset + 4 > length || offset < 24 || kind < 1 || kind > 3) {
            okay = 0; break;
        }
        for (unsigned j = offset; j < offset + 4; ++j) {
            unsigned char mask = (unsigned char)(1u << (j & 7));
            if (seen[j >> 3] & mask)
                okay = 0;
            seen[j >> 3] |= mask;
        }
        int64_t value = kind == 3 ? (int64_t)read32(result + offset) : (int64_t)(int32_t)read32(result + offset);
        value += kind == 2 ? -delta : delta;
        if ((kind == 3 && (value < 0 || value > UINT_MAX)) ||
            (kind != 3 && (value < INT_MIN || value > INT_MAX))) {
            okay = 0; break;
        }
        unsigned encoded = (unsigned)value;
        memcpy(result + offset, &encoded, 4);
    }
    if (seen)
        HeapFree(GetProcessHeap(), 0, seen);
    if (!okay) {
        if (result)
            HeapFree(GetProcessHeap(), 0, result);
        return fail(message, capacity, "Invalid relocation or insufficient memory");
    }
    *output = result;
    *output_size = length;
    return 1;
}

typedef struct { unsigned low, high; } lx_claim_t;
static lx_claim_t lx_claims[LX_MAX_CLAIMS];
static unsigned lx_claim_count, lx_code_cursor;

static int lx_check_claims(const unsigned char *patch, size_t size,
                          const unsigned char *module, char *message, size_t capacity, int remember)
{
    lx_claim_t pending[MAX_RECORDS * 2];
    unsigned count = 0;
    size_t at = 24;
    if (size < 24)
        return fail(message, capacity, "Truncated native patch");
    for (unsigned i = 0; i < read32(patch + 20); ++i) {
        if (at + 12 > size)
            return fail(message, capacity, "Truncated native record");
        unsigned kind = read32(patch + at), rva = read32(patch + at + 4), length = read32(patch + at + 8);
        uint64_t payload = kind == KIND_HOOK ? 2ull * length : kind == KIND_BLOCK ? length :
            kind == KIND_FUNCTIONS ? 12ull * length : kind == KIND_WRITABLE || kind == KIND_DELAY ? 0 : UINT64_MAX;
        if (payload == UINT64_MAX || payload > size - at - 12)
            return fail(message, capacity, "Invalid native record");
        if (kind == KIND_HOOK || kind == KIND_BLOCK) {
            if (!length || (uint64_t)rva + length > UINT_MAX || count == MAX_RECORDS * 2)
                return fail(message, capacity, "Invalid native claim");
            pending[count++] = (lx_claim_t){rva, rva + length};
            if (remember && kind == KIND_BLOCK && rva + length > lx_code_cursor)
                lx_code_cursor = (rva + length + 65535u) & ~65535u;
        }
        at += 12 + (size_t)payload;
    }
    if (at != size)
        return fail(message, capacity, "Invalid native directory");
    if (module) {
        unsigned fixes = read32(module + 16), claims = read32(module + 20);
        const unsigned char *items = module + LX_MOD_HEADER + read32(module + 12) + fixes * 8;
        for (unsigned i = 0; i < claims; ++i) {
            unsigned rva = read32(items + i * 8), length = read32(items + i * 8 + 4);
            if (count == MAX_RECORDS * 2)
                return fail(message, capacity, "Too many native claims");
            pending[count++] = (lx_claim_t){rva, rva + length};
        }
    }
    if (count > LX_MAX_CLAIMS - lx_claim_count)
        return fail(message, capacity, "Native mod claim limit reached");
    for (unsigned i = 0; i < count; ++i)
        for (unsigned j = 0; j < lx_claim_count; ++j)
            if (pending[i].low < lx_claims[j].high && lx_claims[j].low < pending[i].high)
                return fail(message, capacity, "Conflicts with another enabled mod's code or state");
    if (remember) {
        memcpy(lx_claims + lx_claim_count, pending, count * sizeof *pending);
        lx_claim_count += count;
    }
    return 1;
}

#if !defined(LX_NO_DLLMAIN) || defined(LX_MOD_TEST)
static void folder_file(wchar_t *path, size_t capacity, const wchar_t *name);
static void write_log(const char *text);

typedef struct { const char *at, *end; unsigned depth; } lx_json_t;
typedef struct {
    wchar_t folder[MAX_PATH * 2];
    char id[256], name[256], needs[32][256];
    int enabled, order, valid, applied;
    int needs_data;
    unsigned needed;
    unsigned char *data;
    size_t size;
} lx_mod_t;

static void lx_space(lx_json_t *json)
{
    while (json->at < json->end && (*json->at == ' ' || *json->at == '\r' || *json->at == '\n' || *json->at == '\t'))
        ++json->at;
}

static int lx_take(lx_json_t *json, char value)
{
    lx_space(json);
    if (json->at == json->end || *json->at != value)
        return 0;
    ++json->at;
    return 1;
}

static int lx_hex4(lx_json_t *json, unsigned *value)
{
    *value = 0;
    for (int i = 0; i < 4; ++i) {
        if (json->at == json->end)
            return 0;
        char c = *json->at++;
        unsigned digit = c >= '0' && c <= '9' ? c - '0' :
            c >= 'a' && c <= 'f' ? c - 'a' + 10 : c >= 'A' && c <= 'F' ? c - 'A' + 10 : 16;
        if (digit == 16)
            return 0;
        *value = *value * 16 + digit;
    }
    return 1;
}

static int lx_string(lx_json_t *json, char *out, size_t capacity)
{
    if (!lx_take(json, '"'))
        return 0;
    size_t length = 0;
    while (json->at < json->end) {
        unsigned c = (unsigned char)*json->at++;
        if (c == '"') {
            if (out) out[length] = 0;
            return 1;
        }
        if (c < 32)
            return 0;
        unsigned char bytes[4];
        unsigned count = 1;
        bytes[0] = (unsigned char)c;
        if (c == '\\') {
            if (json->at == json->end)
                return 0;
            c = (unsigned char)*json->at++;
            if (c == 'u') {
                if (!lx_hex4(json, &c)) return 0;
                if (c >= 0xd800 && c <= 0xdbff) {
                    unsigned low;
                    if (json->end - json->at < 2 || json->at[0] != '\\' || json->at[1] != 'u') return 0;
                    json->at += 2;
                    if (!lx_hex4(json, &low) || low < 0xdc00 || low > 0xdfff) return 0;
                    c = 0x10000 + ((c - 0xd800) << 10) + low - 0xdc00;
                } else if (c >= 0xdc00 && c <= 0xdfff) return 0;
                if (!c) return 0;
                if (c < 0x80) bytes[0] = (unsigned char)c;
                else if (c < 0x800) {count = 2; bytes[0] = 0xc0 | (c >> 6); bytes[1] = 0x80 | (c & 63);}
                else if (c < 0x10000) {count = 3; bytes[0] = 0xe0 | (c >> 12); bytes[1] = 0x80 | ((c >> 6) & 63); bytes[2] = 0x80 | (c & 63);}
                else {count = 4; bytes[0] = 0xf0 | (c >> 18); bytes[1] = 0x80 | ((c >> 12) & 63); bytes[2] = 0x80 | ((c >> 6) & 63); bytes[3] = 0x80 | (c & 63);}
            } else {
                const char *escaped = "\"\\/bfnrt", *values = "\"\\/\b\f\n\r\t";
                const char *match = strchr(escaped, (int)c);
                if (!match) return 0;
                bytes[0] = (unsigned char)values[match - escaped];
            }
        }
        if (out) {
            if (length + count >= capacity) return 0;
            memcpy(out + length, bytes, count);
        }
        length += count;
    }
    return 0;
}

static int lx_literal(lx_json_t *json, const char *text)
{
    size_t size = strlen(text);
    lx_space(json);
    if ((size_t)(json->end - json->at) < size || memcmp(json->at, text, size)) return 0;
    json->at += size;
    return 1;
}

static int lx_value(lx_json_t *json)
{
    lx_space(json);
    if (json->at == json->end || json->depth >= 16) return 0;
    char c = *json->at;
    if (c == '"') return lx_string(json, NULL, 0);
    if (c == '{' || c == '[') {
        ++json->at; ++json->depth;
        char end = c == '{' ? '}' : ']';
        if (lx_take(json, end)) {--json->depth; return 1;}
        do {
            if (c == '{' && (!lx_string(json, NULL, 0) || !lx_take(json, ':'))) return 0;
            if (!lx_value(json)) return 0;
            if (lx_take(json, end)) {--json->depth; return 1;}
        } while (lx_take(json, ','));
        return 0;
    }
    if (c == 't') return lx_literal(json, "true");
    if (c == 'f') return lx_literal(json, "false");
    if (c == 'n') return lx_literal(json, "null");
    if (c == '-') ++json->at;
    if (json->at == json->end || *json->at < '0' || *json->at > '9') return 0;
    if (*json->at++ != '0')
        while (json->at < json->end && *json->at >= '0' && *json->at <= '9') ++json->at;
    if (json->at < json->end && *json->at == '.') {
        ++json->at;
        const char *start = json->at;
        while (json->at < json->end && *json->at >= '0' && *json->at <= '9') ++json->at;
        if (json->at == start) return 0;
    }
    if (json->at < json->end && (*json->at == 'e' || *json->at == 'E')) {
        ++json->at;
        if (json->at < json->end && (*json->at == '+' || *json->at == '-')) ++json->at;
        const char *start = json->at;
        while (json->at < json->end && *json->at >= '0' && *json->at <= '9') ++json->at;
        if (json->at == start) return 0;
    }
    return 1;
}

static int lx_metadata(lx_mod_t *mod, const char *data, size_t size)
{
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, data, (int)size, NULL, 0)) return 0;
    lx_json_t json = {data, data + size, 0};
    if (size >= 3 && !memcmp(data, "\xef\xbb\xbf", 3)) json.at += 3;
    unsigned seen = 0;
    mod->order = 1000;
    if (!lx_take(&json, '{') || lx_take(&json, '}')) return 0;
    do {
        char key[256];
        if (!lx_string(&json, key, sizeof key) || !lx_take(&json, ':')) return 0;
        unsigned bit = !strcmp(key, "id") ? 1 : !strcmp(key, "enabled") ? 2 :
            !strcmp(key, "order") ? 4 : !strcmp(key, "requires") ? 8 : !strcmp(key, "name") ? 16 : 0;
        if (bit && (seen & bit)) return 0;
        seen |= bit;
        if (bit == 1 || bit == 16) {
            if (!lx_string(&json, bit == 1 ? mod->id : mod->name, 256)) return 0;
        } else if (bit == 2) {
            if (lx_literal(&json, "true")) mod->enabled = 1;
            else if (!lx_literal(&json, "false")) return 0;
        } else if (bit == 4) {
            lx_space(&json);
            const char *start = json.at;
            if (!lx_value(&json) || json.at - start > 11) return 0;
            for (const char *c = start; c < json.at; ++c)
                if ((*c < '0' || *c > '9') && !(c == start && *c == '-')) return 0;
            char number[12] = {0};
            memcpy(number, start, (size_t)(json.at - start));
            long long value = strtoll(number, NULL, 10);
            if (value < INT_MIN || value > INT_MAX) return 0;
            mod->order = (int)value;
        } else if (bit == 8) {
            if (!lx_take(&json, '[')) return 0;
            if (!lx_take(&json, ']')) {
                do {
                    if (mod->needed == 32 || !lx_string(&json, mod->needs[mod->needed], 256) ||
                        !mod->needs[mod->needed][0]) return 0;
                    ++mod->needed;
                    if (lx_take(&json, ']')) goto needs_done;
                } while (lx_take(&json, ','));
                return 0;
            }
needs_done: ;
        } else if (!lx_value(&json)) return 0;
        if (lx_take(&json, '}')) {
            lx_space(&json);
            return json.at == json.end && mod->id[0] && mod->name[0];
        }
    } while (lx_take(&json, ','));
    return 0;
}

static unsigned char *lx_read_file(const wchar_t *path, size_t limit, size_t *size)
{
    *size = 0;
    DWORD attributes = GetFileAttributesW(path);
    if (attributes == INVALID_FILE_ATTRIBUTES || (attributes & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DIRECTORY))) return NULL;
    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return NULL;
    LARGE_INTEGER length;
    unsigned char *data = NULL;
    if (GetFileSizeEx(file, &length) && length.QuadPart > 0 && length.QuadPart <= (LONGLONG)limit) {
        data = (unsigned char *)HeapAlloc(GetProcessHeap(), 0, (size_t)length.QuadPart);
        DWORD read = 0;
        if (data && ReadFile(file, data, (DWORD)length.QuadPart, &read, NULL) && read == length.QuadPart)
            *size = read;
        else if (data) {HeapFree(GetProcessHeap(), 0, data); data = NULL;}
    }
    CloseHandle(file);
    return data;
}

static void lx_mod_log(const lx_mod_t *mod, const char *message)
{
    char text[768];
    snprintf(text, sizeof text, "%s: %s", mod->name[0] ? mod->name : mod->id, message);
    write_log(text);
}

static int lx_mod_order(const void *a, const void *b)
{
    const lx_mod_t *first = (const lx_mod_t *)a, *second = (const lx_mod_t *)b;
    unsigned fixed_a = first->data && first->size >= 32 ? read32(first->data + 24) : 0;
    unsigned fixed_b = second->data && second->size >= 32 ? read32(second->data + 24) : 0;
    if (!!fixed_a != !!fixed_b) return fixed_a ? -1 : 1;
    if (first->order != second->order) return first->order < second->order ? -1 : 1;
    return _stricmp(first->name, second->name);
}

static unsigned lx_module_base(unsigned char *image, const lx_mod_t *mod)
{
    const unsigned char *patch = mod->data + LX_MOD_HEADER;
    size_t at = 24, size = read32(mod->data + 12);
    for (unsigned i = 0; i < read32(patch + 20) && at + 12 <= size; ++i) {
        unsigned kind = read32(patch + at), rva = read32(patch + at + 4), length = read32(patch + at + 8);
        if (kind == KIND_BLOCK) {
            if (read32(mod->data + 24)) return rva;
            unsigned cursor = lx_code_cursor;
            for (unsigned attempt = 0; attempt < 256 && cursor < 0x70000000u; ++attempt) {
                MEMORY_BASIC_INFORMATION info;
                if (!VirtualQuery(image + cursor, &info, sizeof info)) return 0;
                if (info.State == MEM_FREE && info.RegionSize >= length) return cursor;
                uintptr_t next = (uintptr_t)info.BaseAddress + info.RegionSize - (uintptr_t)image;
                if (next > 0x70000000u) return 0;
                cursor = ((unsigned)next + 65535u) & ~65535u;
            }
            return 0;
        }
        at += 12 + (kind == KIND_HOOK ? 2ull * length : kind == KIND_FUNCTIONS ? 12ull * length : 0);
    }
    return 0;
}

static void lx_library_roots(wchar_t roots[3][MAX_PATH * 2])
{
    wchar_t ini[MAX_PATH * 2], defaults[MAX_PATH * 2];
    folder_file(ini, MAX_PATH * 2, L"lexeditor-ds1.ini");
    defaults[0] = 0;
    if (SUCCEEDED(SHGetFolderPathW(NULL, CSIDL_PERSONAL, NULL, SHGFP_TYPE_CURRENT, defaults)) && wcslen(defaults)+10 < MAX_PATH*2)
        wcscat(defaults, L"\\Mods\\ds1");
    GetPrivateProfileStringW(L"Mods", L"Library", defaults, roots[0], MAX_PATH * 2, ini);
    folder_file(roots[1], MAX_PATH * 2, L"");
    size_t game_length = wcslen(roots[1]);
    if (game_length && roots[1][game_length-1] == L'\\') roots[1][game_length-1] = 0;
    swprintf(roots[2], MAX_PATH * 2, L"%ls\\mods", roots[1]);
}

static char lx_data_ids[LX_MAX_MODS][256];
static unsigned lx_data_count;

static int lx_read_data_report(void)
{
    wchar_t path[MAX_PATH*2];
    folder_file(path,MAX_PATH*2,L"lexeditor-ds1-load.json");
    size_t size=0;
    unsigned char *data=lx_read_file(path,1024*1024,&size);
    lx_data_count=0;
    if(!data)return 0;
    lx_json_t json={(char *)data,(char *)data+size,0};
    unsigned seen=0;
    int valid=0;
    if(!lx_take(&json,'{'))goto done;
    do {
        char key[256];
        if(!lx_string(&json,key,sizeof key)||!lx_take(&json,':'))goto done;
        if(!strcmp(key,"loaded")){
            if((seen&1)||!lx_take(&json,'['))goto done;
            seen|=1;
            if(!lx_take(&json,']')){
                for(;;){
                    if(lx_data_count==LX_MAX_MODS||!lx_string(&json,lx_data_ids[lx_data_count],256)||
                       !lx_data_ids[lx_data_count][0])goto done;
                    ++lx_data_count;
                    if(lx_take(&json,']'))break;
                    if(!lx_take(&json,','))goto done;
                }
            }
        }else if(!strcmp(key,"version")){
            if((seen&2)||!lx_literal(&json,"1"))goto done;
            seen|=2;
        }else if(!strcmp(key,"error")||!lx_value(&json))goto done;
        if(lx_take(&json,'}')){
            lx_space(&json);valid=seen==3&&json.at==json.end;break;
        }
    }while(lx_take(&json,','));
done:
    HeapFree(GetProcessHeap(),0,data);
    if(!valid)lx_data_count=0;
    return valid;
}

static int lx_data_loaded(const char *id)
{
    for(unsigned i=0;i<lx_data_count;++i){
        if(!strcmp(id,lx_data_ids[i]))return 1;
    }
    return 0;
}

static int lx_data_ready;

static int lx_prepare_data(void)
{
    wchar_t roots[3][MAX_PATH*2], ini[MAX_PATH*2], python[MAX_PATH*2], engine[MAX_PATH*2];
    wchar_t fallback_python[MAX_PATH*2], fallback_engine[MAX_PATH*2], entry[MAX_PATH*2];
    lx_library_roots(roots);
    folder_file(ini,MAX_PATH*2,L"lexeditor-ds1.ini");
    folder_file(fallback_python,MAX_PATH*2,L"lexeditor-runtime\\pythonw.exe");
    folder_file(fallback_engine,MAX_PATH*2,L"lexeditor-runtime\\engine");
    GetPrivateProfileStringW(L"Runtime",L"Python",fallback_python,python,MAX_PATH*2,ini);
    GetPrivateProfileStringW(L"Runtime",L"Engine",fallback_engine,engine,MAX_PATH*2,ini);
    if(GetFileAttributesW(python)==INVALID_FILE_ATTRIBUTES) wcscpy(python,fallback_python);
    swprintf(entry,MAX_PATH*2,L"%ls\\plugins\\ds1\\standalone_entry.py",engine);
    if(GetFileAttributesW(entry)==INVALID_FILE_ATTRIBUTES){
        wcscpy(engine,fallback_engine);
        swprintf(entry,MAX_PATH*2,L"%ls\\plugins\\ds1\\standalone_entry.py",engine);
    }
    if(GetFileAttributesW(python)==INVALID_FILE_ATTRIBUTES || GetFileAttributesW(entry)==INVALID_FILE_ATTRIBUTES){
        write_log("Data merger is unavailable; native-only mods still load. Install the complete loader package for data mods.");return 0;
    }
    wchar_t command[8192];
    for(unsigned i=0;i<3;++i)
        if(wcschr(roots[i],L'"')){write_log("Invalid mod-library path");return 0;}
    if(swprintf(command,8192,L"\"%ls\" -I \"%ls\" --game \"%ls\" --root \"%ls\" --root \"%ls\" --root \"%ls\" --startup-pid %lu",
                python,entry,roots[1],roots[0],roots[1],roots[2],GetCurrentProcessId())<0){write_log("Loader paths exceed the command limit");return 0;}
    wchar_t event_name[96];
    swprintf(event_name,96,L"Local\\Lexeditor.DS1.Startup.%lu",GetCurrentProcessId());
    HANDLE window=CreateEventW(NULL,TRUE,TRUE,event_name);
    if(!window){write_log("The loader startup window could not be created");return 0;}
    STARTUPINFOW startup;
    PROCESS_INFORMATION process;
    memset(&startup,0,sizeof startup);startup.cb=sizeof startup;
    memset(&process,0,sizeof process);
    if(!CreateProcessW(python,command,NULL,NULL,FALSE,CREATE_NO_WINDOW,NULL,roots[1],&startup,&process)){
        CloseHandle(window);write_log("The prebuilt data merger could not start");return 0;
    }
    DWORD wait=WaitForSingleObject(process.hProcess,60000), code=1;
    if(wait==WAIT_OBJECT_0)GetExitCodeProcess(process.hProcess,&code);
    else {TerminateProcess(process.hProcess,0x4c58);WaitForSingleObject(process.hProcess,5000);}
    CloseHandle(process.hThread);CloseHandle(process.hProcess);
    ResetEvent(window);CloseHandle(window);
    int ready=code==0&&lx_read_data_report();
    write_log(ready?"Prebuilt data mods are ready":"Data preparation failed; dependent native mods were skipped. See lexeditor-ds1-load.json.");
    return ready;
}

static void lx_load_mod_folders(void)
{
    wchar_t roots[3][MAX_PATH * 2];
    lx_library_roots(roots);
    lx_mod_t *mods = (lx_mod_t *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, LX_MAX_MODS * sizeof *mods);
    if (!mods) return;
    unsigned count = 0;
    size_t total = 0;
    for (unsigned root_index = 0; root_index < 3; ++root_index) {
    const wchar_t *root = roots[root_index];
    if (!root[0]) continue;
    if (root_index && !_wcsicmp(root, roots[0])) continue;
    wchar_t search[MAX_PATH * 2];
    if (swprintf(search, MAX_PATH * 2, L"%ls\\*", root) < 0) continue;
    WIN32_FIND_DATAW found;
    HANDLE find = FindFirstFileW(search, &found);
    if (find == INVALID_HANDLE_VALUE) continue;
    do {
        if (!(found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) || (found.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) ||
            found.cFileName[0] == '.') continue;
        if (count == LX_MAX_MODS) {write_log("Folder-mod limit reached (128); remaining folders were skipped"); break;}
        lx_mod_t *mod = mods + count;
        if (swprintf(mod->folder, MAX_PATH * 2, L"%ls\\%ls", root, found.cFileName) < 0) continue;
        WideCharToMultiByte(CP_UTF8, 0, found.cFileName, -1, mod->id, sizeof mod->id, NULL, NULL);
        wchar_t path[MAX_PATH * 2];
        if (swprintf(path, MAX_PATH * 2, L"%ls\\mod.json", mod->folder) < 0) continue;
        size_t size = 0;
        unsigned char *metadata = lx_read_file(path, 65536, &size);
        if (!metadata) continue;
        int valid = lx_metadata(mod, (char *)metadata, size);
        HeapFree(GetProcessHeap(), 0, metadata);
        if (!valid) {lx_mod_log(mod, "Invalid mod.json; skipped"); memset(mod, 0, sizeof *mod); continue;}
        if (!mod->enabled) {memset(mod, 0, sizeof *mod); continue;}
        if (swprintf(path, MAX_PATH * 2, L"%ls\\runtime.lxd", mod->folder) < 0) continue;
        mod->data = lx_read_file(path, MAX_PATCH, &mod->size);
        if (!mod->data) {
            DWORD attributes=GetFileAttributesW(path), error=GetLastError();
            if(attributes==INVALID_FILE_ATTRIBUTES && error==ERROR_FILE_NOT_FOUND && lx_data_ready && lx_data_loaded(mod->id)){
                mod->valid=1;mod->applied=1;++count;
            }
            else memset(mod,0,sizeof *mod);
            continue;
        }
        if (mod->size > LX_MAX_TOTAL - total) {
            lx_mod_log(mod, "Combined prebuilt-mod size limit reached (64 MiB); skipped");
            HeapFree(GetProcessHeap(), 0, mod->data); memset(mod, 0, sizeof *mod); continue;
        }
        total += mod->size;
        unsigned char *checked = NULL;
        size_t checked_size = 0;
        char message[256];
        /* Base zero only validates movable modules; fixed code retains its address. */
        unsigned original_base = 0;
        if (mod->size >= LX_MOD_HEADER + 24 && read32(mod->data + 12) <= mod->size - LX_MOD_HEADER) {
            const unsigned char *patch = mod->data + LX_MOD_HEADER;
            size_t at = 24;
            for (unsigned i = 0; i < read32(patch + 20) && at + 12 <= read32(mod->data + 12); ++i) {
                unsigned kind = read32(patch + at), n = read32(patch + at + 8);
                if (kind == KIND_BLOCK) {original_base = read32(patch + at + 4); break;}
                uint64_t bytes = kind == KIND_HOOK ? 2ull*n : kind == KIND_FUNCTIONS ? 12ull*n : 0;
                if (bytes > mod->size) break;
                at += 12 + (size_t)bytes;
            }
        }
        mod->valid = lx_link_module(mod->data, mod->size, original_base, &checked, &checked_size, message, sizeof message);
        if (mod->valid) mod->needs_data=read32(mod->data+28)!=0;
        if (checked) HeapFree(GetProcessHeap(), 0, checked);
        if (!mod->valid) lx_mod_log(mod, message);
        ++count;
    } while (FindNextFileW(find, &found));
    FindClose(find);
    }
    for (unsigned i = 0; i < count; ++i)
        for (unsigned j = i + 1; j < count; ++j)
            if (!_stricmp(mods[i].id, mods[j].id)) {
                mods[i].valid = mods[j].valid = 0;
                lx_mod_log(mods + i, "Duplicate enabled mod ID; both copies skipped");
            }
    qsort(mods, count, sizeof *mods, lx_mod_order);
    unsigned char *image = (unsigned char *)GetModuleHandleW(NULL);
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)image;
    IMAGE_NT_HEADERS64 *nt = (IMAGE_NT_HEADERS64 *)(image + dos->e_lfanew);
    if (lx_code_cursor < nt->OptionalHeader.SizeOfImage)
        lx_code_cursor = (nt->OptionalHeader.SizeOfImage + 65535u) & ~65535u;
    /* Reserve the address range of every fixed module in the layout before
     * placing movable code, even when a fixed module has dependencies. */
    for (unsigned i = 0; i < count; ++i) {
        if (!mods[i].valid || !mods[i].data || !read32(mods[i].data + 24)) continue;
        const unsigned char *patch = mods[i].data + LX_MOD_HEADER;
        size_t at = 24;
        for (unsigned j = 0; j < read32(patch + 20); ++j) {
            unsigned kind = read32(patch + at), rva = read32(patch + at + 4), n = read32(patch + at + 8);
            if (kind == KIND_BLOCK) {
                uint64_t end = (uint64_t)rva + n + 65535;
                if (end >= 0x70000000u) {mods[i].valid = 0; lx_mod_log(mods+i, "Fixed code address is outside the linking range");}
                else if (end > lx_code_cursor) lx_code_cursor = (unsigned)end & ~65535u;
                break;
            }
            at += 12 + (kind == KIND_HOOK ? 2ull*n : kind == KIND_FUNCTIONS ? 12ull*n : 0);
        }
    }
    for (unsigned pass = 0; pass < count; ++pass) {
        int progress = 0;
        for (unsigned i = 0; i < count; ++i) {
            lx_mod_t *mod = mods + i;
            if (!mod->valid || mod->applied) continue;
            if(mod->needs_data && !lx_data_ready){mod->valid=0;lx_mod_log(mod,"Required data could not be prepared; skipped");continue;}
            int ready = 1;
            for (unsigned n = 0; n < mod->needed; ++n) {
                if (!strcmp(mod->needs[n], mod->id) || !strcmp(mod->needs[n], "lexeditor-loader")) continue;
                int present = 0;
                for (unsigned j = 0; j < count; ++j)
                    if (!strcmp(mod->needs[n], mods[j].id) && mods[j].applied) present = 1;
                if (!present) ready = 0;
            }
            if (!ready) continue;
            char message[256];
            unsigned char *patch = NULL;
            size_t size = 0;
            unsigned base = lx_module_base(image, mod);
            int okay = lx_link_module(mod->data, mod->size, base, &patch, &size, message, sizeof message);
#ifndef LX_ONLINE_BUILD
            if (okay && !lx_block_network()) {okay = 0; snprintf(message, sizeof message, "Network isolation failed; skipped");}
#endif
            if (okay) okay = lx_check_claims(patch, size, mod->data, message, sizeof message, 0);
            if (okay) okay = lx_apply(image, patch, size, message, sizeof message);
            if (okay) lx_check_claims(patch, size, mod->data, message, sizeof message, 1);
            if (patch) HeapFree(GetProcessHeap(), 0, patch);
            mod->applied = okay;
            mod->valid = okay;
            progress = 1;
            lx_mod_log(mod, message);
        }
        if (!progress) break;
    }
    for (unsigned i = 0; i < count; ++i) {
        if (mods[i].valid && !mods[i].applied) lx_mod_log(mods + i, "Missing, failed or cyclic dependency; skipped");
        if (mods[i].data) HeapFree(GetProcessHeap(), 0, mods[i].data);
    }
    HeapFree(GetProcessHeap(), 0, mods);
}
#endif
