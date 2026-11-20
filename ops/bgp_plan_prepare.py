"""Prepare a bounded, immutable BGP-plan study. No Qwen calls or topology mutation."""
import sys,json,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'ops'))
from a1_intent_routing.bgp_hybrid_eval import load_case,dump
from a1_intent_routing.bgp_plan import render,schema,VERSION
from a1_intent_routing.verifiers import syntax_checker,Evidence,diagnostic_failed
from a1_intent_routing.batfish import verify
from a1_intent_routing.contracts import CaseOracle,Topology
from bgp_plan_controls import controls
OUT=ROOT/'runs/bgp-plan-study-20261120'


def main():
    if OUT.exists():raise RuntimeError('Preserve existing study')
    OUT.mkdir();entries=[]
    for cid in ['dev_ebgp_prefix_01','dev_ebgp_prefix_02']:
        public,t,base,d=load_case(ROOT,cid)
        for label,plan in controls(public,t):
            directory=OUT/'controls'/(cid+'--'+label);directory.mkdir(parents=True);dump(directory/'plan.json',plan);configs=render(plan,base);target=directory/'configs';target.mkdir()
            for n,text in configs.items():(target/(n+'.conf')).write_text(text)
            entries.append({'case_id':cid,'label':cid+'--'+label,'configs':str(target),'expected':'pass' if label=='positive' else 'fail','variant':label})
    # Independent parser/API probe, no real links. Empty JSON is never a semantic pass.
    public,t,base,d=load_case(ROOT,'dev_ebgp_prefix_01');node=next(n for n in t.nodes if n.name=='R2')
    class Probe(Evidence):
        def __init__(self,path):super().__init__(path);self.probes=[]
        def run(self,argv,*args,**kw):
            if list(argv)[:2]==['docker','logs']:
                for command in ['show running-config','show ip route json','show bgp ipv4 unicast json','show bgp ipv4 unicast import-check-table json','show bgp ipv4 unicast neighbors 10.6.1.1 advertised-routes json']:
                    result=super().run(['docker','exec',argv[2],'vtysh','-c',command],check=False)
                    self.probes.append({'command':command,'artifact':self.last,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr,'parser_accepted':not diagnostic_failed(result)})
            return super().run(argv,*args,**kw)
    evidence=Probe(OUT/'cli-probe');report=syntax_checker({'R2':d/'reference/R2.conf'},Topology('isolated-cli',(node,),()),json.loads((ROOT/'labs/sixrouter/images.lock.json').read_text()),evidence).to_dict();dump(OUT/'cli-probe/report.json',report);dump(OUT/'cli-probe/commands.json',evidence.probes)
    if report['status']!='pass':raise RuntimeError('Pinned FRR CLI probe failed')
    origins=[]
    for backing in ['connected','static','absent','learned-bgp']:
        for check in ['on','off']:
            directory=OUT/'origination'/(backing+'-'+check);directory.mkdir(parents=True);target=directory/'configs';target.mkdir()
            prefix='192.168.2.0/24' if backing=='learned-bgp' else '203.0.113.0/24'
            for source in (d/'reference').glob('*.conf'):
                text=source.read_text()
                if source.stem=='R2':
                    if backing=='connected':text='interface lo\n ip address 203.0.113.1/24\nexit\n'+text
                    if backing=='static':text='ip route 203.0.113.0/24 10.6.2.2\n'+text
                    text=text.replace('router bgp 65002\n','router bgp 65002\n '+('bgp network import-check' if check=='on' else 'no bgp network import-check')+'\n',1)
                    text=text.replace(' address-family ipv4 unicast\n',' address-family ipv4 unicast\n  network '+prefix+'\n',1)
                (target/source.name).write_text(text)
            origins.append({'label':backing+'-'+check,'backing':backing,'import_check':check,'prefix':prefix,'configs':str(target)})
    # Freeze after all study code is final; main runner calls freeze separately.
    dump(OUT/'definition.json',{'version':'bgp-plan-study-v1','case_ids':['dev_ebgp_prefix_01','dev_ebgp_prefix_02'],'controls':entries,'origination':origins,
      'origination_rationale':'6connected/static/absent contrasts plus2learned contrasts needed to isolate the already-observed transit counterexample; peering and import/export policy remain fixed.',
      'max_trajectories':6,'max_candidate_generations':26,'max_repairs':5,'repeat':1,'schema':schema(base),'pilot_model':'qwen3:4b-instruct-2507-q4_K_M','options':{'num_ctx':12288,'num_predict':3072,'temperature':0,'seed':539,'top_k':40,'top_p':0.9,'repeat_penalty':1.0},'status':'prepared_not_calibrated'})
    print(OUT/'definition.json')

if __name__=='__main__':main()
