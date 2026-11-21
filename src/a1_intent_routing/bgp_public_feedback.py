"""Feedback for public-precheck failures only, isolated from frozen pilot v1."""
import json
VERSION='bgp-public-root-feedback-v1'
def feedback(method,report):
    if report['status']!='fail':raise ValueError('Only proven precheck failures may reach repair; coverage/environment is not feedback')
    if method=='A1':return 'FAIL'
    if method!='A2':raise ValueError('B1 receives no feedback')
    errors=sorted(report['errors'],key=lambda e:(0 if e['property']=='ir_schema' else 1 if e['property'].startswith(('fixed_asn','required_peer','self_neighbor','required_network')) else 2,e['property'],str(e.get('device'))))
    selected=[]
    for error in errors[:6]:
        selected.append({k:error.get(k) for k in ['device','property','expected','observed','object_ids']})
    return json.dumps({'status':'fail','instruction':'Revise the failed BGP plan to satisfy the reported public constraints. Preserve other decisions unless needed. Return the complete IR JSON only.','errors':selected},ensure_ascii=False,separators=(',',':'))
