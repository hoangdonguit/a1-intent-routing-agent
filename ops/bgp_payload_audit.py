"""Read-only exact and content-normalized audit of the saved BGP02 repair loop."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def h(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def main():
    rows=[];prior=None
    for p in sorted((ROOT/'runs/bgp-remaining-repairs-20261117').glob('round-*/dev_ebgp_prefix_02/request.json')):
        request=json.loads(p.read_text());directory=p.parent;raw=directory/'raw-response.json';response=json.loads(raw.read_text());content=response.get('message',{}).get('content','');record=json.loads((directory/'record.json').read_text())
        candidate={f.name:f.read_text() for f in sorted((directory/'candidate').glob('*.conf'))}
        normalized={k:[line.strip() for line in v.splitlines() if line.strip() and not line.strip().startswith('!')] for k,v in candidate.items()}
        messages=request['messages'];normalized_messages=re.sub(r'/home/[^"\s]+','<LOCAL_PATH>',json.dumps(messages,ensure_ascii=False,sort_keys=True))
        errors=[{k:e.get(k) for k in ['device','property','expected','observed','tool']} for e in record.get('evaluation',{}).get('errors',[])]
        row={'round':p.parts[-3],'messages_sha256':h(messages),'options_sha256':h(request.get('options')),'messages_path_normalized_sha256':h(normalized_messages),'raw_response_sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),'assistant_content_sha256':h(content),'candidate_sha256':h(candidate),'candidate_statements_sha256':h(normalized),'errors_sha256':h(errors),'request':str(p.relative_to(ROOT)),'changed_devices':[] if prior is None else [k for k in candidate if candidate[k]!=prior['_candidate'].get(k)]}
        if prior:
            row['comparison']='identical messages/options' if row['messages_sha256']==prior['messages_sha256'] and row['options_sha256']==prior['options_sha256'] else 'path-normalized messages equal' if row['messages_path_normalized_sha256']==prior['messages_path_normalized_sha256'] else 'messages differ; inspect actual feedback'
            row['same_candidate']=row['candidate_sha256']==prior['candidate_sha256']
        prior=dict(row,_candidate=candidate);rows.append(row)
    target=ROOT/'results/bgp-plan-study-20261120';target.mkdir(parents=True,exist_ok=True);(target/'payload-audit.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n');print(json.dumps(rows,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
