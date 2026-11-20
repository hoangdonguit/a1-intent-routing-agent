"""Passive IPv4 echo-request evidence in owned lab namespaces, independent of reply routes."""
import json,socket,struct,subprocess,sys,time
from pathlib import Path

class CaptureFailure(RuntimeError):pass


def decode_echo(frame,source,destination):
    if len(frame)<42 or struct.unpack('!H',frame[12:14])[0]!=0x0800:return None
    ip=frame[14:];ihl=(ip[0]&15)*4
    if ip[0]>>4!=4 or ihl<20 or len(ip)<ihl+8 or ip[9]!=1:return None
    if struct.unpack('!H',ip[6:8])[0]&0x1fff:return None
    if socket.inet_ntoa(ip[12:16])!=source or socket.inet_ntoa(ip[16:20])!=destination:return None
    if ip[ihl]!=8 or ip[ihl+1]!=0:return None
    ident,sequence=struct.unpack('!HH',ip[ihl+4:ihl+8])
    return {'identifier':ident,'sequence':sequence,'ttl':ip[8]}


def analyze_paths(captures,source,destination,topology):
    groups={};delivered=set()
    for node,capture in captures.items():
        for packet in capture['packets']:
            key=(packet['identifier'],packet['sequence'])
            groups.setdefault(key,set()).add((packet['ttl'],node))
            if node==destination:delivered.add(key)
    result={'delivered':bool(delivered),'received_probes':len(delivered),'paths':[],'evidence_gap':None}
    edges={frozenset((link.a.node,link.b.node)) for link in topology.links}
    for key in sorted(delivered):
        hops=sorted(groups[key],reverse=True);ttls=[ttl for ttl,node in hops]
        if not hops or ttls[0]!=64 or any(a-b!=1 for a,b in zip(ttls,ttls[1:])):
            result['evidence_gap']='Missing/duplicate ingress TTL observation; cannot infer omitted hops';continue
        path=[source]+[node for ttl,node in hops]
        if path[-1]!=destination or any(frozenset((a,b)) not in edges for a,b in zip(path,path[1:])):
            result['evidence_gap']='Captured path is incomplete or not adjacent in physical topology';continue
        result['paths'].append(path)
    return result


class CaptureSet:
    def __init__(self,evidence,topology,check,index):
        self.evidence=evidence;self.check=check;self.nodes=[n.name for n in topology.nodes if n.kind=='router']
        if check.destination.node not in self.nodes:self.nodes.append(check.destination.node)
        self.root=evidence.root/'packet-captures'/f'flow-{index}';self.root.mkdir(parents=True,exist_ok=False)
        self.processes={};self.logs=[]
    def start(self):
        project=Path(__file__).resolve().parents[2]
        try:
            for node in self.nodes:
                path=self.root/f'{node}.json';ready=self.root/f'{node}.ready.json';log=(self.root/f'{node}.worker.log').open('w');self.logs.append(log)
                argv=[sys.executable,str(project/'scripts/capture_icmp.py'),'--container',f'clab-{self.evidence.lab_name}-{node}',
                      '--node',node,'--source',self.check.source.ip,'--destination',self.check.destination.ip,'--out',str(path),'--ready',str(ready)]
                process=subprocess.Popen(argv,stdout=log,stderr=log);self.processes[node]=(process,path,ready)
            deadline=time.monotonic()+10
            while True:
                if all(ready.is_file() for process,path,ready in self.processes.values()):break
                for node,(process,path,ready) in self.processes.items():
                    if process.poll() is not None and not ready.is_file():
                        raise CaptureFailure('Receiver capture failed to start for '+node+': '+(path.read_text() if path.exists() else str(path)))
                if time.monotonic()>=deadline:raise CaptureFailure('Receiver capture readiness timeout')
                time.sleep(.05)
            return self
        except Exception:
            self.stop();raise
    def stop(self):
        for process,path,ready in self.processes.values():
            if process.poll() is None:process.terminate()
        for process,path,ready in self.processes.values():
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
        for log in self.logs:log.close()
    def results(self):
        result={}
        for node,(process,path,ready) in self.processes.items():
            if not ready.is_file() or not path.is_file():raise CaptureFailure('Incomplete capture evidence for '+node)
            value=json.loads(path.read_text())
            if value.get('status')!='pass':raise CaptureFailure('Capture environment failure: '+str(value))
            result[node]=value
        return result
    def artifacts(self):return [str(path) for process,path,ready in self.processes.values()]
