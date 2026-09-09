"""Check separate Recon radius loading, mode selection and settings round trips."""
import argparse
import ast
import json
import os
from pathlib import Path
import shutil
import tempfile
from verify_rdr2_camera_switch import run_variants

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtime-root',type=Path,default=Path('C:/RDR2Mod'))
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    source=(args.runtime_root/'GameplayTweaks/modules/recon.cpp').read_text('utf-8')
    start=source.index('\tconst float requestedAimTolerancePercent =')
    end=source.index('\tg_reconCachedSettings.tagFadeStartMeters =',start)
    load=source[start:end]
    start=source.index('    g_reconAimRadius = g_binocularsActive ?')
    end=source.index('\tconst Entity reticleEntity',start)
    select=source[start:end]
    code='void load(){'+load+'}\nfloat select(bool g_binocularsActive){'+select+'return g_reconAimRadius;}\n'
    prelude=r'''
#include <algorithm>
#include <cmath>
#include <cstring>
struct Settings {float binocularAimRadius=.05f,weaponAimRadius=.05f;}g_reconCachedSettings;
float g_reconAimRadius=.05f,bino=12,gun=3;bool gunPresent=false;
float readF(const char*,const char*key,float fallback){
 return !std::strcmp(key,"ScreenCenterTolerancePercent")?bino:gunPresent?gun:fallback;}
#define CHECK(x) do{if(!(x))return __LINE__;}while(0)
'''
    tests=r'''
int main(){
 load();CHECK(std::fabs(select(true)-.12f)<.00001f);CHECK(select(false)==select(true));
 gunPresent=true;load();CHECK(std::fabs(select(false)-.03f)<.00001f);CHECK(select(true)>.1f);
 bino=100;gun=-3;load();CHECK(std::fabs(select(true)-.35f)<.00001f);CHECK(std::fabs(select(false)-.001f)<.00001f);
 bino=14;gun=7;load();CHECK(std::fabs(select(true)-.14f)<.00001f);CHECK(std::fabs(select(false)-.07f)<.00001f);
}
'''
    run_variants({'production':code,
        'shared-radius':code.replace('g_reconCachedSettings.weaponAimRadius;','g_reconCachedSettings.binocularAimRadius;'),
        'legacy-default-lost':code.replace('"WeaponScreenCenterTolerancePercent", effectiveAimTolerancePercent','"WeaponScreenCenterTolerancePercent", 5.0f')},prelude,tests)
    menu=(args.runtime_root/'GameplayTweaks/modules/settings_menu.cpp').read_text('utf-8')
    records=menu[menu.index('struct SettingsMenuIniValue {'):menu.index('static bool settingsMenuReadIni()')]
    begin=menu.index('    // #254: old INIs inherit')
    branch=menu[begin:menu.index('\t// The generated table is sorted',begin)]
    menu_code=records+'\nvoid migrate(std::vector<SettingsMenuIniValue>& values){'+branch+'}\n'
    run_variants({'production':menu_code,
        'native-menu-inheritance-lost':menu_code.replace('previous->value,','"5",')},
        '#include <vector>\n#include <string>\n#define CHECK(x) do{if(!(x))return __LINE__;}while(0)\n',r'''
int main(){
 std::vector<SettingsMenuIniValue> values={{"ReconTagging","ScreenCenterTolerancePercent","12",""}};
 migrate(values);CHECK(values.size()==2);CHECK(values[1].value=="12");
 values[1].value="3";migrate(values);CHECK(values.size()==2);CHECK(values[1].value=="3");
}
''')
    start=menu.index('static void settingsMenuWrite(')
    writer=menu[start:menu.index('\n}',start)+2]
    writer_prelude=r'''
#include <string>
#include <cstring>
std::string g_iniPath="fixture.ini",savedGun="",savedBino="12";bool fail=false;
struct SettingsMenuEntry {std::string section,key,value;};
bool settingsMenuNormalizeValue(const SettingsMenuEntry&,const std::string& in,std::string& out){out=in;return true;}
void GetPrivateProfileStringA(const char*,const char*key,const char*fallback,char*out,unsigned n,const char*){
 const auto& value=!std::strcmp(key,"ScreenCenterTolerancePercent")?savedBino:savedGun;
 std::strncpy(out,value.empty()?fallback:value.c_str(),n-1);out[n-1]=0;}
bool WritePrivateProfileStringA(const char*,const char*key,const char*value,const char*){
 if(fail)return false;
 (!std::strcmp(key,"ScreenCenterTolerancePercent")?savedBino:savedGun)=value;return true;}
void loadConfig(){}
#define CHECK(x) do{if(!(x))return __LINE__;}while(0)
'''
    writer_tests=r'''
int main(){
 SettingsMenuEntry entry={"ReconTagging","ScreenCenterTolerancePercent","12"};
 settingsMenuWrite(entry,"20");CHECK(savedBino=="20" && savedGun=="12");
 savedGun="3";settingsMenuWrite(entry,"25");CHECK(savedBino=="25" && savedGun=="3");
 savedGun="";fail=true;settingsMenuWrite(entry,"30");CHECK(savedBino=="25");
}
'''
    run_variants({'production':writer,
        'binocular-save-changes-gun':writer.replace('previous, g_iniPath.c_str())) return;', 'normalized.c_str(), g_iniPath.c_str())) return;')},writer_prelude,writer_tests)
    module=ast.parse((root/'games/rdr2/server.py').read_text('utf-8'))
    names={'_parse_gameplay_settings','_gameplay_settings_schema','_clamp_displayed_settings',
        '_recon_radius_compatibility','_insert_recon_radius_setting','get_gameplay_settings','save_gameplay_settings'}
    selected=ast.Module(body=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
    assert len(selected.body)==len(names)
    schema=json.loads((root/'games/rdr2/settings_schema.json').read_text('utf-8'))
    for key in ('ScreenCenterTolerancePercent','WeaponScreenCenterTolerancePercent'):
        compound='ReconTagging|'+key
        assert schema['ranges'][compound]=={'min':.1,'max':35.,'step':.5}
        assert 'screen width' in schema['help'][compound]
    with tempfile.TemporaryDirectory(prefix='lex-recon-radii-') as temp:
        folder=Path(temp);ini=folder/'GameplayTweaks.ini'
        original='; keep this\n[ReconTagging]\nScreenCenterTolerancePercent=12\nEnabled=1\n[Other]\nKeep=9\n'
        ini.write_text(original,'utf-8')
        env={'json':json,'os':os,'shutil':shutil,'GAMEPLAY_INI_FILE':ini,'GAME_ROOT':folder/'no-game',
            'SETTINGS_SCHEMA_FILE':root/'games/rdr2/settings_schema.json'}
        exec(compile(selected,'server-settings','exec'),env)
        read=env['get_gameplay_settings'];save=env['save_gameplay_settings']
        def values():return {r['key']:r['value'] for s in read()['sections'] if s['name']=='ReconTagging' for r in s['settings']}
        assert values()['WeaponScreenCenterTolerancePercent']=='12'
        assert ini.read_text('utf-8')==original,'read mutated legacy INI'
        save([{'section':'ReconTagging','key':'ScreenCenterTolerancePercent','value':20}])
        assert values()['WeaponScreenCenterTolerancePercent']=='12','binocular edit changed inherited gun value'
        assert values()['ScreenCenterTolerancePercent']=='20'
        ini.write_text(original,'utf-8')
        assert save([{'section':'ReconTagging','key':'WeaponScreenCenterTolerancePercent','value':3}])==1
        assert values()['WeaponScreenCenterTolerancePercent']=='3'
        assert values()['ScreenCenterTolerancePercent']=='12'
        save([{'section':'ReconTagging','key':'ScreenCenterTolerancePercent','value':20}])
        assert values()['WeaponScreenCenterTolerancePercent']=='3'
        save([{'section':'ReconTagging','key':'WeaponScreenCenterTolerancePercent','value':100}])
        assert values()['WeaponScreenCenterTolerancePercent']=='35'
        assert 'Keep=9' in ini.read_text('utf-8') and '; keep this' in ini.read_text('utf-8')
        try:save([{'section':'ReconTagging','key':'UnknownRadius','value':3}])
        except ValueError:pass
        else:raise AssertionError('unknown setting accepted')
    print('PASS: independent radii, inherited legacy default, bounded controls and real settings save/readback. Rendered acceptance remains separate.')

if __name__=='__main__':main()
