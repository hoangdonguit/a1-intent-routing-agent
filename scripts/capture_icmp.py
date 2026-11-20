"""Read-only AF_PACKET worker. Join only an identified project container's network namespace."""
import argparse,json,os,signal,socket,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from a1_intent_routing.packet_capture import decode_echo

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--container',required=True);p.add_argument('--node',required=True);p.add_argument('--source',required=True);p.add_argument('--destination',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--ready',type=Path,required=True);a=p.parse_args();record={'container':a.container,'node':a.node,'packets':[],'status':'environment_error'};stop=[False];sock=None
 signal.signal(signal.SIGTERM,lambda *_:stop.__setitem__(0,True))
 try:
  if os.geteuid()!=0 or not hasattr(os,'setns'):raise RuntimeError('Root + Python os.setns required for owned namespace capture')
  template='{"pid":{{.State.Pid}},"running":{{.State.Running}},"labels":{{json .Config.Labels}}}'
  r=subprocess.run(['docker','inspect','--format',template,a.container],capture_output=True,text=True,timeout=5,check=True);info=json.loads(r.stdout);labels=info['labels'];lab=labels.get('containerlab')
  if lab not in ('a1-triangle3','a1-sixrouter') or labels.get('a1.project')!='a1-intent-routing-agent' or a.container!=f'clab-{lab}-{a.node}' or not info['running']:raise RuntimeError('Refusing capture outside a running owned project container')
  pid=info['pid'];namespace=os.readlink(f'/proc/{pid}/ns/net');record.update(namespace=namespace,container_pid=pid,source=a.source,destination=a.destination)
  with open(f'/proc/{pid}/ns/net','rb') as fd:os.setns(fd.fileno(),0)
  if os.readlink('/proc/self/ns/net')!=namespace:raise RuntimeError('Network namespace mismatch')
  sock=socket.socket(socket.AF_PACKET,socket.SOCK_RAW,socket.htons(0x0800));sock.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,1024*1024);sock.settimeout(.2)
  a.ready.write_text(json.dumps({'ready':True,'namespace':namespace,'container':a.container})+'\n')
  deadline=time.monotonic()+30
  while not stop[0] and time.monotonic()<deadline:
   try:frame,address=sock.recvfrom(65535)
   except socket.timeout:continue
   if address[2]==socket.PACKET_OUTGOING:continue
   decoded=decode_echo(frame,a.source,a.destination)
   if decoded is not None:record['packets'].append(dict(decoded,interface=address[0]))
  record['status']='pass'
 except Exception as exc:record['error']=str(exc)
 finally:
  if sock is not None:sock.close()
  a.out.write_text(json.dumps(record,indent=2)+'\n')
 return 0 if record['status']=='pass' else 2
if __name__=='__main__':sys.exit(main())
