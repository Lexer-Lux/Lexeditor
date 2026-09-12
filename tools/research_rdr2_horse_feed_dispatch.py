"""Resolve the item-aware feed award chain in the retained 1491.50 script source."""
import argparse,hashlib,json,re
from pathlib import Path

def functions(text):
    pattern=r'^([^\n]+?\b(func_\d+)\([^\n]*\)) // Position - (0x[0-9A-F]+)[^\n]*\n\{'
    starts=list(re.finditer(pattern,text,re.M));result={}
    for i,m in enumerate(starts):
        body=text[m.end():starts[i+1].start() if i+1<len(starts) else len(text)]
        result[m[2]]={'position':m[3],'body':body,'line':text.count('\n',0,m.start())+1}
    return result

def resolve(text):
    f=functions(text)
    required={
      'func_739':['func_724(hParam1)','func_790(pedParam0, hParam1)','func_959(hParam1)','func_960(hParam1)','func_454(num, 16)','num6 >= 50 || flag2','num7 < 30','num6 >= 25','num6 >= 0','func_454(num, num8)'],
      'func_357':['func_652(iParam1, &attributeIndex)','ATTRIBUTE::GET_ATTRIBUTE_BASE_RANK(pedParam0, attributeIndex)'],
      'func_652':['case 2:','*uParam1 = 13;'],
      'func_454':['func_470(iParam0, iParam1)','func_756(iParam0, iParam1)','num2 = func_758(iParam1)','num2 * (1f + Global_40.f_11095.f_68)','func_760(iParam0, num2)','func_472(iParam0, iParam1, num + num2)'],
      'func_760':['.f_372.f_1 + fParam1','func_677(ped2, BUILTIN::FLOOR'],
      'func_677':['ATTRIBUTE::SET_ATTRIBUTE_POINTS(pedParam0, 7, iParam1)'],
      'func_962':['return 20;'],
      'func_895':['.f_407[iParam1 /*4*/].f_2 = fParam2'],
    }
    for name,needles in required.items():
        for needle in needles:
            if needle not in f.get(name,{}).get('body',''):raise ValueError(name+' missing '+needle)
    tiers={int(k):float(v) for k,v in re.findall(r'case (\d+):\s*return ([\d.]+)f;',f['func_758']['body'])}
    if {n:tiers.get(n) for n in (13,14,15,16)}!={13:15.,14:5.,15:1.,16:5.}:raise ValueError('Feed tier values changed')
    if 'func_962(' in f['func_739']['body']:raise ValueError('Fixed20 unexpectedly enters feed award')
    names=lambda name:re.findall(r'joaat\("([^"]+)"\)',f[name]['body'])
    referenced=set(required)|{'func_724','func_758','func_789','func_959','func_960'}
    return {'source_sha256':hashlib.sha256(text.encode()).hexdigest(),'functions':{name:{k:f[name][k] for k in ('position','line')} for name in sorted(referenced)},'eligible_items':names('func_724'),'preferred_order':names('func_789'),'no_bond_items':names('func_959'),'special_5_base_points':names('func_960'),'feeding_events':{n:tiers[n] for n in (13,14,15,16)},'item_aware_hook':'func_739 before its two func_454 calls; preserve native rank/event-cap/motivation/accounting and replace the one selected magnitude, never add a second award','fixed20_is_not_feed_bond':True}

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=Path('C:/RDR2Mod/_downloads/RDR2-Decompiled-Scripts-1491.50/1491.50/script_rel/player_horse.ysc.c'));p.add_argument('--output',type=Path);a=p.parse_args()
    text=a.source.read_text(encoding='utf-8-sig');result=resolve(text)
    for before,after in [('num2 = func_758(iParam1)','num2 = 20'),('func_454(num, 16)','func_454(num, 15)'),('ATTRIBUTE::SET_ATTRIBUTE_POINTS(pedParam0, 7, iParam1)','ATTRIBUTE::SET_ATTRIBUTE_POINTS(pedParam0, 0, iParam1)')]:
        candidate=text.replace(before,after);assert candidate!=text
        try:resolve(candidate)
        except ValueError:pass
        else:raise AssertionError('Mutation escaped: '+before)
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2))
    print('PASS: feed award chain;'+str(len(result['eligible_items']))+' eligible items; events13/14/15/16 =15/5/1/5;3 mutations rejected')
if __name__=='__main__':main()
