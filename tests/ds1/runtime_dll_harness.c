/*
 * Loads the shipped dinput8.dll the way the game does, from this program's
 * own folder, and calls DirectInput8Create through it, as the game does.
 * With no patch file beside it, the DLL changes nothing and says so in
 * lexeditor-ds1-patch.log. Prints: loaded=<0|1> created=<hresult>
 */
#include <windows.h>
#include <stdio.h>

static const GUID IID_IDirectInput8W_ = {0xBF798031, 0x483A, 0x4DA2, {0xAA, 0x99, 0x5D, 0x64, 0xED, 0x36, 0x97, 0x00}};
typedef HRESULT(WINAPI *create_t)(HINSTANCE, DWORD, REFIID, LPVOID *, LPUNKNOWN);

int main(void)
{
    wchar_t path[MAX_PATH];
    DWORD length = GetModuleFileNameW(NULL, path, MAX_PATH);
    while (length && path[length - 1] != L'\\')
        --length;
    path[length] = 0;
    wcscat(path, L"dinput8.dll");
    HMODULE dll = LoadLibraryW(path);
    if (!dll) {
        printf("loaded=0 created=0\n");
        return 0;
    }
    create_t create = (create_t)GetProcAddress(dll, "DirectInput8Create");
    IUnknown *input = NULL;
    HRESULT hr = create ? create(GetModuleHandleW(NULL), 0x0800, &IID_IDirectInput8W_, (void **)&input, NULL) : E_FAIL;
    if (input)
        input->lpVtbl->Release(input);
    printf("loaded=1 created=%ld\n", (long)hr);
    return 0;
}
