"""Pinned manual Ollama install, loopback service and single authorized model pull."""
from datetime import datetime
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from a1_intent_routing.ollama_client import OllamaClient,LocalAPIError
CONFIG=json.loads((ROOT/'configs/one-pass-pilot.json').read_text())
SETUP=ROOT/'runs/ollama-setup'
PREFIX=ROOT/f'runs/tools/ollama-{CONFIG["ollama"]["version"]}'
BINARY=PREFIX/'bin/ollama'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['install','start','status','pull'])
    args=parser.parse_args(); SETUP.mkdir(parents=True,exist_ok=True)
    if args.action=='install':
        archive=SETUP/'ollama-linux-amd64.tar.zst'
        if not archive.exists():
            subprocess.run(['curl','-fL','--max-time','1150',CONFIG['ollama']['archive_url'],'-o',str(archive)],check=True,timeout=1160)
        if hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()!=CONFIG['ollama']['archive_sha256']:
            raise SystemExit('Ollama archive checksum mismatch; refusing extract')
        PREFIX.mkdir(parents=True,exist_ok=True)
        subprocess.run(['tar','--zstd','-xf',str(archive),'-C',str(PREFIX),'--no-same-owner'],check=True,timeout=180)
        (SETUP/'installation.json').write_text(json.dumps({'version':CONFIG['ollama']['version'],'archive_sha256':CONFIG['ollama']['archive_sha256'],'prefix':str(PREFIX),'binary_sha256':hashlib.sha256(BINARY.read_bytes()).hexdigest()},indent=2)+'\n')
        print('Installed pinned binary/libraries locally:',BINARY)
        return
    client=OllamaClient(CONFIG['endpoint'])
    if args.action=='start':
        try:
            value,_=client.request('/api/version')
            if value['version']!=CONFIG['ollama']['version']: raise SystemExit('Existing service version differs; not replacing it')
            print('Compatible local service already running:',value);return
        except LocalAPIError:
            pass
        if not BINARY.is_file(): raise SystemExit('Run install first')
        env=os.environ.copy();env.update(CONFIG['server_environment']);env['OLLAMA_MODELS']=str(ROOT/'models/ollama')
        (ROOT/'models/ollama').mkdir(parents=True,exist_ok=True)
        with (SETUP/'serve.log').open('ab') as log:
            process=subprocess.Popen([str(BINARY),'serve'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        (SETUP/'serve.pid').write_text(str(process.pid)+'\n')
        for _ in range(40):
            if process.poll() is not None: raise SystemExit('Ollama exited; see runs/ollama-setup/serve.log')
            try:
                value,_=client.request('/api/version',timeout=2)
                if value['version']!=CONFIG['ollama']['version']: raise SystemExit('Service version mismatch')
                print('Loopback Ollama ready:',value,'PID',process.pid);return
            except LocalAPIError:time.sleep(.5)
        raise SystemExit('Local service readiness timeout; log retained')
    if args.action=='pull':
        env=os.environ.copy();env['OLLAMA_HOST']=CONFIG['server_environment']['OLLAMA_HOST']
        attempt=datetime.now().astimezone().strftime('%Y%m%dT%H%M%S%z')
        logfile=SETUP/f'pull-model-{attempt}.log'
        with logfile.open('w') as log:
            result=subprocess.run([str(BINARY),'pull',CONFIG['model']['tag']],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
        (SETUP/f'pull-attempt-{attempt}.json').write_text(json.dumps({'tag':CONFIG['model']['tag'],'returncode':result.returncode,'log':str(logfile)},indent=2)+'\n')
        if result.returncode:raise SystemExit('Model pull failed; see '+str(logfile))
        tags,_=client.request('/api/tags'); model=next((m for m in tags['models'] if m['name']==CONFIG['model']['tag']),None)
        if not model or model['digest'].removeprefix('sha256:')!=CONFIG['model']['digest']:raise SystemExit('Pulled tag digest differs; generation blocked')
        show,_=client.request('/api/show',{'model':CONFIG['model']['tag']})
        for name,value in [('tags',tags),('show',show)]: (SETUP/f'model-{name}.json').write_text(json.dumps(value,indent=2)+'\n')
        if show['details']['quantization_level']!=CONFIG['model']['quantization']:raise SystemExit('Quantization mismatch')
        print('Pulled and verified single model:',CONFIG['model']['tag'],model['digest']);return
    for path in ('/api/version','/api/tags','/api/ps'):
        value,_=client.request(path); print(path,json.dumps(value))


if __name__=='__main__':main()
