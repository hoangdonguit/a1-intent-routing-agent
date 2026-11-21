"""Read-only evidence demo. No model, Docker, network, sudo or lab execution."""
import argparse,copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'results/bgp-policy-and-coverage-20261121/full-pass-proof.json'
def verify(root,proof):
    root=Path(root)
    for name,expected in proof['artifact_hashes'].items():
        path=root/name
        if not path.is_file():raise ValueError('Local raw artifact missing: '+name)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('Evidence hash mismatch: '+name)
    result=json.loads((root/proof['final_result']).read_text());required={'syntax_checker','protocol_scope','batfish_verifier','lab_ping_tester','bgp_export_tester'}
    if proof['final_status']!='pass' or proof['restore']!='pass' or result['status']!='pass' or result.get('disagreements'):raise ValueError('No complete PASS/restore proof')
    reports={r['tool']:r for r in result['reports']}
    if not required<=reports.keys():raise ValueError('Missing mandatory tool')
    for report in reports.values():
        if report['status']!='pass' or report.get('unsupported') or not report.get('checks') or any(c['status']!='pass' or not c.get('evidence') for c in report['checks']):raise ValueError('Incomplete mandatory evidence')
        for c in report['checks']:
            for e in c['evidence']:
                path=Path(e)
                if path.is_absolute():
                    try:name=str(path.relative_to(Path(proof.get('recorded_workspace_root',root))))
                    except ValueError:raise ValueError('Evidence outside recorded workspace')
                else:name=str(path)
                if name not in proof['artifact_hashes']:raise ValueError('Unhashed check evidence: '+name)
    parent=json.loads((root/proof['final_parent_ir']).read_text());candidate=json.loads((root/proof['final_ir']).read_text());update=json.loads((root/proof['final_update']).read_text());raw=json.loads((root/proof['final_raw_model_response']).read_text())
    if json.loads(raw['message']['content'])!=update:raise ValueError('Stored update is not actual model response')
    if set(update)!={'version','updates'} or update['version']!='bgp-origin-update-v1':raise ValueError('Wrong update contract')
    materialized=copy.deepcopy(parent);devices={d['id']:d for d in materialized['devices']};seen=set()
    for row in update['updates']:
        if set(row)!={'device_id','originate'} or row['device_id'] in seen or row['device_id'] not in devices:raise ValueError('Invalid/duplicate object update')
        seen.add(row['device_id']);devices[row['device_id']]['originate']=row['originate']
    if materialized!=candidate:raise ValueError('Final IR is not the literal model update applied to its fixed parent')
    return reports

def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--proof',type=Path,default=DEFAULT);a=p.parse_args()
    try:
        proof=json.loads(a.proof.read_text());reports=verify(ROOT,proof)
    except (OSError,ValueError,KeyError,TypeError) as exc:p.exit(2,str(exc)+'\n')
    print('READ-ONLY EVIDENCE DEMO: one staged/supervised dev diagnostic; not a frozen benchmark comparison.')
    for row in proof['stages']:
        tools=row.get('tools',{});print(row['stage'],row['verdict'],'lab='+tools.get('lab_ping_tester',row.get('lab','not_run')),'export='+tools.get('bgp_export_tester','not_run'),'scope='+row.get('scope','see stage records'))
    print('FINAL:',proof['case_id'],'PASS; all mandatory tools PASS; disagreements0; restorePASS')
    print('Verified artifacts:',len(proof['artifact_hashes']),'Checks:',sum(len(r['checks']) for r in reports.values()))
    print('Rejected proposal retained. Literal model update verified; no manual merge, grader rewrite or snapshot substitution.')
    print('No new model/lab run. Fresh-host and live-intent demo remain separate acceptance items.')
if __name__=='__main__':main()
