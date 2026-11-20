"""Evaluator-only independent controls; NEVER called to construct model requests."""
from copy import deepcopy
from ipaddress import IPv4Interface
from a1_intent_routing.bgp_plan import VERSION


def positive(public,t):
    ps=public['specification']['bgp'];nodes={n.name:n for n in t.nodes};ip=t.interfaces
    banned=[str(IPv4Interface(nodes[h].interfaces[0].ipv4).network) for h in ps['deny_export_hosts']]
    policies=[{'id':'accept','rules':[],'default':'permit'},{'id':'send','rules':[{'id':'ban'+str(i),'prefix':p,'action':'deny'} for i,p in enumerate(banned)],'default':'permit'}]
    devices=[]
    for node in t.nodes:
        if node.kind!='router':continue
        peers=[];originate=[]
        for link in t.links:
            for a,b in ((link.a,link.b),(link.b,link.a)):
                if a.node!=node.name:continue
                if nodes[b.node].kind=='router':peers.append({'id':a.node+'_'+b.node,'address':str(ip[b].ip),'remote_as':ps['asns'][b.node],'ipv4':True,'import':'accept','export':'send'})
                elif b.node in ps['advertise_hosts']:originate.append(str(ip[a].network))
        devices.append({'id':node.name,'asn':ps['asns'][node.name],'originate':originate,'peers':peers})
    return {'version':VERSION,'policies':policies,'devices':devices}


def controls(public,t):
    good=positive(public,t);rows=[('positive',good)]
    if public['case_id']!='dev_ebgp_prefix_02':return rows
    def variant(name,change):
        p=deepcopy(good);change(p);rows.append((name,p))
    def dev(p,n):return next(x for x in p['devices'] if x['id']==n)
    variant('wrong-asn',lambda p:dev(p,'R2').update(asn=60002))
    variant('self-neighbor',lambda p:dev(p,'R1')['peers'][0].update(address='10.6.1.1'))
    variant('missing-peer',lambda p:dev(p,'R2')['peers'].pop())
    variant('missing-originate',lambda p:dev(p,'R5').update(originate=[]))
    variant('leak',lambda p:p['policies'][1].update(rules=[]))
    variant('unattached-policy',lambda p:[peer.update({'import':'none'}) for peer in dev(p,'R1')['peers']])
    variant('inverted-decision',lambda p:p['policies'][1]['rules'][0].update(action='permit'))
    def masked(p):
        p['policies'][0]['rules']=[{'id':'receiverH2','prefix':'192.168.2.0/24','action':'deny'}]
        p['policies'][1]['rules']=[]
    variant('sender-allows-receiver-denies',masked)
    return rows
