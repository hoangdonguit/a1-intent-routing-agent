"""Conservative, property-level combination. Never resolve disagreements by voting."""
import json


def combine(reports, required_tools=('syntax_checker', 'batfish_verifier', 'lab_ping_tester')):
    reports=list(reports)
    checks=[dict(c,tool=r['tool']) for r in reports for c in r.get('checks',[])]
    missing=sorted(set(required_tools)-{r['tool'] for r in reports})
    incomplete=missing or any(r.get('status') not in ('pass','fail','environment_error') or
        any(c.get('status') not in ('pass','fail','environment_error') for c in r.get('checks',[])) or r.get('unsupported') or not r.get('checks') or
        any(not c.get('evidence') for c in r.get('checks',[])) or r.get('status')=='environment_error' for r in reports)
    disagreements=[]
    by_property={}
    for c in checks:
        # Explicit IDs only: differently scoped checks must not be merged by accident.
        if c.get('property_id'):
            by_property.setdefault(c['property_id'],[]).append(c)
    for key,items in by_property.items():
        if len({c['status'] for c in items})>1:
            disagreements.append({'property_id':key,'observations':items})
    status='environment_error' if incomplete or disagreements else ('fail' if any(r['status']=='fail' for r in reports) or any(c.get('status')=='fail' for c in checks) else 'pass')
    return {'status':status,'checks':checks,'reports':reports,'missing_tools':missing,'disagreements':disagreements,
            'errors':[c for c in checks if c['status']!='pass']}


def repair_feedback(method, evaluation):
    """A1 has precisely two constant payloads. Environment errors never reach a model."""
    if evaluation['status']=='environment_error':
        raise ValueError('Infrastructure/coverage must be resolved outside the model trajectory')
    if method=='A1':
        return 'PASS' if evaluation['status']=='pass' else 'FAIL'
    if method!='A2':
        raise ValueError('Only agent methods receive feedback')
    # No oracle file or complete expected-check inventory; only observed violations.
    fields=('device','property','expected','observed','evidence','tool')
    return json.dumps({'status':evaluation['status'],'errors':[
        {k:c.get(k) for k in fields} for c in evaluation.get('errors',[]) if c.get('status')=='fail']},ensure_ascii=False)
