#include <windows.h>

#ifndef LX_WITHOUT_INPUT_EXPORT
__declspec(dllexport) HRESULT WINAPI DirectInput8Create(HINSTANCE instance, DWORD version, REFIID iid, LPVOID *out, LPUNKNOWN outer)
{
    (void)instance; (void)version; (void)iid; (void)out; (void)outer;
    return 42;
}
#else
__declspec(dllexport) int fixture_no_input(void) {return 42;}
#endif

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved)
{
    (void)instance; (void)reason; (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        typedef HRESULT(WINAPI *input_t)(HINSTANCE,DWORD,REFIID,LPVOID *,LPUNKNOWN);
        input_t input = (input_t)GetProcAddress(GetModuleHandleW(NULL),"DirectInput8Create");
        if (input) {
            /* A valid but unsupported IID lets system input reject the call
             * safely, while exercising re-entry during the proxy's attach. */
            const GUID unsupported = {0};
            void *out = NULL;
            input(GetModuleHandleW(NULL),0x0800,&unsupported,&out,NULL);
        }
    }
    return TRUE;
}
