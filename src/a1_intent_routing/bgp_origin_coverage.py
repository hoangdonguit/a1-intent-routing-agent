"""Conservative coverage guard calibrated by paired real-FRR/lab/Batfish evidence.

Transit/nonconnected BGP network statements are not universally invalid. The
pinned Batfish model disagreed with FRR for a reference plus one such statement.
Do not rewrite/remove them or present model predictions as acceptance evidence.
"""
from ipaddress import IPv4Interface,IPv4Network

VERSION='connected-network-origination-coverage-v1'


def origination_gaps(topology,configs):
    result=[]
    for node in topology.nodes:
        if node.kind!='router':continue
        connected={IPv4Interface(i.ipv4).network for i in node.interfaces}
        path=configs.get(node.name)
        if path is None:continue  # Missing configs are handled by mandatory syntax/interface checks.
        for number,line in enumerate(path.read_text().splitlines(),1):
            words=line.strip().split()
            if words[:1]!=['network']:continue
            reason=None;prefix=None
            try:
                if len(words)!=2:raise ValueError('alternate network form')
                prefix=IPv4Network(words[1])
                if prefix not in connected:reason='network is not an exact public connected prefix; transit origination differs between pinned models'
            except ValueError:reason='network statement form outside calibrated direct IPv4 subset'
            if reason:
                result.append({'device':node.name,'line':number,'statement':line.strip(),'prefix':str(prefix) if prefix is not None else None,
                               'public_connected_prefixes':sorted(str(n) for n in connected),'reason':reason})
    return result
