"""Execute fixed Shoot queue, native timer setup and ATB debit without launching FF8."""
from verify_ff8_scan_draw_execution import machine, run, put32, read32, pe, STACK, STOP
from unicorn.x86_const import *
from games.ff8 import shoot_issue_54 as s

for site in s.QUEUE_CALLS:
    assert pe.get_data(site-0x400000,5)==s._near(site,s.QUEUE_FUNCTION,b'\xe8')
    for command in (s.SHOT,1):
        u=machine()
        u.mem_write(site,s._near(site,s.QUEUE_CAVE,b'\xe8'))
        u.mem_write(s.QUEUE_CAVE,s._queue_payload())
        u.mem_write(s.ACTIVE_STATE,b'\x00')
        u.mem_write(s.QUEUE_FUNCTION,b'\xc3')
        args=(0,1,command,5,8)
        for i,v in enumerate(args): put32(u,STACK+i*4,v)
        u.mem_write(s.ACTIVE_SLOT,b'\x02')
        u.mem_write(s.BATTLE_ACTOR_BASE+s.BATTLE_ACTOR_STRIDE+s.CHARACTER_ID_OFFSET,b'\x02')
        run(u,site,site+5)
        assert u.reg_read(UC_X86_REG_ESP)==STACK
        assert tuple(read32(u,STACK+i*4) for i in range(5))==args
        assert u.mem_read(s.ACTIVE_STATE,1)[0]==int(command==s.SHOT)

assert pe.get_data(s.UI_OPEN_CALL-0x400000,5)==s._near(s.UI_OPEN_CALL,s.UI_OPEN_FUNCTION,b'\xe8')
for active in (0,1,2):
    u=machine()
    u.mem_write(s.UI_OPEN_CAVE,s._ui_open_payload())
    u.mem_write(0x1CF8B4C,b'\x3c') # native crisis-1 duration loaded at runtime
    u.mem_write(s.ACTIVE_STATE,bytes((active,)))
    put32(u,STACK+4,0)
    put32(u,STACK+8,1)
    run(u,s.UI_OPEN_CAVE,0x4AD7E9)
    assert read32(u,STACK+8)==(60 if active else 1)
    assert int.from_bytes(u.mem_read(0x1D76750,2),'little')==(240 if active else 4)

for actor in range(3):
    for shots in range(1,11):
        u=machine()
        u.mem_write(s.POST_FIRE_CAVE,s._post_fire_payload())
        u.mem_write(s.ACTIVE_STATE,b'\x01')
        u.mem_write(0x1D7675B,b'\x00')
        u.mem_write(s.SHOT_ACTOR,bytes((actor,)))
        u.mem_write(s.BATTLE_ACTOR_BASE+actor*s.BATTLE_ACTOR_STRIDE+s.CHARACTER_ID_OFFSET,b'\x02')
        u.mem_write(s.IRVINE_WEAPON_ID,b'\x00')
        u.mem_write(s.WEAPON_BASE+s.SHOTS_OFFSET,bytes((shots,)))
        for slot in range(3):
            put32(u,s.PARTICIPANT_BASE+slot*s.PARTICIPANT_STRIDE+0x10,1000)
            put32(u,s.PARTICIPANT_BASE+slot*s.PARTICIPANT_STRIDE+0x14,900+slot)
        run(u,s.POST_FIRE_CAVE,s.POST_FIRE_HOOK+5)
        for slot in range(3):
            expect=max(0,900+slot-(1000+shots-1)//shots) if slot==actor else 900+slot
            assert read32(u,s.PARTICIPANT_BASE+slot*s.PARTICIPANT_STRIDE+0x14)==expect
        assert u.reg_read(UC_X86_REG_ESP)==STACK
        assert u.mem_read(s.ACTIVE_STATE,1)==b'\x02'
        assert u.mem_read(0x1D7675B,1)[0]==int(max(0,900+actor-(1000+shots-1)//shots)==0)
print('PASS: five native queue callers, custom/vanilla timer setup, all three actors and 1-10 shots ATB debit')



# Native unregister arguments and custom cancel/fire return lifecycle.
from unicorn import UC_HOOK_CODE
for state in (0,1,2):
    u=machine()
    u.mem_write(s.FINISH_CAVE,s._finish_payload())
    u.mem_write(s.ACTIVE_STATE,bytes((state,)))
    u.mem_write(s.SHOOT_LOCK,b'\x00')
    u.mem_write(s.SHOT_ACTOR,b'\x01')
    for i,v in enumerate((6,0,0,0,0,0)): put32(u,STACK+i*4,v)
    calls=[]
    def stub(uc,address,size,_):
        if address in (s.UNREGISTER_UI,s.RETURN_TO_COMMANDS):
            sp=uc.reg_read(UC_X86_REG_ESP)
            calls.append((address,read32(uc,sp+4)))
            uc.reg_write(UC_X86_REG_EIP,read32(uc,sp))
            uc.reg_write(UC_X86_REG_ESP,sp+4)
    u.hook_add(UC_HOOK_CODE,stub)
    run(u,s.FINISH_CAVE,s.SHOT_UI_UNREGISTER_CALL+5)
    assert calls==[(s.UNREGISTER_UI,6)]+([(s.RETURN_TO_COMMANDS,1)] if state else [])
    assert u.reg_read(UC_X86_REG_ESP)==STACK
    assert u.mem_read(s.SHOOT_LOCK,1)[0]==int(state==2)
    assert u.mem_read(s.ACTIVE_STATE,1)==b'\x00'
print('PASS: Shot UI unregister stack, cancel without lock, fired return with lock')
