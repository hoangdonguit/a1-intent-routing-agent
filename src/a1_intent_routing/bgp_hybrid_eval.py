"""Opt-in common grader: legacy assertions retained plus sender export evidence."""
from pathlib import Path
import importlib.util,json,subprocess,sys,time
from .contracts import Topology,CaseOracle
from .verifiers import Evidence,syntax_checker,lab_ping_tester
from .policy import check_protocols
from .batfish import verify
from .evaluation import combine
from .bgp_export import check_exports
from .isolation import isolation_changes
VERSION='bgp-hybrid-export-v1'


def load_case(root,cid):
    root=Path(root)
    if cid not in ('dev_ebgp_prefix_01','dev_ebgp_prefix_02'):raise ValueError('Hybrid pilot is BGP dev only')
    m=json.loads((root/'data/benchmark/manifest.json').read_text());entry=next(e for e in m['entries'] if e['case_id']==cid and e['split']=='dev');d=root/entry['path']
    public=json.loads((d/'public.json').read_text());t=Topology.from_dict(json.loads((d/public['topology']).read_text()));base={n.name:(d/'base'/f'{n.name}.conf').read_text() for n in t.nodes if n.kind=='router'}
    return public,t,base,d


def dump(path,data):Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def inventory():
    rows=[json.loads(s) for s in subprocess.check_output(['docker','ps','-a','--format','{{json .}}'],text=True,timeout=15).splitlines()]
    return {'own':sorted(r['ID'] for r in rows if r['Names'].startswith('clab-a1-sixrouter-')),'other':{r['ID']:{k:r[k] for k in ['Names','State','Image']} for r in rows if not r['Names'].startswith('clab-a1-sixrouter-')},'networks':sorted(subprocess.check_output(['docker','network','ls','-q'],text=True,timeout=15).split()),'routes':json.loads(subprocess.check_output(['ip','-j','route'],text=True,timeout=15))}


def evaluate(root,cid,configs,out,diagnostic_connected=False,diagnostic_static=False):
    root=Path(root);out=Path(out);out.mkdir(parents=True,exist_ok=False);public,t,base,d=load_case(root,cid);ps=public['specification'];reports=[];start=time.monotonic()
    if diagnostic_connected:
        from dataclasses import replace
        from .contracts import Interface
        t=replace(t,nodes=tuple(replace(n,interfaces=n.interfaces+(Interface('lo','203.0.113.1/24'),)) if n.name=='R2' else n for n in t.nodes))
    files={n:Path(configs)/(n+'.conf') for n in base};syntax=syntax_checker(files,t,json.loads((root/'labs/triangle3/images.lock.json').read_text()),Evidence(out/'syntax')).to_dict();reports.append(syntax)
    if syntax['status']=='pass':reports.append(check_protocols(t,files,['bgp','static'] if diagnostic_static else ['bgp'],fixed_asns=ps['bgp']['asns']))
    if any(r['status']!='pass' for r in reports):
        result={'status':'environment_error' if any(r['status']=='environment_error' for r in reports) else 'fail','reports':reports,'errors':[dict(e,tool=r['tool']) for r in reports for e in r.get('errors',[])],'gate':'syntax_or_scope'}
    else:
        try:
            # Caller owns shared project flock; no nested health --start.
            subprocess.run([sys.executable,str(root/'scripts/lab.py'),'destroy'],check=True,timeout=180)
            before=inventory();Evidence(out/'lifecycle').run([sys.executable,str(root/'scripts/six_lab.py'),'reset','--configs',str(Path(configs).resolve())],timeout=600);after=inventory();isolation=isolation_changes(before,after)
            fresh=len(after['own'])==len(t.nodes) and not set(before['own']).intersection(after['own']);dump(out/'isolation.json',dict(isolation,fresh_container_ids=fresh))
            if not isolation['other_resources_unchanged'] or not fresh:raise RuntimeError('Reset isolation failed')
            raw=json.loads((d/'oracle.json').read_text());oracle=CaseOracle.from_dict({k:v for k,v in raw.items() if k!='prefix_checks'},t)
            lab=lab_ping_tester(oracle,t,Evidence(out/'lab',lab_name='a1-sixrouter'),bgp_spec=ps['bgp'],prefix_checks=raw.get('prefix_checks',[])).to_dict();index=-1
            for c in lab['checks']:
                if c['property'].endswith('.reachability'):index+=1;c['property_id']=f'traffic:{index}:reachability'
                elif c['property'].endswith('.path'):c['property_id']=f'traffic:{index}:path'
            bf=verify(t,oracle,files,out/'batfish',public_spec=ps,prefix_checks=raw.get('prefix_checks',[]))
            for report in [lab,bf]:
                for c in report['checks']:
                    if c['property'].startswith('prefix:'):c['property_id']=str(c['device'])+':'+c['property']
            reports.extend([lab,bf]);legacy=combine(reports);dump(out/'legacy-result.json',legacy)
            from pybatfish.client.session import Session
            session=Session(host='127.0.0.1',timeout=15);session.set_network('a1-intent-routing');session.set_snapshot(bf['snapshot_name'])
            exports=check_exports(t,ps,Evidence(out/'export',lab_name='a1-sixrouter'),session);reports.append(exports)
            result=combine(reports,required_tools=('syntax_checker','batfish_verifier','lab_ping_tester','bgp_export_tester'))
        except Exception as exc:
            error={'device':None,'property':'evaluator_environment','expected':'available calibrated tools/lab','observed':f'{type(exc).__name__}: {exc}','status':'environment_error','tool':'environment','evidence':[str(out/'result.json')]}
            result={'status':'environment_error','reports':reports,'errors':[error],'gate':'environment'}
    result.update(case_id=cid,grader_version=VERSION,elapsed_seconds=time.monotonic()-start);dump(out/'result.json',result);return result
