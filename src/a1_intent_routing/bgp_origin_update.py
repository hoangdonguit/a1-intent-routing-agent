"""Model-chosen originate updates by stable ID; preserve all other source fields.

No topology, intent, oracle or reference input. Never infer/add/remove a prefix
except the literal replacement arrays returned by the model.
"""
from copy import deepcopy
from .bgp_plan import obj,validate,PlanError
VERSION='bgp-origin-update-v1'
def schema(devices):
    return obj({'version':{'type':'string','enum':[VERSION]},'updates':{'type':'array','maxItems':len(devices),'items':obj({'device_id':{'type':'string','enum':sorted(devices)},'originate':{'type':'array','maxItems':8,'uniqueItems':True,'items':{'type':'string'}}})}})
def apply(source,patch):
    from jsonschema import Draft202012Validator
    devices={d['id'] for d in source['devices']};errors=list(Draft202012Validator(schema(devices)).iter_errors(patch))
    if errors:raise PlanError(errors[0].message)
    ids=[u['device_id'] for u in patch['updates']]
    if len(ids)!=len(set(ids)):raise PlanError('Duplicate device update')
    candidate=deepcopy(source);by_id={d['id']:d for d in candidate['devices']}
    for update in patch['updates']:by_id[update['device_id']]['originate']=deepcopy(update['originate'])
    validate(candidate,devices)
    return candidate
