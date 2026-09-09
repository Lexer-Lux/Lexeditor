"""Run the local RDR2 source checks with bounded time and no native windows."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys

# These legacy checks invoke the native host or regenerate live project data.
# Run them separately with their required setup; never count omission as a pass.
MANUAL = {
 'verify_lexeditor_integration_issue_141.py':'Native WebView2 host smoke; separate explicit window test.',
 'verify_gang_hideouts_issue_80.py':'Regenerates live collectibles data; needs an isolated data fixture.',
}

def main():
 p=argparse.ArgumentParser();p.add_argument('--runtime-root',type=Path,default=Path('C:/RDR2Mod'));p.add_argument('--timeout',type=int,default=60);args=p.parse_args()
 root=args.runtime_root.resolve();out=Path(__file__).resolve().parents[1]/'out/rdr2-runtime-audit';out.mkdir(parents=True,exist_ok=True)
 sys.path.insert(0,str(root/'tools'))
 from verifier_status import classify
 results=[]
 local_tools=Path(__file__).resolve().parent
 harnesses=[local_tools/name for name in ('verify_rdr2_climb_transitions.py',
             'verify_rdr2_minimap_lifecycle.py', 'verify_rdr2_gold_core_render.py',
             'verify_rdr2_camera_switch.py', 'verify_rdr2_vehicle_camera.py', 'verify_rdr2_player_core_rates.py',
             'verify_rdr2_train_tracking.py', 'verify_rdr2_duplicate_card_transactions.py',
             'verify_rdr2_smoking_cards.py', 'verify_rdr2_lantern_crouch.py', 'verify_rdr2_recon_area.py',
             'verify_rdr2_recon_radii.py', 'verify_rdr2_horse_exhaustion.py', 'verify_rdr2_casing_acquisition.py', 'verify_rdr2_gear_identity_probe.py', 'verify_rdr2_recon_cutscenes.py', 'verify_rdr2_stealth_indicators.py', 'verify_rdr2_camera_authoring.py',
             'verify_rdr2_overflow_registry.py', 'verify_rdr2_binocular_stow.py')]
 for script in sorted((root/'tools/reverse-engineering').glob('verify_*.py'))+harnesses:
  if script.name in MANUAL:
   results.append({'name':script.name,'status':'NOT-RUN','detail':MANUAL[script.name]});continue
  try:
   command=[sys.executable,'-X','utf8',str(script)]
   if script in harnesses: command += ['--runtime-root',str(root)]
   result=subprocess.run(command,cwd=root,env={**os.environ,'PYTHONUTF8':'1'},capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=args.timeout)
   output=result.stdout+result.stderr;status,detail=classify(output,result.returncode)
  except subprocess.TimeoutExpired:
   output=f'Exceeded {args.timeout} seconds';status,detail='TIMEOUT',output
  (out/(script.stem+'.log')).write_text(output[:1024*1024],'utf-8')
  results.append({'name':script.name,'status':status,'detail':detail})
  print(f'{status}: {script.name}',flush=True)
 (out/'results.json').write_text(json.dumps(results,indent=2),'utf-8')
 counts={s:sum(r['status']==s for r in results) for s in sorted({r['status'] for r in results})}
 print(json.dumps(counts),flush=True)
 return int(any(r['status']!='PASS' for r in results))
if __name__=='__main__':sys.exit(main())
