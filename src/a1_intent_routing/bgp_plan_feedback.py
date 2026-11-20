"""Frozen short-history policy for the opt-in hybrid pilot, not raw-FRR A1/A2."""
from copy import deepcopy
import json
from .bgp_plan import digest,semantic_digest
VERSION='bgp-plan-history2-stagnation-v1'


def feedback(method,evaluation,plan=None):
    if method=='A1':return 'FAIL'
    errors=[x for x in evaluation.get('errors',[]) if x.get('status')=='fail']
    priority=lambda x:0 if x.get('tool') in ('ir_validator','syntax_checker','protocol_scope') else 1 if 'peer' in x.get('property','') or 'export' in x.get('property','') else 2
    errors=sorted(errors,key=priority);rows=[];seen=set()
    for e in errors:
        key=(e.get('device'),e.get('property'))
        if key in seen:continue
        seen.add(key);row={k:e.get(k) for k in ['device','property','expected','observed','tool']}
        if isinstance(row['observed'],list):row['observed']={'present':bool(row['observed']),'count':len(row['observed'])}
        elif len(json.dumps(row['observed'],ensure_ascii=False))>600:row['observed']={'summary':str(row['observed'])[:600],'truncated':True}
        if plan and e.get('device'):
            row['object_ids']=[d['id'] for d in plan['devices'] if d['id']==e['device']]
            for d in plan['devices']:
                if d['id']==e['device']:
                    row['object_ids'] += [p['id'] for p in d['peers'] if p['address'] in e.get('property','')]
        rows.append(row)
        if len(rows)==6:break
    return json.dumps({'status':'fail','errors':rows},ensure_ascii=False,separators=(',',':'))


def messages(initial,history,method):
    result=deepcopy(initial)
    for turn in history[-2:]:
        result.append({'role':'assistant','content':turn['content']})
        result.append({'role':'user','content':'FAIL' if method=='A1' else turn['feedback']})
    return result


def repeated(plan,seen):return semantic_digest(plan) in seen
