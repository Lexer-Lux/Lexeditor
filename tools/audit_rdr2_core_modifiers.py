"""Check known #226 script evidence; this does not verify a runtime repair."""
import argparse
from pathlib import Path
import re

def function(source, number):
    match=re.search(r"^\w+ func_"+str(number)+r"\([^\n]*\n\{",source,re.M)
    assert match,number
    end=source.index("\n}",match.end())+2
    return source[match.start():end]

def audit(source):
    weight=function(source,2976);mounted=function(source,3740)
    assert "num = func_2978(13);" in weight
    assert "num2 == 0" in weight and "return 0.15f;" in weight
    assert "num2 == 10 || num2 == -10" in weight and "return -0.25f;" in weight
    assert "PED::IS_PED_ON_MOUNT(Global_35)" in mounted and "return 0.25f;" in mounted
    caller=function(source,1632)
    for fn,field in ((2880,50),(2881,51),(2882,49)):
        body=function(source,fn)
        assert f"\n\tfunc_{fn}();" in caller
        assert "num2 = func_2976();" in body and "num3 = func_3740();" in body
        assert f"num2 + num3 + num4 + num5 + Global_40.f_11095.f_{field}" in body
        assert "func_2876(" in body and "func_2877(" in body
        assert "_SET_ATTRIBUTE_CORE_VALUE" not in body
    for fn in (2876,2877):
        body=function(source,fn)
        assert "DATABINDING::_DATABINDING_WRITE_DATA" in body
        assert "_SET_ATTRIBUTE_CORE_VALUE" not in body
    print("Confirmed UI forecast: perfect weight +0.15, extreme weight -0.25, mounted +0.25.")
    print("The three forecast returns are discarded; side effects update DataBinding.")
    print("These routines are not a proved core writer. Runtime removal remains unimplemented.")

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--runtime-root",type=Path,default=Path("C:/RDR2Mod"))
    args=parser.parse_args()
    path=args.runtime_root / "_downloads/RDR2-Decompiled-Scripts-1491.50/1491.50/script_rel/short_update.ysc.c"
    audit(path.read_text("utf-8"))
if __name__=="__main__":main()
