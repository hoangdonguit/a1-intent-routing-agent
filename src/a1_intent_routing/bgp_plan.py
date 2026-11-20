"""Opt-in BGP decision IR. Renderer knows public base, never intent/oracle/answers."""
from copy import deepcopy
from ipaddress import IPv4Address,IPv4Network
import hashlib,json,re

VERSION='bgp-plan-v1'
RENDERER_VERSION='bgp-plan-renderer-v1'


def obj(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}


def schema(devices):
    ident={'type':'string','pattern':'^[A-Za-z][A-Za-z0-9_-]{0,31}$'}
    policy=obj({'id':ident,'rules':{'type':'array','maxItems':8,'items':obj({'id':ident,'prefix':{'type':'string'},'action':{'type':'string','enum':['permit','deny']}})},'default':{'type':'string','enum':['permit','deny']}})
    peer=obj({'id':ident,'address':{'type':'string'},'remote_as':{'type':'integer','minimum':1,'maximum':4294967295},'ipv4':{'type':'boolean'},'import':{'type':'string'},'export':{'type':'string'}})
    device=obj({'id':{'type':'string','enum':sorted(devices)},'asn':{'type':'integer','minimum':1,'maximum':4294967295},'originate':{'type':'array','maxItems':8,'uniqueItems':True,'items':{'type':'string'}},'peers':{'type':'array','maxItems':8,'items':peer}})
    return obj({'version':{'type':'string','enum':[VERSION]},'policies':{'type':'array','maxItems':8,'items':policy},'devices':{'type':'array','minItems':len(devices),'maxItems':len(devices),'items':device}})


class PlanError(ValueError):
    def __init__(self,message,path='$'):super().__init__(message);self.path=path


def unique_json(text):
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise PlanError('Duplicate JSON key: '+k)
            d[k]=v
        return d
    return json.loads(text,object_pairs_hook=pairs)


def validate(plan,devices):
    from jsonschema import Draft202012Validator
    errors=sorted(Draft202012Validator(schema(devices)).iter_errors(plan),key=lambda e:str(list(e.path)))
    if errors:raise PlanError(errors[0].message,'$.'+'.'.join(map(str,errors[0].path)))
    def distinct(rows,path):
        ids=[x['id'] for x in rows]
        if len(set(ids))!=len(ids):raise PlanError('Object IDs must be unique',path)
    distinct(plan['devices'],'$.devices');distinct(plan['policies'],'$.policies')
    if {x['id'] for x in plan['devices']}!=set(devices):raise PlanError('Exactly the public device set is required','$.devices')
    known={p['id'] for p in plan['policies']}
    if 'none' in known:raise PlanError('Policy ID none is reserved for unattached policy')
    for i,p in enumerate(plan['policies']):
        distinct(p['rules'],f'$.policies.{i}.rules')
        for j,rule in enumerate(p['rules']):
            try:IPv4Network(rule['prefix'],strict=True)
            except ValueError as exc:raise PlanError('Expected canonical IPv4 prefix',f'$.policies.{i}.rules.{j}.prefix') from exc
    for i,d in enumerate(plan['devices']):
        distinct(d['peers'],f'$.devices.{i}.peers');addresses=set()
        for prefix in d['originate']:
            try:IPv4Network(prefix,strict=True)
            except ValueError as exc:raise PlanError('Invalid IPv4 originate prefix',f'$.devices.{i}.originate') from exc
        for j,p in enumerate(d['peers']):
            try:IPv4Address(p['address'])
            except ValueError as exc:raise PlanError('Expected IPv4 peer address',f'$.devices.{i}.peers.{j}.address') from exc
            if p['address'] in addresses:raise PlanError('Duplicate peer address',f'$.devices.{i}.peers.{j}')
            addresses.add(p['address'])
            for direction in ['import','export']:
                if p[direction]!='none' and p[direction] not in known:raise PlanError('Undefined policy ID',f'$.devices.{i}.peers.{j}.{direction}')
    return plan


def render(plan,base):
    validate(plan,base);result={}
    for d in plan['devices']:
        # Public base is trusted only as immutable interface boilerplate, not a solver.
        if re.search(r'^\s*(router |ip route |route-map |ip prefix-list |network |neighbor )',base[d['id']],re.M):raise PlanError('BGP prototype requires an interface-only public base')
        lines=[]
        for policy in plan['policies']:
            for index,rule in enumerate(policy['rules'],1):
                name='IR_'+policy['id']+'_'+rule['id'];lines += [f'ip prefix-list {name} seq 10 permit {rule["prefix"]}',f'route-map IR_{policy["id"]} {rule["action"]} {index*10}',f' match ip address prefix-list {name}','exit']
            lines += [f'route-map IR_{policy["id"]} {policy["default"]} 65000','exit']
        lines += [f'router bgp {d["asn"]}']
        for peer in d['peers']:lines += [f' neighbor {peer["address"]} remote-as {peer["remote_as"]}']
        lines += [' address-family ipv4 unicast']
        for prefix in d['originate']:lines += ['  network '+prefix]
        for peer in d['peers']:
            lines += [('  neighbor '+peer['address']+' activate') if peer['ipv4'] else ('  no neighbor '+peer['address']+' activate')]
            for direction in ['import','export']:
                if peer[direction]!='none':lines += [f'  neighbor {peer["address"]} route-map IR_{peer[direction]} {"in" if direction=="import" else "out"}']
        lines += [' exit-address-family','exit']
        result[d['id']]=base[d['id']]+('' if base[d['id']].endswith('\n') else '\n')+'! bgp-plan-renderer-v1\n'+'\n'.join(lines)+'\n'
    return result


def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def semantic_digest(plan):
    x=deepcopy(plan);policy_ids={p['id']:digest({'rules':[{k:r[k] for k in ['prefix','action']} for r in p['rules']],'default':p['default']}) for p in x['policies']}
    for d in x['devices']:
        d['originate']=sorted(d['originate'])
        for p in d['peers']:
            p.pop('id')
            for key in ['import','export']:p[key]=policy_ids.get(p[key],p[key])
        d['peers']=sorted(d['peers'],key=lambda p:p['address'])
    return digest({'devices':sorted(x['devices'],key=lambda d:d['id'])})
