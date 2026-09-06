"""Synthetic stock-style Win32 launcher for tests; never loads game assets."""
import ctypes
from ctypes import wintypes as w
import json
from pathlib import Path
import sys

u = ctypes.WinDLL('user32', use_last_error=True)
k = ctypes.WinDLL('kernel32', use_last_error=True)
RESULT = ctypes.c_ssize_t
PROC = ctypes.WINFUNCTYPE(RESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
class WNDCLASS(ctypes.Structure):
    _fields_ = [('style', w.UINT), ('lpfnWndProc', PROC), ('cbClsExtra', ctypes.c_int),
                ('cbWndExtra', ctypes.c_int), ('hInstance', w.HINSTANCE), ('hIcon', w.HICON),
                ('hCursor', w.HANDLE), ('hbrBackground', w.HBRUSH),
                ('lpszMenuName', w.LPCWSTR), ('lpszClassName', w.LPCWSTR)]
for name, args, result in [
    ('CreateWindowExW', [w.DWORD,w.LPCWSTR,w.LPCWSTR,w.DWORD,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.HWND,w.HMENU,w.HINSTANCE,ctypes.c_void_p],w.HWND),
    ('DefWindowProcW',[w.HWND,w.UINT,w.WPARAM,w.LPARAM],RESULT),
    ('RegisterClassW',[ctypes.POINTER(WNDCLASS)],w.ATOM),
    ('SendMessageW',[w.HWND,w.UINT,w.WPARAM,w.LPARAM],RESULT),
    ('DestroyWindow',[w.HWND],w.BOOL), ('GetMessageW',[ctypes.POINTER(w.MSG),w.HWND,w.UINT,w.UINT],w.BOOL),
    ('DispatchMessageW',[ctypes.POINTER(w.MSG)],RESULT),
]:
    f=getattr(u,name); f.argtypes=args; f.restype=result
k.GetModuleHandleW.argtypes=[w.LPCWSTR];k.GetModuleHandleW.restype=w.HMODULE
instance=k.GetModuleHandleW(None)
output=Path(sys.argv[1]); wanted=sys.argv[2]; mode=sys.argv[3] if len(sys.argv)>3 else 'normal'
module_names=['Native', wanted, 'Another mod'] if mode != 'missing' else ['Native', 'Another mod']
if mode == 'duplicate': module_names.append(wanted)
combo=None; selected=''; game=None
@PROC
def handler(hwnd,msg,wp,lp):
    global selected,game
    if msg==0x111:  # WM_COMMAND
        control,notification=wp & 0xFFFF, (wp >> 16) & 0xFFFF
        if control==1030 and notification==1:
            index=u.SendMessageW(combo,0x147,0,0)
            selected=module_names[index] if 0<=index<len(module_names) else ''
        elif control==1029 and notification==0:
            output.write_text(json.dumps({'selected':selected, 'realPlay':True}),encoding='utf-8')
            game=u.CreateWindowExW(0,'WarbandFixture','Game',0x10CF0000,80,80,800,600,None,None,instance,None)
            u.DestroyWindow(hwnd)
        elif control==1040:
            output.write_text(json.dumps({'decoy':True}),encoding='utf-8')
    if msg==0x10:  # WM_CLOSE
        u.DestroyWindow(hwnd)
        return 0
    return u.DefWindowProcW(hwnd,msg,wp,lp)
wc=WNDCLASS(0,handler,0,0,instance,None,None,w.HBRUSH(6),None,'WarbandFixture')
assert u.RegisterClassW(ctypes.byref(wc)),ctypes.get_last_error()
launcher=u.CreateWindowExW(0,'WarbandFixture','Stock launcher fixture',0x10CF0000,40,40,600,450,None,None,instance,None)
assert launcher,ctypes.get_last_error()
combo=u.CreateWindowExW(0,'COMBOBOX','',0x50010003,30,30,320,220,launcher,w.HMENU(1030),instance,None)
for name in module_names:
    text=ctypes.create_unicode_buffer(name)
    u.SendMessageW(combo,0x143,0,ctypes.addressof(text))  # CB_ADDSTRING
u.SendMessageW(combo,0x14E,0,0)
u.CreateWindowExW(0,'BUTTON','Play',0x50010000,30,90,100,40,launcher,w.HMENU(1029),instance,None)
u.CreateWindowExW(0,'BUTTON','Decoy',0x50010000,180,90,100,40,launcher,w.HMENU(1040),instance,None)
msg=w.MSG()
while u.GetMessageW(ctypes.byref(msg),None,0,0)>0:
    u.TranslateMessage(ctypes.byref(msg));u.DispatchMessageW(ctypes.byref(msg))
