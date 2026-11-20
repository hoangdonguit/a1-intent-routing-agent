"""New study revision; retain invalid old control and reuse only hash-verified evidence."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from a1_intent_routing.bgp_hybrid_eval import dump,load_case
from a1_intent_routing.bgp_plan import render
OLD=ROOT/'runs/bgp-plan-study-20261120';OUT=ROOT/'runs/bgp-plan-study-20261120-02'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 if OUT.exists():raise RuntimeError('Keep existing revision')
 manifest=json.loads((OLD/'manifest.json').read_text());previous=json.loads((OLD/'state.json').read_text());definition=json.loads((OLD/'definition.json').read_text());completed={};provenance=[]
 # Only syntax lo handling, diagnostic-only static allowance, the no-op control,
 # and runner paths/summary labeling changed. Legacy no-lo controls remain valid.
 for entry in definition['controls']+definition['origination']:
  for config in Path(entry['configs']).glob('*.conf'):
   if sha(config)!=manifest['files'][str(config.relative_to(ROOT))]:raise RuntimeError('Old config changed: '+str(config))
 OUT.mkdir();definition['version']='bgp-plan-study-v2';definition['revision_reason']='lo namespace materialization fix, diagnostic-only static scope, replace no-op R5 negative with R6 originate removal; no model/method/options/renderer change'
 for entry in definition['controls']:
  key='controls/'+entry['label'];old=previous['completed'].get(key)
  if entry['variant']=='missing-originate':
   p=Path(entry['configs']).parent/'plan.json';plan=json.loads(p.read_text());r6=next(d for d in plan['devices'] if d['id']=='R6');assert r6['originate'];r6['originate']=[]
   public,t,base,d=load_case(ROOT,entry['case_id']);configs=render(plan,base);target=OUT/'controls'/entry['label'];target.mkdir(parents=True);dump(target/'plan.json',plan);(target/'configs').mkdir()
   for n,text in configs.items():(target/'configs'/(n+'.conf')).write_text(text)
   assert any(configs[n]!=(Path(entry['configs'])/(n+'.conf')).read_text() for n in configs),'Negative must change config'
   entry['configs']=str(target/'configs');continue
  if old and old['calibrated']:
   completed[key]=dict(old,reused=True);provenance.append({'key':key,'config_hashes':{p.name:sha(p) for p in Path(entry['configs']).glob('*.conf')},'result_sha256':sha(old['result'])})
 for entry in definition['origination']:
  key='origination/'+entry['label'];old=previous['completed'].get(key)
  if entry['backing'] in ['absent','learned-bgp'] and old:
   completed[key]=dict(old,calibrated=None,reused=True);provenance.append({'key':key,'result_sha256':sha(old['result'])})
 dump(OUT/'definition.json',definition);dump(OUT/'reuse.json',{'source':str(OLD),'entries':provenance,'retired_control':previous['completed'].get('controls/dev_ebgp_prefix_02--missing-originate'),'rerun_reason':'Only connected/static diagnostic execution was invalid. Five passing no-lo controls and four diagnostic observations reused; old verdicts retained.'})
 dump(OUT/'state.json',{'completed':completed,'trajectories':{},'calls':0,'source_revision':str(OLD)});print('Prepared revision2; reused',len(completed),'entries; new model calls0')
if __name__=='__main__':main()
